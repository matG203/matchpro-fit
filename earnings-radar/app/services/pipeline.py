"""EarningsPipeline — orchestrates DETECT → VERIFY → ANALYSE → SCORE → NOTIFY.

Every stage writes an audit row and advances the event state machine. The
deterministic provisional score is computed before the LLM call so a slow or
failing analysis cannot cost us the notification entirely.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import (
    Analysis,
    Company,
    EarningsEvent,
    Estimate,
    ExtractedFinancial,
    MarketContext,
    Release,
    ReleaseSource,
    Score,
)
from app.domain.canonical import canonical_release_key
from app.domain.enums import EventState, GuidanceStatus, ReleaseSourceKind, assert_transition
from app.domain.timeutil import utcnow
from app.providers.base import AllProvidersFailed, EstimateDTO, FilingProvider, ProviderError
from app.services.analysis import AnalysisFailed, EarningsAnalysisService
from app.services.audit import AuditService
from app.services.expectations import build_expectations, surprise_pct_vs_band
from app.services.extraction import extract_financials
from app.services.marketdata import MarketContextData, MarketDataService
from app.services.monitor import DetectionCandidate, ReleaseMonitorService
from app.services.notification import NotificationService
from app.services.scoring import ScoringInputs, compute_scores
from app.services.verification import verify_release_document

logger = logging.getLogger("earnings_radar.pipeline")

_SOURCE_QUALITY = {
    ReleaseSourceKind.SEC: 1.0,
    ReleaseSourceKind.BUSINESSWIRE: 0.95,
    ReleaseSourceKind.PRNEWSWIRE: 0.95,
    ReleaseSourceKind.GLOBENEWSWIRE: 0.95,
    ReleaseSourceKind.IR: 0.85,
    ReleaseSourceKind.OTHER: 0.7,
}


@dataclass
class PipelineResult:
    release_id: int | None = None
    final_score: float | None = None
    notified: bool = False
    state: EventState = EventState.MONITORING
    detail: str = ""


class EarningsPipeline:
    def __init__(self, *, settings: Settings, monitor: ReleaseMonitorService,
                 filings: FilingProvider | None, market: MarketDataService,
                 analysis: EarningsAnalysisService | None,
                 notifications: NotificationService):
        self._settings = settings
        self.monitor = monitor
        self._filings = filings
        self._market = market
        self._analysis = analysis
        self._notifications = notifications

    # ── state helpers ─────────────────────────────────────────────────────────

    def _transition(self, session: Session, audit: AuditService, event: EarningsEvent,
                    new_state: EventState, detail: str = "") -> None:
        current = EventState(event.state)
        assert_transition(current, new_state)
        event.state = new_state.value
        event.state_changed_at = utcnow()
        audit.log("pipeline", "state_change", f"{current} -> {new_state} {detail}".strip(),
                  event_id=event.id)
        session.flush()

    # ── main entry ────────────────────────────────────────────────────────────

    def process_detection(self, session: Session, event: EarningsEvent,
                          candidates: list[DetectionCandidate]) -> PipelineResult:
        """Run the full pipeline for a detected release. Idempotent per
        canonical key: an existing scored release is never re-processed."""
        audit = AuditService(session)
        company: Company = event.company
        detected_at = utcnow()

        canonical = canonical_release_key(company.ticker, event.fiscal_year,
                                          event.fiscal_quarter)
        existing = session.query(Release).filter_by(canonical_key=canonical).first()
        if existing and existing.verified:
            self._record_sources(session, existing, candidates)
            audit.log("pipeline", "duplicate_release",
                      f"{canonical} already verified — sources merged, no re-analysis",
                      event_id=event.id, release_id=existing.id)
            return PipelineResult(release_id=existing.id, state=EventState(event.state),
                                  detail="duplicate")

        if EventState(event.state) in (EventState.MONITORING, EventState.NOT_YET_VERIFIED):
            self._transition(session, audit, event, EventState.RELEASE_DETECTED,
                             f"{len(candidates)} candidate(s)")

        published_at = self.monitor.earliest_publication(candidates)
        release = existing or Release(canonical_key=canonical, event_id=event.id)
        release.detected_at_utc = detected_at
        release.published_at_utc = published_at
        release.detection_latency_ms = self.monitor.detection_latency_ms(
            published_at, detected_at)
        session.add(release)
        session.flush()
        self._record_sources(session, release, candidates)
        audit.log("pipeline", "release_detected",
                  f"{canonical} published={published_at} latency="
                  f"{release.detection_latency_ms}ms sources="
                  f"{[c.source.value for c in candidates]}",
                  event_id=event.id, release_id=release.id)

        # ── VERIFY ────────────────────────────────────────────────────────────
        self._transition(session, audit, event, EventState.VERIFYING)
        verified_candidate, text, verification = self._verify(
            session, audit, event, company, release, candidates)
        if verified_candidate is None:
            self._transition(session, audit, event, EventState.NOT_YET_VERIFIED,
                             "no candidate verified — continuing to monitor")
            return PipelineResult(release_id=release.id, state=EventState.NOT_YET_VERIFIED,
                                  detail="not_yet_verified")

        release.verified = True
        release.verified_at_utc = utcnow()
        release.primary_url = verified_candidate.url
        release.document_type = verified_candidate.document_type
        release.document_text = text[:200000]
        release.verification_notes = "; ".join(verification.reasons)
        session.flush()
        self._transition(session, audit, event, EventState.VERIFIED)

        # ── EXTRACT ───────────────────────────────────────────────────────────
        self._transition(session, audit, event, EventState.EXTRACTING)
        extraction = extract_financials(text)
        for metric, fact in extraction.facts.items():
            session.add(ExtractedFinancial(
                release_id=release.id, metric=metric, value=fact.value, unit=fact.unit,
                source_url=verified_candidate.url, confidence=fact.confidence,
                method=fact.method))
        audit.log("pipeline", "extraction_complete",
                  f"{len(extraction.facts)} metrics: {sorted(extraction.facts)}",
                  event_id=event.id, release_id=release.id)

        # ── CONTEXT (expectations + market) ───────────────────────────────────
        self._transition(session, audit, event, EventState.CONTEXT)
        expectations = self._load_expectations(session, event)
        audit.log("pipeline", "expectations_loaded",
                  f"confidence={expectations.estimate_confidence} "
                  f"bands={ {m: (b.low, b.high) for m, b in expectations.bands.items()} } "
                  f"{'; '.join(expectations.notes)}",
                  event_id=event.id, release_id=release.id)

        market = self._load_market_context(session, event)
        audit.log("pipeline", "market_context",
                  f"pre={market.pre_release_price} reaction={market.current_reaction_pct} "
                  f"pattern={market.reaction_pattern.value} unresolved={market.unresolved}",
                  event_id=event.id, release_id=release.id)

        # Deterministic surprises against the conservative band edge
        eps_actual = extraction.value("eps_adjusted") or extraction.value("eps_diluted")
        rev_actual = extraction.value("revenue")
        eps_surprise = rev_surprise = None
        eps_band, rev_band = expectations.band("eps"), expectations.band("revenue")
        if eps_actual is not None and eps_band:
            eps_surprise, _ = surprise_pct_vs_band(eps_actual, eps_band)
        if rev_actual is not None and rev_band:
            rev_surprise, _ = surprise_pct_vs_band(rev_actual, rev_band)

        # ── ANALYSE ───────────────────────────────────────────────────────────
        self._transition(session, audit, event, EventState.ANALYSING)
        parsed = None
        fact_mismatch = False
        if self._analysis is not None:
            try:
                evidence = self._analysis.build_evidence(
                    ticker=company.ticker, company_name=company.name,
                    fiscal_year=event.fiscal_year, fiscal_quarter=event.fiscal_quarter,
                    release_text=text, extraction=extraction, expectations=expectations,
                    market=market, kpi_profile=company.kpi_profile)
                parsed = self._analysis.analyse(evidence)
                fact_mismatch = self._analysis.fact_mismatch(parsed, extraction)
                session.add(Analysis(
                    release_id=release.id, model=self._settings.analysis_model,
                    raw_json=parsed.model_dump(mode="json"),
                    earnings_quality=parsed.earnings_quality,
                    guidance_score=parsed.guidance_score,
                    business_kpi_score=parsed.business_kpi_score,
                    true_surprise_score=parsed.true_surprise_score,
                    guidance_status=parsed.guidance_status.value,
                    growth_direction=parsed.growth_direction.value,
                    confidence=parsed.confidence, verdict=parsed.verdict,
                    bull_case=parsed.bull_case, bear_case=parsed.bear_case,
                    reasoning_summary=parsed.reasoning_summary,
                    hidden_negatives=parsed.hidden_negatives,
                    pre_announced=parsed.pre_announced_news,
                    one_off_items=parsed.one_off_items))
                audit.log("pipeline", "analysis_complete",
                          f"EQ={parsed.earnings_quality} guidance={parsed.guidance_status} "
                          f"conf={parsed.confidence} mismatch={fact_mismatch}",
                          event_id=event.id, release_id=release.id)
            except AnalysisFailed as exc:
                audit.log("pipeline", "analysis_failed",
                          f"{exc} — falling back to provisional deterministic score",
                          event_id=event.id, release_id=release.id, level="ERROR")

        # ── SCORE ─────────────────────────────────────────────────────────────
        self._transition(session, audit, event, EventState.SCORING)
        inputs = ScoringInputs(
            llm_earnings_quality=parsed.earnings_quality if parsed else None,
            llm_guidance_score=parsed.guidance_score if parsed else None,
            llm_business_kpi_score=parsed.business_kpi_score if parsed else None,
            llm_true_surprise_score=parsed.true_surprise_score if parsed else None,
            llm_confidence=parsed.confidence if parsed else None,
            eps_dominated_by_one_offs=parsed.eps_dominated_by_one_offs if parsed else False,
            hidden_negative_count=len(parsed.hidden_negatives) if parsed else 0,
            guidance_status=parsed.guidance_status if parsed else GuidanceStatus.NONE,
            organic_guidance_change=parsed.organic_guidance_change if parsed else None,
            eps_surprise_pct=eps_surprise,
            revenue_surprise_pct=rev_surprise,
            estimate_confidence=expectations.estimate_confidence,
            consensus_disagreement=any(b.disagreement for b in expectations.bands.values()),
            reaction_pct=market.current_reaction_pct,
            reaction_vs_prev_close_pct=market.reaction_vs_prev_close_pct,
            pre_run_1m_pct=market.run_1m_pct,
            implied_move_pct=market.implied_move_pct,
            reaction_pattern=market.reaction_pattern,
            market_data_unresolved=market.unresolved,
            release_source_quality=_SOURCE_QUALITY.get(verified_candidate.source, 0.7),
            kpi_completeness=min(len(extraction.facts) / 6.0, 1.0),
            llm_fact_mismatch=fact_mismatch,
        )
        result = compute_scores(
            inputs, min_confidence=self._settings.min_confidence_for_notification)

        if result.score_review:
            self._transition(session, audit, event, EventState.SCORE_REVIEW,
                             "earnings quality >= 9 but stock fell — 9+ withheld")

        score_row = session.query(Score).filter_by(
            release_id=release.id,
            scoring_model_version=result.scoring_model_version).first()
        if score_row is None:
            score_row = Score(release_id=release.id,
                              scoring_model_version=result.scoring_model_version)
            session.add(score_row)
        score_row.earnings_quality = result.earnings_quality
        score_row.market_confirmation = result.market_confirmation
        score_row.entry_score = result.entry_score
        score_row.final_trade_score = result.final_trade_score
        score_row.component_breakdown = result.component_breakdown
        score_row.vetoes_applied = result.vetoes_applied
        score_row.analysis_confidence = result.analysis_confidence
        score_row.needs_verification = result.needs_verification
        score_row.score_review = result.score_review
        score_row.provisional = result.provisional
        session.flush()

        audit.log("pipeline", "score_calculated",
                  f"final={result.final_trade_score} EQ={result.earnings_quality} "
                  f"MC={result.market_confirmation} entry={result.entry_score} "
                  f"conf={result.analysis_confidence} vetoes={result.vetoes_applied}",
                  event_id=event.id, release_id=release.id)
        self._transition(session, audit, event, EventState.SCORED)

        # ── NOTIFY ────────────────────────────────────────────────────────────
        notified = False
        if result.provisional and not self._settings.notify_provisional_on_llm_failure:
            audit.log("pipeline", "notification_skipped",
                      "provisional score and provisional notifications disabled",
                      event_id=event.id, release_id=release.id)
        else:
            notified = self._notifications.notify_score(
                session, release_id=release.id, canonical_key=canonical,
                ticker=company.ticker, score=result.final_trade_score,
                confidence=result.analysis_confidence,
                model_version=result.scoring_model_version, provisional=result.provisional)
            audit.log("pipeline", "notification_sent" if notified else "notification_skipped",
                      f"score={result.final_trade_score} conf={result.analysis_confidence}",
                      event_id=event.id, release_id=release.id)
        if notified:
            self._transition(session, audit, event, EventState.NOTIFIED)

        return PipelineResult(release_id=release.id, final_score=result.final_trade_score,
                              notified=notified, state=EventState(event.state))

    # ── stages ────────────────────────────────────────────────────────────────

    def _record_sources(self, session: Session, release: Release,
                        candidates: list[DetectionCandidate]) -> None:
        known = {row.url for row in release.source_rows}
        for candidate in candidates:
            if candidate.url in known:
                continue
            session.add(ReleaseSource(
                release_id=release.id, source=candidate.source.value, url=candidate.url,
                published_at_claimed=candidate.published_at_utc))
        session.flush()

    def _verify(self, session: Session, audit: AuditService, event: EarningsEvent,
                company: Company, release: Release, candidates: list[DetectionCandidate]):
        """Fetch and verify candidates in source-quality order."""
        ordered = sorted(candidates,
                         key=lambda c: -_SOURCE_QUALITY.get(c.source, 0.5))
        for candidate in ordered:
            text = ""
            if self._filings is not None:
                try:
                    text = self._filings.fetch_document_text(candidate.url)
                except ProviderError as exc:
                    audit.log("pipeline", "document_fetch_failed",
                              f"{candidate.url}: {exc}", event_id=event.id,
                              release_id=release.id, level="WARNING")
                    continue
            if not text:
                continue
            verification = verify_release_document(
                text=text, ticker=company.ticker, company_name=company.name,
                expected_fy=event.fiscal_year, expected_fq=event.fiscal_quarter,
                document_type=candidate.document_type)
            audit.log("pipeline", "verification_attempt",
                      f"{candidate.source.value} {candidate.url} -> "
                      f"verified={verification.verified} ({'; '.join(verification.reasons)})",
                      event_id=event.id, release_id=release.id)
            if verification.verified:
                return candidate, text, verification
        return None, "", None

    def _load_expectations(self, session: Session, event: EarningsEvent):
        rows = session.query(Estimate).filter_by(event_id=event.id).all()
        return build_expectations([
            EstimateDTO(metric=r.metric, period=r.period, value=r.value,
                        provider=r.provider, confidence=r.confidence)
            for r in rows
        ])

    def _load_market_context(self, session: Session, event: EarningsEvent
                             ) -> MarketContextData:
        company: Company = event.company
        ctx = session.query(MarketContext).filter_by(event_id=event.id).first()
        data = MarketContextData()
        if ctx is not None:
            data.prev_close = ctx.prev_close
            data.pre_release_price = ctx.pre_release_price
            data.run_5d_pct = ctx.run_5d_pct
            data.run_1m_pct = ctx.run_1m_pct
            data.run_3m_pct = ctx.run_3m_pct
            data.implied_move_pct = ctx.implied_move_pct
        else:
            try:
                data = self._market.pre_earnings_context(company.ticker)
            except AllProvidersFailed as exc:
                data.notes.append(f"pre-earnings context unavailable: {exc.errors}")
                data.unresolved = True

        data = self._market.capture_reaction(company.ticker, data, minutes_after=0.0)
        self._persist_market_context(session, event, data)
        return data

    def _persist_market_context(self, session: Session, event: EarningsEvent,
                                data: MarketContextData) -> None:
        ctx = session.query(MarketContext).filter_by(event_id=event.id).first()
        if ctx is None:
            ctx = MarketContext(event_id=event.id)
            session.add(ctx)
        ctx.prev_close = data.prev_close
        ctx.pre_release_price = data.pre_release_price
        ctx.run_5d_pct = data.run_5d_pct
        ctx.run_1m_pct = data.run_1m_pct
        ctx.run_3m_pct = data.run_3m_pct
        ctx.implied_move_pct = data.implied_move_pct
        ctx.initial_reaction_pct = data.initial_reaction_pct
        ctx.current_reaction_pct = data.current_reaction_pct
        ctx.reaction_vs_prev_close_pct = data.reaction_vs_prev_close_pct
        ctx.reaction_pattern = data.reaction_pattern.value
        ctx.unresolved = data.unresolved
        ctx.notes = "; ".join(data.notes)
        session.flush()

    # ── pre-earnings capture (called by the scheduler before the window) ─────

    def capture_pre_earnings(self, session: Session, event: EarningsEvent) -> None:
        audit = AuditService(session)
        try:
            data = self._market.pre_earnings_context(event.company.ticker)
        except AllProvidersFailed as exc:
            audit.log("pipeline", "pre_earnings_context_failed", str(exc.errors),
                      event_id=event.id, level="WARNING")
            return
        self._persist_market_context(session, event, data)
        audit.log("pipeline", "pre_earnings_context",
                  f"pre={data.pre_release_price} prev_close={data.prev_close} "
                  f"run_1m={data.run_1m_pct}", event_id=event.id)


def now_or(value: datetime | None) -> datetime:
    return value or utcnow()
