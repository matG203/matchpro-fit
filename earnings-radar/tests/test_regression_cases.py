"""The six regression cases from the specification, end to end.

CASE 1  IR page stale but Business Wire has the results  → RELEASE DETECTED
CASE 2  Great report, +11% pre-run, -8% after            → final < earnings quality
CASE 3  Huge EPS from a tax benefit                      → no operating-quality credit
CASE 4  AI contract announced a month earlier            → previously known, not double-counted
CASE 5  One price feed flat, another +20%                → unresolved, verify
CASE 6  Consensus providers disagree significantly       → do not pick the friendliest
"""
from __future__ import annotations

from datetime import timedelta

from app.config import Settings
from app.db.models import Company, EarningsEvent, Release
from app.domain.enums import EventState, GuidanceStatus
from app.domain.schemas import AnalysisOutput, FactCheck
from app.domain.timeutil import utcnow
from app.providers.base import EstimateDTO
from app.services.expectations import build_expectations, surprise_pct_vs_band
from app.services.marketdata import MarketDataService
from app.services.monitor import ReleaseMonitorService
from app.services.notification import NotificationService
from app.services.pipeline import EarningsPipeline
from app.services.scoring import ScoringInputs, compute_scores
from tests.fakes import (
    FakeFilings,
    FakeNewswire,
    FakeNotifier,
    FakePrice,
    filing_hit,
    news_item,
)

TICKER = "ESTC"
DOC_URL = "https://businesswire.test/estc-q2-results"

RESULTS_DOC = """
Elastic N.V. (NYSE: ESTC) Reports Second Quarter Fiscal 2026 Financial Results
Total revenue of $1.16 billion, up 20% year over year. GAAP diluted earnings
per share of $0.21. Non-GAAP diluted earnings per share of $0.59.
Gross margin of 76.4%. Net cash provided by operating activities of $88.2
million. For the three months ended July 31, 2026, the Company reported record
results and raised full-year guidance.
"""


def settings(**overrides) -> Settings:
    base = dict(database_url="sqlite://", min_notification_score=0.0,
                min_confidence_for_notification=75.0)
    base.update(overrides)
    return Settings(**base)


def make_event(session, *, ticker: str = TICKER, fy: int = 2026, fq: int = 2,
               state: EventState = EventState.MONITORING) -> EarningsEvent:
    company = Company(ticker=ticker, name="Elastic N.V.", cik="0001707753",
                      market_cap=12e9)
    session.add(company)
    session.flush()
    event = EarningsEvent(
        company_id=company.id, fiscal_year=fy, fiscal_quarter=fq,
        expected_release_at=utcnow() - timedelta(minutes=1),
        window_start=utcnow() - timedelta(hours=2),
        window_end=utcnow() + timedelta(hours=2),
        state=state.value, schedule_confidence="MEDIUM")
    session.add(event)
    session.flush()
    return event


def build_pipeline(*, filings, newswires, prices, notifier, analysis=None,
                   conf=settings()) -> tuple[EarningsPipeline, FakeNotifier]:
    monitor = ReleaseMonitorService(filings=filings, newswires=newswires)
    market = MarketDataService(prices, conflict_threshold_pct=conf.price_conflict_pct)
    notifications = NotificationService(
        [notifier], min_score=conf.min_notification_score,
        high_score_alert=conf.high_score_alert,
        min_confidence=conf.min_confidence_for_notification)
    pipeline = EarningsPipeline(settings=conf, monitor=monitor, filings=filings,
                                market=market, analysis=analysis,
                                notifications=notifications)
    return pipeline, notifier


class StubAnalysis:
    """Stands in for the Claude call with a fixed, schema-valid result."""

    def __init__(self, output: AnalysisOutput):
        self._output = output
        self.evidence = None

    def build_evidence(self, **kwargs):
        self.evidence = kwargs
        return kwargs

    def analyse(self, evidence):
        return self._output

    @staticmethod
    def fact_mismatch(parsed, extraction, tolerance_pct: float = 2.0) -> bool:
        from app.services.analysis import EarningsAnalysisService
        return EarningsAnalysisService.fact_mismatch(parsed, extraction, tolerance_pct)


