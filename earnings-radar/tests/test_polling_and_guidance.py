"""Adaptive polling schedule and guidance classification."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.config import Settings
from app.domain.enums import GuidanceStatus
from app.domain.timeutil import UTC
from app.services.guidance import classify_guidance
from app.services.polling import poll_interval_seconds

SETTINGS = Settings(database_url="sqlite://")
RELEASE = datetime(2026, 8, 27, 20, 5, tzinfo=UTC)


def at(minutes_from_release: float) -> datetime:
    return RELEASE + timedelta(minutes=minutes_from_release)


# ── polling cadence ──────────────────────────────────────────────────────────

def test_no_polling_far_before_release():
    assert poll_interval_seconds(at(-90), RELEASE, SETTINGS) is None


def test_five_minute_polling_from_sixty_to_fifteen_minutes_before():
    assert poll_interval_seconds(at(-45), RELEASE, SETTINGS) == 300


def test_one_minute_polling_in_the_final_quarter_hour():
    assert poll_interval_seconds(at(-10), RELEASE, SETTINGS) == 60


def test_burst_polling_around_the_release():
    assert poll_interval_seconds(at(1), RELEASE, SETTINGS) == 20
    assert poll_interval_seconds(at(29), RELEASE, SETTINGS) == 20


def test_burst_interval_never_goes_below_sec_etiquette_floor():
    aggressive = Settings(database_url="sqlite://", monitor_burst_interval_seconds=1)
    assert poll_interval_seconds(at(1), RELEASE, aggressive) == 15


def test_cadence_relaxes_after_the_burst_window():
    assert poll_interval_seconds(at(60), RELEASE, SETTINGS) == 60
    assert poll_interval_seconds(at(180), RELEASE, SETTINGS) == 300


def test_unknown_release_time_still_polls():
    assert poll_interval_seconds(at(0), None, SETTINGS) == 300


# ── guidance classification ──────────────────────────────────────────────────

def test_bottom_end_lift_is_narrowed_not_raised():
    # Spec example: $10.0-10.5bn -> $10.2-10.5bn is NOT a major raise
    result = classify_guidance(10.0, 10.5, 10.2, 10.5)
    assert result.status == GuidanceStatus.NARROWED
    assert "bottom-end" in result.note


def test_full_range_raise_is_raised():
    result = classify_guidance(10.0, 10.5, 10.6, 11.0)
    assert result.status == GuidanceStatus.RAISED
    assert result.magnitude_pct > 0


def test_lowered_guidance_is_detected():
    result = classify_guidance(10.0, 10.5, 9.0, 9.8)
    assert result.status == GuidanceStatus.LOWERED
    assert result.magnitude_pct < 0


def test_unchanged_guidance_is_maintained():
    assert classify_guidance(10.0, 10.5, 10.0, 10.5).status == GuidanceStatus.MAINTAINED


def test_missing_guidance_is_none():
    assert classify_guidance(10.0, 10.5, None, None).status == GuidanceStatus.NONE
    assert classify_guidance(None, None, 10.0, 10.5).status == GuidanceStatus.NONE


def test_narrowed_ranks_between_maintained_and_raised():
    narrowed = classify_guidance(10.0, 10.5, 10.2, 10.5)
    raised = classify_guidance(10.0, 10.5, 10.6, 11.0)
    assert narrowed.magnitude_pct < raised.magnitude_pct
