"""Running on a 15-minute delayed price feed (Polygon Stocks Starter).

A delayed feed does not merely make the system slower — it makes a specific
lie available: the measured move reads 0%, which is indistinguishable from
"the stock has not moved" unless the system knows about the delay. These
tests pin the difference, and cover the re-score pass that resolves it.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.catalyst import amplification as amp
from app.catalyst.alerts import CatalystNotifier
from app.catalyst.enums import HaltState
from app.catalyst.pipeline import CatalystPipeline
from app.catalyst.reaction import AbnormalMove, assess_reaction_room
from app.catalyst.scoring import ScoringInputs
from app.config import Settings
from app.db.catalyst_models import CatalystScore, ReactionAnalysis
from app.domain.timeutil import UTC
from app.services.catalyst_market import CatalystMarketDataService
from app.services.delay_impact import assess_delay_impact
from app.services.marketdata import MarketDataService
from app.services.rescore import RescoreService
from tests.fakes import FakeNotifier
from tests.test_market_wiring import ScriptedMarket, _reset, article, seed

NOW = datetime(2026, 8, 27, 14, 30, tzinfo=UTC)
EVENT_AT = NOW - timedelta(minutes=8)          # news broke 8 minutes ago
DELAY = 900.0                                  # feed is 15 minutes behind


def settings(**overrides) -> Settings:
    base = dict(database_url="sqlite://", benchmark_ticker="SPY",
                market_data_delay_seconds=DELAY,
                catalyst_atr_days=14, catalyst_runup_lookback_days=10,
                min_entity_confidence=0.7, news_max_age_seconds=86400.0,
                catalyst_push_score=9.0, catalyst_min_confidence=6.0,
                rescore_window_hours=6)
    base.update(overrides)
    return Settings(**base)


class DelayedMarket(ScriptedMarket):
    """A feed that cannot show anything newer than `visible_through`."""

    def __init__(self, *, visible_through: datetime, **kwargs):
        super().__init__(**kwargs)
        self.visible_through = visible_through

    def bars(self, ticker, *, start, end, timespan="minute", multiplier=1, limit=5000):
        bars = super().bars(ticker, start=start, end=end, timespan=timespan,
                            multiplier=multiplier, limit=limit)
        return [b for b in bars if b.start_utc <= self.visible_through]

    def snapshot(self, ticker):
        """A delayed snapshot reports the last price the feed can see — which
        is the truth as of `visible_through`, not as of now."""
        snap = super().snapshot(ticker)
        visible = [b for b in self._series(self.stock_closes,
                                           EVENT_AT - timedelta(minutes=4))
                   if b.start_utc <= self.visible_through]
        snap.price = visible[-1].close if visible else self.stock_closes[0]
        # The newest print the feed can show. On a healthy delayed feed this is
        # exactly one delay behind now, which nets to zero excess staleness.
        snap.last_trade_at = self.visible_through
        return snap


def build(market, conf: Settings):
    service = CatalystMarketDataService(bars=market, structure=market, settings=conf,
                                        float_providers=[market])
    notifier = FakeNotifier()
    pipeline = CatalystPipeline(
        settings=conf, investigator=None, notifier=CatalystNotifier([notifier]),
        market_context_fn=service.as_context_fn())
    return pipeline, service, notifier


def spiked_market(visible_through: datetime) -> DelayedMarket:
    """The stock has actually run +60% since the news."""
    return DelayedMarket(visible_through=visible_through,
                         stock_closes=[10.0] * 4 + [16.0] * 9,
                         spy_closes=[500.0] * 13)


# ── the two traps ─────────────────────────────────────────────────────────────


def test_a_healthy_delayed_quote_is_not_mistaken_for_a_halt(db):
    """Every quote on a 15-minute plan is 15 minutes old. Measuring raw age
    would flag every single stock as halted and zero its execution quality."""
    conf = settings()
    market = spiked_market(NOW - timedelta(minutes=15))
    _, service, _ = build(market, conf)

    structure = service.context("ACME", NOW, event_at=EVENT_AT).structure

    assert structure.quote_stale_seconds == 0.0
    assert amp.assess_execution_quality(structure).tradeable is True


def test_a_genuine_halt_is_still_caught_on_a_delayed_feed(db):
    """Subtracting the delay must not blind us to real silence: a stock that
    has not printed for 25 minutes is 10 minutes stale on a 15-minute feed."""
    conf = settings()
    market = spiked_market(NOW - timedelta(minutes=15))
    market.snapshot = lambda ticker: _stale_snapshot(market, NOW - timedelta(minutes=25))
    _, service, _ = build(market, conf)

    structure = service.context("ACME", NOW, event_at=EVENT_AT).structure

    assert structure.quote_stale_seconds == pytest.approx(600.0)


def _stale_snapshot(market, last_trade_at):
    snap = ScriptedMarket.snapshot(market, "ACME")
    snap.last_trade_at = last_trade_at
    return snap


def test_an_invisible_move_is_never_scored_as_no_move(db):
    """The dangerous case. The stock has run 60%, the feed cannot show it, and
    the measured move is 0%. Treating that as 'untouched, all the room is
    still there' would produce a high score on a stock that has already gone."""
    conf = settings()
    market = spiked_market(NOW - timedelta(minutes=15))

    with db.db_session() as session:
        _reset(session)
        pipeline, _, _ = build(market, conf)
        seed(session)
        pipeline.process(session, article(), now=NOW)

        reaction = session.query(ReactionAnalysis).one()

    assert reaction.move_observable is False
    assert reaction.unresolved is True
    assert reaction.reaction_room_score == 5.0        # neutral, not optimistic
    assert "not visible yet" in reaction.notes


