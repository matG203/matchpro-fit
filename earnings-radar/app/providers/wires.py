"""Public newswire firehoses — GlobeNewswire, Business Wire, PR Newswire.

Why these, and why free
-----------------------
When a US-listed company discloses something material outside a filing — an
FDA decision, Phase 2/3 topline data, a contract award, a guidance change —
it almost always crosses one of these three wires first, because they are the
Reg FD-compliant distribution channels companies pay to use. The 8-K covering
the same news is filed later, sometimes hours later, sometimes days. SEC EDGAR
therefore sees a large share of catalysts *after* the market already has.

Each wire publishes a public RSS firehose of everything it distributes. No key,
no licence, no per-request cost. What it does not give us is the sub-second
push latency of a licensed feed: we poll, so detection lags publication by up
to one poll interval (30s by default). That is the whole of the difference,
and it is measured rather than assumed — see `detected_lag_seconds` on each
ingested item.

Firehose, not search
--------------------
`app.providers.newswire` already talks to these wires, but per company, via
their search feeds: one request per company per sweep. Across a 400-name
universe that is 800 requests every 30 seconds, which is neither polite nor
survivable. These feeds are the opposite shape — one request returns
everything the wire has just published, for every company — so a sweep costs
three requests regardless of universe size, and it sees companies we have
never heard of.

Entity resolution
-----------------
Wire releases carry an exchange-qualified ticker ("(NASDAQ: RKLB)") because
the wires require it for public-company releases. That is the single strongest
signal `resolve_entity` has (0.98), and it works for companies absent from our
universe — which matters, since our universe is seeded by the earnings
calendar and starts near-empty. The tag usually sits in the release body
rather than the RSS summary, so bodies are fetched for new items, under a
per-sweep budget.

Source tier
-----------
A release on one of these three wires is the company's own disclosure,
distributed verbatim under its control — the same document the 8-K will later
exhibit. That is PRIMARY under the source hierarchy (§5), not second-hand
reporting. Feeds added by configuration default to NEWSWIRE instead, because
we cannot vouch for what an arbitrary feed carries.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.catalyst.enums import SourceTier
from app.domain.timeutil import utcnow
from app.providers.base import CircuitBreaker, ProviderError, RateLimiter
from app.providers.news import NewsArticle, NewsProvider

logger = logging.getLogger("earnings_radar.providers.wires")

_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_DC_NS = "{http://purl.org/dc/elements/1.1/}"
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"\s+")


# Identifies us honestly and gives a contact route, which is what a feed
# publisher wants to see. Some wires sit behind bot filtering that rejects
# unfamiliar agents inconsistently — PR Newswire served 20 items and then 404'd
# minutes later — so this is settable via WIRE_USER_AGENT rather than baked in.
DEFAULT_USER_AGENT = ("EarningsRadar/1.0 (+https://github.com/matG203/earnings-radar; "
                      "RSS reader)")


@dataclass(frozen=True)
class WireFeed:
    """One firehose. `source` names the wire in the audit trail."""

    url: str
    source: str
    tier: SourceTier = SourceTier.NEWSWIRE


# The public "all public-company news" firehoses. These URLs are the wires'
# own published feed addresses; if one is retired the provider degrades to the
# remaining feeds and says so, rather than failing the sweep.
#
# Feed addresses rot, and which one is *right* is not obvious from the outside:
# GlobeNewswire's "public companies" feed turns out to be global, carrying
# Nordic and French releases (and French-language duplicates) that no US ticker
# will ever resolve. `python -m app.probe_feed --candidates` measures the
# alternatives from a machine that can reach them; CANDIDATE_FEEDS below is
# what it tests.
# Chosen by measurement, not by assumption — see the probe results in
# CHANGELOG 0.3.7. Business Wire is deliberately absent: none of its published
# addresses work. The tokenised feed answers and returns nothing, and the
# portal URLs are HTML pages that time out rather than feeds. Two working wires
# beat three where one is silently contributing zero.
DEFAULT_WIRE_FEEDS: list[WireFeed] = [
    WireFeed(
        url=("https://www.globenewswire.com/RssFeed/country/United%20States/"
             "feedTitle/GlobeNewswire%20-%20News%20from%20United%20States"),
        source="GlobeNewswire",
        tier=SourceTier.PRIMARY),
    WireFeed(
        url="https://www.prnewswire.com/rss/news-releases-list.rss",
        source="PR Newswire",
        tier=SourceTier.PRIMARY),
]

# Every address worth trying, per wire, most promising first. The probe reports
# item count, recency and — the figure that actually matters — how many
# releases carry an exchange-qualified ticker. Nothing here is asserted to
# work; that is the point of measuring.
CANDIDATE_FEEDS: dict[str, list[str]] = {
    "GlobeNewswire": [
        # US-only. The whole problem with the global feed is that most of it is
        # not US-listed, so no amount of body fetching will resolve a ticker.
        ("https://www.globenewswire.com/RssFeed/country/United%20States/"
         "feedTitle/GlobeNewswire%20-%20News%20from%20United%20States"),
        ("https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/"
         "GlobeNewswire%20-%20News%20about%20Public%20Companies"),
        ("https://www.globenewswire.com/RssFeed/language/en/feedTitle/"
         "GlobeNewswire%20-%20News%20in%20English"),
    ],
    # None of these worked when probed: the tokenised feed answers and returns
    # nothing, and both portal URLs are HTML pages that time out. Kept so the
    # probe re-tests them — a wire this large may well publish a feed again.
    "Business Wire": [
        "https://www.businesswire.com/portal/site/home/news/",
        "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEF9YWQ==",
        "https://www.businesswire.com/portal/site/home/news/subject/?vnsId=31333",
    ],
    "PR Newswire": [
        "https://www.prnewswire.com/rss/news-releases-list.rss",
        # Duplicate of the above — same items, same timestamps. Kept only so
        # the probe shows it is not a separate source of coverage.
        "https://www.prnewswire.com/rss/all-news-releases-from-PR-newswire-news.rss",
        # Scored the highest ticker rate (40%) and is the *worst* of the set:
        # the matches are securities-litigation ads, which name a ticker
        # perfectly and are not catalysts. A reminder that the ticker rate is a
        # necessary condition, never a sufficient one.
        ("https://www.prnewswire.com/rss/financial-services-latest-news/"
         "financial-services-latest-news-list.rss"),
        # Asia-Pacific: 0% resolvable, as expected — those issuers are not
        # US-listed.
        "https://www.prnewswire.com/apac/rss/news-releases-list.rss",
    ],
}


@dataclass
class FeedEntry:
    title: str
    url: str
    summary: str = ""
    published_at_utc: datetime | None = None


@dataclass
class WireFeedHealth:
    """Per-feed outcome of the most recent sweep — surfaced in the UI so a
    silently dead feed is visible rather than looking like a quiet news day."""

    source: str
    url: str
    ok: bool = False
    items_seen: int = 0
    items_new: int = 0
    error: str = ""
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    newest_item_at: datetime | None = None

    @property
    def state(self) -> str:
        """"Not asked yet" is not the same as "asked and broken".

        For the first sweep after a restart every feed has `ok=False` simply
        because nothing has been fetched. Rendering that as a failure puts
        three red lights on the dashboard of a perfectly healthy system, and
        teaches the operator to ignore red lights.
        """
        if self.last_attempt_at is None:
            return "unpolled"
        return "ok" if self.ok else "failing"


@dataclass
class WireSweepStats:
    """What the last `fetch_since` actually did. This is the raw material for
    the "news is being digested" evidence — counts nobody had to take on
    trust."""

    at: datetime | None = None
    items_seen: int = 0
    items_new: int = 0
    bodies_fetched: int = 0
    body_fetch_failures: int = 0
    budget_exhausted: bool = False
    feeds: list[WireFeedHealth] = field(default_factory=list)


class WireFirehoseProvider(NewsProvider):
    """Polls the public wire firehoses and yields new releases as NewsArticles."""

    name = "wire_rss"
    tier = SourceTier.PRIMARY

    def __init__(self, feeds: list[WireFeed] | None = None,
                 client: httpx.Client | None = None, *,
                 rate_per_second: float = 1.0,
                 max_body_fetches: int = 25,
                 body_chars: int = 40_000,
                 seen_capacity: int = 8_000,
                 overlap_seconds: float = 180.0,
                 user_agent: str = ""):
        self._feeds = list(feeds if feeds is not None else DEFAULT_WIRE_FEEDS)
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self._client = client or httpx.Client(
            timeout=15.0, follow_redirects=True,
            headers={"User-Agent": self.user_agent,
                     "Accept": "application/rss+xml, application/xml, text/xml, */*"})
        self._limiter = RateLimiter(rate_per_second=rate_per_second, burst=3)
        self._max_body_fetches = max_body_fetches
        self._body_chars = body_chars
        # Release URLs already emitted. Bounded LRU: re-seeing an item after
        # eviction costs one duplicate the pipeline discards, which is the
        # failure mode we want — repeat work, never skipped work.
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._seen_capacity = seen_capacity
        # RSS timestamps have second granularity and items can appear slightly
        # out of order, so the cursor is rewound a little on each sweep. `_seen`
        # stops that turning into reprocessing.
        self._overlap = timedelta(seconds=overlap_seconds)
        self._breakers: dict[str, CircuitBreaker] = {
            f.url: CircuitBreaker(failure_threshold=4, cooldown_seconds=300.0)
            for f in self._feeds}
        self._health: dict[str, WireFeedHealth] = {
            f.url: WireFeedHealth(source=f.source, url=f.url) for f in self._feeds}
        self.last_sweep: WireSweepStats | None = None

    # ── introspection (used by /api/catalyst/news and preflight) ──────────────

    @property
    def feeds(self) -> list[WireFeed]:
        return list(self._feeds)

    def health(self) -> list[WireFeedHealth]:
        return [self._health[f.url] for f in self._feeds]

    def enabled(self) -> bool:
        return bool(self._feeds)

    # ── main entry point ─────────────────────────────────────────────────────

    def fetch_since(self, since: datetime) -> list[NewsArticle]:
        cutoff = since - self._overlap
        stats = WireSweepStats(at=utcnow())
        articles: list[NewsArticle] = []
        # Reasons a feed produced nothing. A feed whose circuit is open counts
        # here too: "we have stopped asking" must not be reported as "the wire
        # had no news", which is what a silent empty sweep would look like.
        blocked: list[str] = []
        budget = self._max_body_fetches

        for feed in self._feeds:
            health = self._health[feed.url]
            breaker = self._breakers[feed.url]
            if not breaker.allow():
                blocked.append(f"{feed.source}: not being polled — "
                               f"{health.error or 'repeated failures'}")
                stats.feeds.append(health)
                continue

            health.last_attempt_at = stats.at
            try:
                entries = self._fetch_feed(feed)
            except ProviderError as exc:
                breaker.record_failure()
                health.ok = False
                health.error = str(exc)
                blocked.append(f"{feed.source}: {exc}")
                stats.feeds.append(health)
                logger.warning("wire feed unavailable (%s): %s", feed.source, exc)
                continue

            breaker.record_success()
            health.ok = True
            health.error = ""
            health.last_success_at = stats.at
            health.items_seen = len(entries)
            health.items_new = 0
            health.newest_item_at = max(
                (e.published_at_utc for e in entries if e.published_at_utc), default=None)
            stats.items_seen += len(entries)

            for entry in entries:
                if entry.published_at_utc is not None and entry.published_at_utc < cutoff:
                    continue
                key = _canonical_url(entry.url) or entry.title.strip().lower()
                if not key or key in self._seen:
                    continue
                self._remember(key)
                health.items_new += 1
                stats.items_new += 1

                body = entry.summary
                if budget > 0:
                    fetched = self._fetch_body(entry.url)
                    if fetched is None:
                        stats.body_fetch_failures += 1
                    else:
                        # Only prefer the page over the RSS summary if it is
                        # actually richer — some wires serve a consent
                        # interstitial to non-browser clients.
                        stats.bodies_fetched += 1
                        if len(fetched) > len(entry.summary):
                            body = fetched
                    budget -= 1
                elif not stats.budget_exhausted:
                    stats.budget_exhausted = True

                articles.append(self._to_article(feed, entry, body))

            stats.feeds.append(health)

        self.last_sweep = stats
        if stats.budget_exhausted:
            logger.info("wire body-fetch budget of %d exhausted this sweep; %d new items "
                        "carried their RSS summary only",
                        self._max_body_fetches, stats.items_new - self._max_body_fetches)

        # Only fail loudly when nothing at all could be read. A partial sweep
        # still delivers news, and burying that in an exception would lose it.
        if not articles and len(blocked) == len(self._feeds) and self._feeds:
            raise ProviderError("; ".join(blocked))
        return articles

    # ── internals ────────────────────────────────────────────────────────────

    def _remember(self, key: str) -> None:
        self._seen[key] = None
        while len(self._seen) > self._seen_capacity:
            self._seen.popitem(last=False)

    def _fetch_feed(self, feed: WireFeed) -> list[FeedEntry]:
        self._limiter.acquire()
        try:
            resp = self._client.get(feed.url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"feed request failed: {exc}") from exc
        return parse_wire_feed(resp.text)

    def _fetch_body(self, url: str) -> str | None:
        if not url:
            return None
        self._limiter.acquire()
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.debug("wire body fetch failed (%s): %s", url, exc)
            return None
        return html_to_text(resp.text)[:self._body_chars]

    def _to_article(self, feed: WireFeed, entry: FeedEntry, body: str) -> NewsArticle:
        published = entry.published_at_utc
        return NewsArticle(
            provider=self.name,
            # The release URL is the wire's own stable identifier. Using it
            # means a story re-published under a new headline is recognised as
            # the same item, and a genuinely revised release (same URL, changed
            # text) is caught by the content hash.
            article_id=_canonical_url(entry.url) or entry.title.strip(),
            headline=entry.title.strip()[:400],
            body=body,
            tickers=[],  # left to resolve_entity: the wires do not tag machine-readably
            source_tier=feed.tier,
            source_url=entry.url,
            original_source=feed.source,
            provider_channel=feed.source,
            published_at_utc=published,
            received_at_utc=utcnow())


# ── parsing ──────────────────────────────────────────────────────────────────


def parse_wire_feed(xml_text: str) -> list[FeedEntry]:
    """Parse RSS 2.0 or Atom into entries. Tolerant: a malformed entry is
    dropped rather than losing the sweep."""
    try:
        root = ET.fromstring(xml_text.strip())
    except ET.ParseError as exc:
        raise ProviderError(f"unparseable wire feed: {exc}") from exc

    entries: list[FeedEntry] = []
    for item in root.iter("item"):
        entries.append(FeedEntry(
            title=_clean(_text(item, "title")),
            url=_text(item, "link").strip(),
            summary=_clean(_text(item, "description")),
            published_at_utc=_parse_date(_text(item, "pubDate")
                                         or _text(item, f"{_DC_NS}date"))))
    for entry in root.iter(f"{_ATOM_NS}entry"):
        entries.append(FeedEntry(
            title=_clean(_text(entry, f"{_ATOM_NS}title")),
            url=_atom_link(entry),
            summary=_clean(_text(entry, f"{_ATOM_NS}summary")
                           or _text(entry, f"{_ATOM_NS}content")),
            published_at_utc=_parse_date(_text(entry, f"{_ATOM_NS}published")
                                         or _text(entry, f"{_ATOM_NS}updated"))))
    return [e for e in entries if e.title]


def html_to_text(html: str) -> str:
    """Crude but adequate: strip scripts and tags, unescape, collapse space.

    Press-release pages are simple documents; a full HTML parser would be a
    dependency and an attack surface for no gain here. Script and style blocks
    are removed first — a naive tag strip would otherwise inject minified
    JavaScript into the article body, where the classifier would read it as
    prose."""
    import html as html_mod

    text = _SCRIPT_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", html_mod.unescape(text)).strip()


def _clean(value: str) -> str:
    """RSS descriptions routinely contain escaped HTML."""
    return html_to_text(value or "")


def _atom_link(entry) -> str:
    for link in entry.iter(f"{_ATOM_NS}link"):
        rel = link.get("rel", "alternate")
        if rel == "alternate":
            return (link.get("href") or "").strip()
    first = entry.find(f"{_ATOM_NS}link")
    return (first.get("href", "") if first is not None else "").strip()


def _canonical_url(url: str) -> str:
    """Drop query strings and fragments so the same release tracked with
    different campaign parameters is one item, not several."""
    url = (url or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    if not parts.scheme:
        return url
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                       parts.path.rstrip("/"), "", ""))


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
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
