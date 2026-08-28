"""Discovery, schedule generation, watchlist reconciliation and the monitor loop."""
from __future__ import annotations

from datetime import date, timedelta

from app.config import Settings
from app.db.models import AuditLog, Company, EarningsEvent, Estimate
from app.domain.enums import EventState, MarketSession, ScheduleConfidence
from app.domain.timeutil import to_new_york, utcnow
from app.providers.base import CompanyProfile
from app.services.discovery import (
    EarningsDiscoveryService,
    estimate_release_window,
    liquidity_tier,
    schedule_confidence_for,
)
from app.services.marketdata import MarketDataService
from app.services.monitor import ReleaseMonitorService, looks_like_results_headline
from app.services.notification import NotificationService
from app.services.pipeline import EarningsPipeline
from app.services.scheduler import SchedulerService
from tests.fakes import (
    FakeCalendar,
    FakeFilings,
    FakeNewswire,
    FakeNotifier,
    FakePrice,
    FakeProfile,
    calendar_entry,
)

TODAY = date.today()
CONF = Settings(database_url="sqlite://")


def build_discovery(calendars, profiles=None) -> EarningsDiscoveryService:
    return EarningsDiscoveryService(
        calendars=calendars,
        profiles=profiles or [FakeProfile("fake_profile", {
            "ESTC": CompanyProfile(ticker="ESTC", name="Elastic N.V.", exchange="NYSE",
                                   market_cap=12e9, avg_volume=2e6, cik="0001707753"),
            "AFRM": CompanyProfile(ticker="AFRM", name="Affirm Holdings", exchange="NASDAQ",
                                   market_cap=20e9, avg_volume=8e6, cik="0001820953"),
        })],
        sec=None, settings=CONF)


# ── schedule generation ──────────────────────────────────────────────────────

def test_amc_window_is_anchored_to_eastern_wall_clock():
    expected, start, end = estimate_release_window(date(2026, 8, 27), MarketSession.AMC)
    assert to_new_york(expected).hour == 16
    assert to_new_york(expected).minute == 5
    assert start < expected < end


def test_bmo_window_is_before_the_open():
    expected, start, end = estimate_release_window(date(2026, 8, 27), MarketSession.BMO)
    assert to_new_york(expected).hour == 7
    assert to_new_york(end).hour == 9 and to_new_york(end).minute == 30


def test_release_window_survives_dst_change():
    summer, _, _ = estimate_release_window(date(2026, 8, 27), MarketSession.AMC)
    winter, _, _ = estimate_release_window(date(2026, 1, 27), MarketSession.AMC)
    assert summer.hour == 20 and winter.hour == 21  # same ET wall clock, different UTC


# ── source confidence ────────────────────────────────────────────────────────

def test_two_agreeing_calendars_give_medium_confidence():
    entries = [calendar_entry("ESTC", TODAY, "finnhub"), calendar_entry("ESTC", TODAY, "fmp")]
    confidence, reason = schedule_confidence_for(entries)
    assert confidence == ScheduleConfidence.MEDIUM
    assert "agree" in reason


def test_single_calendar_gives_low_confidence_with_reason():
    confidence, reason = schedule_confidence_for([calendar_entry("ESTC", TODAY, "finnhub")])
    assert confidence == ScheduleConfidence.LOW
    assert "single calendar source" in reason


def test_disagreeing_calendars_give_low_confidence():
    entries = [calendar_entry("ESTC", TODAY, "finnhub"),
               calendar_entry("ESTC", TODAY + timedelta(days=1), "fmp")]
    confidence, reason = schedule_confidence_for(entries)
    assert confidence == ScheduleConfidence.LOW
    assert "disagree" in reason


def test_liquidity_tiers_cover_mega_to_micro():
    assert liquidity_tier(50e9, 1e7) == "LARGE"
    assert liquidity_tier(5e9, 1e6) == "MID"
    assert liquidity_tier(500e6, 1e5) == "SMALL"
    assert liquidity_tier(50e6, 1e4) == "MICRO"
    assert liquidity_tier(None, None) == "UNKNOWN"


