"""End-to-end wiring: real pipeline + real market-data service + fake provider.

These are the tests that would catch a market-data layer that parses perfectly
and still feeds the scoring engine the wrong numbers. Nothing is stubbed
between the bars and the score except the LLM and the HTTP transport.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy import (
    Column,
    Float,
    MetaData,
    Table,
    create_engine,
    inspect,
    text,
)

from app.catalyst.alerts import CatalystNotifier
from app.catalyst.pipeline import CatalystPipeline
from app.config import Settings
from app.db.catalyst_models import CatalystScore, MarketStructureSnapshot
from app.db.models import Company
from app.db.session import add_missing_columns
from app.domain.timeutil import UTC
from app.providers.base import Bar, ShortInterest, Snapshot, TickerDetails
from app.providers.news import NewsArticle
from app.services.catalyst_market import CatalystMarketDataService
from app.services.scheduler import SchedulerService
from tests.fakes import FakeNotifier

NOW = datetime(2026, 8, 27, 14, 30, tzinfo=UTC)
EVENT_AT = NOW - timedelta(minutes=8)


def settings(**overrides) -> Settings:
    base = dict(database_url="sqlite://", benchmark_ticker="SPY", market_data_delay_seconds=0.0,
                catalyst_atr_days=14, catalyst_runup_lookback_days=10,
                min_entity_confidence=0.7, news_max_age_seconds=86400.0,
                catalyst_push_score=9.0, catalyst_min_confidence=6.0)
    base.update(overrides)
    return Settings(**base)


class ScriptedMarket:
    """A price provider whose whole job is to be a specific market state."""

    name = "scripted"

    SUBJECT = "ACME"

    def __init__(self, *, stock_closes, spy_closes, free_float=20e6,
                 short_shares=5e6, day_volume=8_000_000):
        self.stock_closes = stock_closes
        # Every comparator (SPY and any sector ETF) shares this series. Giving
        # a comparator the stock's own series would make the abnormal move
        # collapse to zero and quietly disarm the test.
        self.spy_closes = spy_closes
        self.free_float = free_float
        self.short_shares = short_shares
        self.day_volume = day_volume

    def _series(self, closes, start):
        return [Bar(start_utc=start + timedelta(minutes=i), open=c, high=c * 1.01,
                    low=c * 0.99, close=c, volume=20_000.0)
                for i, c in enumerate(closes)]

    def bars(self, ticker, *, start, end, timespan="minute", multiplier=1, limit=5000):
        closes = (self.stock_closes if ticker.upper() == self.SUBJECT
                  else self.spy_closes)
        origin = EVENT_AT - timedelta(minutes=4)
        return [b for b in self._series(closes, origin) if start <= b.start_utc <= end]

    def daily_bars(self, ticker, days):
        return [Bar(start_utc=NOW - timedelta(days=30 - i), open=10.0, high=10.4,
                    low=9.6, close=10.0, volume=1_000_000.0) for i in range(30)]

    def snapshot(self, ticker):
        return Snapshot(ticker=ticker.upper(), price=self.stock_closes[-1],
                        prev_close=self.stock_closes[0], day_volume=self.day_volume,
                        bid=self.stock_closes[-1] - 0.01,
                        ask=self.stock_closes[-1] + 0.01, last_trade_at=NOW)

    def details(self, ticker):
        return TickerDetails(ticker=ticker.upper(), name="Acme Defense Corporation",
                             market_cap=400e6, shares_outstanding=40e6)

    def short_interest(self, ticker):
        return ShortInterest(ticker=ticker.upper(),
                             settlement_date=(NOW - timedelta(days=5)).date(),
                             short_interest_shares=self.short_shares,
                             days_to_cover=5.5)

    def free_float_shares(self, ticker):
        return self.free_float


def build(market: ScriptedMarket, conf: Settings | None = None):
    conf = conf or settings()
    service = CatalystMarketDataService(bars=market, structure=market, settings=conf,
                                        float_providers=[market])
    notifier = FakeNotifier()
    pipeline = CatalystPipeline(
        settings=conf, investigator=None, notifier=CatalystNotifier([notifier]),
        market_context_fn=service.as_context_fn())
    return pipeline, notifier


def article() -> NewsArticle:
    return NewsArticle(
        provider="sec_edgar", article_id="https://sec.gov/acme-8k.htm",
        headline="Acme Defense Corporation awarded $600 million Air Force contract",
        body=("Acme Defense Corporation (NASDAQ: ACME) today announced it has been "
              "awarded a firm-fixed-price contract with a guaranteed value of "
              "$600 million over 5 years by the United States Air Force."),
        tickers=["ACME"], published_at_utc=EVENT_AT, received_at_utc=NOW)


def _reset(session):
    """Clear everything the pipeline writes, so the same story can be replayed
    against a different market state. Without this the second run correctly
    joins the first run's cluster and is never re-scored."""
    from app.db.catalyst_models import (
        CatalystEvent,
        CatalystSource,
        EventCluster,
        MaterialityAnalysis,
        NegativeOffsetRow,
        NewsItem,
        NoveltyAnalysis,
        PipelineTrace,
        ReactionAnalysis,
    )
    for model in (PipelineTrace, CatalystScore, ReactionAnalysis,
                  MarketStructureSnapshot, NegativeOffsetRow, MaterialityAnalysis,
                  NoveltyAnalysis, CatalystSource, CatalystEvent, NewsItem,
                  EventCluster, Company):
        session.query(model).delete()
    session.flush()


