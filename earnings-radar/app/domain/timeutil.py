"""Timezone discipline: store UTC, convert at the edges.

Europe/London and America/New_York conversions go through zoneinfo so
BST/GMT and EST/EDT are handled automatically.
"""
from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

__all__ = [
    "LONDON",
    "NEW_YORK",
    "UTC",
    "ensure_utc",
    "et_wall_time_to_utc",
    "from_db",
    "london_display",
    "to_london",
    "to_new_york",
    "utcnow",
]

LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Reject naive datetimes rather than guessing their zone."""
    if dt.tzinfo is None:
        raise ValueError("naive datetime — all internal datetimes must be tz-aware")
    return dt.astimezone(UTC)


def from_db(dt: datetime | None) -> datetime | None:
    """Normalise a datetime read back from the database.

    We only ever store UTC, but SQLite (unlike Postgres) drops tzinfo on the
    round trip, so a naive value from the DB is by construction UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_london(dt: datetime) -> datetime:
    return ensure_utc(dt).astimezone(LONDON)


def to_new_york(dt: datetime) -> datetime:
    return ensure_utc(dt).astimezone(NEW_YORK)


def london_display(dt: datetime) -> str:
    return to_london(dt).strftime("%H:%M")


def et_wall_time_to_utc(date_: datetime, hour: int, minute: int) -> datetime:
    """Interpret an Eastern-Time wall clock time on a given date as UTC."""
    local = datetime(date_.year, date_.month, date_.day, hour, minute, tzinfo=NEW_YORK)
    return local.astimezone(UTC)