def analysis_output(**overrides) -> AnalysisOutput:
    base = dict(
        ticker=TICKER, earnings_quality=9.4, guidance_score=9.0,
        business_kpi_score=9.0, true_surprise_score=8.5,
        guidance_status=GuidanceStatus.RAISED, organic_guidance_change=True,
        growth_direction="ACCELERATING", pre_announced_news=[], positives=["strong revenue"],
        negatives=[], hidden_negatives=[], one_off_items=[],
        eps_dominated_by_one_offs=False, bull_case="Beat and raise",
        bear_case="Valuation", reasoning_summary="Strong quarter",
        facts=FactCheck(eps_actual=0.59, revenue_actual=1.16e9),
        confidence=94, verdict="STRONG_BEAT_AND_RAISE")
    base.update(overrides)
    return AnalysisOutput(**base)


# ── CASE 1 ───────────────────────────────────────────────────────────────────

def test_case1_stale_ir_page_but_newswire_has_results(db):
    """IR/SEC silent, Business Wire carries the release → still detected."""
    filings = FakeFilings(hits=[], documents={DOC_URL: RESULTS_DOC})
    newswire = FakeNewswire(items=[news_item(
        TICKER, "Elastic Reports Second Quarter Fiscal 2026 Financial Results", DOC_URL)])
    notifier = FakeNotifier()
    pipeline, notifier = build_pipeline(filings=filings, newswires=[newswire],
                                        prices=[FakePrice("p1", [110.0], prev_close=100.0)],
                                        notifier=notifier,
                                        analysis=StubAnalysis(analysis_output()))

    with db.db_session() as session:
        event = make_event(session)
        attempt = pipeline.monitor.check(ticker=TICKER, company_name="Elastic N.V.",
                                         cik="0001707753",
                                         since=utcnow() - timedelta(hours=2))
        assert attempt.found, "release must be detected from the newswire alone"
        result = pipeline.process_detection(session, event, attempt.candidates)

        release = session.get(Release, result.release_id)
        assert release.verified is True
        assert release.primary_url == DOC_URL
        assert event.state == EventState.NOTIFIED.value
        assert notifier.sent, "a push must be sent"


def test_case1_scheduling_notice_alone_is_not_a_release(db):
    """A 'we will report on X' notice must NOT count as a release."""
    notice_url = "https://businesswire.test/estc-date-announcement"
    filings = FakeFilings(hits=[], documents={notice_url: (
        "Elastic Announces Date of Second Quarter Fiscal 2026 Financial Results. "
        "Elastic today announced that it will report financial results for its "
        "second quarter after market close on August 27, 2026, and invites you to "
        "join the conference call.")})
    newswire = FakeNewswire(items=[news_item(
        TICKER, "Elastic Announces Date of Q2 Fiscal 2026 Financial Results",
        notice_url)])
    pipeline, notifier = build_pipeline(
        filings=filings, newswires=[newswire],
        prices=[FakePrice("p1", [100.0], prev_close=100.0)], notifier=FakeNotifier())

    with db.db_session() as session:
        event = make_event(session)
        attempt = pipeline.monitor.check(ticker=TICKER, company_name="Elastic N.V.",
                                         cik=None, since=utcnow() - timedelta(hours=2))
        # The headline filter already rejects "Announces Date of ..."
        if attempt.found:
            result = pipeline.process_detection(session, event, attempt.candidates)
            assert result.detail == "not_yet_verified"
        assert event.state != EventState.NOTIFIED.value
        assert not notifier.sent


