from __future__ import annotations

from enum import StrEnum


class EventState(StrEnum):
    DISCOVERED = "DISCOVERED"
    SCHEDULED = "SCHEDULED"
    MONITORING = "MONITORING"
    NOT_YET_VERIFIED = "NOT_YET_VERIFIED"
    DELAYED_OR_UNVERIFIED = "DELAYED_OR_UNVERIFIED"
    RELEASE_DETECTED = "RELEASE_DETECTED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    EXTRACTING = "EXTRACTING"
    CONTEXT = "CONTEXT"
    ANALYSING = "ANALYSING"
    SCORING = "SCORING"
    SCORE_REVIEW = "SCORE_REVIEW"
    SCORED = "SCORED"
    NOTIFIED = "NOTIFIED"
    FAILED = "FAILED"


class MarketSession(StrEnum):
    BMO = "BMO"            # before market open
    AMC = "AMC"            # after market close
    INTRADAY = "INTRADAY"
    UNKNOWN = "UNKNOWN"


class ScheduleConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class GuidanceStatus(StrEnum):
    RAISED = "RAISED"
    NARROWED = "NARROWED"
    MAINTAINED = "MAINTAINED"
    LOWERED = "LOWERED"
    NONE = "NONE"


class GrowthDirection(StrEnum):
    ACCELERATING = "ACCELERATING"
    STABLE = "STABLE"
    DECELERATING = "DECELERATING"
    UNKNOWN = "UNKNOWN"


class ReactionPattern(StrEnum):
    NONE = "NONE"
    POST_EARNINGS_REVERSAL = "POST_EARNINGS_REVERSAL"
    POST_EARNINGS_MOMENTUM = "POST_EARNINGS_MOMENTUM"
    UNRESOLVED = "UNRESOLVED"


class ReleaseSourceKind(StrEnum):
    SEC = "SEC"
    BUSINESSWIRE = "BUSINESSWIRE"
    PRNEWSWIRE = "PRNEWSWIRE"
    GLOBENEWSWIRE = "GLOBENEWSWIRE"
    IR = "IR"
    OTHER = "OTHER"


# Legal transitions of the earnings-event state machine. Any transition not in
# this map is a programming error and raises, so state can never silently skip
# verification or scoring stages.
LEGAL_TRANSITIONS: dict[EventState, set[EventState]] = {
    EventState.DISCOVERED: {EventState.SCHEDULED, EventState.FAILED},
    EventState.SCHEDULED: {EventState.SCHEDULED, EventState.MONITORING, EventState.FAILED},
    EventState.MONITORING: {
        EventState.MONITORING,
        EventState.SCHEDULED,          # reconciliation moved the date
        EventState.NOT_YET_VERIFIED,
        EventState.RELEASE_DETECTED,
        EventState.FAILED,
    },
    EventState.NOT_YET_VERIFIED: {
        EventState.NOT_YET_VERIFIED,
        EventState.RELEASE_DETECTED,
        EventState.DELAYED_OR_UNVERIFIED,
        EventState.SCHEDULED,
        EventState.FAILED,
    },
    EventState.DELAYED_OR_UNVERIFIED: {
        EventState.SCHEDULED,
        EventState.RELEASE_DETECTED,
        EventState.FAILED,
    },
    EventState.RELEASE_DETECTED: {EventState.VERIFYING, EventState.FAILED},
    EventState.VERIFYING: {
        EventState.VERIFIED,
        EventState.MONITORING,         # candidate rejected -> keep looking
        EventState.NOT_YET_VERIFIED,
        EventState.FAILED,
    },
    EventState.VERIFIED: {EventState.EXTRACTING, EventState.FAILED},
    EventState.EXTRACTING: {EventState.CONTEXT, EventState.FAILED},
    EventState.CONTEXT: {EventState.ANALYSING, EventState.FAILED},
    EventState.ANALYSING: {EventState.SCORING, EventState.FAILED},
    EventState.SCORING: {EventState.SCORE_REVIEW, EventState.SCORED, EventState.FAILED},
    EventState.SCORE_REVIEW: {EventState.SCORED, EventState.FAILED},
    EventState.SCORED: {EventState.NOTIFIED, EventState.FAILED},
    EventState.NOTIFIED: set(),
    EventState.FAILED: {EventState.SCHEDULED},  # manual/reconciled retry
}


class IllegalTransition(Exception):
    pass


def assert_transition(current: EventState, new: EventState) -> None:
    if new not in LEGAL_TRANSITIONS[current]:
        raise IllegalTransition(f"{current} -> {new} is not a legal transition")