# ── discovery ────────────────────────────────────────────────────────────────

def test_discovery_builds_watchlist_from_multiple_calendars(db):
    calendars = [
        FakeCalendar("finnhub", [calendar_entry("ESTC", TODAY, "finnhub", eps=0.50,
                                                revenue=1.10e9),
                                 calendar_entry("AFRM", TODAY, "finnhub", eps=0.10)]),
        FakeCalendar("fmp", [calendar_entry("ESTC", TODAY, "fmp", eps=0.51,
                                            revenue=1.14e9)]),
    ]
    with db.db_session() as session:
        count = build_discovery(calendars).run(session)
        assert count == 2

        estc = (session.query(EarningsEvent).join(Company)
                .filter(Company.ticker == "ESTC").one())
        assert estc.state == EventState.SCHEDULED.value
        assert estc.schedule_confidence == ScheduleConfidence.MEDIUM.value
        # Both providers' consensus datapoints are kept for the band
        estimates = session.query(Estimate).filter_by(event_id=estc.id, metric="revenue").all()
        assert {e.provider for e in estimates} == {"finnhub", "fmp"}

        afrm = (session.query(EarningsEvent).join(Company)
                .filter(Company.ticker == "AFRM").one())
        assert afrm.schedule_confidence == ScheduleConfidence.LOW.value


def test_discovery_includes_microcaps_but_tags_liquidity(db):
    profiles = [FakeProfile("fake", {"TINY": CompanyProfile(
        ticker="TINY", name="Tiny Corp", market_cap=45e6, avg_volume=20000)})]
    calendars = [FakeCalendar("finnhub", [calendar_entry("TINY", TODAY, "finnhub")])]
    with db.db_session() as session:
        build_discovery(calendars, profiles).run(session)
        company = session.query(Company).filter_by(ticker="TINY").one()
        assert company.liquidity_tier == "MICRO"
        assert session.query(EarningsEvent).count() == 1, "microcaps are not filtered out"


def test_discovery_survives_a_failing_calendar_provider(db):
    class BrokenCalendar(FakeCalendar):
        def fetch_window(self, start, end):
            from app.providers.base import ProviderError
            raise ProviderError("calendar API down")

    calendars = [BrokenCalendar("broken", []),
                 FakeCalendar("fmp", [calendar_entry("ESTC", TODAY, "fmp")])]
    with db.db_session() as session:
        count = build_discovery(calendars).run(session)
        assert count == 1, "a dead provider must not sink discovery"
        failures = session.query(AuditLog).filter_by(action="calendar_failed").all()
        assert failures and "broken" in failures[0].detail


def test_reconciliation_updates_schedule_without_duplicating_events(db):
    tomorrow = TODAY + timedelta(days=1)
    with db.db_session() as session:
        build_discovery([FakeCalendar("finnhub", [
            calendar_entry("ESTC", TODAY, "finnhub")])]).run(session)
        assert session.query(EarningsEvent).count() == 1

        # A later reconciliation pass sees the company move to tomorrow, AMC.
        build_discovery([FakeCalendar("finnhub", [
            calendar_entry("ESTC", tomorrow, "finnhub")])]).run(session)

        events = session.query(EarningsEvent).all()
        assert len(events) == 1, "same fiscal quarter must not create a second event"
        assert events[0].expected_date.date() == tomorrow
        assert session.query(AuditLog).filter_by(action="event_reconciled").count() >= 1


# ── monitoring loop ──────────────────────────────────────────────────────────

def test_headline_filter_separates_results_from_scheduling_notices():
    assert looks_like_results_headline("Elastic Reports Second Quarter Results")
    assert not looks_like_results_headline("Elastic to Report Second Quarter Results")
    assert not looks_like_results_headline("Elastic Announces Conference Call Date")
    assert not looks_like_results_headline("Analyst Preview: What to Expect from ESTC")


