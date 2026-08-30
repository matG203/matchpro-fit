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


# ── earnings: the release lands after the close ───────────────────────────────


def test_an_amc_release_is_rescored_once_the_after_hours_print_arrives(db):
    """The decisive case. A US release lands 16:05 ET = 21:05 UK and the whole
    reaction happens after hours. On a 15-minute feed nothing is visible at
    scoring time, so the release takes the unavailable-prices veto. Without a
    re-score pass that veto is permanent and no report can ever reach 9+."""
    from app.db.models import Company, EarningsEvent, MarketContext, Release, Score
    from app.domain.enums import GuidanceStatus, ReactionPattern
    from app.providers.base import Quote
    from app.services.marketdata import MarketDataService
    from app.services.notification import NotificationService
    from app.services.rescore import EarningsRescoreService
    from app.services.scoring import ScoringInputs as EarningsInputs
    from app.services.scoring import compute_scores

    release_at = NOW - timedelta(minutes=20)        # 15-min feed has caught up
    conf = settings(min_notification_score=0.0, high_score_alert=9.0,
                    min_confidence_for_notification=75.0)

    # An excellent report, scored while the reaction was still invisible.
    blind = EarningsInputs(
        llm_earnings_quality=10.0, llm_guidance_score=10.0,
        llm_business_kpi_score=10.0, llm_true_surprise_score=10.0,
        llm_confidence=100.0, guidance_status=GuidanceStatus.RAISED,
        organic_guidance_change=True, eps_surprise_pct=40.0,
        revenue_surprise_pct=15.0, estimate_confidence="HIGH",
        release_source_quality=1.0, kpi_completeness=1.0,
        reaction_pattern=ReactionPattern.UNRESOLVED, market_data_unresolved=True)
    first = compute_scores(blind)

    with db.db_session() as session:
        company = Company(ticker="ESTC", name="Elastic NV", cik="0000012346")
        session.add(company); session.flush()
        event = EarningsEvent(company_id=company.id, fiscal_year=2026, fiscal_quarter=2,
                              state="SCORED")
        session.add(event); session.flush()
        release = Release(event_id=event.id, canonical_key="ESTC|FY2026|Q2",
                          published_at_utc=release_at, document_type="8-K",
                          verified=True)
        session.add(release); session.flush()
        session.add(MarketContext(event_id=event.id, prev_close=99.0,
                                  pre_release_price=100.0, unresolved=True))
        session.add(Score(release_id=release.id,
                          scoring_model_version=first.scoring_model_version,
                          earnings_quality=first.earnings_quality,
                          market_confirmation=first.market_confirmation,
                          entry_score=first.entry_score,
                          final_trade_score=first.final_trade_score,
                          component_breakdown=first.component_breakdown,
                          vetoes_applied=first.vetoes_applied,
                          analysis_confidence=first.analysis_confidence,
                          scoring_inputs=blind.to_dict()))
        session.flush()

        assert first.final_trade_score <= 8.9, "the veto must cap the blind score"
        assert "contradictory/unavailable live price feeds" in first.vetoes_applied

        # The after-hours print is now visible: +9% on the release.
        class Feed:
            name = "feed"

            def quote(self, ticker):
                return Quote(ticker=ticker, price=109.0, prev_close=99.0)

        notifications = NotificationService([], min_score=0.0, high_score_alert=9.0,
                                            min_confidence=75.0)
        service = EarningsRescoreService(
            settings=conf,
            market=MarketDataService([Feed()], conflict_threshold_pct=5.0,
                                     data_delay_seconds=DELAY),
            notifications=notifications)

        result = service.run(session, NOW)
        row = session.query(Score).one()
        context = session.query(MarketContext).one()

    assert result.rescored == 1
    assert row.score_before_rescore == first.final_trade_score
    assert row.final_trade_score > first.final_trade_score
    assert row.final_trade_score >= 9.0, "9+ must become reachable once priced"
    assert "contradictory/unavailable live price feeds" not in row.vetoes_applied
    assert row.market_confirmation > 5.0
    assert context.current_reaction_pct == pytest.approx(9.0)
    assert row.rescored_at is not None