def test_reaction_room_refuses_to_score_an_unobservable_move():
    """Unit-level guard on the same trap, independent of the pipeline."""
    abnormal = AbnormalMove(raw_move_pct=0.0, abnormal_move_pct=0.0, move_multiple=0.0)

    optimistic = assess_reaction_room(abnormal=abnormal, analogue_expected_move_pct=24.0)
    honest = assess_reaction_room(abnormal=abnormal, analogue_expected_move_pct=24.0,
                                  move_observable=False, data_delay_seconds=DELAY)

    assert optimistic.score == 10.0 and optimistic.unresolved is False
    assert honest.unresolved is True
    assert honest.score == 5.0


def test_a_delayed_score_is_capped_rather_than_confident(db):
    conf = settings()
    with db.db_session() as session:
        _reset(session)
        pipeline, _, _ = build(spiked_market(NOW - timedelta(minutes=15)), conf)
        seed(session)
        result = pipeline.process(session, article(), now=NOW)
        score = session.query(CatalystScore).one()

    assert result.score is not None
    assert "price_current" in score.gates_failed
    assert score.upside_catalyst_score <= 8.4


def test_no_current_price_is_published_when_it_would_predate_the_news(db):
    """A 'current' price from before the disclosure would produce a 0% move
    that looks like a measurement rather than an absence."""
    conf = settings()
    _, service, _ = build(spiked_market(NOW - timedelta(minutes=15)), conf)

    context = service.context("ACME", NOW, event_at=EVENT_AT)

    assert context.move_observable is False
    assert context.price_now is None
    assert context.data_delay_seconds == DELAY


def test_a_real_time_feed_observes_the_move_immediately(db):
    """The upgrade path: one setting, and everything tightens."""
    conf = settings(market_data_delay_seconds=0.0)
    market = ScriptedMarket(stock_closes=[10.0] * 4 + [16.0] * 9, spy_closes=[500.0] * 13)
    _, service, _ = build(market, conf)

    context = service.context("ACME", NOW, event_at=EVENT_AT)

    assert context.move_observable is True
    assert context.price_now is not None


# ── the re-score pass ─────────────────────────────────────────────────────────


def test_the_move_is_scored_properly_once_the_data_arrives(db):
    """End to end: scored blind on arrival, then re-scored when the feed
    catches up — and the score falls, because the move has already gone."""
    conf = settings()
    with db.db_session() as session:
        _reset(session)
        seed(session)
        pipeline, _, _ = build(spiked_market(NOW - timedelta(minutes=15)), conf)
        first = pipeline.process(session, article(), now=NOW)

    later = NOW + timedelta(minutes=20)
    caught_up = spiked_market(later)                 # the feed can now see it all
    service = CatalystMarketDataService(bars=caught_up, structure=caught_up,
                                        settings=conf, float_providers=[caught_up])
    rescorer = RescoreService(settings=conf, notifier=CatalystNotifier([FakeNotifier()]),
                              market_context_fn=service.as_context_fn())

    with db.db_session() as session:
        result = rescorer.run(session, later)
        revisions = (session.query(CatalystScore)
                     .order_by(CatalystScore.revision.asc()).all())
        reaction = session.query(ReactionAnalysis).one()

    assert result.rescored == 1
    assert len(revisions) == 2
    assert revisions[0].superseded is True
    assert revisions[1].revision_reason == "delayed_data_arrived"
    assert reaction.move_observable is True
    assert reaction.rescored_at_utc is not None
    # The stock ran 60%; once visible, there is no room left.
    assert reaction.move_since_disclosure_pct == pytest.approx(60.0, abs=0.5)
    assert revisions[1].reaction_room < revisions[0].reaction_room
    assert revisions[1].upside_catalyst_score < first.score


