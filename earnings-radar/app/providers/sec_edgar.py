"""SEC EDGAR adapter — the primary US release detector and timestamp authority.

Responsible-access rules honoured here (SEC automated-access guidance):
declared User-Agent, self-throttled well below the 10 req/s ceiling, cached
ticker→CIK map, tiny JSON index polls instead of page scraping.
"""
from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.config import get_settings
from app.providers.base import FilingHit, FilingProvider, ProviderError, RateLimiter, TTLCache

logger = logging.getLogger("earnings_radar.providers.sec")

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
CURRENT_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{doc}"

# Forms that can contain an earnings release
EARNINGS_FORMS = {"8-K", "8-K/A", "6-K", "6-K/A", "10-Q", "10-Q/A"}

_TAG_RE = re.compile(r"<[^>]+>")
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
# "8-K - ACME CORP (0001234567) (Filer)". The form itself usually contains a
# hyphen (8-K, 10-Q, S-1, SC 13D/A), so the separator is " - " with spaces —
# matching on a bare hyphen would drop almost every filing.
_FEED_TITLE_RE = re.compile(r"^\s*(?P<form>.+?)\s+-\s+(?P<name>.+?)\s+\((?P<cik>\d{4,10})\)")


@dataclass
class FeedEntry:
    """One row of EDGAR's latest-filings feed: who filed what, and when."""

    cik: str
    form_type: str
    company_name: str
    accepted_at_utc: datetime | None
    url: str = ""


class SecEdgarProvider(FilingProvider):
    name = "sec_edgar"

    def __init__(self, client: httpx.Client | None = None):
        settings = get_settings()
        self._client = client or httpx.Client(
            headers={"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip"},
            # EDGAR's latest-filings endpoint is generated per request and is
            # routinely slow — slower still from a datacentre, where a live
            # deployment timed out at 15s on a call that takes a couple of
            # seconds from a home connection.
            timeout=settings.sec_timeout_seconds,
            follow_redirects=True,
        )
        self._timeout_retries = settings.sec_timeout_retries
        self._limiter = RateLimiter(rate_per_second=4.0, burst=4)
        self._cik_cache = TTLCache(ttl_seconds=86400, max_items=2)
        self._submissions_cache = TTLCache(ttl_seconds=10, max_items=512)

    def _get_with_timeout_retry(self, url: str, **kwargs) -> httpx.Response:
        """GET, retrying only on a timeout.

        A timeout is the one failure worth retrying here: EDGAR builds the
        latest-filings feed per request and its latency varies wildly, so a
        slow response is normal rather than a sign anything is wrong. Every
        other error — 403, 404, a changed format — means retrying would just
        fail again more slowly, so those are raised immediately.

        This matters more than it sounds: a timed-out sweep finds no filings,
        which is indistinguishable from an hour in which nobody filed.
        """
        last: httpx.HTTPError | None = None
        for attempt in range(self._timeout_retries + 1):
            self._limiter.acquire()
            try:
                resp = self._client.get(url, **kwargs)
                resp.raise_for_status()
                return resp
            except (httpx.TimeoutException, httpx.ReadError, httpx.ConnectError) as exc:
                last = exc
                if attempt < self._timeout_retries:
                    logger.info("SEC request timed out (attempt %d/%d), retrying: %s",
                                attempt + 1, self._timeout_retries + 1, exc)
                    time.sleep(1.5 * (attempt + 1))
        assert last is not None
        raise last

    # ── CIK mapping ───────────────────────────────────────────────────────────

    def cik_for_ticker(self, ticker: str) -> str | None:
        mapping = self._cik_cache.get("map")
        if mapping is None:
            data = self._get_json(TICKER_MAP_URL)
            mapping = {row["ticker"].upper(): f"{row['cik_str']:0>10}" for row in data.values()}
            self._cik_cache.put("map", mapping)
        return mapping.get(ticker.upper())

    # ── FilingProvider ────────────────────────────────────────────────────────

    def recent_filings(self, ticker: str, cik: str | None,
                       forms_filter: set[str] | None = None) -> list[FilingHit]:
        """Recent filings for a company.

        `forms_filter` defaults to the earnings forms so Earnings Sentinel's
        behaviour is unchanged; Catalyst Sentinel passes its wider set.
        """
        cik = cik or self.cik_for_ticker(ticker)
        if not cik:
            return []
        wanted = forms_filter if forms_filter is not None else EARNINGS_FORMS
        url = SUBMISSIONS_URL.format(cik=cik)
        data = self._submissions_cache.get(url)
        if data is None:
            data = self._get_json(url)
            self._submissions_cache.put(url, data)

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        hits: list[FilingHit] = []
        for i, form in enumerate(forms[:40]):
            if form not in wanted:
                continue
            accepted = _parse_acceptance(recent["acceptanceDateTime"][i])
            accession = recent["accessionNumber"][i].replace("-", "")
            doc = recent.get("primaryDocument", [""] * len(forms))[i] or ""
            items_raw = recent.get("items", [""] * len(forms))[i] or ""
            hits.append(
                FilingHit(
                    ticker=ticker.upper(),
                    form_type=form,
                    accepted_at_utc=accepted,
                    url=ARCHIVES_URL.format(cik_int=int(cik), accession=accession, doc=doc),
                    description=recent.get("primaryDocDescription", [""] * len(forms))[i] or "",
                    items=[s.strip() for s in items_raw.split(",") if s.strip()],
                )
            )
        return hits

    # ── firehose ──────────────────────────────────────────────────────────────

    def latest_filings(self, form_type: str = "", count: int = 100) -> list[FeedEntry]:
        """EDGAR's latest-filings feed — every filer, one request.

        This is what makes continuous monitoring affordable. Polling the
        submissions JSON for each watched company would be hundreds of requests
        per sweep; this is one, and the per-company call is then made only for
        the handful of companies that actually filed. Item codes are not in the
        feed, so routing still needs that second call — but only for real hits.
        """
        params = {"action": "getcurrent", "owner": "include",
                  "count": str(min(max(count, 10), 100)), "output": "atom"}
        if form_type:
            params["type"] = form_type
        try:
            resp = self._get_with_timeout_retry(CURRENT_FEED_URL, params=params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"SEC latest-filings feed failed: {exc}") from exc

        entries = parse_current_feed(resp.text)
        if not entries and len(resp.text) > 2000:
            # A substantial body that yielded nothing means the feed's shape has
            # changed, not that nobody filed. Silence there would look exactly
            # like a quiet market, which is the one wrong answer this must not
            # give — so it is raised as a provider error and surfaced.
            raise ProviderError(
                f"SEC latest-filings feed returned {len(resp.text)} bytes but no "
                "parseable entries — the feed format may have changed")
        return entries

    def fetch_document_text(self, url: str) -> str:
        self._limiter.acquire()
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"SEC document fetch failed: {exc}") from exc
        text = resp.text
        if url.endswith((".htm", ".html")):
            text = _TAG_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip()

    # ── internals ─────────────────────────────────────────────────────────────

    def _get_json(self, url: str) -> dict:
        self._limiter.acquire()
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"SEC request failed ({url}): {exc}") from exc