def test_an_amc_release_still_inside_the_delay_window_waits(db):
    from app.db.models import Company, EarningsEvent, MarketContext, Release, Score
    from app.services.marketdata import MarketDataService
    from app.services.notification import NotificationService
    from app.services.rescore import EarningsRescoreService
    from app.services.scoring import ScoringInputs as EarningsInputs

    conf = settings()
    blind = EarningsInputs(market_data_unresolved=True, llm_earnings_quality=9.0)

    with db.db_session() as session:
        company = Company(ticker="ESTC", name="Elastic NV")
        session.add(company); session.flush()
        event = EarningsEvent(company_id=company.id, fiscal_year=2026,
                              fiscal_quarter=2, state="SCORED")
        session.add(event); session.flush()
        release = Release(event_id=event.id, canonical_key="ESTC|FY2026|Q2",
                          published_at_utc=NOW - timedelta(minutes=4),
                          document_type="8-K", verified=True)
        session.add(release); session.flush()
        session.add(MarketContext(event_id=event.id, prev_close=99.0,
                                  pre_release_price=100.0, unresolved=True))
        session.add(Score(release_id=release.id, scoring_model_version="1.0.0",
                          earnings_quality=9.0, market_confirmation=5.0,
                          entry_score=5.0, final_trade_score=8.3,
                          scoring_inputs=blind.to_dict()))
        session.flush()

        service = EarningsRescoreService(
            settings=conf,
            market=MarketDataService([], conflict_threshold_pct=5.0,
                                     data_delay_seconds=DELAY),
            notifications=NotificationService([], min_score=0.0,
                                              high_score_alert=9.0, min_confidence=75.0))
        result = service.run(session, NOW)
        row = session.query(Score).one()

    assert result.rescored == 0
    assert result.still_waiting == 1
    assert row.rescored_at is None          # left for a later pass
    assert row.final_trade_score == 8.3


def test_a_release_already_measured_is_not_revisited(db):
    from app.db.models import Company, EarningsEvent, MarketContext, Release, Score
    from app.services.marketdata import MarketDataService
    from app.services.notification import NotificationService
    from app.services.rescore import EarningsRescoreService
    from app.services.scoring import ScoringInputs as EarningsInputs

    measured = EarningsInputs(reaction_pct=6.0, market_data_unresolved=False)

    with db.db_session() as session:
        company = Company(ticker="ESTC", name="Elastic NV")
        session.add(company); session.flush()
        event = EarningsEvent(company_id=company.id, fiscal_year=2026,
                              fiscal_quarter=2, state="SCORED")
        session.add(event); session.flush()
        release = Release(event_id=event.id, canonical_key="ESTC|FY2026|Q2",
                          published_at_utc=NOW - timedelta(minutes=30),
                          document_type="8-K", verified=True)
        session.add(release); session.flush()
        session.add(MarketContext(event_id=event.id, prev_close=99.0,
                                  pre_release_price=100.0))
        session.add(Score(release_id=release.id, scoring_model_version="1.0.0",
                          earnings_quality=9.0, market_confirmation=8.0,
                          entry_score=7.0, final_trade_score=8.6,
                          scoring_inputs=measured.to_dict()))
        session.flush()

        service = EarningsRescoreService(
            settings=settings(),
            market=MarketDataService([], conflict_threshold_pct=5.0,
                                     data_delay_seconds=DELAY),
            notifications=NotificationService([], min_score=0.0,
                                              high_score_alert=9.0, min_confidence=75.0))
        result = service.run(session, NOW)

    assert result.considered == 0
    assert result.rescored == 0


def test_earnings_scoring_inputs_survive_a_round_trip():
    from app.domain.enums import GuidanceStatus, ReactionPattern
    from app.services.scoring import ScoringInputs as EarningsInputs

    original = EarningsInputs(llm_earnings_quality=9.0,
                              guidance_status=GuidanceStatus.RAISED,
                              reaction_pattern=ReactionPattern.POST_EARNINGS_MOMENTUM,
                              eps_surprise_pct=12.0, market_data_unresolved=True)
    assert EarningsInputs.from_dict(original.to_dict()) == original


def test_a_rescore_can_notify_again_only_when_it_crosses_a_band():
    from app.services.notification import NotificationService

    service = NotificationService([], min_score=7.0, high_score_alert=9.0,
                                  min_confidence=75.0)
    assert service.band(6.0) == "below"
    assert service.band(8.3) == "normal"
    assert service.band(9.2) == "high"
    assert service.band(9.2, needs_verification=True) == "normal"
