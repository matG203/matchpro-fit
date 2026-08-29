"""Timezone handling, canonical IDs, and the event state machine."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.canonical import canonical_release_key
from app.domain.enums import EventState, IllegalTransition, assert_transition
from app.domain.timeutil import (
    NEW_YORK,
    UTC,
    ensure_utc,
    et_wall_time_to_utc,
    from_db,
    london_display,
    to_london,
)

# ── timezones ────────────────────────────────────────────────────────────────

def test_bst_conversion_in_summer():
    # 21:05 UTC in August is 22:05 in London (BST, UTC+1)
    utc = datetime(2026, 8, 27, 21, 5, tzinfo=UTC)
    assert london_display(utc) == "22:05"


def test_gmt_conversion_in_winter():
    # 21:05 UTC in January is 21:05 in London (GMT, UTC+0)
    utc = datetime(2026, 1, 27, 21, 5, tzinfo=UTC)
    assert london_display(utc) == "21:05"


def test_et_wall_time_maps_across_dst():
    # 16:05 ET = 20:05 UTC in summer (EDT), 21:05 UTC in winter (EST)
    summer = et_wall_time_to_utc(datetime(2026, 8, 27), 16, 5)
    winter = et_wall_time_to_utc(datetime(2026, 1, 27), 16, 5)
    assert summer.hour == 20
    assert winter.hour == 21
    assert summer.astimezone(NEW_YORK).hour == 16


def test_naive_datetimes_are_rejected():
    with pytest.raises(ValueError):
        ensure_utc(datetime(2026, 8, 27, 21, 5))


def test_from_db_treats_naive_as_utc():
    assert from_db(datetime(2026, 8, 27, 21, 5)).tzinfo is not None
    assert from_db(None) is None
    aware = datetime(2026, 8, 27, 21, 5, tzinfo=UTC)
    assert from_db(aware) == aware


def test_london_round_trip_preserves_instant():
    utc = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    assert to_london(utc).astimezone(UTC) == utc


# ── canonical release identity ───────────────────────────────────────────────

def test_canonical_key_is_stable_and_case_insensitive():
    assert canonical_release_key("estc", 2026, 2) == canonical_release_key("ESTC", 2026, 2)
    assert canonical_release_key("ESTC", 2026, 2) == "ESTC|FY2026|Q2"


def test_canonical_key_rejects_bad_input():
    for args in (("", 2026, 2), ("ESTC", 2026, 5), ("ESTC", 1900, 1)):
        with pytest.raises(ValueError):
            canonical_release_key(*args)


# ── state machine ────────────────────────────────────────────────────────────

def test_happy_path_transitions_are_legal():
    path = [EventState.DISCOVERED, EventState.SCHEDULED, EventState.MONITORING,
            EventState.RELEASE_DETECTED, EventState.VERIFYING, EventState.VERIFIED,
            EventState.EXTRACTING, EventState.CONTEXT, EventState.ANALYSING,
            EventState.SCORING, EventState.SCORED, EventState.NOTIFIED]
    for current, nxt in zip(path, path[1:]):
        assert_transition(current, nxt)


def test_scoring_cannot_be_skipped():
    with pytest.raises(IllegalTransition):
        assert_transition(EventState.VERIFIED, EventState.NOTIFIED)


def test_unverified_release_cannot_be_analysed():
    with pytest.raises(IllegalTransition):
        assert_transition(EventState.RELEASE_DETECTED, EventState.ANALYSING)


def test_failed_verification_returns_to_monitoring():
    assert_transition(EventState.VERIFYING, EventState.MONITORING)
    assert_transition(EventState.NOT_YET_VERIFIED, EventState.DELAYED_OR_UNVERIFIED)
