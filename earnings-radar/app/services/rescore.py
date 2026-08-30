"""Re-scoring — revisiting a catalyst once the price data catches up.

On a delayed feed (Polygon's Starter plan is 15 minutes behind) a filing is
detected and scored before the market's reaction is visible. The first score is
therefore honest but incomplete: Reaction Room is unresolved, and the score is
capped for it. This pass returns when the data arrives, recomputes the
market-derived half of the score, and writes a new revision.

What it deliberately does **not** do:

  * **Re-run Claude.** The adversarial review, the materiality maths and the
    novelty analysis do not change because a price arrived. The original
    `ScoringInputs` are stored verbatim on the score row, so only the
    market-derived fields are replaced. Re-scoring costs no API spend.
  * **Re-alert on noise.** The alert layer already deduplicates by score band,
    so a revision that stays in the same band is silent. A revision that
    crosses into a higher band is a genuinely new decision and does alert.
  * **Rewrite history.** The original score is kept and marked superseded. What
    the system believed at 07:12 with the data it had is part of the record.

On a real-time feed this pass finds nothing to do and costs one query.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.catalyst import amplification as amp
from app.catalyst import reaction as react
from app.catalyst.alerts import AlertContext, CatalystNotifier, decide_alert
from app.catalyst.enums import CatalystState, EventType
from app.catalyst.pipeline import MarketContextInputs, _tape_stopped
from app.catalyst.scoring import ScoringInputs, compute_catalyst_score
from app.config import Settings
from app.db.catalyst_models import (
    CatalystEvent,
    CatalystScore,
    EventCluster,
    MarketStructureSnapshot,
    ReactionAnalysis,
)
from app.db.models import Company
from app.domain.timeutil import from_db, utcnow
from app.services.audit import AuditService

logger = logging.getLogger("earnings_radar.catalyst.rescore")


@dataclass
class RescoreResult:
    considered: int = 0
    rescored: int = 0
    still_waiting: int = 0
    alerted: int = 0
    changes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"rescored {self.rescored}/{self.considered}, "
                f"waiting {self.still_waiting}, alerted {self.alerted}")


class RescoreService:
    def __init__(self, *, settings: Settings, notifier: CatalystNotifier,
                 market_context_fn=None, analogue_fn=None):
        self._settings = settings
        self._notifier = notifier
        self._market_context_fn = market_context_fn
        self._analogue_fn = analogue_fn

    @property
    def available(self) -> bool:
        return self._market_context_fn is not None

    # ── main pass ─────────────────────────────────────────────────────────────

    def run(self, session: Session, now: datetime | None = None) -> RescoreResult:
        now = now or utcnow()
        result = RescoreResult()
        if not self.available:
            return result

        window = now - timedelta(hours=self._settings.rescore_window_hours)
        pending = (session.query(ReactionAnalysis)
                   .filter(ReactionAnalysis.move_observable.is_(False))
                   .filter(ReactionAnalysis.rescored_at_utc.is_(None))
                   .all())

        for reaction in pending:
            event = session.get(CatalystEvent, reaction.event_id)
            if event is None:
                continue
            disclosure = self._disclosure_time(session, event)
            if disclosure is None or disclosure < window:
                # Too old to be worth pricing; mark it done so the query stays
                # small rather than accumulating stragglers forever.
                reaction.rescored_at_utc = now
                continue

            result.considered += 1
            observable_through = now - timedelta(
                seconds=max(0.0, self._settings.market_data_delay_seconds))
            if observable_through <= disclosure:
                result.still_waiting += 1
                continue

            try:
                if self._rescore(session, event, reaction, disclosure, now, result):
                    result.rescored += 1
            except Exception as exc:
                logger.exception("re-score failed for event %s", event.id)
                result.errors.append(f"event {event.id}: {exc}")

        if result.rescored:
            AuditService(session).log("catalyst", "rescore", result.summary(), level="INFO")
        return result

    # ── one event ─────────────────────────────────────────────────────────────

    def _rescore(self, session: Session, event: CatalystEvent,
                 reaction: ReactionAnalysis, disclosure: datetime,
                 now: datetime, result: RescoreResult) -> bool:
        previous = (session.query(CatalystScore)
                    .filter_by(event_id=event.id)
                    .order_by(CatalystScore.revision.desc()).first())
        if previous is None or not previous.scoring_inputs:
            # Nothing to rebuild from. Recording the attempt stops this event
            # being retried on every pass forever.
            reaction.rescored_at_utc = now
            return False

        market = self._market_context(session, event.ticker, now, disclosure)
        if not market.move_observable:
            result.still_waiting += 1
            return False

        inputs = ScoringInputs.from_dict(previous.scoring_inputs)
        abnormal, room, amplification, execution = self._recompute(
            market, inputs, disclosure, now)

        # Only the market-derived half is replaced. Claude's judgement, the
        # materiality maths and the novelty analysis are carried over untouched.
        inputs.move_amplification = amplification.score
        inputs.reaction_room = room.score
        inputs.execution_quality = execution.score
        inputs.market_data_unresolved = room.unresolved
        inputs.is_halted = not execution.tradeable
        inputs.pre_event_runup_pct = market.pre_event_runup_pct
        inputs.event_age_seconds = (now - disclosure).total_seconds()

        score = compute_catalyst_score(inputs)
        moved = score.upside_catalyst_score - previous.upside_catalyst_score

        previous.superseded = True
        session.add(CatalystScore(
            event_id=event.id, model_version=score.model_version,
            revision=previous.revision + 1,
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
            immediate_reaction_potential=score.immediate_reaction_potential,
            scoring_inputs=inputs.to_dict(),
            revision_reason="delayed_data_arrived"))

        self._update_reaction(reaction, market, abnormal, room, now)
        self._update_structure(session, event.id, market)

        result.changes.append(
            f"{event.ticker} {previous.upside_catalyst_score:.1f} → "
            f"{score.upside_catalyst_score:.1f} ({moved:+.1f})")

        if self._maybe_alert(session, event, score, market, abnormal, now):
            result.alerted += 1

        session.flush()
        return True

    def _recompute(self, market: MarketContextInputs, inputs: ScoringInputs,
                   disclosure: datetime, now: datetime):
        normal_move, normal_basis = react.normal_expected_move_pct(
            realised_volatility_pct=market.structure.realised_volatility_pct,
            atr_pct=market.structure.atr_pct)
        abnormal = react.compute_abnormal_move(
            price_before=market.price_before, price_now=market.price_now,
            benchmark_before=market.benchmark_before, benchmark_now=market.benchmark_now,
            sector_before=market.sector_before, sector_now=market.sector_now,
            normal_move_pct=normal_move, normal_basis=normal_basis)

        analogue_move, _ = self._analogue(
            EventType(inputs.event_type) if isinstance(inputs.event_type, str)
            else inputs.event_type, market.structure)

        room = react.assess_reaction_room(
            abnormal=abnormal, analogue_expected_move_pct=analogue_move,
            pre_event_runup_pct=market.pre_event_runup_pct,
            minutes_since_disclosure=amp.timedelta_minutes(disclosure, now),
            halt_state=market.structure.halt_state,
            volume_multiple=market.structure.relative_volume,
            prices_stale=_tape_stopped(market.structure),
            move_observable=market.move_observable,
            data_delay_seconds=market.data_delay_seconds)

        return (abnormal, room,
                amp.assess_amplification(market.structure, now),
                amp.assess_execution_quality(market.structure))

    # ── persistence ───────────────────────────────────────────────────────────

    @staticmethod
    def _update_reaction(reaction: ReactionAnalysis, market: MarketContextInputs,
                         abnormal: react.AbnormalMove, room: react.ReactionRoom,
                         now: datetime) -> None:
        reaction.move_since_disclosure_pct = abnormal.raw_move_pct
        reaction.abnormal_move_pct = abnormal.abnormal_move_pct
        reaction.benchmark_move_pct = abnormal.benchmark_move_pct
        reaction.sector_move_pct = abnormal.sector_move_pct
        reaction.move_multiple = abnormal.move_multiple
        reaction.analogue_expected_move_pct = room.analogue_expected_move_pct
        reaction.reaction_room_score = room.score
        reaction.unresolved = room.unresolved
        reaction.pre_event_runup_pct = market.pre_event_runup_pct
        reaction.observable_through_utc = market.observable_through
        reaction.move_observable = True
        reaction.rescored_at_utc = now
        reaction.notes = "; ".join(room.notes + abnormal.notes)[:2000]

    @staticmethod
    def _update_structure(session: Session, event_id: int,
                          market: MarketContextInputs) -> None:
        row = (session.query(MarketStructureSnapshot)
               .filter_by(event_id=event_id).first())
        if row is None:
            return
        structure = market.structure
        row.relative_volume = structure.relative_volume
        row.spread_pct = structure.spread_pct
        row.quote_stale_seconds = structure.quote_stale_seconds
        row.session = structure.session
        row.missing_inputs = structure.missing()

    # ── alerting ──────────────────────────────────────────────────────────────

    def _maybe_alert(self, session: Session, event: CatalystEvent, score,
                     market: MarketContextInputs, abnormal: react.AbnormalMove,
                     now: datetime) -> bool:
        cluster = session.get(EventCluster, event.cluster_id)
        disclosure = self._disclosure_time(session, event) or now

        decision = decide_alert(
            score,
            push_threshold=self._settings.catalyst_push_score,
            extreme_threshold=self._settings.catalyst_extreme_score,
            min_confidence=self._settings.catalyst_min_confidence,
            event_age_seconds=(now - disclosure).total_seconds(),
            max_age_seconds=self._settings.news_max_age_seconds,
            price_revalidated=True)
        if not decision.should_alert:
            return False

        context = AlertContext(
            ticker=event.ticker,
            event_label=event.event_type.replace("_", " ").title(),
            headline=event.headline,
            price=market.price_now,
            move_since_disclosure_pct=abnormal.raw_move_pct,
            materiality_line="",
            extras=["Re-scored — delayed price data now in"])

        alerted = self._notifier.send(
            session, event_id=event.id, score_id=None,
            canonical=cluster.cluster_key if cluster else f"event-{event.id}",
            score=score, context=context, decision=decision)
        if alerted:
            event.state = CatalystState.ALERTED.value
            event.state_changed_at = now
        return alerted

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _disclosure_time(session: Session, event: CatalystEvent) -> datetime | None:
        cluster = session.get(EventCluster, event.cluster_id)
        if cluster is None:
            return None
        return from_db(cluster.earliest_public_at_utc) or from_db(event.created_at)

    def _market_context(self, session: Session, ticker: str, now: datetime,
                        disclosure: datetime) -> MarketContextInputs:
        company = session.query(Company).filter_by(ticker=ticker.upper()).first()
        return self._market_context_fn(
            ticker, now, disclosure,
            company.sector if company else "",
            company.industry if company else "")

    def _analogue(self, event_type, structure) -> tuple[float | None, int]:
        if self._analogue_fn is not None:
            return self._analogue_fn(event_type, structure)
        return amp.default_analogue_move_pct(structure), 0
