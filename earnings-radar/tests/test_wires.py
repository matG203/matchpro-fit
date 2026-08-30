"""Free newswire firehoses.

The wires themselves are unreachable from the build environment (network
egress policy), so parsing is exercised against recorded samples of each
wire's real feed format rather than a live response — the same approach taken
for the EDGAR latest-filings feed. What that does and does not prove:

  * proven here — the parser handles both feed dialects the wires emit,
    survives junk, deduplicates correctly across sweeps, respects the body
    budget, and produces articles the catalyst pipeline resolves to the right
    ticker;
  * NOT proven here — that the feed URLs still serve these shapes today.
    `run_preflight` fetches all three for real on the deployed machine and
    fails loudly if a feed is unreachable, empty or unparseable, which is the
    only place that check can honestly be made.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest

from app.catalyst.entities import resolve_entity
from app.catalyst.enums import SourceTier
from app.domain.timeutil import UTC
from app.providers.base import ProviderError
from app.providers.wires import (
    WireFeed,
    WireFirehoseProvider,
    html_to_text,
    parse_wire_feed,
)

NOW = datetime(2026, 8, 30, 13, 0, tzinfo=UTC)


# ── recorded feed samples ────────────────────────────────────────────────────

# GlobeNewswire: RSS 2.0, description is escaped HTML carrying the dateline and
# the exchange-qualified ticker.
GLOBENEWSWIRE_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>GlobeNewswire - News about Public Companies</title>
    <link>https://www.globenewswire.com/</link>
    <item>
      <title>Kestrel Therapeutics Announces FDA Approval of KTX-401</title>
      <link>https://www.globenewswire.com/news-release/2026/08/30/1/en/Kestrel.html?ref=rss&amp;utm_source=feed</link>
      <description>&lt;p&gt;CAMBRIDGE, Mass., Aug. 30, 2026 (GLOBE NEWSWIRE) -- Kestrel
        Therapeutics Inc. (NASDAQ: KTRX) today announced that the U.S. Food and
        Drug Administration has approved KTX-401.&lt;/p&gt;</description>
      <pubDate>Sun, 30 Aug 2026 12:45:00 GMT</pubDate>
    </item>
    <item>
      <title>Northvale Industries to Present at the Autumn Investor Conference</title>
      <link>https://www.globenewswire.com/news-release/2026/08/30/2/en/Northvale.html</link>
      <description>&lt;p&gt;Northvale Industries Corp. (NYSE: NVI) will present.&lt;/p&gt;</description>
      <pubDate>Sun, 30 Aug 2026 11:00:00 GMT</pubDate>
    </item>
    <item>
      <title>An older release nobody should reprocess</title>
      <link>https://www.globenewswire.com/news-release/2026/08/29/3/en/Old.html</link>
      <description>Yesterday.</description>
      <pubDate>Sat, 29 Aug 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

# Business Wire: RSS 2.0 with a dc:date rather than pubDate.
BUSINESSWIRE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Business Wire News</title>
    <item>
      <title>Halden Systems Awarded $240 Million U.S. Navy Contract</title>
      <link>https://www.businesswire.com/news/home/20260830005001/en/</link>
      <description>Halden Systems, Inc. (NYSE: HSY) announced today...</description>
      <dc:date>2026-08-30T12:50:00Z</dc:date>
    </item>
  </channel>
</rss>
"""

# Some wires serve Atom. Same parser, different dialect.
ATOM_FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Orrin Biosciences Reports Positive Phase 3 Topline Results</title>
    <link rel="self" href="https://example.com/self"/>
    <link rel="alternate" href="https://wire.example.com/releases/orrin-phase3"/>
    <summary>Orrin Biosciences (NASDAQ: ORRN) met its primary endpoint.</summary>
    <published>2026-08-30T12:55:00Z</published>
  </entry>
  <entry>
    <title></title>
    <link rel="alternate" href="https://wire.example.com/releases/blank"/>
    <published>2026-08-30T12:56:00Z</published>
  </entry>
