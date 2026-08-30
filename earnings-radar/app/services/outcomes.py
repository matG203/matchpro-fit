"""Outcome capture — what actually happened after each scored catalyst.

Without this, calibration is an opinion. `/api/catalyst/performance` reports a
sample size of zero because nothing has ever recorded whether a 9.2 was
followed by a 12% move or a fade. This job closes that loop.

Design decisions that matter:

  * **Measured from the disclosure, not from the alert.** The alert timestamp
    tells you how fast the system was; the disclosure timestamp tells you
    whether the event was worth trading. Both are stored, and returns are
    computed from the price at disclosure.
  * **Benchmark-adjusted.** A 4% gain on a day the market rose 4% is not a
    result. The abnormal figures are the ones calibration should use.
  * **Backfilled from bars, not sampled live.** A job that had to be awake at
    exactly +5 minutes would miss most events. Reading historical minute bars
    afterwards produces the same numbers and survives restarts.
  * **Incremental and idempotent.** Each pass fills in whichever horizons have
    matured, records how far it got in `captured_through`, and leaves the rest
    for a later pass. Re-running changes nothing.

MFE/MAE (maximum favourable/adverse excursion) are recorded too: the honest
question is not only "where did it close" but "was there ever a point where
this trade was working".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.catalyst.reaction import pct_change
from app.config import Settings
from app.db.catalyst_models import (
    CatalystAlert,
    CatalystEvent,
    CatalystOutcome,
    EventCluster,
    HistoricalAnalogue,
    MarketStructureSnapshot,
)
from app.domain.timeutil import NEW_YORK, from_db, utcnow
from app.providers.base import Bar, BarProvider, ProviderError, ProviderUnavailable
from app.services.catalyst_market import price_at

logger = logging.getLogger("earnings_radar.catalyst.outcomes")

# (column suffix, minutes after disclosure)
HORIZONS: list[tuple[str, int]] = [
    ("1m", 1), ("5m", 5), ("15m", 15), ("30m", 30), ("60m", 60),
]


@dataclass
class CaptureResult:
    events_considered: int = 0
    events_updated: int = 0
    events_completed: int = 0
    errors: list[str] = None            # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


class OutcomeCaptureService:
    def __init__(self, *, bars: BarProvider | None, settings: Settings):
        self._bars = bars
        self._settings = settings
        self.last_run_at: datetime | None = None

    @property
    def available(self) -> bool:
        return self._bars is not None

    def run(self, session: Session, now: datetime | None = None) -> CaptureResult:
        now = now or utcnow()
        self.last_run_at = now
        result = CaptureResult()
        if not self.available:
            return result

        window = now - timedelta(days=self._settings.outcome_capture_window_days)
        events = (session.query(CatalystEvent)
                  .filter(CatalystEvent.created_at >= window)
                  .filter(CatalystEvent.state.in_(("SCORED", "ALERTED")))
                  .all())

        for event in events:
            result.events_considered += 1
            try:
                if self._capture(session, event, now, result):
                    result.events_updated += 1
            except Exception as exc:
                logger.exception("outcome capture failed for event %s", event.id)
                result.errors.append(f"event {event.id}: {exc}")
        return result

    # ── per event ─────────────────────────────────────────────────────────────

    def _capture(self, session: Session, event: CatalystEvent, now: datetime,
                 result: CaptureResult) -> bool:
        disclosure = self._disclosure_time(session, event)
        if disclosure is None:
            return False

        outcome = (session.query(CatalystOutcome)
                   .filter_by(event_id=event.id).first())
        if outcome is None:
            outcome = CatalystOutcome(event_id=event.id)
            session.add(outcome)
            session.flush()

        final_horizon = disclosure + timedelta(days=1)
        if outcome.captured_through is not None:
            captured = from_db(outcome.captured_through)
            if captured is not None and captured >= min(final_horizon, now):
                return False            # nothing new has matured since last pass

        bars = self._bars_for(event.ticker, disclosure, now, result)
        if not bars:
            return False

        base = price_at(bars, disclosure, completed_only=True)
        if base is None:
            # No print at or before the disclosure — usually a filing that
            # landed before the stock's first trade. The next pass will have
            # bars either side of it.
            return False

        outcome.price_earliest_public = base
        outcome.price_at_detection = outcome.price_at_detection or base
        outcome.session_at_event = _session_label(disclosure)

        alert = (session.query(CatalystAlert)
                 .filter_by(event_id=event.id)
                 .order_by(CatalystAlert.id.asc()).first())
        if alert is not None and alert.price_at_alert:
            outcome.price_at_alert = alert.price_at_alert
        if alert is not None:
            # What the tape actually was when the alert went out, as opposed to
            # what the feed could show us at the time. On a delayed plan those
            # differ by the whole delay, and only this one can answer "did the
            # alert arrive before the market moved?" — the other answers the
            # much weaker "before we could see that it had".
            sent = from_db(alert.sent_at) or from_db(alert.created_at)
            if sent is not None and sent <= now:
                on_tape = price_at(bars, sent)
                if on_tape is not None:
                    outcome.price_on_tape_at_alert = on_tape

        for suffix, minutes in HORIZONS:
            target = disclosure + timedelta(minutes=minutes)
            if target > now:
                continue
            price = price_at(bars, target)
            if price is not None:
                setattr(outcome, f"ret_{suffix}", round(pct_change(base, price), 3))

        self._capture_session_points(outcome, bars, base, disclosure, now)
        self._capture_excursions(outcome, bars, base, disclosure, now)
        self._capture_abnormal(outcome, base, disclosure, now, result)

        outcome.captured_through = min(now, final_horizon)
        if outcome.captured_through >= final_horizon:
            result.events_completed += 1
            self._record_analogue(session, event, outcome, disclosure)

        session.flush()
        return True

    # ── horizons ──────────────────────────────────────────────────────────────

    def _capture_session_points(self, outcome: CatalystOutcome, bars: list[Bar],
                                base: float, disclosure: datetime, now: datetime) -> None:
        """Close, next open and +1 day.

        Session boundaries come from New York wall clock, so an after-hours
        catalyst is measured against the *next* session's close rather than the
        one that had already happened when it broke.
        """
        local = disclosure.astimezone(NEW_YORK)
        close_at = local.replace(hour=16, minute=0, second=0, microsecond=0)
        if local >= close_at:
            close_at = _next_session(close_at + timedelta(days=1)).replace(
                hour=16, minute=0, second=0, microsecond=0)

        if close_at <= now:
            price = price_at(bars, close_at)
            if price is not None:
                outcome.ret_close = round(pct_change(base, price), 3)

        next_open = _next_session(close_at + timedelta(days=1)).replace(
            hour=9, minute=30, second=0, microsecond=0)
        if next_open <= now:
            price = price_at(bars, next_open + timedelta(minutes=1))
            if price is not None:
                outcome.ret_next_open = round(pct_change(base, price), 3)

        day_later = disclosure + timedelta(days=1)
        if day_later <= now:
            price = price_at(bars, day_later)
            if price is not None:
                outcome.ret_1d = round(pct_change(base, price), 3)

    def _capture_excursions(self, outcome: CatalystOutcome, bars: list[Bar],
                            base: float, disclosure: datetime, now: datetime) -> None:
        """How good and how bad it got — not just where it ended."""
        after = [b for b in bars if b.start_utc >= disclosure]
        if not after:
            return

        hour = [b for b in after if b.start_utc <= disclosure + timedelta(hours=1)]
        if hour and (disclosure + timedelta(hours=1)) <= now:
            outcome.mfe_1h = round(pct_change(base, max(b.high for b in hour)), 3)

        day = [b for b in after if b.start_utc <= disclosure + timedelta(days=1)]
        if day and (disclosure + timedelta(days=1)) <= now:
            outcome.mfe_1d = round(pct_change(base, max(b.high for b in day)), 3)
            outcome.mae_1d = round(pct_change(base, min(b.low for b in day)), 3)

    def _capture_abnormal(self, outcome: CatalystOutcome, base: float,
                          disclosure: datetime, now: datetime,
                          result: CaptureResult) -> None:
        """Benchmark-adjusted returns — the ones calibration should trust."""
        benchmark = self._settings.benchmark_ticker
        if not benchmark:
            return
        bench_bars = self._bars_for(benchmark, disclosure, now, result)
        if not bench_bars:
            return
        bench_base = price_at(bench_bars, disclosure, completed_only=True)
        if bench_base is None:
            return

        for attr, minutes in (("60m", 60), ("1d", 1440)):
            raw = getattr(outcome, f"ret_{attr}")
            if raw is None:
                continue
            target = disclosure + timedelta(minutes=minutes)
            bench_price = price_at(bench_bars, target)
            if bench_price is None:
                continue
            bench_move = pct_change(bench_base, bench_price)
            setattr(outcome, f"abnormal_ret_{attr}", round(raw - bench_move, 3))

    def _record_analogue(self, session: Session, event: CatalystEvent,
                         outcome: CatalystOutcome, disclosure: datetime) -> None:
        """Feed the analogue store, so future events have real comparables.

        This is the only route by which the analogue engine ever stops
        returning a placeholder — every completed outcome makes the next
        Reaction Room assessment slightly less of a guess.
        """
        existing = (session.query(HistoricalAnalogue)
                    .filter_by(event_id=event.id).first())
        if existing is not None:
            return

        structure = (session.query(MarketStructureSnapshot)
                     .filter_by(event_id=event.id).first())
        features = {
            "ticker": event.ticker,
            "certainty": event.certainty,
            "market_cap": structure.market_cap if structure else None,
            "free_float_shares": structure.free_float_shares if structure else None,
            "short_percent_float": structure.short_percent_float if structure else None,
            "atr_pct": structure.atr_pct if structure else None,
            "session": structure.session if structure else "",
        }
        session.add(HistoricalAnalogue(
            event_id=event.id, event_type=event.event_type, features=features,
            observed_at_utc=disclosure,
            outcome_ret_60m=outcome.ret_60m, outcome_ret_1d=outcome.ret_1d,
            outcome_abnormal_1d=outcome.abnormal_ret_1d))

    # ── plumbing ──────────────────────────────────────────────────────────────

    @staticmethod
    def _disclosure_time(session: Session, event: CatalystEvent) -> datetime | None:
        cluster = session.get(EventCluster, event.cluster_id)
        if cluster is None:
            return None
        return from_db(cluster.earliest_public_at_utc) or from_db(event.created_at)

    def _bars_for(self, ticker: str, disclosure: datetime, now: datetime,
                  result: CaptureResult) -> list[Bar]:
        end = min(now, disclosure + timedelta(days=1, hours=12))
        try:
            return self._bars.bars(ticker, start=disclosure - timedelta(minutes=30),
                                   end=end, timespan="minute")
        except (ProviderError, ProviderUnavailable) as exc:
            result.errors.append(f"{ticker} bars: {exc}")
            return []


def _next_session(when: datetime) -> datetime:
    """Next weekday. Exchange holidays are not modelled — a holiday simply
    leaves that horizon unfilled rather than recording a wrong number."""
    local = when.astimezone(NEW_YORK)
    while local.weekday() >= 5:
        local += timedelta(days=1)
    return local


def _session_label(when: datetime) -> str:
    from app.catalyst.amplification import market_session
    return market_session(when)
