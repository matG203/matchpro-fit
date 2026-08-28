"""SEC EDGAR adapter — the primary US release detector and timestamp authority.

Responsible-access rules honoured here (SEC automated-access guidance):
declared User-Agent, self-throttled well below the 10 req/s ceiling, cached
ticker→CIK map, tiny JSON index polls instead of page scraping.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx

from app.config import get_settings
from app.providers.base import FilingHit, FilingProvider, ProviderError, RateLimiter, TTLCache

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{doc}"

# Forms that can contain an earnings release
EARNINGS_FORMS = {"8-K", "8-K/A", "6-K", "6-K/A", "10-Q", "10-Q/A"}

_TAG_RE = re.compile(r"<[^>]+>")


class SecEdgarProvider(FilingProvider):
    name = "sec_edgar"

    def __init__(self, client: httpx.Client | None = None):
        settings = get_settings()
        self._client = client or httpx.Client(
            headers={"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip"},
            timeout=15.0,
            follow_redirects=True,
        )
        self._limiter = RateLimiter(rate_per_second=4.0, burst=4)
        self._cik_cache = TTLCache(ttl_seconds=86400, max_items=2)
        self._submissions_cache = TTLCache(ttl_seconds=10, max_items=512)

    # ── CIK mapping ───────────────────────────────────────────────────────────

    def cik_for_ticker(self, ticker: str) -> str | None:
        mapping = self._cik_cache.get("map")
        if mapping is None:
            data = self._get_json(TICKER_MAP_URL)
            mapping = {row["ticker"].upper(): f"{row['cik_str']:0>10}" for row in data.values()}
            self._cik_cache.put("map", mapping)
        return mapping.get(ticker.upper())

    # ── FilingProvider ────────────────────────────────────────────────────────

    def recent_filings(self, ticker: str, cik: str | None) -> list[FilingHit]:
        cik = cik or self.cik_for_ticker(ticker)
        if not cik:
            return []
        url = SUBMISSIONS_URL.format(cik=cik)
        data = self._submissions_cache.get(url)
        if data is None:
            data = self._get_json(url)
            self._submissions_cache.put(url, data)

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        hits: list[FilingHit] = []
        for i, form in enumerate(forms[:40]):
            if form not in EARNINGS_FORMS:
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