</feed>
"""

RELEASE_PAGE = """<html><head>
<style>.headline{font-size:2em}</style>
<script>window.dataLayer=[{"ticker":"WRONG"}];</script>
</head><body>
<h1>Kestrel Therapeutics Announces FDA Approval of KTX-401</h1>
<p>CAMBRIDGE, Mass., Aug. 30, 2026 (GLOBE NEWSWIRE) -- Kestrel Therapeutics Inc.
(NASDAQ: KTRX), a clinical-stage company, today announced that the FDA has
approved KTX-401 for the treatment of adults. Peak annual sales are expected to
exceed &pound;300 million.</p>
</body></html>"""


# ── transport double ─────────────────────────────────────────────────────────


class FakeTransport:
    """httpx client backed by a URL → (status, text) map, recording calls."""

    def __init__(self, routes: dict[str, tuple[int, str]]):
        self.routes = routes
        self.calls: list[str] = []

    def client(self) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            self.calls.append(url)
            status, text = self.routes.get(url, (404, "not found"))
            return httpx.Response(status, text=text,
                                  headers={"content-type": "application/xml"})

        return httpx.Client(transport=httpx.MockTransport(handler))


GNW = WireFeed(url="https://gnw.test/feed", source="GlobeNewswire",
               tier=SourceTier.PRIMARY)
BW = WireFeed(url="https://bw.test/feed", source="Business Wire",
              tier=SourceTier.PRIMARY)


def build(routes, **kwargs) -> tuple[WireFirehoseProvider, FakeTransport]:
    transport = FakeTransport(routes)
    feeds = kwargs.pop("feeds", [GNW])
    provider = WireFirehoseProvider(feeds=feeds, client=transport.client(),
                                    rate_per_second=1000.0, **kwargs)
    return provider, transport


# ── parsing ──────────────────────────────────────────────────────────────────


def test_parses_rss_with_escaped_html_description():
    entries = parse_wire_feed(GLOBENEWSWIRE_RSS)
    assert len(entries) == 3
    first = entries[0]
    assert first.title == "Kestrel Therapeutics Announces FDA Approval of KTX-401"
    # The escaped <p> must not survive into the text the classifier reads.
    assert "<p>" not in first.summary
    assert "(NASDAQ: KTRX)" in first.summary
    assert first.published_at_utc == datetime(2026, 8, 30, 12, 45, tzinfo=UTC)


def test_parses_dc_date_when_pubdate_absent():
    entries = parse_wire_feed(BUSINESSWIRE_RSS)
    assert entries[0].published_at_utc == datetime(2026, 8, 30, 12, 50, tzinfo=UTC)


def test_parses_atom_and_prefers_the_alternate_link():
    entries = parse_wire_feed(ATOM_FEED)
    # The untitled entry is dropped, not carried through as a blank headline.
    assert len(entries) == 1
    assert entries[0].url == "https://wire.example.com/releases/orrin-phase3"
    assert "ORRN" in entries[0].summary


def test_unparseable_feed_raises_rather_than_returning_nothing():
    # Silence here would read as "quiet news day" — the one failure mode that
    # must never be silent.
    with pytest.raises(ProviderError):
        parse_wire_feed("<rss><channel><item><title>unclosed")


def test_html_to_text_drops_script_and_style_bodies():
    text = html_to_text(RELEASE_PAGE)
    assert "window.dataLayer" not in text
    assert "WRONG" not in text          # a naive tag strip would leak this ticker
    assert "font-size" not in text
    assert "(NASDAQ: KTRX)" in text
    assert "£300 million" in text        # HTML entities unescaped


# ── sweeps ───────────────────────────────────────────────────────────────────


def test_returns_only_items_newer_than_the_cursor():
    provider, _ = build({GNW.url: (200, GLOBENEWSWIRE_RSS)}, max_body_fetches=0)
    articles = provider.fetch_since(NOW - timedelta(hours=2))

    headlines = [a.headline for a in articles]
    assert "An older release nobody should reprocess" not in headlines
    assert len(articles) == 2


def test_same_release_is_not_re_emitted_on_the_next_sweep():
    provider, transport = build({GNW.url: (200, GLOBENEWSWIRE_RSS)}, max_body_fetches=0)
    first = provider.fetch_since(NOW - timedelta(hours=2))
    second = provider.fetch_since(NOW - timedelta(hours=2))

    assert len(first) == 2
    assert second == []
    # The feed is still polled — it just yields nothing new.
    assert transport.calls.count(GNW.url) == 2


def test_tracking_parameters_do_not_create_a_second_copy():
    # The first item's link carries ?ref=rss&utm_source=feed.
    provider, _ = build({GNW.url: (200, GLOBENEWSWIRE_RSS)}, max_body_fetches=0)
    articles = provider.fetch_since(NOW - timedelta(hours=2))
    kestrel = next(a for a in articles if "Kestrel" in a.headline)
    assert "?" not in kestrel.article_id
    assert kestrel.article_id.endswith("/Kestrel.html")
    # The full link is kept for the human following the alert.
    assert "utm_source=feed" in kestrel.source_url


def test_body_is_fetched_and_replaces_the_rss_summary():
    release_url = ("https://www.globenewswire.com/news-release/2026/08/30/1/en/"
                   "Kestrel.html?ref=rss&utm_source=feed")
    provider, transport = build({GNW.url: (200, GLOBENEWSWIRE_RSS),
                                 release_url: (200, RELEASE_PAGE)},
                                max_body_fetches=5)
    articles = provider.fetch_since(NOW - timedelta(hours=2))
    kestrel = next(a for a in articles if "Kestrel" in a.headline)

    assert release_url in transport.calls
    assert "Peak annual sales" in kestrel.body      # page text, not the summary
    # Two new items, two attempts: one page served, the other 404s.
    assert provider.last_sweep.bodies_fetched == 1
    assert provider.last_sweep.body_fetch_failures == 1


def test_body_fetch_failure_falls_back_to_the_rss_summary():
    provider, _ = build({GNW.url: (200, GLOBENEWSWIRE_RSS)}, max_body_fetches=5)
    articles = provider.fetch_since(NOW - timedelta(hours=2))
    kestrel = next(a for a in articles if "Kestrel" in a.headline)

    # The release page 404s, but the ticker is still in the summary, so the
    # item remains resolvable rather than being lost.
    assert "(NASDAQ: KTRX)" in kestrel.body
    assert provider.last_sweep.body_fetch_failures == 2


def test_body_budget_is_a_hard_ceiling():
    provider, transport = build({GNW.url: (200, GLOBENEWSWIRE_RSS)}, max_body_fetches=1)
    articles = provider.fetch_since(NOW - timedelta(hours=2))

    assert len(articles) == 2                      # every item still emitted
    assert len([c for c in transport.calls if c != GNW.url]) == 1
    assert provider.last_sweep.budget_exhausted is True


def test_a_short_page_does_not_overwrite_a_richer_summary():
    release_url = ("https://www.globenewswire.com/news-release/2026/08/30/1/en/"
                   "Kestrel.html?ref=rss&utm_source=feed")
    consent_wall = "<html><body><p>Enable cookies.</p></body></html>"
    provider, _ = build({GNW.url: (200, GLOBENEWSWIRE_RSS),
                         release_url: (200, consent_wall)}, max_body_fetches=5)
    articles = provider.fetch_since(NOW - timedelta(hours=2))
    kestrel = next(a for a in articles if "Kestrel" in a.headline)

    assert "(NASDAQ: KTRX)" in kestrel.body
    assert "Enable cookies" not in kestrel.body


# ── failure handling ─────────────────────────────────────────────────────────


def test_one_dead_feed_does_not_lose_the_other():
    provider, _ = build({BW.url: (200, BUSINESSWIRE_RSS)},
                        feeds=[GNW, BW], max_body_fetches=0)
    articles = provider.fetch_since(NOW - timedelta(hours=2))

    assert [a.headline for a in articles] == [
        "Halden Systems Awarded $240 Million U.S. Navy Contract"]
    health = {h.source: h for h in provider.health()}
    assert health["GlobeNewswire"].ok is False
    assert health["GlobeNewswire"].error
    assert health["Business Wire"].ok is True
    assert health["Business Wire"].items_new == 1


def test_every_feed_failing_raises():
    provider, _ = build({}, feeds=[GNW, BW], max_body_fetches=0)
    with pytest.raises(ProviderError):
        provider.fetch_since(NOW - timedelta(hours=2))


def test_repeated_failure_opens_the_circuit_and_stops_hammering():
    provider, transport = build({}, feeds=[GNW], max_body_fetches=0)
    errors = []
    for _ in range(6):
        with pytest.raises(ProviderError) as caught:
            provider.fetch_since(NOW - timedelta(hours=2))
        errors.append(str(caught.value))
    # failure_threshold=4: requests stop once the breaker opens...
    assert len(transport.calls) == 4
    # ...but the sweep keeps failing loudly. Returning [] once we had given up
    # asking would be indistinguishable from a quiet news day.
    assert "not being polled" in errors[-1]


# ── what the pipeline does with the result ───────────────────────────────────


def test_wire_article_resolves_to_a_company_we_have_never_heard_of():
    """The point of the wires: they reach outside our universe.

    Our company table is seeded by the earnings calendar, so it starts nearly
    empty. A wire release carries its own exchange-qualified ticker, which
    resolves at 0.98 with no universe entry at all — well above the 0.7 alert
    threshold.
    """
    provider, _ = build({GNW.url: (200, GLOBENEWSWIRE_RSS)}, max_body_fetches=0)
    articles = provider.fetch_since(NOW - timedelta(hours=2))
    kestrel = next(a for a in articles if "Kestrel" in a.headline)

    resolution = resolve_entity(headline=kestrel.headline, body=kestrel.body,
                                provider_tickers=kestrel.tickers,
                                known_companies={})    # deliberately empty
    assert resolution.ticker == "KTRX"
    assert resolution.confidence >= 0.7
    assert resolution.resolved


def test_article_carries_the_wire_tier_and_provenance():
    provider, _ = build({GNW.url: (200, GLOBENEWSWIRE_RSS)}, max_body_fetches=0)
    article = provider.fetch_since(NOW - timedelta(hours=2))[0]

    assert article.provider == "wire_rss"
    assert article.source_tier == SourceTier.PRIMARY
    assert article.original_source == "GlobeNewswire"
    assert article.published_at_utc is not None
    assert article.received_at_utc is not None
    # Detection lag is measurable from these two alone — no extra schema.
    assert article.received_at_utc >= article.published_at_utc


def test_a_wire_release_travels_end_to_end_into_the_database(db):
    """The whole point, exercised for real.

    Feed → provider → poller → the real pipeline → rows on disk. Only the LLM
    and the price feed are absent, which is exactly how the system runs before
    those keys are set. Nothing about the company is seeded: the release is
    from a business we have never heard of.
    """
    from app.catalyst.alerts import CatalystNotifier
    from app.catalyst.pipeline import CatalystPipeline
    from app.config import Settings
    from app.db.catalyst_models import CatalystEvent, NewsItem
    from app.db.models import Company
    from app.services.catalyst_poller import CatalystPollingService
    from tests.fakes import FakeNotifier

    conf = Settings(database_url="sqlite://", min_entity_confidence=0.7,
                    news_max_age_seconds=86400.0)
    release_url = ("https://www.globenewswire.com/news-release/2026/08/30/1/en/"
                   "Kestrel.html?ref=rss&utm_source=feed")
    provider, _ = build({GNW.url: (200, GLOBENEWSWIRE_RSS),
                         release_url: (200, RELEASE_PAGE)}, max_body_fetches=5)
    pipeline = CatalystPipeline(settings=conf, investigator=None,
                                notifier=CatalystNotifier([FakeNotifier()]),
                                market_context_fn=None)
    poller = CatalystPollingService(pipeline=pipeline, sec=None,
                                    news_providers=[provider], settings=conf)

    with db.db_session() as session:
        assert session.query(Company).count() == 0
        result = poller.poll(session, NOW)

    assert result.articles_seen == 2
    assert result.articles_processed == 2

    with db.db_session() as session:
        stored = {i.headline: i for i in session.query(NewsItem).all()}
        assert len(stored) == 2
        kestrel = next(i for h, i in stored.items() if "Kestrel" in h)
        assert kestrel.provider == "wire_rss"
        assert kestrel.original_source == "GlobeNewswire"
        # The body came from the release page, not the RSS stub.
        assert "Peak annual sales" in kestrel.body
        # Detection lag is a real measured number, not an assumption.
        lag = (kestrel.received_at_utc - kestrel.published_at_utc).total_seconds()
        assert lag > 0

        # An event exists for a ticker that was never in the company table.
        tickers = {e.ticker for e in session.query(CatalystEvent).all()}
        assert "KTRX" in tickers


def test_a_second_sweep_of_an_unchanged_feed_writes_nothing_new(db):
    """Idempotency where it matters: the poller runs every 30 seconds."""
    from app.catalyst.alerts import CatalystNotifier
    from app.catalyst.pipeline import CatalystPipeline
    from app.config import Settings
    from app.db.catalyst_models import CatalystEvent, NewsItem
    from app.services.catalyst_poller import CatalystPollingService
    from tests.fakes import FakeNotifier

    conf = Settings(database_url="sqlite://", min_entity_confidence=0.7,
                    news_max_age_seconds=86400.0)
    provider, _ = build({GNW.url: (200, GLOBENEWSWIRE_RSS)}, max_body_fetches=0)
    poller = CatalystPollingService(
        pipeline=CatalystPipeline(settings=conf, investigator=None,
                                  notifier=CatalystNotifier([FakeNotifier()]),
                                  market_context_fn=None),
        sec=None, news_providers=[provider], settings=conf)

    with db.db_session() as session:
        poller.poll(session, NOW)
    with db.db_session() as session:
        before = (session.query(NewsItem).count(), session.query(CatalystEvent).count())
        second = poller.poll(session, NOW + timedelta(seconds=30))
        after = (session.query(NewsItem).count(), session.query(CatalystEvent).count())

    assert second.articles_seen == 0
    assert before == after


def test_a_revised_release_at_the_same_url_changes_the_content_hash():
    """Same URL, edited text. `article_id` is stable so the pipeline matches it
    to the original; the hash differs so the revision is not swallowed."""
    original = parse_wire_feed(GLOBENEWSWIRE_RSS)[0]
    provider, _ = build({}, max_body_fetches=0)
    first = provider._to_article(GNW, original, original.summary)
    revised = provider._to_article(GNW, original, original.summary + " Updated: dosing.")

    assert first.article_id == revised.article_id
    assert first.content_hash() != revised.content_hash()