def build_scheduler(db, *, newswire_items=None, documents=None) -> SchedulerService:
    filings = FakeFilings(hits=[], documents=documents or {})
    newswire = FakeNewswire(items=newswire_items or [])
    market = MarketDataService([FakePrice("p1", [100.0], prev_close=100.0)],
                              conflict_threshold_pct=5.0)
    notifications = NotificationService([FakeNotifier()], min_score=0.0,
                                        high_score_alert=9.0, min_confidence=75.0)
    pipeline = EarningsPipeline(
        settings=CONF, monitor=ReleaseMonitorService(filings=filings, newswires=[newswire]),
        filings=filings, market=market, analysis=None, notifications=notifications)
    return SchedulerService(settings=CONF, discovery=build_discovery([]), pipeline=pipeline)


def test_monitor_starts_monitoring_inside_the_window_and_leases_the_event(db):
    scheduler = build_scheduler(db)
    with db.db_session() as session:
        company = Company(ticker="ESTC", name="Elastic N.V.")
        session.add(company)
        session.flush()
        session.add(EarningsEvent(
            company_id=company.id, fiscal_year=2026, fiscal_quarter=2,
            expected_release_at=utcnow() + timedelta(minutes=10),
            window_start=utcnow() - timedelta(hours=1),
            state=EventState.SCHEDULED.value))

    assert scheduler.monitor_tick() == 1
    with db.db_session() as session:
        event = session.query(EarningsEvent).one()
        assert event.state == EventState.MONITORING.value
        assert event.monitor_lease_until is not None

    # The lease suppresses the immediately following tick.
    assert scheduler.monitor_tick() == 0


def test_far_future_event_is_not_polled(db):
    scheduler = build_scheduler(db)
    with db.db_session() as session:
        company = Company(ticker="WDAY", name="Workday")
        session.add(company)
        session.flush()
        session.add(EarningsEvent(
            company_id=company.id, fiscal_year=2026, fiscal_quarter=2,
            expected_release_at=utcnow() + timedelta(hours=8),
            state=EventState.SCHEDULED.value))
    assert scheduler.monitor_tick() == 0
    with db.db_session() as session:
        assert session.query(EarningsEvent).one().state == EventState.SCHEDULED.value


def test_missing_release_becomes_not_yet_verified_then_delayed(db):
    scheduler = build_scheduler(db)
    with db.db_session() as session:
        company = Company(ticker="ESTC", name="Elastic N.V.")
        session.add(company)
        session.flush()
        session.add(EarningsEvent(
            company_id=company.id, fiscal_year=2026, fiscal_quarter=2,
            expected_release_at=utcnow() - timedelta(minutes=20),
            window_start=utcnow() - timedelta(hours=2),
            state=EventState.MONITORING.value))

    scheduler.monitor_tick()
    with db.db_session() as session:
        event = session.query(EarningsEvent).one()
        assert event.state == EventState.NOT_YET_VERIFIED.value, "never 'not released'"
        # Push it well past the grace period.
        event.expected_release_at = utcnow() - timedelta(
            minutes=CONF.delayed_grace_minutes + 30)
        event.monitor_lease_until = None

    scheduler.monitor_tick()
    with db.db_session() as session:
        assert session.query(EarningsEvent).one().state == \
            EventState.DELAYED_OR_UNVERIFIED.value


def test_audit_trail_records_every_source_check(db):
    scheduler = build_scheduler(db)
    with db.db_session() as session:
        company = Company(ticker="ESTC", name="Elastic N.V.")
        session.add(company)
        session.flush()
        session.add(EarningsEvent(
            company_id=company.id, fiscal_year=2026, fiscal_quarter=2,
            expected_release_at=utcnow() - timedelta(minutes=1),
            window_start=utcnow() - timedelta(hours=1),
            state=EventState.MONITORING.value))
    scheduler.monitor_tick()
    with db.db_session() as session:
        checks = session.query(AuditLog).filter_by(action="source_checked").all()
        assert checks, "every source check must be auditable"
        assert any("fake_wire" in c.detail for c in checks)
