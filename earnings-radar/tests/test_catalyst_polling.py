"""Continuous catalyst polling and outcome capture.

Both jobs run against the real database with fake providers, so the SQL,
the routing decisions and the idempotency all execute for real.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.catalyst.enums import SourceTier
from app.config import Settings
from app.db.catalyst_models import (
    CatalystEvent,
    CatalystOutcome,
    EventCluster,
    HistoricalAnalogue,
    NewsItem,
)
from app.db.models import Company
from app.domain.timeutil import UTC
from app.providers.base import Bar, FilingHit, ProviderError
from app.providers.news import MockNewsProvider, NewsArticle
from app.providers.sec_edgar import FeedEntry, parse_current_feed
from app.services.catalyst_poller import CatalystPollingService
from app.services.outcomes import OutcomeCaptureService

NOW = datetime(2026, 8, 27, 14, 30, tzinfo=UTC)


def settings(**overrides) -> Settings:
    base = dict(database_url="sqlite://", catalyst_filing_lookback_minutes=90,
                catalyst_max_universe=400, news_max_age_seconds=3600.0,
                benchmark_ticker="SPY", outcome_capture_window_days=5)
    base.update(overrides)
    return Settings(**base)


# ── EDGAR feed parsing ────────────────────────────────────────────────────────


FEED_XML = """<?xml version="1.0" encoding="ISO-8859-1"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>8-K - ACME DEFENSE CORP (0000012345) (Filer)</title>
    <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/12345/x-index.htm"/>
    <category scheme="https://www.sec.gov/" label="form type" term="8-K"/>
    <updated>2026-08-27T10:20:31-04:00</updated>
  </entry>
  <entry>
    <title>4 - Smith John (0000099999) (Reporting)</title>
    <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/99999/y-index.htm"/>
    <category scheme="https://www.sec.gov/" label="form type" term="4"/>
    <updated>2026-08-27T10:21:00-04:00</updated>
  </entry>
  <entry>
    <title>malformed entry with no cik</title>
  </entry>
</feed>
"""


def test_feed_parsing_extracts_cik_form_and_time():
    entries = parse_current_feed(FEED_XML)

    assert len(entries) == 2                 # the malformed entry is skipped
    assert entries[0].cik == "0000012345"
    assert entries[0].form_type == "8-K"
    assert entries[0].company_name == "ACME DEFENSE CORP"
    assert entries[0].accepted_at_utc == datetime(2026, 8, 27, 14, 20, 31, tzinfo=UTC)


def test_form_types_containing_hyphens_are_parsed():
    """The separator is ' - ' with spaces. Splitting on a bare hyphen would
    drop 8-K, 10-Q, S-1 and SC 13D/A — very nearly everything."""
    xml = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>SC 13D/A - ACME CORP (0000012345) (Filer)</title>
      <category term="SC 13D/A"/><updated>2026-08-27T10:20:00-04:00</updated></entry>
    </feed>"""
    entries = parse_current_feed(xml)
    assert entries[0].form_type == "SC 13D/A"
    assert entries[0].cik == "0000012345"


def test_broken_xml_raises_rather_than_silently_returning_nothing():
    """An empty list would read as 'nothing filed' — the one wrong answer."""
    with pytest.raises(ProviderError):
        parse_current_feed("<feed><entry>unclosed")


def test_a_big_response_with_no_entries_is_treated_as_a_format_change():
    """If EDGAR changes the feed's shape, parsing yields nothing — which looks
    identical to a quiet market. That silence must be loud."""
    import httpx

    from app.providers.sec_edgar import SecEdgarProvider

    body = "<feed xmlns='http://www.w3.org/2005/Atom'>" + ("<x>pad</x>" * 400) + "</feed>"
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text=body)))
    provider = SecEdgarProvider(client=client)

    with pytest.raises(ProviderError, match="format may have changed"):
        provider.latest_filings()


def test_a_genuinely_empty_feed_is_not_an_error():
    import httpx

    from app.providers.sec_edgar import SecEdgarProvider

    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(
            200, text="<feed xmlns='http://www.w3.org/2005/Atom'></feed>")))

    assert SecEdgarProvider(client=client).latest_filings() == []


# ── fakes ─────────────────────────────────────────────────────────────────────