def test_case1_same_release_from_three_sources_is_analysed_once(db):
    """SEC + Business Wire + IR for one quarter → one release, one push."""
    sec_url = "https://sec.test/estc-8k"
    filings = FakeFilings(hits=[filing_hit(TICKER, sec_url)],
                          documents={sec_url: RESULTS_DOC, DOC_URL: RESULTS_DOC})
    newswire = FakeNewswire(items=[news_item(
        TICKER, "Elastic Reports Second Quarter Fiscal 2026 Results", DOC_URL)])
    pipeline, notifier = build_pipeline(
        filings=filings, newswires=[newswire],
        prices=[FakePrice("p1", [110.0], prev_close=100.0)], notifier=FakeNotifier(),
        analysis=StubAnalysis(analysis_output()))

    with db.db_session() as session:
        event = make_event(session)
        attempt = pipeline.monitor.check(ticker=TICKER, company_name="Elastic N.V.",
                                         cik="0001707753",
                                         since=utcnow() - timedelta(hours=2))
        assert len(attempt.candidates) >= 2, "multiple sources should be seen"
        first = pipeline.process_detection(session, event, attempt.candidates)
        second = pipeline.process_detection(session, event, attempt.candidates)

        assert first.release_id == second.release_id
        assert second.detail == "duplicate"
        assert session.query(Release).count() == 1
        assert len(notifier.sent) == 1, "exactly one push per canonical release"
        release = session.get(Release, first.release_id)
        assert len(release.source_rows) >= 2, "all source URLs recorded on one release"


# ── CASE 2 ───────────────────────────────────────────────────────────────────

def test_case2_pre_run_then_selloff_scores_below_earnings_quality():
    """Report is excellent, stock rose 11% into it and falls 8% after."""
    inputs = ScoringInputs(
        llm_earnings_quality=9.4, llm_guidance_score=9.0, llm_business_kpi_score=9.0,
        llm_true_surprise_score=8.0, llm_confidence=92,
        guidance_status=GuidanceStatus.RAISED, organic_guidance_change=True,
        eps_surprise_pct=15.0, revenue_surprise_pct=4.0, estimate_confidence="HIGH",
        reaction_pct=-8.0, reaction_vs_prev_close_pct=2.0, pre_run_1m_pct=11.0,
        release_source_quality=1.0, kpi_completeness=1.0)
    result = compute_scores(inputs)

    assert result.final_trade_score < result.earnings_quality
    assert result.final_trade_score < 9.0
    assert result.score_review is True, "great report + falling stock must trigger review"
    assert "material post-release decline" in result.vetoes_applied


def test_case2_still_above_yesterdays_close_is_not_treated_as_rejection():
    """Down after hours but above yesterday's close — the dual baseline."""
    common = dict(
        llm_earnings_quality=9.0, llm_guidance_score=8.5, llm_business_kpi_score=8.5,
        llm_true_surprise_score=8.0, llm_confidence=90,
        guidance_status=GuidanceStatus.RAISED, estimate_confidence="HIGH",
        reaction_pct=-4.0, pre_run_1m_pct=5.0)
    above = compute_scores(ScoringInputs(reaction_vs_prev_close_pct=3.0, **common))
    below = compute_scores(ScoringInputs(reaction_vs_prev_close_pct=-9.0, **common))
    assert above.final_trade_score > below.final_trade_score


# ── CASE 3 ───────────────────────────────────────────────────────────────────

def test_case3_one_off_tax_benefit_gets_no_operating_quality_credit():
    """Huge GAAP EPS driven by a tax valuation allowance release."""
    common = dict(
        llm_guidance_score=6.0, llm_business_kpi_score=6.0, llm_true_surprise_score=6.0,
        llm_confidence=88, guidance_status=GuidanceStatus.MAINTAINED,
        eps_surprise_pct=300.0, revenue_surprise_pct=0.5, estimate_confidence="HIGH",
        reaction_pct=2.0, release_source_quality=1.0, kpi_completeness=1.0)
    one_off = compute_scores(ScoringInputs(
        llm_earnings_quality=6.0, eps_dominated_by_one_offs=True, **common))
    clean = compute_scores(ScoringInputs(
        llm_earnings_quality=6.0, eps_dominated_by_one_offs=False, **common))

    assert one_off.final_trade_score < clean.final_trade_score
    assert one_off.final_trade_score < 9.0
    assert "earnings dominated by one-off accounting items" in one_off.vetoes_applied