def seed(session, sector="Industrials"):
    company = Company(ticker="ACME", name="Acme Defense Corporation",
                      market_cap=400e6, sector=sector, cik="0000012345")
    session.add(company)
    session.flush()
    return company


# ── the wiring actually changes the answer ────────────────────────────────────


def test_a_stock_that_has_already_moved_scores_lower_than_one_that_has_not(db):
    """The whole point of live prices: two identical catalysts, different
    amounts of move left. If the wiring were inert these would score the same."""
    fresh = ScriptedMarket(stock_closes=[10.0] * 4 + [10.1] * 9,
                           spy_closes=[500.0] * 13)
    repriced = ScriptedMarket(stock_closes=[10.0] * 4 + [16.0] * 9,
                              spy_closes=[500.0] * 13)

    scores = []
    for market in (fresh, repriced):
        with db.db_session() as session:
            _reset(session)
            pipeline, _ = build(market)
            seed(session)
            result = pipeline.process(session, article(), now=NOW)
            scores.append(result.score)

    assert scores[0] is not None and scores[1] is not None
    assert scores[0] > scores[1], "an already-repriced stock must score lower"


def test_a_market_wide_rally_is_not_credited_to_the_company(db):
    """+6% on a day the sector rose +6% is not a company-specific move."""
    with db.db_session() as session:
        market = ScriptedMarket(stock_closes=[10.0] * 4 + [10.6] * 9,
                                spy_closes=[500.0] * 4 + [530.0] * 9)
        pipeline, _ = build(market)
        seed(session)
        pipeline.process(session, article(), now=NOW)

        from app.db.catalyst_models import ReactionAnalysis
        reaction = session.query(ReactionAnalysis).one()

    assert reaction.move_since_disclosure_pct == pytest.approx(6.0, abs=0.1)
    assert reaction.abnormal_move_pct == pytest.approx(0.0, abs=0.2)


def test_market_structure_is_persisted_from_live_data(db):
    with db.db_session() as session:
        pipeline, _ = build(ScriptedMarket(stock_closes=[10.0] * 4 + [10.2] * 9,
                                           spy_closes=[500.0] * 13))
        seed(session)
        pipeline.process(session, article(), now=NOW)

        snapshot = session.query(MarketStructureSnapshot).one()

    assert snapshot.free_float_shares == 20e6
    assert snapshot.shares_outstanding == 40e6
    assert snapshot.short_percent_float == pytest.approx(25.0)
    assert snapshot.short_percent_shares_outstanding == pytest.approx(12.5)
    assert snapshot.spread_pct is not None
    assert snapshot.atr_pct is not None
    assert snapshot.free_float_shares != snapshot.shares_outstanding


def test_the_sector_comparator_is_used_when_the_company_has_a_sector(db):
    with db.db_session() as session:
        pipeline, _ = build(ScriptedMarket(stock_closes=[10.0] * 4 + [10.5] * 9,
                                           spy_closes=[500.0] * 13))
        seed(session, sector="Technology")
        pipeline.process(session, article(), now=NOW)

        from app.db.catalyst_models import ReactionAnalysis
        reaction = session.query(ReactionAnalysis).one()

    assert reaction.sector_move_pct is not None


def test_scoring_still_completes_when_market_data_is_entirely_absent(db):
    """A dead price feed degrades the score; it never crashes the pipeline."""
    with db.db_session() as session:
        conf = settings()
        service = CatalystMarketDataService(bars=None, structure=None, settings=conf)
        pipeline = CatalystPipeline(
            settings=conf, investigator=None,
            notifier=CatalystNotifier([FakeNotifier()]),
            market_context_fn=service.as_context_fn())
        seed(session)
        result = pipeline.process(session, article(), now=NOW)

        score = session.query(CatalystScore).one()

    assert result.score is not None
    assert score.gates_failed or score.caps_applied


# ── scheduler registration ────────────────────────────────────────────────────