class FakeSec:
    name = "sec_edgar"

    def __init__(self, entries: list[FeedEntry], filings: dict[str, list[FilingHit]],
                 documents: dict[str, str] | None = None, feed_error: bool = False):
        self._entries = entries
        self._filings = filings
        self._documents = documents or {}
        self._feed_error = feed_error
        self.document_fetches: list[str] = []

    def latest_filings(self, form_type: str = "", count: int = 100):
        if self._feed_error:
            raise ProviderError("EDGAR down")
        return self._entries

    def recent_filings(self, ticker, cik, forms_filter=None):
        return self._filings.get(ticker.upper(), [])

    def fetch_document_text(self, url):
        self.document_fetches.append(url)
        return self._documents.get(url, "")


class RecordingPipeline:
    """Stands in for the scoring pipeline: records what it was handed."""

    def __init__(self, score=None, alerted=False):
        self.articles: list[NewsArticle] = []
        self._score = score
        self._alerted = alerted

    def process(self, session, article, *, now=None):
        self.articles.append(article)

        class Result:
            score = self._score
            alerted = self._alerted
        return Result()


def seed(session, ticker="ACME", cik="0000012345") -> Company:
    company = Company(ticker=ticker, name="Acme Defense Corporation",
                      cik=cik, market_cap=400e6)
    session.add(company)
    session.flush()
    return company


def filing(url: str, form="8-K", items=None, minutes_ago=5, description="") -> FilingHit:
    return FilingHit(ticker="ACME", form_type=form,
                     accepted_at_utc=NOW - timedelta(minutes=minutes_ago),
                     url=url, description=description, items=items or [])


# ── SEC stream ────────────────────────────────────────────────────────────────


def test_a_material_agreement_filing_reaches_the_pipeline(db):
    with db.db_session() as session:
        seed(session)
        sec = FakeSec(
            [FeedEntry(cik="0000012345", form_type="8-K", company_name="ACME",
                       accepted_at_utc=NOW - timedelta(minutes=5))],
            {"ACME": [filing("https://sec.gov/a.htm", items=["1.01"])]},
            {"https://sec.gov/a.htm": "Acme signed a $500 million agreement."})
        pipeline = RecordingPipeline(score=8.4)
        poller = CatalystPollingService(pipeline=pipeline, sec=sec,
                                        news_providers=[], settings=settings())

        result = poller.poll(session, NOW)

    assert result.filings_processed == 1
    assert result.scored == 1
    article = pipeline.articles[0]
    assert article.provider == "sec_edgar"
    assert article.source_tier == SourceTier.PRIMARY
    assert article.tickers == ["ACME"]
    assert "500 million" in article.body


def test_results_filings_are_left_to_earnings_sentinel(db):
    """Item 2.02 is the earnings release. Scoring it here too would produce two
    competing numbers for one event."""
    with db.db_session() as session:
        seed(session)
        sec = FakeSec(
            [FeedEntry(cik="0000012345", form_type="8-K", company_name="ACME",
                       accepted_at_utc=NOW - timedelta(minutes=2))],
            {"ACME": [filing("https://sec.gov/earnings.htm", items=["2.02"])]})
        pipeline = RecordingPipeline()
        poller = CatalystPollingService(pipeline=pipeline, sec=sec,
                                        news_providers=[], settings=settings())

        poller.poll(session, NOW)

    assert pipeline.articles == []
    assert sec.document_fetches == []       # not even downloaded


def test_filings_from_companies_we_do_not_track_are_ignored(db):
    with db.db_session() as session:
        seed(session, cik="0000012345")
        sec = FakeSec(
            [FeedEntry(cik="0000077777", form_type="8-K", company_name="OTHER",
                       accepted_at_utc=NOW)],
            {})
        pipeline = RecordingPipeline()
        poller = CatalystPollingService(pipeline=pipeline, sec=sec,
                                        news_providers=[], settings=settings())

        result = poller.poll(session, NOW)

    assert result.filings_seen == 1
    assert result.filings_processed == 0
    assert pipeline.articles == []