def parse_current_feed(xml_text: str) -> list[FeedEntry]:
    """Parse the latest-filings Atom feed. Tolerant: a malformed entry is
    skipped rather than losing the whole sweep."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ProviderError(f"unparseable EDGAR feed: {exc}") from exc

    entries: list[FeedEntry] = []
    for entry in root.iter(f"{_ATOM_NS}entry"):
        title_el = entry.find(f"{_ATOM_NS}title")
        title = (title_el.text or "") if title_el is not None else ""
        match = _FEED_TITLE_RE.match(title)
        if not match:
            continue

        form = match.group("form").strip().upper()
        category = entry.find(f"{_ATOM_NS}category")
        if category is not None and category.get("term"):
            form = category.get("term", form).strip().upper()

        updated_el = entry.find(f"{_ATOM_NS}updated")
        accepted = None
        if updated_el is not None and updated_el.text:
            try:
                accepted = _parse_acceptance(updated_el.text.strip())
            except ValueError:
                accepted = None

        link_el = entry.find(f"{_ATOM_NS}link")
        entries.append(FeedEntry(
            cik=match.group("cik").zfill(10),
            form_type=form,
            company_name=match.group("name").strip(),
            accepted_at_utc=accepted,
            url=link_el.get("href", "") if link_el is not None else ""))
    return entries


def _parse_acceptance(value: str) -> datetime:
    # e.g. "2026-08-27T21:05:03.000Z"
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def is_earnings_filing(hit: FilingHit) -> bool:
    """8-K Item 2.02 = Results of Operations; 10-Q/6-K always carry results."""
    if hit.form_type.startswith("10-Q"):
        return True
    if hit.form_type.startswith("6-K"):
        return True
    if hit.form_type.startswith("8-K"):
        if any(item.startswith("2.02") for item in hit.items):
            return True
        blob = hit.description.lower()
        return any(k in blob for k in ("results of operations", "earnings", "financial results"))
    return False