def test_case3_massive_eps_surprise_alone_cannot_reach_nine():
    result = compute_scores(ScoringInputs(
        llm_earnings_quality=6.5, llm_guidance_score=5.5, llm_business_kpi_score=5.5,
        llm_true_surprise_score=5.0, llm_confidence=85,
        guidance_status=GuidanceStatus.MAINTAINED, eps_dominated_by_one_offs=True,
        eps_surprise_pct=500.0, revenue_surprise_pct=0.2, estimate_confidence="HIGH",
        reaction_pct=1.0))
    assert result.final_trade_score < 9.0


# ── CASE 4 ───────────────────────────────────────────────────────────────────

def test_case4_previously_known_news_does_not_earn_full_surprise_credit(db):
    """AI contracts announced a month earlier are tagged, not double-counted."""
    known = analysis_output(
        pre_announced_news=["$4bn AI ARR contracts originally announced July 20"],
        true_surprise_score=5.0)
    fresh = analysis_output(pre_announced_news=[], true_surprise_score=9.0)

    def score_for(output: AnalysisOutput) -> float:
        return compute_scores(ScoringInputs(
            llm_earnings_quality=output.earnings_quality,
            llm_guidance_score=output.guidance_score,
            llm_business_kpi_score=output.business_kpi_score,
            llm_true_surprise_score=output.true_surprise_score,
            llm_confidence=output.confidence,
            guidance_status=output.guidance_status, organic_guidance_change=True,
            eps_surprise_pct=12.0, revenue_surprise_pct=4.0,
            estimate_confidence="HIGH", reaction_pct=6.0,
            release_source_quality=1.0, kpi_completeness=1.0)).final_trade_score

    assert score_for(known) < score_for(fresh)

    # And the tag is persisted for the dashboard.
    filings = FakeFilings(hits=[], documents={DOC_URL: RESULTS_DOC})
    newswire = FakeNewswire(items=[news_item(TICKER, "Elastic Reports Q2 Results", DOC_URL)])
    pipeline, _ = build_pipeline(filings=filings, newswires=[newswire],
                                 prices=[FakePrice("p1", [106.0], prev_close=100.0)],
                                 notifier=FakeNotifier(), analysis=StubAnalysis(known))
    with db.db_session() as session:
        event = make_event(session)
        attempt = pipeline.monitor.check(ticker=TICKER, company_name="Elastic N.V.",
                                         cik=None, since=utcnow() - timedelta(hours=2))
        result = pipeline.process_detection(session, event, attempt.candidates)
        from app.db.models import Analysis
        stored = session.query(Analysis).filter_by(release_id=result.release_id).first()
        assert stored.pre_announced == known.pre_announced_news


def test_case4_organic_vs_acquisition_driven_guidance_raise():
    """A raise mostly funded by an acquisition is not a full-credit raise."""
    common = dict(
        llm_earnings_quality=8.5, llm_guidance_score=8.5, llm_business_kpi_score=8.0,
        llm_true_surprise_score=8.0, llm_confidence=90,
        guidance_status=GuidanceStatus.RAISED, eps_surprise_pct=8.0,
        revenue_surprise_pct=3.0, estimate_confidence="HIGH", reaction_pct=5.0)
    organic = compute_scores(ScoringInputs(organic_guidance_change=True, **common))
    acquired = compute_scores(ScoringInputs(organic_guidance_change=False, **common))
    assert acquired.final_trade_score < organic.final_trade_score