def test_stale_filings_outside_the_lookback_are_skipped(db):
    with db.db_session() as session:
        seed(session)
        sec = FakeSec(
            [FeedEntry(cik="0000012345", form_type="8-K", company_name="ACME",
                       accepted_at_utc=NOW - timedelta(hours=6))],
            {"ACME": [filing("https://sec.gov/old.htm", items=["1.01"], minutes_ago=360)]})
        poller = CatalystPollingService(pipeline=RecordingPipeline(), sec=sec,
                                        news_providers=[], settings=settings())

        assert poller.poll(session, NOW).filings_processed == 0


def test_the_same_filing_is_never_processed_twice(db):
    with db.db_session() as session:
        seed(session)
        sec = FakeSec(
            [FeedEntry(cik="0000012345", form_type="8-K", company_name="ACME",
                       accepted_at_utc=NOW - timedelta(minutes=5))],
            {"ACME": [filing("https://sec.gov/a.htm", items=["1.01"])]})
        pipeline = RecordingPipeline()
        poller = CatalystPollingService(pipeline=pipeline, sec=sec,
                                        news_providers=[], settings=settings())

        poller.poll(session, NOW)
        poller.poll(session, NOW)

    assert len(pipeline.articles) == 1


def test_high_volume_forms_are_routed_without_downloading_the_document(db):
    """Form 4s run to thousands a day; fetching each one would be the whole
    rate budget for no added signal."""
    with db.db_session() as session:
        seed(session)
        sec = FakeSec(
            [FeedEntry(cik="0000012345", form_type="4", company_name="ACME",
                       accepted_at_utc=NOW)],
            {"ACME": [filing("https://sec.gov/f4.htm", form="4")]})
        poller = CatalystPollingService(pipeline=RecordingPipeline(), sec=sec,
                                        news_providers=[], settings=settings())

        poller.poll(session, NOW)

    assert sec.document_fetches == []


def test_an_edgar_outage_is_recorded_and_the_news_stream_still_runs(db):
    with db.db_session() as session:
        seed(session)
        news = MockNewsProvider([NewsArticle(
            provider="mock", article_id="n1", headline="Acme wins contract",
            body="Acme Defense Corporation won a contract.", tickers=["ACME"],
            published_at_utc=NOW - timedelta(minutes=1))])
        pipeline = RecordingPipeline()
        poller = CatalystPollingService(
            pipeline=pipeline, sec=FakeSec([], {}, feed_error=True),
            news_providers=[news], settings=settings())

        result = poller.poll(session, NOW)

    assert any("sec feed" in e for e in result.errors)
    assert result.articles_processed == 1


# ── news stream ───────────────────────────────────────────────────────────────


def test_news_already_ingested_unchanged_is_not_reprocessed(db):
    article = NewsArticle(provider="mock", article_id="n1",
                          headline="Acme wins a contract",
                          body="Acme Defense Corporation won a contract.",
                          tickers=["ACME"], published_at_utc=NOW - timedelta(minutes=1))
    with db.db_session() as session:
        seed(session)
        session.add(NewsItem(provider="mock", article_id="n1",
                             headline=article.headline, body=article.body,
                             tickers=["ACME"], content_hash=article.content_hash(),
                             received_at_utc=NOW - timedelta(minutes=1)))
        session.flush()

        pipeline = RecordingPipeline()
        poller = CatalystPollingService(pipeline=pipeline, sec=None,
                                        news_providers=[MockNewsProvider([article])],
                                        settings=settings())
        poller.poll(session, NOW)

    assert pipeline.articles == []


def test_a_revised_story_is_reprocessed_because_it_may_carry_new_information(db):
    original = NewsArticle(provider="mock", article_id="n1", headline="Acme in talks",
                           body="Acme Defense Corporation is in talks.",
                           tickers=["ACME"], published_at_utc=NOW - timedelta(minutes=5))
    revised = NewsArticle(provider="mock", article_id="n1",
                          headline="Acme signs $500m deal",
                          body="Acme Defense Corporation signed a $500 million deal.",
                          tickers=["ACME"], published_at_utc=NOW - timedelta(minutes=1))
    with db.db_session() as session:
        seed(session)
        session.add(NewsItem(provider="mock", article_id="n1",
                             headline=original.headline, body=original.body,
                             tickers=["ACME"], content_hash=original.content_hash(),
                             received_at_utc=NOW - timedelta(minutes=5)))
        session.flush()

        pipeline = RecordingPipeline()
        poller = CatalystPollingService(pipeline=pipeline, sec=None,
                                        news_providers=[MockNewsProvider([revised])],
                                        settings=settings())
        poller.poll(session, NOW)

    assert len(pipeline.articles) == 1