class StubDiscovery:
    def run(self, session):
        return 0


class StubPoller:
    def __init__(self):
        self.calls = 0

    def poll(self, session, now=None):
        self.calls += 1
        return "polled"


class StubOutcomes:
    available = True

    def __init__(self):
        self.calls = 0

    def run(self, session, now=None):
        self.calls += 1
        return "captured"


def make_scheduler(conf: Settings, poller=None, outcomes=None) -> SchedulerService:
    return SchedulerService(settings=conf, discovery=StubDiscovery(), pipeline=None,
                            catalyst_poller=poller, outcomes=outcomes)


def test_catalyst_jobs_are_registered_when_their_services_exist(db):
    scheduler = make_scheduler(settings(catalyst_poll_seconds=30,
                                        outcome_capture_interval_seconds=300),
                               poller=StubPoller(), outcomes=StubOutcomes())
    scheduler.start()
    try:
        ids = {job.id for job in scheduler._scheduler.get_jobs()}
    finally:
        scheduler.shutdown()

    assert "catalyst-poll" in ids
    assert "outcome-capture" in ids


def test_no_catalyst_jobs_without_the_services(db):
    scheduler = make_scheduler(settings())
    scheduler.start()
    try:
        ids = {job.id for job in scheduler._scheduler.get_jobs()}
    finally:
        scheduler.shutdown()

    assert "catalyst-poll" not in ids
    assert "outcome-capture" not in ids


def test_outcome_capture_can_be_switched_off(db):
    scheduler = make_scheduler(settings(outcome_capture_enabled=False),
                               poller=StubPoller(), outcomes=StubOutcomes())
    scheduler.start()
    try:
        ids = {job.id for job in scheduler._scheduler.get_jobs()}
    finally:
        scheduler.shutdown()

    assert "catalyst-poll" in ids
    assert "outcome-capture" not in ids


def test_a_failing_poll_never_escapes_into_the_scheduler(db):
    """A provider outage must not kill the loop that would recover from it."""
    class Exploding:
        def poll(self, session, now=None):
            raise RuntimeError("provider on fire")

    scheduler = make_scheduler(settings(), poller=Exploding())
    assert scheduler.catalyst_poll(NOW) is None
    assert scheduler.last_catalyst_poll_at == NOW


def test_a_failing_outcome_capture_never_escapes_either(db):
    class Exploding:
        available = True

        def run(self, session, now=None):
            raise RuntimeError("bars unavailable")

    scheduler = make_scheduler(settings(), outcomes=Exploding())
    assert scheduler.capture_outcomes(NOW) is None
    assert scheduler.last_outcome_capture_at == NOW


def test_manual_triggers_run_the_jobs(db):
    poller, outcomes = StubPoller(), StubOutcomes()
    scheduler = make_scheduler(settings(), poller=poller, outcomes=outcomes)

    assert scheduler.catalyst_poll(NOW) == "polled"
    assert scheduler.capture_outcomes(NOW) == "captured"
    assert poller.calls == 1
    assert outcomes.calls == 1


# ── additive schema migration ─────────────────────────────────────────────────


def test_a_new_nullable_column_is_added_to_an_existing_table(tmp_path):
    """`create_all` only creates missing tables, so without this an existing
    local database breaks on the next insert after a schema addition."""
    url = f"sqlite:///{tmp_path / 'm.db'}"
    engine = create_engine(url)

    old = MetaData()
    Table("widgets", old, Column("id", Float, primary_key=True))
    old.create_all(engine)

    new = MetaData()
    Table("widgets", new, Column("id", Float, primary_key=True),
          Column("added_later", Float, nullable=True))

    added = add_missing_columns(engine, new)

    assert added == ["widgets.added_later"]
    assert "added_later" in {c["name"] for c in inspect(engine).get_columns("widgets")}


