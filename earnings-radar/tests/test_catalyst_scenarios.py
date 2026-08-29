"""End-to-end Catalyst Sentinel scenarios (spec §102-108).

These run the real pipeline against a mock news feed with injected market data,
so every stage — ingest, resolution, clustering, novelty, classification,
materiality, offsets, reaction room, amplification, scoring, alerting —
executes for real. Only the LLM and network providers are stubbed.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.catalyst.alerts import CatalystNotifier
from app.catalyst.amplification import MarketStructure
from app.catalyst.enums import CatalystState, EventType, HaltState, RejectReason, SourceTier
from app.catalyst.materiality import CompanyFinancials
from app.catalyst.pipeline import CatalystPipeline, MarketContextInputs
from app.catalyst.schemas import DeepInvestigation, NegativeOffset
from app.config import Settings
from app.db.catalyst_models import (
    CatalystEvent,
    CatalystScore,
    EventCluster,
    NegativeOffsetRow,
    NewsItem,
)
from app.db.models import Company, EarningsEvent
from app.domain.timeutil import UTC
from app.providers.news import NewsArticle
from tests.fakes import FakeNotifier

NOW = datetime(2026, 8, 27, 14, 30, tzinfo=UTC)


def settings(**overrides) -> Settings:
    base = dict(database_url="sqlite://", catalyst_push_score=9.0,
                catalyst_extreme_score=9.5, catalyst_min_confidence=6.0,
                min_entity_confidence=0.7, news_max_age_seconds=86400.0)
    base.update(overrides)
    return Settings(**base)


class StubInvestigator:
    """Stands in for the Claude deep pass with a fixed, schema-valid result."""

    deep_model = "stub-model"

    def __init__(self, output: DeepInvestigation | None = None, fail: bool = False):
        self._output = output
        self._fail = fail
        self.calls = 0
        self.last_evidence = None

    def investigate(self, evidence):
        self.calls += 1
        self.last_evidence = evidence
        if self._fail:
            from app.catalyst.investigator import InvestigationFailed
            raise InvestigationFailed("stubbed failure")
        return self._output or default_investigation(), 120

    @staticmethod
    def invented_financials(parsed, retrieved, tolerance_pct: float = 2.0):
        from app.catalyst.investigator import CatalystInvestigator
        return CatalystInvestigator.invented_financials(parsed, retrieved, tolerance_pct)


def default_investigation(**overrides) -> DeepInvestigation:
    base = dict(
        event_type=EventType.GOVERNMENT_CONTRACT,
        summary="Company awarded a firm government contract.",
        facts=[], new_information="Contract award announced today.",
        previously_known_information="Nothing previously public.",
        incremental_information="Award is new and binding.",
        certainty="EXECUTED", source_quality=1.0, entity_mapping_correct=True,
        positive_factors=["binding award"], negative_offsets=[], uncertainties=[],
        adversarial_findings=[], event_quality=9.0, strategic_significance=9.0,
        confidence_adjustment=0.0, invalidate=False)
    base.update(overrides)
    return DeepInvestigation(**base)


def make_pipeline(conf: Settings, investigator=None, *, market=None,
                  financials=None, analogue=None):
    notifier = FakeNotifier()
    return CatalystPipeline(
        settings=conf,
        investigator=investigator,
        notifier=CatalystNotifier([notifier]),
        market_context_fn=market or (lambda t, n: MarketContextInputs(
            price_before=10.0, price_now=10.1,
            structure=MarketStructure(market_cap=400e6, free_float_shares=20e6,
                                      share_price=10.1, avg_dollar_volume=10e6,
                                      relative_volume=3.0, spread_pct=0.4,
                                      short_percent_float=14.0,
                                      short_interest_as_of=NOW - timedelta(days=4),
                                      atr_pct=5.0, session="regular",
                                      halt_state=HaltState.NONE))),
        financials_fn=financials or (lambda t: CompanyFinancials(
            market_cap=400e6, annual_revenue=120e6, share_price=10.1)),
        analogue_fn=analogue or (lambda et, s: (25.0, 30)),
    ), notifier


def seed_company(session, ticker="ACME", name="Acme Defense Corporation") -> Company:
    company = Company(ticker=ticker, name=name, market_cap=400e6)
    session.add(company)
    session.flush()
    return company


def article(headline: str, body: str = "", *, ticker="ACME",
            tier=SourceTier.PRIMARY, published=None, article_id="a1",
            provider="mock_news") -> NewsArticle:
    return NewsArticle(
        provider=provider, article_id=article_id, headline=headline, body=body,
        tickers=[ticker], source_tier=tier,
        source_url=f"https://example.test/{article_id}",
        published_at_utc=published or NOW, received_at_utc=published or NOW)


# ── §103: synthetic true positive ────────────────────────────────────────────

def test_synthetic_positive_scores_highly(db):
    """$400m cap, $120m revenue, binding $250m contract with $100m funded,
    previously unknown, credible source, stock barely moved."""
    conf = settings()
    pipeline, notifier = make_pipeline(conf, StubInvestigator())

    with db.db_session() as session:
        seed_company(session)
        result = pipeline.process(session, article(
            "Acme Defense Corporation (NASDAQ: ACME) awarded $250 million U.S. Navy contract",
            "Acme has been awarded a 1-year firm contract by the Department of Defense "
            "valued at $250 million. The contract has an initially funded value of "
            "$100 million.", ), now=NOW)

        assert not result.rejected
        assert result.score is not None
        assert result.score >= 8.5, f"expected a strong score, got {result.score}"

        event = session.get(CatalystEvent, result.event_id)
        assert event.ticker == "ACME"
        materiality = session.query(CatalystScore).filter_by(event_id=event.id).first()
        assert materiality.catalyst_strength >= 8.0


# ── §104: synthetic false positive — multi-award ceiling ─────────────────────

def test_multi_award_ceiling_does_not_become_a_high_score(db):
    """'$5bn AI programme' shared with 30 vendors, nothing guaranteed,
    already announced, stock already +25%."""
    conf = settings()
    market = lambda t, n: MarketContextInputs(
        price_before=10.0, price_now=12.5, pre_event_runup_pct=25.0,
        structure=MarketStructure(market_cap=500e6, free_float_shares=20e6,
                                  share_price=12.5, avg_dollar_volume=10e6,
                                  atr_pct=5.0, session="regular",
                                  halt_state=HaltState.NONE))
    pipeline, notifier = make_pipeline(conf, StubInvestigator(), market=market)

    with db.db_session() as session:
        seed_company(session)
        # Prior announcement so novelty is degraded too.
        pipeline.process(session, article(
            "Acme selected for $5 billion AI programme",
            "Acme was selected as one of the approved vendors for a multiple-award "
            "programme with a ceiling of up to $5 billion.",
            article_id="prior", published=NOW - timedelta(days=3)), now=NOW - timedelta(days=3))

        result = pipeline.process(session, article(
            "Acme's $5 billion AI programme win could transform the company",
            "Acme was selected as one of 30 approved vendors for the multiple-award "
            "programme with a ceiling of up to $5 billion and no guaranteed order volume.",
            article_id="followup"), now=NOW)

        assert result.rejected or (result.score is not None and result.score < 8.0), (
            f"recycled multi-award ceiling should not score highly, got {result.score}")
        assert not notifier.sent


# ── §105: biotech false positive — endpoint missed ───────────────────────────

def test_missed_primary_endpoint_is_heavily_penalised(db):
    """Headline trumpets a subgroup; the primary endpoint was missed and there
    is a serious adverse event."""
    conf = settings()
    investigation = default_investigation(
        event_type=EventType.PHASE_3_RESULT,
        negative_offsets=[
            NegativeOffset(description="primary endpoint was not met", severity=9.0),
            NegativeOffset(description="serious adverse events reported", severity=8.0),
        ],
        adversarial_findings=["headline emphasises a subgroup, not the full population"],
        event_quality=3.0, strategic_significance=3.0)
    pipeline, notifier = make_pipeline(conf, StubInvestigator(investigation))

    with db.db_session() as session:
        seed_company(session, "BIO", "Biotech Therapeutics")
        result = pipeline.process(session, article(
            "Biotech Therapeutics (NASDAQ: BIO) Phase 3 study demonstrates statistically "
            "significant improvement in key subgroup",
            "The study did not meet its primary endpoint in the overall population. "
            "A pre-specified subgroup analysis showed benefit. One serious adverse "
            "event was reported.",
            ticker="BIO"), now=NOW)

        assert result.score is not None
        assert result.score < 7.0, f"endpoint miss must be penalised, got {result.score}"
        assert not notifier.sent

        offsets = session.query(NegativeOffsetRow).filter_by(event_id=result.event_id).all()
        assert max(o.severity for o in offsets) >= 9.0


# ── §106: buyback false positive ─────────────────────────────────────────────

def test_buyback_authorisation_is_not_scored_as_execution(db):
    """$1bn authorisation on a $5bn cap, replacing a barely-used programme,
    with little free cash flow."""
    conf = settings()
    financials = lambda t: CompanyFinancials(
        market_cap=5e9, annual_revenue=2e9, free_cash_flow=40e6, share_price=50.0)
    pipeline, notifier = make_pipeline(
        conf, StubInvestigator(default_investigation(
            event_type=EventType.BUYBACK_AUTHORISATION, event_quality=5.0,
            strategic_significance=4.0)),
        financials=financials)

    with db.db_session() as session:
        seed_company(session, "BUY", "Buyback Industries")
        result = pipeline.process(session, article(
            "Buyback Industries (NYSE: BUY) board authorizes $1 billion share repurchase",
            "The board has authorized the repurchase of up to $1 billion of common stock. "
            "The programme replaces the existing authorization.",
            ticker="BUY"), now=NOW)

        assert result.score is not None
        assert result.score <= 8.0, f"authorisation should be capped, got {result.score}"
        score_row = session.query(CatalystScore).filter_by(event_id=result.event_id).first()
        assert any("capped" in c.lower() or "authoris" in c.lower()
                   for c in score_row.caps_applied) or score_row.upside_catalyst_score <= 8.0


# ── §107: already-priced ─────────────────────────────────────────────────────

def test_transformative_catalyst_with_no_room_left_is_not_pushed(db):
    """Catalyst is genuinely excellent but the stock has already run +70%."""
    conf = settings()
    market = lambda t, n: MarketContextInputs(
        price_before=10.0, price_now=17.0, pre_event_runup_pct=15.0,
        structure=MarketStructure(market_cap=680e6, free_float_shares=20e6,
                                  share_price=17.0, avg_dollar_volume=10e6,
                                  relative_volume=12.0, spread_pct=0.4, atr_pct=6.0,
                                  session="regular", halt_state=HaltState.NONE))
    pipeline, notifier = make_pipeline(conf, StubInvestigator(), market=market)

    with db.db_session() as session:
        seed_company(session)
        result = pipeline.process(session, article(
            "Acme Defense Corporation (NASDAQ: ACME) receives FDA approval",
            "Acme has been awarded a $250 million contract. The company has entered "
            "into a definitive agreement.",
            article_id="moved"), now=NOW)

        assert result.score is not None
        assert result.score <= 8.9, f"already-moved stock must not push, got {result.score}"
        assert not notifier.sent

        score_row = session.query(CatalystScore).filter_by(event_id=result.event_id).first()
        assert "reaction_room" in score_row.gates_failed
        assert score_row.reaction_room < 3.0


# ── §108: earnings interaction ───────────────────────────────────────────────

def test_earnings_coverage_routes_to_earnings_sentinel_not_catalyst(db):
    """Derivative earnings articles must link, not create catalysts."""
    conf = settings()
    pipeline, notifier = make_pipeline(conf, StubInvestigator())

    with db.db_session() as session:
        company = seed_company(session)
        session.add(EarningsEvent(company_id=company.id, fiscal_year=2026,
                                  fiscal_quarter=2, state="SCORED"))
        session.flush()

        results = []
        for i in range(5):
            results.append(pipeline.process(session, article(
                f"Acme Defense Corporation (NASDAQ: ACME) reports second quarter results "
                f"— coverage {i}",
                "Acme today announced financial results for its second quarter.",
                article_id=f"earn{i}", published=NOW + timedelta(seconds=i)), now=NOW))

        # The first is screened out to Earnings Sentinel; the rest are
        # recognised as the same story and simply join that cluster.
        assert results[0].rejected
        assert results[0].reject_reason == RejectReason.EARNINGS_EVENT.value
        assert all(not r.alerted for r in results)
        assert session.query(EventCluster).count() == 1

        events = session.query(CatalystEvent).all()
        assert all(e.state == CatalystState.ROUTED_TO_EARNINGS.value for e in events)
        assert any(e.earnings_event_id is not None for e in events)
        assert session.query(CatalystScore).count() == 0
        assert not notifier.sent


# ── §102: dedup, wrong mapping, halts, missing price ─────────────────────────

def test_five_syndicated_copies_collapse_into_one_event(db):
    """Company release, SEC, two wires and a syndicator = ONE event."""
    conf = settings()
    pipeline, notifier = make_pipeline(conf, StubInvestigator())
    headlines = [
        ("ir", "Acme Defense Corporation (NASDAQ: ACME) awarded $250 million Navy contract"),
        ("sec", "Acme Defense Corporation awarded $250 million Navy contract"),
        ("wire1", "Navy awards Acme Defense $250 million contract"),
        ("wire2", "Acme Defense wins $250 million Navy contract"),
        ("synd", "Acme Defense Corporation awarded $250 million contract by Navy"),
    ]

    with db.db_session() as session:
        seed_company(session)
        results = []
        for i, (aid, headline) in enumerate(headlines):
            results.append(pipeline.process(session, article(
                headline,
                "Acme has been awarded a firm contract valued at $250 million.",
                article_id=aid, published=NOW + timedelta(seconds=i * 30)),
                now=NOW + timedelta(seconds=i * 30)))

        assert session.query(EventCluster).count() == 1, "all copies must share one cluster"
        assert session.query(CatalystEvent).count() == 1
        assert session.query(NewsItem).count() == 5
        assert session.query(CatalystScore).count() == 1, "scored exactly once"
        assert len(notifier.sent) <= 1


def test_unmappable_story_is_rejected_before_any_analysis(db):
    conf = settings()
    investigator = StubInvestigator()
    pipeline, notifier = make_pipeline(conf, investigator)

    with db.db_session() as session:
        seed_company(session)
        result = pipeline.process(session, NewsArticle(
            provider="mock_news", article_id="vague",
            headline="Apple harvest reaches record levels this season",
            body="Growers reported a strong season.", tickers=[],
            source_tier=SourceTier.NEWSWIRE, published_at_utc=NOW), now=NOW)

        assert result.rejected
        assert result.reject_reason == RejectReason.LOW_ENTITY_CONFIDENCE.value
        assert investigator.calls == 0, "must not spend an LLM call on an unmapped story"


def test_halted_stock_is_scored_but_not_pushed(db):
    conf = settings()
    market = lambda t, n: MarketContextInputs(
        price_before=10.0, price_now=10.0,
        structure=MarketStructure(market_cap=400e6, free_float_shares=20e6,
                                  share_price=10.0, avg_dollar_volume=10e6,
                                  atr_pct=5.0, session="regular",
                                  halt_state=HaltState.NEWS_PENDING))
    pipeline, notifier = make_pipeline(conf, StubInvestigator(), market=market)

    with db.db_session() as session:
        seed_company(session)
        result = pipeline.process(session, article(
            "Acme Defense Corporation (NASDAQ: ACME) awarded $250 million contract",
            "Acme has been awarded a firm contract valued at $250 million.",
            article_id="halted"), now=NOW)

        assert result.score is not None, "analysis continues during a halt"
        assert not notifier.sent, "no price-sensitive push while halted"
        score_row = session.query(CatalystScore).filter_by(event_id=result.event_id).first()
        assert "halt" in score_row.gates_failed or "price_current" in score_row.gates_failed


def test_missing_price_data_prevents_a_fresh_push(db):
    conf = settings()
    market = lambda t, n: MarketContextInputs(
        price_before=None, price_now=None,
        structure=MarketStructure(market_cap=400e6, session="regular"))
    pipeline, notifier = make_pipeline(conf, StubInvestigator(), market=market)

    with db.db_session() as session:
        seed_company(session)
        result = pipeline.process(session, article(
            "Acme Defense Corporation (NASDAQ: ACME) awarded $250 million contract",
            "Acme has been awarded a firm contract valued at $250 million.",
            article_id="noprice"), now=NOW)

        assert not notifier.sent
        score_row = session.query(CatalystScore).filter_by(event_id=result.event_id).first()
        assert "price_current" in score_row.gates_failed


def test_llm_unavailable_still_scores_but_cannot_push_nine(db):
    """§98 — never pretend an unvalidated event was fully reviewed."""
    conf = settings()
    pipeline, notifier = make_pipeline(conf, StubInvestigator(fail=True))

    with db.db_session() as session:
        seed_company(session)
        result = pipeline.process(session, article(
            "Acme Defense Corporation (NASDAQ: ACME) awarded $250 million Navy contract",
            "Acme has been awarded a firm 1-year contract valued at $250 million with "
            "an initially funded value of $100 million.",
            article_id="nollm"), now=NOW)

        assert result.score is not None
        assert result.score < 9.0
        score_row = session.query(CatalystScore).filter_by(event_id=result.event_id).first()
        assert "claude_review" in score_row.gates_failed


def test_pipeline_records_a_full_trace(db):
    """§112 — every stage traceable under one correlation id."""
    from app.db.catalyst_models import PipelineTrace

    conf = settings()
    pipeline, _ = make_pipeline(conf, StubInvestigator())
    with db.db_session() as session:
        seed_company(session)
        result = pipeline.process(session, article(
            "Acme Defense Corporation (NASDAQ: ACME) awarded $250 million contract",
            "Acme has been awarded a firm contract valued at $250 million.",
            article_id="trace"), now=NOW)

        traces = (session.query(PipelineTrace)
                  .filter_by(correlation_id=result.correlation_id).all())
        stages = {t.stage for t in traces}
        assert {"ingest", "entity_resolution", "clustering", "classification",
                "market_data", "materiality", "reaction_and_structure",
                "adversarial_review", "scoring", "notification"} <= stages
        assert all(t.duration_ms is not None for t in traces)


def test_story_revision_is_stored_not_overwritten(db):
    """§7 — an update can itself carry new information."""
    from app.db.catalyst_models import NewsRevision

    conf = settings()
    pipeline, _ = make_pipeline(conf, StubInvestigator())
    with db.db_session() as session:
        seed_company(session)
        pipeline.process(session, article(
            "Acme Defense Corporation (NASDAQ: ACME) awarded contract",
            "Initial report.", article_id="rev1"), now=NOW)
        pipeline.process(session, article(
            "Acme Defense Corporation (NASDAQ: ACME) awarded contract — UPDATED",
            "Updated with contract value of $250 million.", article_id="rev1"),
            now=NOW + timedelta(minutes=5))

        assert session.query(NewsItem).count() == 1
        assert session.query(NewsRevision).count() == 1


def test_earnings_sentinel_tables_are_untouched(db):
    """Regression guard: the catalyst pipeline must not write earnings rows."""
    from app.db.models import Release, Score

    conf = settings()
    pipeline, _ = make_pipeline(conf, StubInvestigator())
    with db.db_session() as session:
        seed_company(session)
        pipeline.process(session, article(
            "Acme Defense Corporation (NASDAQ: ACME) awarded $250 million contract",
            "Acme has been awarded a firm contract valued at $250 million.",
            article_id="isolation"), now=NOW)

        assert session.query(Release).count() == 0
        assert session.query(Score).count() == 0