def test_the_news_cursor_advances_so_a_backlog_is_not_re_read(db):
    provider = MockNewsProvider([NewsArticle(
        provider="mock", article_id="n1", headline="Acme wins",
        body="Acme Defense Corporation won.", tickers=["ACME"],
        published_at_utc=NOW - timedelta(minutes=30))])
    with db.db_session() as session:
        seed(session)
        poller = CatalystPollingService(pipeline=RecordingPipeline(), sec=None,
                                        news_providers=[provider], settings=settings())
        poller.poll(session, NOW)

    assert poller._news_cursor["mock_news"] == NOW - timedelta(minutes=30)


def test_one_bad_article_does_not_stop_the_batch(db):
    class ExplodingPipeline(RecordingPipeline):
        def process(self, session, article, *, now=None):
            if article.article_id == "bad":
                raise RuntimeError("boom")
            return super().process(session, article, now=now)

    articles = [
        NewsArticle(provider="mock", article_id="bad", headline="Bad",
                    body="Acme Defense Corporation.", tickers=["ACME"],
                    published_at_utc=NOW - timedelta(minutes=2)),
        NewsArticle(provider="mock", article_id="good", headline="Good",
                    body="Acme Defense Corporation won.", tickers=["ACME"],
                    published_at_utc=NOW - timedelta(minutes=1)),
    ]
    with db.db_session() as session:
        seed(session)
        pipeline = ExplodingPipeline()
        poller = CatalystPollingService(pipeline=pipeline, sec=None,
                                        news_providers=[MockNewsProvider(articles)],
                                        settings=settings())
        result = poller.poll(session, NOW)

    assert result.articles_processed == 1
    assert any("boom" in e for e in result.errors)


# ── outcome capture ───────────────────────────────────────────────────────────


class FakeBarSource:
    def __init__(self, series: dict[str, list[Bar]]):
        self.series = series

    def bars(self, ticker, *, start, end, timespan="minute", multiplier=1, limit=5000):
        return [b for b in self.series.get(ticker.upper(), []) if start <= b.start_utc <= end]

    def daily_bars(self, ticker, days):
        return self.series.get(f"{ticker.upper()}:daily", [])


def minute_series(closes: list[float], start: datetime) -> list[Bar]:
    return [Bar(start_utc=start + timedelta(minutes=i), open=c, high=c * 1.02,
                low=c * 0.98, close=c, volume=1000.0) for i, c in enumerate(closes)]


def seed_scored_event(session, disclosure: datetime, ticker="ACME") -> CatalystEvent:
    cluster = EventCluster(cluster_key=f"{ticker}|test", ticker=ticker,
                           earliest_public_at_utc=disclosure)
    session.add(cluster)
    session.flush()
    event = CatalystEvent(cluster_id=cluster.id, ticker=ticker, event_type="government_contract",
                          event_category="CONTRACT", state="SCORED", headline="Acme wins")
    session.add(event)
    session.flush()
    return event


def test_returns_are_measured_from_the_disclosure_price(db):
    disclosure = NOW - timedelta(minutes=90)
    # Flat at 10 until the news, then a step up.
    closes = [10.0] * 10 + [12.0] * 10 + [12.5] * 80
    bars = minute_series(closes, disclosure - timedelta(minutes=10))

    with db.db_session() as session:
        event = seed_scored_event(session, disclosure)
        service = OutcomeCaptureService(
            bars=FakeBarSource({"ACME": bars, "SPY": []}), settings=settings())
        result = service.run(session, NOW)

        outcome = session.query(CatalystOutcome).filter_by(event_id=event.id).one()

    assert result.events_updated == 1
    assert outcome.price_earliest_public == 10.0
    assert outcome.ret_5m == pytest.approx(20.0)
    assert outcome.ret_60m == pytest.approx(25.0)


