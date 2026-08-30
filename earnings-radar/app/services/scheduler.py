"""SchedulerService — daily discovery, reconciliation, and the adaptive
monitoring loop.

APScheduler (not Celery) for the MVP: a single background scheduler in the
FastAPI process, no broker to operate. The monitor tick is deliberately
frequent and cheap; per-event polling cadence comes from polling.py, and a
per-event lease prevents overlapping checks of the same company.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import EarningsEvent
from app.db.session import db_session
from app.domain.enums import EventState, assert_transition
from app.domain.timeutil import LONDON, from_db, utcnow
from app.services.audit import AuditService
from app.services.discovery import EarningsDiscoveryService
from app.services.pipeline import EarningsPipeline
from app.services.polling import poll_interval_seconds

logger = logging.getLogger("earnings_radar.scheduler")

_ACTIVE_STATES = (EventState.SCHEDULED.value, EventState.MONITORING.value,
                  EventState.NOT_YET_VERIFIED.value)


class SchedulerService:
    def __init__(self, *, settings: Settings, discovery: EarningsDiscoveryService,
                 pipeline: EarningsPipeline, monitor_tick_seconds: int = 15,
                 catalyst_poller=None, outcomes=None, rescore=None,
                 earnings_rescore=None):
        self._settings = settings
        self._discovery = discovery
        self._pipeline = pipeline
        self._tick = monitor_tick_seconds
        self._catalyst_poller = catalyst_poller
        self._outcomes = outcomes
        self._rescore = rescore
        self._earnings_rescore = earnings_rescore
        self._scheduler: BackgroundScheduler | None = None
        self.last_discovery_at: datetime | None = None
        self.last_monitor_tick_at: datetime | None = None
        self.last_catalyst_poll_at: datetime | None = None
        self.last_outcome_capture_at: datetime | None = None
        self.last_rescore_at: datetime | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._scheduler is not None:
            return
        self._scheduler = BackgroundScheduler(timezone=LONDON)
        for hour, minute in self._settings.discovery_time_list():
            self._scheduler.add_job(
                self.run_discovery, CronTrigger(hour=hour, minute=minute, timezone=LONDON),
                id=f"discovery-{hour:02d}{minute:02d}", max_instances=1,
                coalesce=True, misfire_grace_time=600)
        self._scheduler.add_job(
            self.monitor_tick, IntervalTrigger(seconds=self._tick),
            id="monitor", max_instances=1, coalesce=True)

        # Catalysts are unscheduled by nature, so this runs continuously rather
        # than around known release windows.
        if self._catalyst_poller is not None:
            self._scheduler.add_job(
                self.catalyst_poll,
                IntervalTrigger(seconds=self._settings.catalyst_poll_seconds),
                id="catalyst-poll", max_instances=1, coalesce=True,
                misfire_grace_time=self._settings.catalyst_poll_seconds)

        if self._outcomes is not None and self._settings.outcome_capture_enabled:
            self._scheduler.add_job(
                self.capture_outcomes,
                IntervalTrigger(seconds=self._settings.outcome_capture_interval_seconds),
                id="outcome-capture", max_instances=1, coalesce=True,
                misfire_grace_time=600)

        # On a delayed feed a catalyst is scored before its move is visible;
        # this pass returns once the data arrives.
        if ((self._rescore is not None or self._earnings_rescore is not None)
                and self._settings.rescore_enabled):
            self._scheduler.add_job(
                self.run_rescore,
                IntervalTrigger(seconds=self._settings.rescore_interval_seconds),
                id="catalyst-rescore", max_instances=1, coalesce=True,
                misfire_grace_time=self._settings.rescore_interval_seconds)

        self._scheduler.start()
        logger.info(
            "scheduler started: discovery at %s Europe/London, monitor every %ss, "
            "catalyst polling %s, outcome capture %s, re-score %s",
            self._settings.discovery_times, self._tick,
            f"every {self._settings.catalyst_poll_seconds}s"
            if self._catalyst_poller is not None else "off",
            f"every {self._settings.outcome_capture_interval_seconds}s"
            if self._outcomes is not None and self._settings.outcome_capture_enabled
            else "off",
            f"every {self._settings.rescore_interval_seconds}s"
            if self._rescore is not None and self._settings.rescore_enabled else "off")

    def shutdown(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    @property
    def running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    # ── jobs ──────────────────────────────────────────────────────────────────

    def run_discovery(self) -> int:
        with db_session() as session:
            count = self._discovery.run(session)
        self.last_discovery_at = utcnow()
        return count

    def catalyst_poll(self, now: datetime | None = None):
        """One catalyst detection sweep. Never raises into the scheduler: a
        provider outage must not stop the loop that would recover from it."""
        if self._catalyst_poller is None:
            return None
        now = now or utcnow()
        self.last_catalyst_poll_at = now
        try:
            with db_session() as session:
                return self._catalyst_poller.poll(session, now)
        except Exception:
            logger.exception("catalyst poll failed")
            return None

    def capture_outcomes(self, now: datetime | None = None):
        """Backfill what actually happened after recent catalysts."""
        if self._outcomes is None:
            return None
        now = now or utcnow()
        self.last_outcome_capture_at = now
        try:
            with db_session() as session:
                return self._outcomes.run(session, now)
        except Exception:
            logger.exception("outcome capture failed")
            return None

    def run_rescore(self, now: datetime | None = None):
        """Revisit scores made before the market's response was visible.

        Both pipelines need this on a delayed feed. The earnings one matters
        most: its releases land after the close, so without it the
        unavailable-prices veto never lifts and nothing ever reaches 9+.
        """
        now = now or utcnow()
        self.last_rescore_at = now
        catalyst_result = earnings_result = None
        try:
            with db_session() as session:
                if self._rescore is not None:
                    catalyst_result = self._rescore.run(session, now)
        except Exception:
            logger.exception("catalyst re-score failed")
        try:
            with db_session() as session:
                if self._earnings_rescore is not None:
                    earnings_result = self._earnings_rescore.run(session, now)
        except Exception:
            logger.exception("earnings re-score failed")
        return catalyst_result if earnings_result is None else (
            catalyst_result, earnings_result)

    def monitor_tick(self, now: datetime | None = None) -> int:
        """Check every event that is due. Returns how many were checked."""
        now = now or utcnow()
        self.last_monitor_tick_at = now
        checked = 0
        with db_session() as session:
            events = (session.query(EarningsEvent)
                      .filter(EarningsEvent.state.in_(_ACTIVE_STATES))
                      .all())
            for event in events:
                try:
                    if self._check_event(session, event, now):
                        checked += 1
                except Exception:
                    logger.exception("monitor failed for event %s", event.id)
                    AuditService(session).log(
                        "monitor", "check_failed", f"event {event.id}",
                        event_id=event.id, level="ERROR")
        return checked

    # ── per-event logic ───────────────────────────────────────────────────────

    def _check_event(self, session: Session, event: EarningsEvent,
                     now: datetime) -> bool:
        audit = AuditService(session)

        # Lease prevents overlapping checks for the same company.
        lease = from_db(event.monitor_lease_until)
        if lease and lease > now:
            return False

        expected = from_db(event.expected_release_at)
        interval = poll_interval_seconds(now, expected, self._settings)
        if interval is None:
            return False

        # Timeout → DELAYED_OR_UNVERIFIED (never "not released", per spec)
        if expected is not None:
            overdue = (now - expected).total_seconds() / 60
            if overdue > self._settings.delayed_grace_minutes:
                if event.state != EventState.DELAYED_OR_UNVERIFIED.value:
                    assert_transition(EventState(event.state),
                                      EventState.DELAYED_OR_UNVERIFIED)
                    event.state = EventState.DELAYED_OR_UNVERIFIED.value
                    event.state_changed_at = now
                    audit.log("monitor", "delayed_or_unverified",
                              f"{event.company.ticker}: {overdue:.0f} min past expected "
                              "release with no verified document", event_id=event.id)
                return False

        if event.state == EventState.SCHEDULED.value:
            assert_transition(EventState(event.state), EventState.MONITORING)
            event.state = EventState.MONITORING.value
            event.state_changed_at = now
            audit.log("monitor", "monitoring_started",
                      f"{event.company.ticker} expected {expected.isoformat() if expected else '?'}",
                      event_id=event.id)
            # Capture the pre-earnings baseline once, at the start of monitoring.
            self._pipeline.capture_pre_earnings(session, event)

        event.monitor_lease_until = now + timedelta(seconds=max(interval, 5))
        session.flush()

        since = from_db(event.window_start) or (now - timedelta(hours=12))
        attempt = self._pipeline.monitor.check(
            ticker=event.company.ticker, company_name=event.company.name,
            cik=event.company.cik, since=since)

        for source, outcome in attempt.checks:
            audit.log("monitor", "source_checked", f"{event.company.ticker} {source}: {outcome}",
                      event_id=event.id)

        if not attempt.found:
            if event.state == EventState.MONITORING.value and expected and now > expected:
                assert_transition(EventState(event.state), EventState.NOT_YET_VERIFIED)
                event.state = EventState.NOT_YET_VERIFIED.value
                event.state_changed_at = now
                audit.log("monitor", "not_yet_verified",
                          f"{event.company.ticker}: past expected release, still searching",
                          event_id=event.id)
            return True

        self._pipeline.process_detection(session, event, attempt.candidates)
        return True