def test_rescoring_does_not_call_claude_again(db):
    """Claude's judgement does not change because a price arrived. The stored
    inputs are reused, so a re-score costs no API spend."""
    conf = settings()
    with db.db_session() as session:
        _reset(session)
        seed(session)
        pipeline, _, _ = build(spiked_market(NOW - timedelta(minutes=15)), conf)
        pipeline.process(session, article(), now=NOW)

    later = NOW + timedelta(minutes=20)
    caught_up = spiked_market(later)
    service = CatalystMarketDataService(bars=caught_up, structure=caught_up,
                                        settings=conf, float_providers=[caught_up])

    class ExplodingInvestigator:
        deep_model = "must-not-be-called"

        def investigate(self, evidence):
            raise AssertionError("re-scoring must not call the LLM")

    rescorer = RescoreService(settings=conf, notifier=CatalystNotifier([FakeNotifier()]),
                              market_context_fn=service.as_context_fn())
    # RescoreService has no investigator at all — this asserts the design, and
    # the run below would fail loudly if that ever changed.
    assert not hasattr(rescorer, "_investigator")

    with db.db_session() as session:
        assert rescorer.run(session, later).rescored == 1


def test_an_event_still_inside_the_delay_window_waits(db):
    conf = settings()
    with db.db_session() as session:
        _reset(session)
        seed(session)
        pipeline, _, _ = build(spiked_market(NOW - timedelta(minutes=15)), conf)
        pipeline.process(session, article(), now=NOW)

    market = spiked_market(NOW - timedelta(minutes=13))
    service = CatalystMarketDataService(bars=market, structure=market, settings=conf,
                                        float_providers=[market])
    rescorer = RescoreService(settings=conf, notifier=CatalystNotifier([FakeNotifier()]),
                              market_context_fn=service.as_context_fn())

    with db.db_session() as session:
        # Two minutes later the disclosure is still newer than the feed can show.
        result = rescorer.run(session, NOW + timedelta(minutes=2))

    assert result.rescored == 0
    assert result.still_waiting == 1


def test_rescoring_is_idempotent(db):
    conf = settings()
    with db.db_session() as session:
        _reset(session)
        seed(session)
        pipeline, _, _ = build(spiked_market(NOW - timedelta(minutes=15)), conf)
        pipeline.process(session, article(), now=NOW)

    later = NOW + timedelta(minutes=20)
    caught_up = spiked_market(later)
    service = CatalystMarketDataService(bars=caught_up, structure=caught_up,
                                        settings=conf, float_providers=[caught_up])
    rescorer = RescoreService(settings=conf, notifier=CatalystNotifier([FakeNotifier()]),
                              market_context_fn=service.as_context_fn())

    with db.db_session() as session:
        rescorer.run(session, later)
        second = rescorer.run(session, later + timedelta(minutes=5))
        assert session.query(CatalystScore).count() == 2

    assert second.rescored == 0


def test_a_real_time_feed_has_nothing_to_rescore(db):
    conf = settings(market_data_delay_seconds=0.0)
    market = ScriptedMarket(stock_closes=[10.0] * 4 + [16.0] * 9, spy_closes=[500.0] * 13)
    service = CatalystMarketDataService(bars=market, structure=market, settings=conf,
                                        float_providers=[market])
    with db.db_session() as session:
        _reset(session)
        seed(session)
        pipeline, _, _ = build(market, conf)
        pipeline.process(session, article(), now=NOW)

        rescorer = RescoreService(settings=conf,
                                  notifier=CatalystNotifier([FakeNotifier()]),
                                  market_context_fn=service.as_context_fn())
        result = rescorer.run(session, NOW + timedelta(minutes=20))

    assert result.considered == 0
    assert result.rescored == 0


def test_scoring_inputs_survive_a_round_trip():
    """Re-scoring depends on rebuilding the inputs exactly; enums included."""
    original = ScoringInputs(materiality_score=7.5, negative_offset_severity=3.2,
                             llm_event_quality=8.0, claude_available=False,
                             materiality_missing=["annual_revenue"])
    restored = ScoringInputs.from_dict(original.to_dict())

    assert restored == original