def test_abnormal_returns_strip_out_the_market(db):
    """A 10% gain on a day the market rose 10% is not a result."""
    disclosure = NOW - timedelta(minutes=90)
    stock = minute_series([10.0] * 10 + [11.0] * 90, disclosure - timedelta(minutes=10))
    spy = minute_series([500.0] * 10 + [550.0] * 90, disclosure - timedelta(minutes=10))

    with db.db_session() as session:
        event = seed_scored_event(session, disclosure)
        OutcomeCaptureService(bars=FakeBarSource({"ACME": stock, "SPY": spy}),
                              settings=settings()).run(session, NOW)
        outcome = session.query(CatalystOutcome).filter_by(event_id=event.id).one()

    assert outcome.ret_60m == pytest.approx(10.0)
    assert outcome.abnormal_ret_60m == pytest.approx(0.0, abs=0.01)


def test_excursions_record_the_best_and_worst_points(db):
    disclosure = NOW - timedelta(minutes=90)
    closes = [10.0] * 10 + [14.0] + [8.0] + [11.0] * 88
    bars = minute_series(closes, disclosure - timedelta(minutes=10))

    with db.db_session() as session:
        event = seed_scored_event(session, disclosure)
        OutcomeCaptureService(bars=FakeBarSource({"ACME": bars}),
                              settings=settings()).run(session, NOW)
        outcome = session.query(CatalystOutcome).filter_by(event_id=event.id).one()

    assert outcome.mfe_1h > 40          # touched 14.28 at the high
    assert outcome.mae_1d is None       # the day is not over yet


def test_immature_horizons_are_left_unfilled_rather_than_guessed(db):
    disclosure = NOW - timedelta(minutes=3)
    bars = minute_series([10.0, 10.0, 11.0, 11.5], disclosure - timedelta(minutes=1))

    with db.db_session() as session:
        event = seed_scored_event(session, disclosure)
        OutcomeCaptureService(bars=FakeBarSource({"ACME": bars}),
                              settings=settings()).run(session, NOW)
        outcome = session.query(CatalystOutcome).filter_by(event_id=event.id).one()

    assert outcome.ret_1m is not None
    assert outcome.ret_30m is None
    assert outcome.ret_1d is None


def test_a_completed_event_feeds_the_analogue_store(db):
    """This is the only route by which Reaction Room ever stops guessing."""
    disclosure = NOW - timedelta(days=2)
    bars = minute_series([10.0] * 5 + [13.0] * 2000, disclosure - timedelta(minutes=5))

    with db.db_session() as session:
        event = seed_scored_event(session, disclosure)
        result = OutcomeCaptureService(bars=FakeBarSource({"ACME": bars}),
                                       settings=settings()).run(session, NOW)
        analogue = session.query(HistoricalAnalogue).filter_by(event_id=event.id).one()

    assert result.events_completed == 1
    assert analogue.event_type == "government_contract"
    assert analogue.outcome_ret_1d == pytest.approx(30.0)


def test_capture_is_idempotent_once_an_event_has_matured(db):
    disclosure = NOW - timedelta(days=2)
    bars = minute_series([10.0] * 5 + [13.0] * 2000, disclosure - timedelta(minutes=5))

    with db.db_session() as session:
        seed_scored_event(session, disclosure)
        service = OutcomeCaptureService(bars=FakeBarSource({"ACME": bars}),
                                        settings=settings())
        service.run(session, NOW)
        second = service.run(session, NOW)

        assert session.query(HistoricalAnalogue).count() == 1
    assert second.events_updated == 0


def test_capture_without_a_bar_provider_does_nothing_rather_than_failing(db):
    with db.db_session() as session:
        seed_scored_event(session, NOW - timedelta(hours=2))
        service = OutcomeCaptureService(bars=None, settings=settings())
        result = service.run(session, NOW)

    assert service.available is False
    assert result.events_considered == 0


def test_missing_bars_leave_the_outcome_alone(db):
    with db.db_session() as session:
        event = seed_scored_event(session, NOW - timedelta(hours=2))
        OutcomeCaptureService(bars=FakeBarSource({}), settings=settings()).run(session, NOW)

        assert session.query(CatalystOutcome).filter_by(event_id=event.id).count() == 1
        outcome = session.query(CatalystOutcome).filter_by(event_id=event.id).one()
        assert outcome.ret_5m is None
