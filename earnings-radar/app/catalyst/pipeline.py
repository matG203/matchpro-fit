"""Catalyst Sentinel pipeline (spec §112, §115).

    NEW INFORMATION → VERIFY SOURCE → WHAT CHANGED → QUANTIFY MATERIALITY
    → VS EXPECTATION → HIDDEN NEGATIVES → FINANCIAL POSITION → PRICE BEFORE
    → PRICE SINCE → MARKET STRUCTURE → ANALOGUES → REACTION ROOM
    → ADVERSARIAL REVIEW → REVALIDATE PRICE → SCORE → ONLY THEN ALERT

Every stage writes a trace row with a shared correlation id, so any alert can
be reconstructed end to end and its latency attributed.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.catalyst import amplification as amp
from app.catalyst import classify as classify_mod
from app.catalyst import dedup as dedup_mod
from app.catalyst import materiality as mat
from app.catalyst import negatives as neg
from app.catalyst import novelty as nov
from app.catalyst import reaction as react
from app.catalyst.alerts import AlertContext, CatalystNotifier, decide_alert
from app.catalyst.entities import resolve_entity
from app.catalyst.enums import (
    CatalystHalfLife,
    CatalystState,
    Certainty,
    EventType,
    RejectReason,
    SourceTier,
    category_for,
)
from app.catalyst.investigator import (
    CatalystInvestigator,
    InvestigationEvidence,
    InvestigationFailed,
)
from app.catalyst.scoring import ScoringInputs, compute_catalyst_score
from app.config import Settings
from app.db.catalyst_models import (
    CatalystEvent,
    CatalystScore,
    CatalystSource,
    ClaudeInvestigation,
    EventCluster,
    EventFact,
    MarketStructureSnapshot,
    MaterialityAnalysis,
    NegativeOffsetRow,
    NewsItem,
    NoveltyAnalysis,
    PipelineTrace,
    ReactionAnalysis,
)
from app.db.models import Company
from app.domain.timeutil import from_db, utcnow
from app.providers.news import NewsArticle
from app.services.audit import AuditService

logger = logging.getLogger("earnings_radar.catalyst.pipeline")

# Half-life by event type (§53).
HALF_LIFE_BY_TYPE: dict[EventType, CatalystHalfLife] = {
    EventType.ANALYST_ACTION: CatalystHalfLife.MINUTES,
    EventType.PRODUCT_LAUNCH: CatalystHalfLife.HOURS,
    EventType.TECHNICAL_MILESTONE: CatalystHalfLife.HOURS,
    EventType.TAKEOVER_OFFER: CatalystHalfLife.DAYS,
    EventType.TENDER_OFFER: CatalystHalfLife.DAYS,
    EventType.DEAL_APPROVAL: CatalystHalfLife.DAYS,
    EventType.GOVERNMENT_CONTRACT: CatalystHalfLife.STRUCTURAL,
    EventType.COMMERCIAL_CONTRACT: CatalystHalfLife.STRUCTURAL,
    EventType.FDA_APPROVAL: CatalystHalfLife.STRUCTURAL,
    EventType.PHASE_3_RESULT: CatalystHalfLife.STRUCTURAL,
    EventType.GUIDANCE_RAISE: CatalystHalfLife.DAYS,
    EventType.BUYBACK_AUTHORISATION: CatalystHalfLife.DAYS,
    EventType.ACTIVIST_13D: CatalystHalfLife.DAYS,
}


@dataclass
class PipelineResult:
    correlation_id: str
    event_id: int | None = None
    state: CatalystState = CatalystState.INGESTED
    rejected: bool = False
    reject_reason: str = ""
    score: float | None = None
    alerted: bool = False
    detail: str = ""
    traces: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class MarketContextInputs:
    """Supplied by the market-data layer at decision time."""

    price_before: float | None = None
    price_now: float | None = None
    benchmark_before: float | None = None
    benchmark_now: float | None = None
    sector_before: float | None = None
    sector_now: float | None = None
    pre_event_runup_pct: float | None = None
    structure: amp.MarketStructure = field(default_factory=amp.MarketStructure)
    price_captured_at: datetime | None = None


class CatalystPipeline:
    def __init__(self, *, settings: Settings,
                 investigator: CatalystInvestigator | None,
                 notifier: CatalystNotifier,
                 market_context_fn=None,
                 financials_fn=None,
                 analogue_fn=None):
        self._settings = settings
        self._investigator = investigator
        self._notifier = notifier
        # Injected so the pipeline stays testable without network access.
        self._market_context_fn = market_context_fn
        self._financials_fn = financials_fn
        self._analogue_fn = analogue_fn

    # ── tracing ───────────────────────────────────────────────────────────────

    def _trace(self, session: Session, correlation_id: str, stage: str,
               started: float, detail: str = "", event_id: int | None = None) -> float:
        duration = (time.monotonic() - started) * 1000
        session.add(PipelineTrace(
            correlation_id=correlation_id, event_id=event_id, stage=stage,
            duration_ms=round(duration, 2), detail=detail[:2000]))
        return duration

    # ── ingest ────────────────────────────────────────────────────────────────

    def ingest(self, session: Session, article: NewsArticle) -> NewsItem:
        """Store the raw item, or record a revision if we have seen it before."""
        existing = session.query(NewsItem).filter_by(
            provider=article.provider, article_id=article.article_id).first()
        content_hash = article.content_hash()

        if existing is None:
            item = NewsItem(
                provider=article.provider, article_id=article.article_id,
                headline=article.headline, body=article.body,
                tickers=[t.upper() for t in article.tickers], author=article.author,
                source_tier=article.source_tier.value, source_url=article.source_url,
                original_source=article.original_source,
                provider_tags=article.provider_tags, provider_channel=article.provider_channel,
                published_at_utc=article.published_at_utc,
                updated_at_utc=article.updated_at_utc,
                received_at_utc=article.received_at_utc or utcnow(),
                content_hash=content_hash)
            session.add(item)
            session.flush()
            return item

        if existing.content_hash != content_hash:
            # A materially updated story can itself carry new information (§7).
            from app.db.catalyst_models import NewsRevision
            session.add(NewsRevision(
                news_item_id=existing.id, headline=article.headline, body=article.body,
                content_hash=content_hash, materially_changed=True,
                change_notes="content hash changed since last version"))
            existing.headline = article.headline
            existing.body = article.body
            existing.content_hash = content_hash
            existing.updated_at_utc = article.updated_at_utc or utcnow()
            session.flush()
        return existing

    # ── clustering ────────────────────────────────────────────────────────────

    def cluster(self, session: Session, item: NewsItem, ticker: str,
                entity_confidence: float, evidence: str) -> tuple[EventCluster, bool]:
        """Attach the item to an existing cluster or open a new one (§12)."""
        published = from_db(item.published_at_utc) or from_db(item.received_at_utc) or utcnow()
        window_start = published - timedelta(hours=36)

        recent = (session.query(EventCluster)
                  .filter(EventCluster.ticker == ticker.upper())
                  .filter(EventCluster.first_seen_at_utc >= window_start)
                  .order_by(EventCluster.id.desc()).limit(25).all())

        for cluster in recent:
            members = session.query(NewsItem).filter_by(cluster_id=cluster.id).all()
            candidate = dedup_mod.ClusterCandidate(
                cluster_key=cluster.cluster_key, ticker=cluster.ticker,
                headline=members[0].headline if members else "",
                tokens=set().union(*[dedup_mod.tokenise(f"{m.headline} {m.body[:600]}")
                                     for m in members]) if members else set(),
                numbers=set().union(*[dedup_mod.extract_numbers(f"{m.headline} {m.body[:1200]}")
                                      for m in members]) if members else set(),
                earliest_public_at=from_db(cluster.earliest_public_at_utc),
                urls={m.source_url for m in members if m.source_url})
            match = dedup_mod.is_same_event(
                candidate, ticker=ticker, headline=item.headline, body=item.body,
                published_at=published, url=item.source_url)
            if match.matched:
                item.cluster_id = cluster.id
                cluster.member_count += 1
                earliest = from_db(cluster.earliest_public_at_utc)
                if earliest is None or published < earliest:
                    cluster.earliest_public_at_utc = published
                if SourceTier(item.source_tier) == SourceTier.PRIMARY:
                    cluster.best_source_tier = SourceTier.PRIMARY.value
                session.flush()
                return cluster, False

        cluster = EventCluster(
            cluster_key=dedup_mod.build_cluster_key(ticker, published, item.headline),
            ticker=ticker.upper(), entity_confidence=entity_confidence,
            entity_evidence=evidence, earliest_public_at_utc=published,
            best_source_tier=item.source_tier, member_count=1)
        session.add(cluster)
        session.flush()
        item.cluster_id = cluster.id
        session.flush()
        return cluster, True

    # ── main entry ────────────────────────────────────────────────────────────

    def process(self, session: Session, article: NewsArticle, *,
                now: datetime | None = None) -> PipelineResult:
        """Run one inbound item all the way through."""
        now = now or utcnow()
        correlation_id = uuid.uuid4().hex[:16]
        audit = AuditService(session)
        result = PipelineResult(correlation_id=correlation_id)
        stage_start = time.monotonic()

        item = self.ingest(session, article)
        self._trace(session, correlation_id, "ingest", stage_start,
                    f"{article.provider}:{article.article_id}")

        # ── entity resolution (§9) ──
        stage_start = time.monotonic()
        known = {c.ticker: c.name for c in session.query(Company).all() if c.name}
        resolution = resolve_entity(
            headline=article.headline, body=article.body,
            provider_tickers=article.tickers, known_companies=known)
        self._trace(session, correlation_id, "entity_resolution", stage_start,
                    f"{resolution.ticker} @ {resolution.confidence}")

        if not resolution.resolved or resolution.confidence < self._settings.min_entity_confidence:
            audit.log("catalyst", "rejected_entity",
                      f"{article.headline[:120]} — confidence {resolution.confidence:.2f} "
                      f"({'; '.join(resolution.evidence) or 'no signal'})", level="INFO")
            result.rejected = True
            result.reject_reason = RejectReason.LOW_ENTITY_CONFIDENCE.value
            result.detail = f"entity confidence {resolution.confidence:.2f}"
            return result

        ticker = resolution.ticker
        assert ticker is not None

        # ── clustering / dedup (§12) ──
        stage_start = time.monotonic()
        cluster, is_new = self.cluster(session, item, ticker,
                                       resolution.confidence,
                                       "; ".join(resolution.evidence))
        self._trace(session, correlation_id, "clustering", stage_start,
                    f"cluster {cluster.cluster_key} new={is_new}")

        if not is_new and cluster.catalyst_event is not None:
            audit.log("catalyst", "duplicate_source",
                      f"{ticker}: additional source joined cluster {cluster.cluster_key}",
                      level="INFO")
            self._record_source(session, cluster.catalyst_event.id, item)
            result.event_id = cluster.catalyst_event.id
            result.detail = "joined existing cluster — not re-scored"
            return result

        # ── classification + screen (§10-11) ──
        stage_start = time.monotonic()
        classification = classify_mod.classify_event(article.headline, article.body)
        prior = self._prior_mentions(session, ticker, cluster.id, now)
        novelty = nov.assess_novelty(
            headline=article.headline, body=article.body,
            published_at=from_db(item.published_at_utc) or now,
            prior_mentions=prior)
        screen = classify_mod.screen(
            classification=classification, entity_confidence=resolution.confidence,
            source_tier=SourceTier(item.source_tier),
            is_restatement=novelty.is_restatement,
            min_entity_confidence=self._settings.min_entity_confidence)
        self._trace(session, correlation_id, "classification", stage_start,
                    f"{classification.event_type.value} passed={screen.passed}")

        event = self._create_event(session, cluster, item, ticker, classification, novelty)
        self._record_source(session, event.id, item)
        result.event_id = event.id

        if not screen.passed:
            event.state = (CatalystState.ROUTED_TO_EARNINGS.value
                           if screen.reject_reason == RejectReason.EARNINGS_EVENT
                           else CatalystState.REJECTED.value)
            event.reject_reason = screen.reject_reason.value if screen.reject_reason else ""
            event.state_changed_at = now
            if screen.reject_reason == RejectReason.EARNINGS_EVENT:
                self._link_earnings_event(session, event, ticker)
            audit.log("catalyst", "screened_out",
                      f"{ticker}: {screen.reject_reason.value if screen.reject_reason else '?'} "
                      f"— {screen.detail}", release_id=None, level="INFO")
            session.flush()
            result.rejected = True
            result.reject_reason = event.reject_reason
            result.state = CatalystState(event.state)
            result.detail = screen.detail
            return result

        # ── quantitative stages ──
        stage_start = time.monotonic()
        financials = self._get_financials(session, ticker)
        market = self._get_market_context(ticker, now)
        self._trace(session, correlation_id, "market_data", stage_start,
                    f"price={market.price_now}", event_id=event.id)

        certainty, certainty_evidence = nov.detect_certainty(
            f"{article.headline}. {article.body[:2000]}")

        stage_start = time.monotonic()
        materiality = self._assess_materiality(
            classification.event_type, article, certainty, financials)
        self._trace(session, correlation_id, "materiality", stage_start,
                    f"score={materiality.materiality_score}", event_id=event.id)

        offsets = neg.detect_textual_offsets(f"{article.headline} {article.body}")
        offsets += neg.structural_offsets(
            event_type=classification.event_type, certainty=certainty,
            materiality_missing=materiality.missing_inputs)
        dilution = neg.assess_dilution(financials)
        offsets += neg.dilution_offsets(dilution)

        stage_start = time.monotonic()
        normal_move, normal_basis = react.normal_expected_move_pct(
            realised_volatility_pct=market.structure.realised_volatility_pct,
            atr_pct=market.structure.atr_pct)
        abnormal = react.compute_abnormal_move(
            price_before=market.price_before, price_now=market.price_now,
            benchmark_before=market.benchmark_before, benchmark_now=market.benchmark_now,
            sector_before=market.sector_before, sector_now=market.sector_now,
            normal_move_pct=normal_move, normal_basis=normal_basis)
        analogue_move, analogue_n = self._get_analogue(classification.event_type,
                                                       market.structure)
        earliest_public = from_db(cluster.earliest_public_at_utc) or now
        room = react.assess_reaction_room(
            abnormal=abnormal, analogue_expected_move_pct=analogue_move,
            pre_event_runup_pct=market.pre_event_runup_pct,
            minutes_since_disclosure=amp.timedelta_minutes(earliest_public, now),
            halt_state=market.structure.halt_state,
            volume_multiple=market.structure.relative_volume)
        amplification = amp.assess_amplification(market.structure, now)
        execution = amp.assess_execution_quality(market.structure)
        self._trace(session, correlation_id, "reaction_and_structure", stage_start,
                    f"room={room.score} amp={amplification.score}", event_id=event.id)

        # ── adversarial investigation (§59-60) ──
        stage_start = time.monotonic()
        investigation = None
        invented: list[str] = []
        claude_available = self._investigator is not None
        if claude_available and screen.deep_analysis_warranted:
            try:
                evidence = InvestigationEvidence(
                    ticker=ticker,
                    company_name=known.get(ticker, ""),
                    headline=article.headline,
                    document_text=article.body[:40000],
                    source_tier=item.source_tier,
                    source_urls=[item.source_url] if item.source_url else [],
                    published_at_utc=str(from_db(item.published_at_utc) or ""),
                    classified_event_type=classification.event_type.value,
                    entity_confidence=resolution.confidence,
                    entity_evidence=resolution.evidence,
                    prior_public_items=[
                        {"published_at": str(m.published_at), "headline": m.headline}
                        for m in prior],
                    detected_certainty=certainty.value,
                    novelty={
                        "novelty_score": novelty.novelty_score,
                        "is_restatement": novelty.is_restatement,
                        "information_delta": novelty.information_delta,
                    },
                    retrieved_financials={
                        "market_cap": financials.market_cap,
                        "annual_revenue": financials.annual_revenue,
                        "cash": financials.cash,
                        "shares_outstanding": financials.shares_outstanding,
                    },
                    market_structure={
                        "free_float_shares": market.structure.free_float_shares,
                        "short_percent_float": market.structure.short_percent_float,
                        "relative_volume": market.structure.relative_volume,
                        "session": market.structure.session,
                    },
                    price_context={
                        "price_before": market.price_before,
                        "price_now": market.price_now,
                        "abnormal_move_pct": abnormal.abnormal_move_pct,
                        "pre_event_runup_pct": market.pre_event_runup_pct,
                    },
                    engine_detected_offsets=[
                        {"description": o.description, "severity": o.severity} for o in offsets],
                )
                investigation, latency = self._investigator.investigate(evidence)
                invented = self._investigator.invented_financials(
                    investigation, {"market_cap": financials.market_cap,
                                    "annual_revenue": financials.annual_revenue})
                session.add(ClaudeInvestigation(
                    event_id=event.id, pass_name="deep",
                    model=self._investigator.deep_model,
                    raw_json=investigation.model_dump(mode="json"),
                    invalidated=investigation.invalidate, latency_ms=latency))
                for offset in investigation.negative_offsets:
                    offsets.append(neg.Offset(
                        description=offset.description, severity=offset.severity,
                        source="claude", evidence=offset.evidence_quote or ""))
                if investigation.certainty:
                    certainty = investigation.certainty
            except InvestigationFailed as exc:
                claude_available = False
                session.add(ClaudeInvestigation(
                    event_id=event.id, pass_name="deep",
                    model=self._investigator.deep_model if self._investigator else "",
                    error=str(exc)))
                audit.log("catalyst", "investigation_failed", str(exc), level="ERROR")
        self._trace(session, correlation_id, "adversarial_review", stage_start,
                    f"available={claude_available}", event_id=event.id)

        severity = neg.aggregate_severity(offsets)

        # ── scoring (§64-74) ──
        stage_start = time.monotonic()
        scoring_inputs = ScoringInputs(
            event_type=classification.event_type,
            certainty=certainty,
            source_tier=SourceTier(item.source_tier),
            half_life=HALF_LIFE_BY_TYPE.get(classification.event_type,
                                            CatalystHalfLife.UNKNOWN),
            materiality_score=materiality.materiality_score or None,
            materiality_complete=materiality.data_complete,
            materiality_missing=materiality.missing_inputs,
            novelty_score=novelty.novelty_score,
            is_restatement=novelty.is_restatement,
            information_delta_score=self._delta_score(novelty),
            pre_event_runup_pct=market.pre_event_runup_pct,
            had_prior_signalling=novelty.prior_mention_count > 0,
            move_amplification=amplification.score,
            reaction_room=room.score,
            execution_quality=execution.score,
            negative_offset_severity=severity,
            market_data_unresolved=room.unresolved,
            entity_confidence=resolution.confidence,
            is_halted=not execution.tradeable,
            llm_event_quality=investigation.event_quality if investigation else None,
            llm_strategic_significance=(
                investigation.strategic_significance if investigation else None),
            llm_confidence_adjustment=(
                investigation.confidence_adjustment if investigation else 0.0),
            llm_invalidated=bool(investigation and investigation.invalidate),
            llm_invented_financials=bool(invented),
            event_age_seconds=(now - earliest_public).total_seconds(),
            corroborating_primary_sources=(
                1 if SourceTier(item.source_tier) == SourceTier.PRIMARY else 0),
            claude_available=claude_available,
            analogue_sample_size=analogue_n,
        )
        score = compute_catalyst_score(scoring_inputs)
        self._trace(session, correlation_id, "scoring", stage_start,
                    f"score={score.upside_catalyst_score}", event_id=event.id)

        self._persist(session, event, materiality, novelty, offsets, market,
                      abnormal, room, score, certainty, investigation)
        result.score = score.upside_catalyst_score

        audit.log("catalyst", "scored",
                  f"{ticker} {classification.event_type.value} → "
                  f"{score.upside_catalyst_score:.1f} ({score.band}) "
                  f"strength={score.catalyst_strength} surprise={score.surprise_novelty} "
                  f"room={score.reaction_room} offsets={severity:.1f} "
                  f"caps={score.caps_applied}")

        # ── pre-alert revalidation + dispatch (§79) ──
        stage_start = time.monotonic()
        decision = decide_alert(
            score,
            push_threshold=self._settings.catalyst_push_score,
            extreme_threshold=self._settings.catalyst_extreme_score,
            min_confidence=self._settings.catalyst_min_confidence,
            event_age_seconds=scoring_inputs.event_age_seconds,
            max_age_seconds=self._settings.news_max_age_seconds,
            price_revalidated=not room.unresolved)

        if decision.should_alert:
            context = AlertContext(
                ticker=ticker,
                event_label=classification.event_type.value.replace("_", " ").title(),
                headline=article.headline,
                price=market.price_now,
                move_since_disclosure_pct=abnormal.raw_move_pct,
                materiality_line=self._materiality_line(materiality))
            alerted = self._notifier.send(
                session, event_id=event.id, score_id=None,
                canonical=cluster.cluster_key, score=score,
                context=context, decision=decision)
            result.alerted = alerted
            if alerted:
                event.state = CatalystState.ALERTED.value
                event.state_changed_at = now
        else:
            audit.log("catalyst", "alert_withheld", f"{ticker}: {decision.reason}")
        self._trace(session, correlation_id, "notification", stage_start,
                    decision.reason, event_id=event.id)

        if event.state != CatalystState.ALERTED.value:
            event.state = CatalystState.SCORED.value
            event.state_changed_at = now
        session.flush()
        result.state = CatalystState(event.state)
        result.detail = decision.reason
        return result

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _delta_score(novelty: nov.NoveltyResult) -> float | None:
        if novelty.certainty_before is None:
            return None
        delta = novelty.certainty_after - novelty.certainty_before
        return round(max(0.0, min(delta, 1.0)) * 10.0, 2)

    @staticmethod
    def _materiality_line(result: mat.MaterialityResult) -> str:
        if result.annualised_to_revenue is not None:
            return f"Annualised value = {result.annualised_to_revenue:.0%} of revenue"
        if result.value_to_revenue is not None:
            return f"Value = {result.value_to_revenue:.0%} of revenue"
        if result.value_to_market_cap is not None:
            return f"Value = {result.value_to_market_cap:.0%} of market cap"
        return ""

    def _prior_mentions(self, session: Session, ticker: str, cluster_id: int,
                        now: datetime) -> list[nov.PriorMention]:
        """Everything already public about this company in the lookback window."""
        window = now - timedelta(days=45)
        rows = (session.query(NewsItem)
                .filter(NewsItem.cluster_id.isnot(None))
                .filter(NewsItem.cluster_id != cluster_id)
                .filter(NewsItem.received_at_utc >= window)
                .order_by(NewsItem.id.desc()).limit(200).all())
        mentions: list[nov.PriorMention] = []
        for row in rows:
            if ticker.upper() not in [t.upper() for t in (row.tickers or [])]:
                cluster = session.get(EventCluster, row.cluster_id)
                if cluster is None or cluster.ticker.upper() != ticker.upper():
                    continue
            certainty, _ = nov.detect_certainty(f"{row.headline}. {row.body[:800]}")
            mentions.append(nov.PriorMention(
                published_at=from_db(row.published_at_utc) or from_db(row.received_at_utc) or now,
                headline=row.headline, certainty=certainty, source=row.provider))
        return mentions

    def _get_financials(self, session: Session, ticker: str) -> mat.CompanyFinancials:
        if self._financials_fn is not None:
            return self._financials_fn(ticker)
        company = session.query(Company).filter_by(ticker=ticker.upper()).first()
        if company is None:
            return mat.CompanyFinancials()
        return mat.CompanyFinancials(market_cap=company.market_cap)

    def _get_market_context(self, ticker: str, now: datetime) -> MarketContextInputs:
        if self._market_context_fn is not None:
            return self._market_context_fn(ticker, now)
        return MarketContextInputs(
            structure=amp.MarketStructure(session=amp.market_session(now)))

    def _get_analogue(self, event_type: EventType,
                      structure: amp.MarketStructure) -> tuple[float | None, int]:
        """Expected move from comparable historical events (§40).

        Until the analogue store has real data this returns a volatility-scaled
        placeholder with sample size 0, which the confidence engine penalises.
        """
        if self._analogue_fn is not None:
            return self._analogue_fn(event_type, structure)
        return amp.default_analogue_move_pct(structure), 0

    def _assess_materiality(self, event_type: EventType, article: NewsArticle,
                            certainty: Certainty,
                            financials: mat.CompanyFinancials) -> mat.MaterialityResult:
        text = f"{article.headline}\n{article.body}"
        if mat.is_contract_event(event_type):
            amounts = mat.parse_all_money(text)
            headline_value = max(amounts) if amounts else None
            guaranteed = mat.parse_money(
                _after_keyword(text, ("guaranteed", "firm order", "minimum commitment",
                                      "initially funded", "initial funding", "funded value")))
            multi = bool(_search_any(text, ("multiple-award", "multi-award",
                                            "multiple award", "idiq",
                                            "indefinite delivery")))
            term = _parse_years(text)
            inputs = mat.ContractInputs(
                headline_value=headline_value,
                guaranteed_value=guaranteed,
                ceiling_value=headline_value,
                term_years=term,
                single_award=False if multi else None,
                certainty=certainty)
            return mat.assess_contract(inputs, financials)

        if event_type in (EventType.BUYBACK_AUTHORISATION, EventType.BUYBACK_EXECUTED):
            amount = mat.parse_money(text)
            executed = amount if event_type == EventType.BUYBACK_EXECUTED else None
            authorised = amount if event_type == EventType.BUYBACK_AUTHORISATION else None
            replaces = bool(_search_any(text, ("replaces", "replacing the existing")))
            return mat.assess_buyback(
                mat.BuybackInputs(authorised_amount=authorised, executed_amount=executed,
                                  replaces_existing=replaces or None), financials)

        if event_type == EventType.SPECIAL_DIVIDEND:
            per_share = _parse_per_share(text)
            return mat.assess_special_dividend(per_share, None, financials)

        if event_type in (EventType.TAKEOVER_OFFER, EventType.TENDER_OFFER,
                          EventType.MERGER_ANNOUNCEMENT, EventType.ACQUISITION):
            return mat.assess_deal(
                mat.DealInputs(is_target=event_type in (EventType.TAKEOVER_OFFER,
                                                        EventType.TENDER_OFFER),
                               offer_price_per_share=_parse_per_share(text),
                               current_price=financials.share_price,
                               purchase_price_total=mat.parse_money(text),
                               certainty=certainty), financials)

        if event_type in (EventType.LAWSUIT_WIN, EventType.SETTLEMENT,
                          EventType.PATENT_RULING):
            return mat.assess_legal_award(
                mat.parse_money(text),
                appeal_likely=bool(_search_any(text, ("appeal",))) or None,
                insurance_covered=None, financials=financials)

        # Generic: scale any stated amount against the company.
        amount = mat.parse_money(text)
        if amount is None:
            return mat.MaterialityResult(
                0.0, basis="no_stated_value",
                missing_inputs=financials.missing("market_cap", "annual_revenue"),
                notes=["no monetary value stated — materiality not quantifiable"])
        result = mat.MaterialityResult(0.0, headline_value=amount, expected_value=amount,
                                       basis="generic")
        if financials.annual_revenue:
            result.value_to_revenue = amount / financials.annual_revenue
            result.materiality_score = round(
                min(mat._score_from_ratio(result.value_to_revenue), 10.0), 2)
        elif financials.market_cap:
            result.value_to_market_cap = amount / financials.market_cap
            result.materiality_score = round(
                min(mat._score_from_ratio(result.value_to_market_cap), 10.0), 2)
        else:
            result.missing_inputs = ["market_cap", "annual_revenue"]
        return result

    def _create_event(self, session: Session, cluster: EventCluster, item: NewsItem,
                      ticker: str, classification: classify_mod.Classification,
                      novelty: nov.NoveltyResult) -> CatalystEvent:
        company = session.query(Company).filter_by(ticker=ticker.upper()).first()
        event = CatalystEvent(
            cluster_id=cluster.id, company_id=company.id if company else None,
            ticker=ticker.upper(),
            event_type=classification.event_type.value,
            event_category=category_for(classification.event_type).value,
            headline=item.headline, primary_url=item.source_url,
            document_text=item.body[:100000],
            state=CatalystState.CLASSIFIED.value)
        session.add(event)
        session.flush()
        return event

    def _record_source(self, session: Session, event_id: int, item: NewsItem) -> None:
        exists = (session.query(CatalystSource)
                  .filter_by(event_id=event_id, news_item_id=item.id).first())
        if exists:
            return
        session.add(CatalystSource(
            event_id=event_id, news_item_id=item.id, tier=item.source_tier,
            provider=item.provider, url=item.source_url,
            published_at_utc=item.published_at_utc,
            is_primary_document=SourceTier(item.source_tier) == SourceTier.PRIMARY))
        session.flush()

    def _link_earnings_event(self, session: Session, event: CatalystEvent,
                             ticker: str) -> None:
        """§108 — derivative earnings coverage links to the existing event
        rather than creating a parallel catalyst."""
        from app.db.models import EarningsEvent
        company = session.query(Company).filter_by(ticker=ticker.upper()).first()
        if company is None:
            return
        earnings = (session.query(EarningsEvent)
                    .filter_by(company_id=company.id)
                    .order_by(EarningsEvent.id.desc()).first())
        if earnings is not None:
            event.earnings_event_id = earnings.id
            session.flush()

    def _persist(self, session: Session, event: CatalystEvent,
                 materiality: mat.MaterialityResult, novelty: nov.NoveltyResult,
                 offsets: list[neg.Offset], market: MarketContextInputs,
                 abnormal: react.AbnormalMove, room: react.ReactionRoom,
                 score, certainty: Certainty, investigation) -> None:
        event.certainty = certainty.value
        event.half_life = HALF_LIFE_BY_TYPE.get(
            EventType(event.event_type), CatalystHalfLife.UNKNOWN).value
        if investigation is not None:
            event.summary = investigation.summary[:2000]
            for fact in investigation.facts:
                session.add(EventFact(
                    event_id=event.id, name=fact.name[:64], value_text=fact.value_text[:2000],
                    value_number=fact.value_number, unit=(fact.unit or "")[:24],
                    quote=fact.quote[:2000], extracted_by="claude"))

        session.add(NoveltyAnalysis(
            event_id=event.id, novelty_score=novelty.novelty_score,
            earliest_known_public_at_utc=novelty.earliest_known_public_at,
            prior_mentions=novelty.prior_mention_count,
            is_restatement=novelty.is_restatement,
            information_delta=novelty.information_delta[:2000],
            certainty_before=novelty.certainty_before,
            certainty_after=novelty.certainty_after,
            notes="; ".join(novelty.notes)[:2000]))

        session.add(MaterialityAnalysis(
            event_id=event.id, headline_value=materiality.headline_value,
            guaranteed_value=materiality.guaranteed_value,
            expected_value=materiality.expected_value,
            annualised_value=materiality.annualised_value,
            value_to_market_cap=materiality.value_to_market_cap,
            value_to_revenue=materiality.value_to_revenue,
            annualised_to_revenue=materiality.annualised_to_revenue,
            value_to_ebitda=materiality.value_to_ebitda,
            materiality_score=materiality.materiality_score,
            basis=materiality.basis[:32],
            missing_inputs=materiality.missing_inputs,
            notes="; ".join(materiality.notes)[:2000]))

        for offset in offsets:
            session.add(NegativeOffsetRow(
                event_id=event.id, description=offset.description[:2000],
                severity=offset.severity, evidence_quote=offset.evidence[:2000],
                detected_by=offset.source))

        structure = market.structure
        session.add(MarketStructureSnapshot(
            event_id=event.id, market_cap=structure.market_cap,
            free_float_shares=structure.free_float_shares,
            shares_outstanding=structure.shares_outstanding,
            avg_dollar_volume=structure.avg_dollar_volume,
            relative_volume=structure.relative_volume, spread_pct=structure.spread_pct,
            short_percent_float=structure.short_percent_float,
            days_to_cover=structure.days_to_cover,
            short_interest_as_of=structure.short_interest_as_of,
            realised_volatility=structure.realised_volatility_pct,
            atr_pct=structure.atr_pct, session=structure.session,
            halt_state=structure.halt_state.value,
            missing_inputs=structure.missing()))

        session.add(ReactionAnalysis(
            event_id=event.id,
            pre_event_runup_pct=market.pre_event_runup_pct,
            move_since_disclosure_pct=abnormal.raw_move_pct,
            abnormal_move_pct=abnormal.abnormal_move_pct,
            benchmark_move_pct=abnormal.benchmark_move_pct,
            sector_move_pct=abnormal.sector_move_pct,
            move_multiple=abnormal.move_multiple,
            analogue_expected_move_pct=room.analogue_expected_move_pct,
            reaction_room_score=room.score, unresolved=room.unresolved,
            notes="; ".join(room.notes + abnormal.notes)[:2000]))

        session.add(CatalystScore(
            event_id=event.id, model_version=score.model_version, revision=1,
            catalyst_strength=score.catalyst_strength,
            surprise_novelty=score.surprise_novelty,
            move_amplification=score.move_amplification,
            reaction_room=score.reaction_room, confidence=score.confidence,
            execution_quality=score.execution_quality,
            negative_offset_severity=score.negative_offset_severity,
            upside_catalyst_score=score.upside_catalyst_score,
            component_breakdown=score.component_breakdown,
            caps_applied=score.caps_applied, gates_failed=score.gates_failed,
            fundamental_impact=score.fundamental_impact,
            immediate_reaction_potential=score.immediate_reaction_potential))
        session.flush()


# ── small text helpers (deterministic, no LLM) ───────────────────────────────


def _search_any(text: str, needles: tuple[str, ...]) -> str | None:
    lowered = text.lower()
    for needle in needles:
        if needle in lowered:
            return needle
    return None


def _after_keyword(text: str, keywords: tuple[str, ...], window: int = 160) -> str:
    """Text following a keyword — used to find the amount attached to
    'guaranteed', 'initially funded' etc. rather than the headline figure."""
    lowered = text.lower()
    for keyword in keywords:
        index = lowered.find(keyword)
        if index >= 0:
            return text[index:index + window]
    return ""


def _parse_years(text: str) -> float | None:
    import re
    match = re.search(r"\b(\d{1,2}(?:\.\d)?)[- ]year\b", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r"\bover\s+(\d{1,2})\s+years\b", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def _parse_per_share(text: str) -> float | None:
    import re
    match = re.search(r"\$\s?([0-9]+(?:\.[0-9]+)?)\s*(?:per share|/share|a share)",
                      text, re.IGNORECASE)
    return float(match.group(1)) if match else None
