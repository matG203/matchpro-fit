"""Adaptive polling plan (spec §ADAPTIVE MONITORING). Pure and testable."""
from __future__ import annotations

from datetime import datetime

from app.config import Settings
from app.domain.timeutil import ensure_utc


def poll_interval_seconds(now: datetime, expected_release: datetime | None,
                          settings: Settings) -> float | None:
    """Seconds until this event should be checked again; None = don't poll yet.

    Once past expected release + delayed_grace_minutes the monitor marks the
    event DELAYED_OR_UNVERIFIED (handled by the caller, not here).
    """
    if expected_release is None:
        return float(settings.monitor_far_interval_seconds)

    delta = (ensure_utc(expected_release) - ensure_utc(now)).total_seconds()

    if delta > settings.monitor_wake_before_minutes * 60:
        return None
    if delta > 15 * 60:
        return float(settings.monitor_far_interval_seconds)
    if delta > 0:
        return float(settings.monitor_near_interval_seconds)
    since = -delta
    if since <= settings.monitor_burst_window_minutes * 60:
        # SEC etiquette floor of 15s regardless of configuration
        return float(max(settings.monitor_burst_interval_seconds, 15))
    if since <= 120 * 60:
        return float(settings.monitor_cooldown_interval_seconds)
    return float(settings.monitor_late_interval_seconds)