def test_unknown_stored_fields_do_not_break_a_newer_scorer():
    """An old row written by a previous version must not crash the rebuild."""
    data = ScoringInputs().to_dict()
    data["a_field_that_no_longer_exists"] = 42

    assert ScoringInputs.from_dict(data) == ScoringInputs()


# ── earnings pipeline, same trap ──────────────────────────────────────────────


def test_earnings_reaction_is_withheld_inside_the_delay_window():
    """A quote taken 2 minutes after a release on a 15-minute feed still shows
    the pre-release price — recording that as a 0% reaction would be logged as
    the market declining to confirm a good report."""
    from app.services.marketdata import MarketContextData

    service = MarketDataService([], conflict_threshold_pct=5.0, data_delay_seconds=DELAY)
    ctx = MarketContextData(pre_release_price=100.0, prev_close=99.0)

    result = service.capture_reaction("ACME", ctx, minutes_after=2)

    assert result.unresolved is True
    assert result.current_reaction_pct is None
    assert "not visible yet" in result.notes[-1]


def test_earnings_reaction_is_measured_once_past_the_delay():
    from app.providers.base import Quote
    from app.services.marketdata import MarketContextData

    class Feed:
        name = "feed"

        def quote(self, ticker):
            return Quote(ticker=ticker, price=112.0, prev_close=99.0)

    service = MarketDataService([Feed()], conflict_threshold_pct=5.0,
                                data_delay_seconds=DELAY)
    ctx = MarketContextData(pre_release_price=100.0, prev_close=99.0)

    result = service.capture_reaction("ACME", ctx, minutes_after=20)

    assert result.unresolved is False
    assert result.current_reaction_pct == pytest.approx(12.0)


def test_a_real_time_feed_measures_the_reaction_at_once():
    from app.providers.base import Quote
    from app.services.marketdata import MarketContextData

    class Feed:
        name = "feed"

        def quote(self, ticker):
            return Quote(ticker=ticker, price=112.0, prev_close=99.0)

    service = MarketDataService([Feed()], conflict_threshold_pct=5.0,
                                data_delay_seconds=0.0)
    ctx = MarketContextData(pre_release_price=100.0, prev_close=99.0)

    assert service.capture_reaction("ACME", ctx, minutes_after=2).unresolved is False


# ── delay impact reporting ────────────────────────────────────────────────────


def test_delay_impact_is_honest_about_a_tiny_sample(db):
    conf = settings()
    with db.db_session() as session:
        _reset(session)
        seed(session)
        pipeline, _, _ = build(spiked_market(NOW - timedelta(minutes=15)), conf)
        pipeline.process(session, article(), now=NOW)
        impact = assess_delay_impact(session, conf)

    assert impact.delay_minutes == 15.0
    assert impact.scored_blind == 1
    assert impact.rescored == 0
    assert "nothing to judge" in impact.verdict


def test_delay_impact_records_a_move_that_had_already_gone(db):
    conf = settings()
    with db.db_session() as session:
        _reset(session)
        seed(session)
        pipeline, _, _ = build(spiked_market(NOW - timedelta(minutes=15)), conf)
        pipeline.process(session, article(), now=NOW)

    later = NOW + timedelta(minutes=20)
    caught_up = spiked_market(later)
    service = CatalystMarketDataService(bars=caught_up, structure=caught_up,
                                        settings=conf, float_providers=[caught_up])
    rescorer = RescoreService(settings=conf, notifier=CatalystNotifier([FakeNotifier()]),
                              market_context_fn=service.as_context_fn())

    with db.db_session() as session:
        rescorer.run(session, later)
        impact = assess_delay_impact(session, conf)

    assert impact.rescored == 1
    assert impact.move_already_gone == 1
    assert impact.examples and impact.examples[0]["ticker"] == "ACME"
    assert "anecdote" in impact.verdict          # one event proves nothing


def test_delay_impact_on_a_real_time_feed_says_there_is_nothing_to_measure(db):
    with db.db_session() as session:
        impact = assess_delay_impact(session, settings(market_data_delay_seconds=0.0))

    assert impact.delay_minutes == 0.0
    assert "Real-time feed" in impact.verdict


def test_halt_still_beats_the_delay_logic():
    """A declared halt is unresolved regardless of what the feed can show."""
    abnormal = AbnormalMove(raw_move_pct=5.0, abnormal_move_pct=5.0, move_multiple=1.0)
    room = assess_reaction_room(abnormal=abnormal, analogue_expected_move_pct=20.0,
                                halt_state=HaltState.NEWS_PENDING)
    assert room.unresolved is True
