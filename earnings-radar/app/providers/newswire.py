"""Newswire RSS adapter.

Polls small RSS/Atom feeds instead of scraping article pages. Feed URL
templates are configurable ({ticker} / {query} placeholders) so per-company
Business Wire / IR feeds can be added per watchlist entry without code
changes; the defaults use the wires' public search feeds.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import httpx

from app.domain.enums import ReleaseSourceKind
from app.providers.base import NewsItem, NewswireProvider, ProviderError, RateLimiter, TTLCache

DEFAULT_FEED_TEMPLATES: list[tuple[str, ReleaseSourceKind]] = [
    ("https://www.globenewswire.com/en/search/rss?query={query}", ReleaseSourceKind.GLOBENEWSWIRE),
    ("https://www.businesswire.com/portal/site/home/search/?searchType=all&searchTerm={query}&rss=1",
     ReleaseSourceKind.BUSINESSWIRE),
]

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


class RssNewswireProvider(NewswireProvider):
    name = "newswire_rss"

    def __init__(self, client: httpx.Client | None = None,
                 feed_templates: list[tuple[str, ReleaseSourceKind]] | None = None):
        self._client = client or httpx.Client(timeout=10.0, follow_redirects=True,
                                              headers={"User-Agent": "EarningsRadar/1.0"})
        self._templates = feed_templates or DEFAULT_FEED_TEMPLATES
        self._limiter = RateLimiter(rate_per_second=2.0, burst=4)
        self._cache = TTLCache(ttl_seconds=15, max_items=512)

    def recent_items(self, ticker: str, company_name: str) -> list[NewsItem]:
        query = quote_plus(company_name or ticker)
        items: list[NewsItem] = []
        errors: list[str] = []
        for template, kind in self._templates:
            url = template.format(query=query, ticker=quote_plus(ticker))
            cached = self._cache.get(url)
            if cached is not None:
                items.extend(cached)
                continue
            try:
                fetched = self._fetch_feed(url, ticker, kind)
                self._cache.put(url, fetched)
                items.extend(fetched)
            except ProviderError as exc:
                errors.append(str(exc))
        if not items and errors and len(errors) == len(self._templates):
            raise ProviderError("; ".join(errors))
        return items

    def _fetch_feed(self, url: str, ticker: str, kind: ReleaseSourceKind) -> list[NewsItem]:
        self._limiter.acquire()
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"newswire feed failed ({url}): {exc}") from exc
        return parse_feed(resp.text, ticker, kind)


def parse_feed(xml_text: str, ticker: str, kind: ReleaseSourceKind) -> list[NewsItem]:
    """Parse RSS 2.0 or Atom into NewsItems. Tolerant of junk."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ProviderError(f"unparseable feed: {exc}") from exc

    items: list[NewsItem] = []
    # RSS 2.0
    for item in root.iter("item"):
        items.append(_news_item(
            title=_text(item, "title"),
            url=_text(item, "link"),
            published=_parse_date(_text(item, "pubDate")),
            summary=_text(item, "description"),
            ticker=ticker, kind=kind,
        ))
    # Atom
    for entry in root.iter(f"{_ATOM_NS}entry"):
        link_el = entry.find(f"{_ATOM_NS}link")
        items.append(_news_item(
            title=_text(entry, f"{_ATOM_NS}title"),
            url=link_el.get("href", "") if link_el is not None else "",
            published=_parse_date(_text(entry, f"{_ATOM_NS}published")
                                  or _text(entry, f"{_ATOM_NS}updated")),
            summary=_text(entry, f"{_ATOM_NS}summary"),
            ticker=ticker, kind=kind,
        ))
    return [i for i in items if i.title]


def _news_item(title: str, url: str, published, summary: str, ticker: str,
               kind: ReleaseSourceKind) -> NewsItem:
    return NewsItem(ticker=ticker.upper(), title=title.strip(), url=url.strip(),
                    published_at_utc=published, source=kind, summary=summary.strip())


def _text(el, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "") if child is not None else ""


def _parse_date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