# ── CASE 5 ───────────────────────────────────────────────────────────────────

def test_case5_conflicting_price_feeds_mark_market_data_unresolved():
    """One provider says flat, another says +20% → do not score confirmation."""
    flat = FakePrice("provider_a", [100.0], prev_close=100.0)
    spiking = FakePrice("provider_b", [120.0], prev_close=100.0)
    market = MarketDataService([flat, spiking], conflict_threshold_pct=5.0)

    ctx = market.pre_earnings_context(TICKER)
    ctx.pre_release_price = 100.0
    ctx = market.capture_reaction(TICKER, ctx, minutes_after=1.0)

    assert ctx.unresolved is True
    assert "conflict" in ctx.notes[-1]
    assert ctx.current_reaction_pct is None, "no reaction is recorded while unresolved"


def test_case5_unresolved_market_data_withholds_confirmation_and_caps_score():
    result = compute_scores(ScoringInputs(
        llm_earnings_quality=9.3, llm_guidance_score=9.0, llm_business_kpi_score=9.0,
        llm_true_surprise_score=8.5, llm_confidence=90,
        guidance_status=GuidanceStatus.RAISED, organic_guidance_change=True,
        eps_surprise_pct=15.0, revenue_surprise_pct=5.0, estimate_confidence="HIGH",
        market_data_unresolved=True, reaction_pct=None))
    assert result.market_confirmation == 5.0, "neutral, not bullish"
    assert result.final_trade_score < 9.0
    assert "contradictory/unavailable live price feeds" in result.vetoes_applied


def test_case5_agreeing_providers_resolve_normally():
    a = FakePrice("provider_a", [108.0], prev_close=100.0)
    b = FakePrice("provider_b", [108.4], prev_close=100.0)
    market = MarketDataService([a, b], conflict_threshold_pct=5.0)
    ctx = market.pre_earnings_context(TICKER)
    ctx.pre_release_price = 100.0
    ctx = market.capture_reaction(TICKER, ctx, minutes_after=1.0)
    assert ctx.unresolved is False
    assert round(ctx.current_reaction_pct, 1) == 8.0


# ── CASE 6 ───────────────────────────────────────────────────────────────────

def test_case6_disagreeing_consensus_is_not_resolved_favourably():
    """Providers say $1.10bn / $1.14bn, actual $1.16bn → 1.8%, not 5.5%."""
    exp = build_expectations([
        EstimateDTO("revenue", "current", 1.10e9, "finnhub"),
        EstimateDTO("revenue", "current", 1.14e9, "fmp"),
    ])
    conservative, favourable = surprise_pct_vs_band(1.16e9, exp.bands["revenue"])

    assert exp.bands["revenue"].disagreement is True
    assert round(conservative, 1) == 1.8
    assert round(favourable, 1) == 5.5

    scored_conservatively = compute_scores(ScoringInputs(
        revenue_surprise_pct=conservative, estimate_confidence=exp.estimate_confidence,
        consensus_disagreement=True, llm_earnings_quality=8.0, llm_guidance_score=8.0,
        llm_business_kpi_score=8.0, llm_true_surprise_score=7.5, llm_confidence=85,
        guidance_status=GuidanceStatus.RAISED, reaction_pct=5.0))
    scored_favourably = compute_scores(ScoringInputs(
        revenue_surprise_pct=favourable, estimate_confidence="HIGH",
        consensus_disagreement=False, llm_earnings_quality=8.0, llm_guidance_score=8.0,
        llm_business_kpi_score=8.0, llm_true_surprise_score=7.5, llm_confidence=85,
        guidance_status=GuidanceStatus.RAISED, reaction_pct=5.0))

    assert scored_conservatively.final_trade_score < scored_favourably.final_trade_score
    assert "low-confidence consensus" in scored_conservatively.vetoes_applied
    assert scored_conservatively.analysis_confidence < scored_favourably.analysis_confidence