def test_running_the_migration_twice_changes_nothing(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    engine = create_engine(url)
    meta = MetaData()
    Table("widgets", meta, Column("id", Float, primary_key=True),
          Column("extra", Float, nullable=True))
    meta.create_all(engine)

    assert add_missing_columns(engine, meta) == []


def test_a_non_nullable_addition_is_refused_rather_than_guessed_at(tmp_path):
    """Filling a NOT NULL column needs a decision about existing rows that
    only a hand-written migration can make."""
    url = f"sqlite:///{tmp_path / 'm.db'}"
    engine = create_engine(url)

    old = MetaData()
    Table("widgets", old, Column("id", Float, primary_key=True))
    old.create_all(engine)

    new = MetaData()
    Table("widgets", new, Column("id", Float, primary_key=True),
          Column("required", Float, nullable=False))

    assert add_missing_columns(engine, new) == []
    assert "required" not in {c["name"] for c in inspect(engine).get_columns("widgets")}


def test_the_polygon_adapter_reports_itself_disabled_without_a_key():
    from app.providers.polygon import PolygonProvider

    assert PolygonProvider(client=httpx.Client(), api_key="").enabled() is False
    assert PolygonProvider(client=httpx.Client(), api_key="k").enabled() is True


# ── NOT NULL columns with defaults (the v0.3.3 startup failure) ───────────────


def test_a_not_null_column_with_a_default_is_added(tmp_path):
    """The bug that broke a live database: `default=` is applied in Python on
    insert, never in DDL, so the column was refused as non-nullable and every
    later INSERT named a column the table did not have."""
    from sqlalchemy import Boolean, Integer, String

    url = f"sqlite:///{tmp_path / 'm.db'}"
    engine = create_engine(url)

    old = MetaData()
    Table("widgets", old, Column("id", Integer, primary_key=True))
    old.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO widgets (id) VALUES (1)"))

    new = MetaData()
    Table("widgets", new, Column("id", Integer, primary_key=True),
          Column("flag", Boolean, nullable=False, default=False),
          Column("reason", String(16), nullable=False, default="initial"))

    added = add_missing_columns(engine, new)

    assert set(added) == {"widgets.flag", "widgets.reason"}
    with engine.begin() as conn:
        row = conn.execute(text("SELECT flag, reason FROM widgets")).one()
    # The pre-existing row gets the same value a new row would.
    assert row[0] == 0
    assert row[1] == "initial"


def test_a_json_column_defaulting_to_a_callable_is_added(tmp_path):
    """`default=dict` is a callable, which needs calling to get a literal."""
    from sqlalchemy import JSON, Integer

    url = f"sqlite:///{tmp_path / 'm.db'}"
    engine = create_engine(url)

    old = MetaData()
    Table("widgets", old, Column("id", Integer, primary_key=True))
    old.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO widgets (id) VALUES (1)"))

    new = MetaData()
    Table("widgets", new, Column("id", Integer, primary_key=True),
          Column("payload", JSON, nullable=False, default=dict),
          Column("items", JSON, nullable=False, default=list))

    assert set(add_missing_columns(engine, new)) == {"widgets.payload", "widgets.items"}
    with engine.begin() as conn:
        row = conn.execute(text("SELECT payload, items FROM widgets")).one()
    assert row[0] == "{}"
    assert row[1] == "[]"


def test_a_not_null_column_without_a_default_is_still_refused(tmp_path):
    """No honest value exists for the rows already there."""
    from sqlalchemy import Integer, String

    url = f"sqlite:///{tmp_path / 'm.db'}"
    engine = create_engine(url)

    old = MetaData()
    Table("widgets", old, Column("id", Integer, primary_key=True))
    old.create_all(engine)

    new = MetaData()
    Table("widgets", new, Column("id", Integer, primary_key=True),
          Column("required", String(16), nullable=False))

    assert add_missing_columns(engine, new) == []
    assert "required" not in {c["name"] for c in inspect(engine).get_columns("widgets")}


def test_the_v0_3_upgrade_path_works_on_a_populated_database(db):
    """The exact failure a live database hit: columns added in 0.3.1-0.3.3 were
    NOT NULL, so the migration refused them, and every later INSERT named a
    column the table did not have."""
    from sqlalchemy import inspect as sa_inspect

    from app.db import models
    from app.db.session import get_engine

    engine = get_engine()
    added_since_0_3_0 = [
        ("catalyst_scores", "scoring_inputs"),
        ("catalyst_scores", "revision_reason"),
        ("catalyst_scores", "superseded"),
        ("market_structure_snapshots", "data_provider"),
        ("reaction_analysis", "move_observable"),
        ("reaction_analysis", "data_delay_seconds"),
        ("scores", "scoring_inputs"),
        # 0.3.6 — the tape price at alert time, added for the lead-time view.
        ("catalyst_outcomes", "price_on_tape_at_alert"),
    ]
    with engine.begin() as conn:
        for table, column in added_since_0_3_0:
            conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))

    restored = add_missing_columns(engine, models.Base.metadata)

    assert set(restored) >= {f"{t}.{c}" for t, c in added_since_0_3_0}
    for table, column in added_since_0_3_0:
        present = {c["name"] for c in sa_inspect(engine).get_columns(table)}
        assert column in present, f"{table}.{column} was not restored"

    # And the insert that used to fail now succeeds.
    with db.db_session() as session:
        session.add(CatalystScore(event_id=1, model_version="1.0.0", revision=1))
        session.flush()
        row = session.query(CatalystScore).one()
    assert row.scoring_inputs == {}
    assert row.revision_reason == "initial"
    assert row.superseded is False
