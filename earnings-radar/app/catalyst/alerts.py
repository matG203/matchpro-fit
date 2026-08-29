"""Catalyst alert formatting, gating and deduplication (spec §77-81).

Notifications stay short enough to read at a glance, and re-alerting on the
same event requires a genuine material change — not a score drifting from
9.1 to 9.2.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.catalyst.scoring import CatalystScoreResult
from app.db.catalyst_models import CatalystAlert
from app.domain.timeutil import utcnow
from app.providers.base import NotifierProvider, ProviderError


@dataclass
class AlertContext:
    ticker: str
    event_label: str
    headline: str
    price: float | None = None
    move_since_disclosure_pct: float | None = None
    materiality_line: str = ""
    extras: list[str] = field(default_factory=list)


def format_alert(score: CatalystScoreResult, context: AlertContext,
                 extreme: bool = False) -> tuple[str, str]:
    """Returns (title, body). Title carries the decision; body carries the why."""
    marker = "🔥 EXTREME CATALYST" if extreme else "🚨 CATALYST"
    title = f"{marker} {score.upside_catalyst_score:.1f} — {context.ticker.upper()}"

    lines = [context.event_label]
    if context.materiality_line:
        lines.append(context.materiality_line)
    lines.extend(context.extras)
    lines.append(
        f"Catalyst {score.catalyst_strength:.1f} · Surprise {score.surprise_novelty:.1f} · "
        f"Amp {score.move_amplification:.1f} · Room {score.reaction_room:.1f}")
    if context.move_since_disclosure_pct is not None:
        lines.append(f"Since disclosure: {context.move_since_disclosure_pct:+.1f}%")
    if score.negative_offset_severity >= 4.0:
        lines.append(f"⚠ Offsets {score.negative_offset_severity:.1f}/10")
    return title, "\n".join(lines)


def dedup_key(canonical: str, model_version: str, band: str) -> str:
    """One alert per (event, model version, band). Crossing into a higher band
    is a new decision; drifting within one is not."""
    return f"catalyst|{canonical}|{model_version}|{band}"


@dataclass
class AlertDecision:
    should_alert: bool
    reason: str
    extreme: bool = False
    band: str = ""


def decide_alert(score: CatalystScoreResult, *, push_threshold: float,
                 extreme_threshold: float, min_confidence: float,
                 event_age_seconds: float | None,
                 max_age_seconds: float,
                 previous_band: str | None = None,
                 previous_score: float | None = None,
                 price_revalidated: bool = True) -> AlertDecision:
    """§76-79 — decide whether this score warrants pushing to a phone."""
    band = score.band

    if score.rejected:
        return AlertDecision(False, f"rejected: {score.reject_reason}", band=band)
    if score.upside_catalyst_score < push_threshold:
        return AlertDecision(False,
                             f"score {score.upside_catalyst_score:.1f} below push threshold "
                             f"{push_threshold:.1f}", band=band)
    if score.confidence < min_confidence:
        return AlertDecision(False,
                             f"confidence {score.confidence:.1f} below {min_confidence:.1f}",
                             band=band)
    if not price_revalidated:
        return AlertDecision(False, "price could not be revalidated before sending", band=band)
    if event_age_seconds is not None and event_age_seconds > max_age_seconds:
        return AlertDecision(False,
                             f"event {event_age_seconds:.0f}s old exceeds freshness limit "
                             f"{max_age_seconds:.0f}s", band=band)

    # §81 — suppress noise on an unchanged event.
    if previous_band == band:
        if previous_score is not None and score.upside_catalyst_score - previous_score < 0.5:
            return AlertDecision(False,
                                 f"already alerted in band {band}; score moved "
                                 f"{previous_score:.1f} → {score.upside_catalyst_score:.1f}",
                                 band=band)

    extreme = score.upside_catalyst_score >= extreme_threshold
    return AlertDecision(True, "meets push criteria", extreme=extreme, band=band)


class CatalystNotifier:
    """Idempotent dispatch — the key is reserved before the send, so a crash
    mid-flight cannot double-notify."""

    def __init__(self, notifiers: list[NotifierProvider]):
        self._notifiers = [n for n in notifiers if n.enabled()]

    @property
    def channels(self) -> list[str]:
        return [n.name for n in self._notifiers]

    def send(self, session: Session, *, event_id: int, score_id: int | None,
             canonical: str, score: CatalystScoreResult, context: AlertContext,
             decision: AlertDecision) -> bool:
        title, body = format_alert(score, context, extreme=decision.extreme)
        sent_any = False

        for notifier in self._notifiers:
            key = dedup_key(canonical, score.model_version, decision.band) + f"|{notifier.name}"
            existing = session.query(CatalystAlert).filter_by(dedup_key=key).first()
            if existing and existing.status == "SENT":
                continue
            record = existing or CatalystAlert(event_id=event_id, dedup_key=key)
            record.score_id = score_id
            record.band = decision.band
            record.score_at_alert = score.upside_catalyst_score
            record.price_at_alert = context.price
            record.move_at_alert_pct = context.move_since_disclosure_pct
            record.title = title
            record.body = body
            session.add(record)
            session.flush()
            try:
                notifier.send(title, body, high_priority=decision.extreme)
                record.status = "SENT"
                record.sent_at = utcnow()
                sent_any = True
            except ProviderError as exc:
                record.status = "FAILED"
                record.error = str(exc)
        return sent_any
