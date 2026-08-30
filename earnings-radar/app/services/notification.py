"""NotificationService — minimal push, idempotent, multi-channel.

Format (spec §PUSH NOTIFICATION RULES):   🔥 ESTC — 9.2/10
Details stay in the dashboard; the push is just ticker + rating.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models import Notification
from app.domain.timeutil import utcnow
from app.providers.base import NotifierProvider, ProviderError

logger = logging.getLogger("earnings_radar.notify")


def score_emoji(score: float) -> str:
    if score >= 9.0:
        return "🔥"
    if score >= 8.0:
        return "🟢"
    if score >= 7.0:
        return "🟡"
    return "🔴"


def format_notification(ticker: str, score: float, *, needs_verification: bool = False,
                        provisional: bool = False) -> tuple[str, str]:
    """Returns (title, body). Intentionally minimal."""
    emoji = score_emoji(score)
    core = f"{ticker.upper()} — {score:.1f}/10"
    title = f"{emoji} {core}" if score >= 9.0 else f"{core} {emoji}"
    suffix = ""
    if needs_verification:
        suffix = " (unverified)"
    elif provisional:
        suffix = " (provisional)"
    return title, core + suffix


class NotificationService:
    def __init__(self, notifiers: list[NotifierProvider], *, min_score: float,
                 high_score_alert: float, min_confidence: float):
        self._notifiers = [n for n in notifiers if n.enabled()]
        self._min_score = min_score
        self._high_score_alert = high_score_alert
        self._min_confidence = min_confidence

    def band(self, score: float, needs_verification: bool = False) -> str:
        """Coarse decision bands. Re-notifying is warranted only when a score
        crosses one of these — a drift from 9.1 to 9.2 is not a new decision."""
        if score < self._min_score:
            return "below"
        if score >= self._high_score_alert and not needs_verification:
            return "high"
        return "normal"

    def notify_score(self, session: Session, *, release_id: int, canonical_key: str,
                     ticker: str, score: float, confidence: float,
                     model_version: str, provisional: bool = False,
                     revision: int = 1) -> bool:
        """Idempotent dispatch. Returns True if at least one channel sent.

        `revision` lets a genuinely new decision through the dedup key — a
        re-score that crossed a band. The caller decides, because only it knows
        whether the band actually changed.
        """
        if score < self._min_score:
            return False
        needs_verification = confidence < self._min_confidence
        title, body = format_notification(ticker, score,
                                          needs_verification=needs_verification,
                                          provisional=provisional)
        high_priority = score >= self._high_score_alert and not needs_verification

        sent_any = False
        for notifier in self._notifiers:
            suffix = "" if revision <= 1 else f"|r{revision}"
            dedup_key = f"{canonical_key}|{model_version}|{notifier.name}{suffix}"
            existing = session.query(Notification).filter_by(dedup_key=dedup_key).first()
            if existing and existing.status == "SENT":
                continue
            record = existing or Notification(
                release_id=release_id, dedup_key=dedup_key, channel=notifier.name)
            record.title, record.body = title, body
            session.add(record)
            session.flush()          # reserve the dedup key before dispatch
            try:
                notifier.send(title, body, high_priority=high_priority)
                record.status = "SENT"
                record.sent_at = utcnow()
                sent_any = True
            except ProviderError as exc:
                record.status = "FAILED"
                record.error = str(exc)
                logger.error("notification via %s failed: %s", notifier.name, exc)
        return sent_any
