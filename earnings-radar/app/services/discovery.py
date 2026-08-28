"""EarningsDiscoveryService — build the next-24h watchlist (spec §EARNINGS
DISCOVERY).

Merges multiple calendar providers (never trusts one), tags schedule
confidence with an explicit reason, estimates the expected release time and
window, and upserts companies/events. Runs at 05:00 Europe/London plus
reconciliation passes.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Company, EarningsEvent, Estimate
from app.domain.enums import EventState, MarketSession, ScheduleConfidence, assert_transition
from app.domain.timeutil import UTC, et_wall_time_to_utc, utcnow
from app.providers.base import (
    CalendarEntry,
    EarningsCalendarProvider,
    ProfileProvider,
    ProviderError,
    ProviderUnavailable,
)
from app.providers.sec_edgar import SecEdgarProvider
from app.services.audit import AuditService

logger = logging.getLogger("earnings_radar.discovery")

# Default ET wall-clock estimates per session when nothing better is known.
_SESSION_ESTIMATES = {
    MarketSession.BMO: ((7, 0), (6, 0), (9, 30)),
    MarketSession.AMC: ((16, 5), (16, 0), (20, 0)),
    MarketSession.INTRADAY: ((12, 0), (9, 30), (16, 0)),
    MarketSession.UNKNOWN: ((16, 5), (6, 0), (20, 0)),
}


def merge_calendar_entries(all_entries: list[list[CalendarEntry]]) -> dict[str, list[CalendarEntry]]:
    """Group per-ticker; each ticker keeps every provider's view."""
    merged: dict[str, list[CalendarEntry]] = {}
    for provider_entries in all_entries:
        for entry in provider_entries:
            merged.setdefault(entry.ticker, []).append(entry)
    return merged


def schedule_confidence_for(entries: list[CalendarEntry]) -> tuple[ScheduleConfidence, str]:
    providers = {e.provider for e in entries}
    dates = {e.date for e in entries}
    if len(providers) >= 2 and len(dates) == 1:
        return (ScheduleConfidence.MEDIUM,
                f"{len(providers)} calendars agree on {next(iter(dates))} "
                f"({', '.join(sorted(providers))})")
    if len(dates) > 1:
        return (ScheduleConfidence.LOW,
                f"calendars disagree on date: {sorted(str(d) for d in dates)}")
    return (ScheduleConfidence.LOW,
            f"single calendar source ({', '.join(sorted(providers))}) — estimated date only")


def pick_session(entries: list[CalendarEntry]) -> MarketSession:
    for entry in entries:
        if entry.session != MarketSession.UNKNOWN:
            return entry.session
    return MarketSession.UNKNOWN


def fiscal_period_for(entries: list[CalendarEntry], report_date: date) -> tuple[int, int]:
    for entry in entries:
        if entry.fiscal_year and entry.fiscal_quarter:
            return entry.fiscal_year, entry.fiscal_quarter
    # Fallback: calendar quarter of the *reported* period ≈ previous quarter
    prev_month_anchor = report_date - timedelta(days=45)
    return prev_month_anchor.year, (prev_month_anchor.month - 1) // 3 + 1


def estimate_release_window(report_date: date, session: MarketSession
                            ) -> tuple[datetime, datetime, datetime]:
    """(expected_at, window_start, window_end) in UTC from ET wall times.
    Historical per-company release-time learning is a Phase 2 refinement."""
    anchor = datetime(report_date.year, report_date.month, report_date.day)
    (eh, em), (sh, sm), (wh, wm) = _SESSION_ESTIMATES[session]
    return (
        et_wall_time_to_utc(anchor, eh, em),
        et_wall_time_to_utc(anchor, sh, sm),
        et_wall_time_to_utc(anchor, wh, wm),
    )


def liquidity_tier(market_cap: float | None, avg_volume: float | None) -> str:
    if market_cap is None:
        return "UNKNOWN"
    if market_cap >= 10e9:
        return "LARGE"
    if market_cap >= 2e9:
        return "MID"
    if market_cap >= 300e6:
        return "SMALL"
    return "MICRO"


class EarningsDiscoveryService:
    def __init__(self, calendars: list[EarningsCalendarProvider],
                 profiles: list[ProfileProvider], sec: SecEdgarProvider | None,
                 settings: Settings):
        self._calendars = calendars
        self._profiles = profiles
        self._sec = sec
        self._settings = settings

    def run(self, session: Session, *, now: datetime | None = None) -> int:
        """Discover events in [today, today+1]. Returns number of watchlist rows."""
        now = now or utcnow()
        audit = AuditService(session)
        start, end = now.date(), (now + timedelta(days=1)).date()

        per_provider: list[list[CalendarEntry]] = []
        for provider in self._calendars:
            try:
                entries = provider.fetch_window(start, end)
                per_provider.append(entries)
                audit.log("discovery", "calendar_fetched",
                          f"{provider.name}: {len(entries)} entries for {start}..{end}")
            except (ProviderError, ProviderUnavailable) as exc:
                audit.log("discovery", "calendar_failed", f"{provider.name}: {exc}",
                          level="WARNING")
        merged = merge_calendar_entries(per_provider)

        count = 0
        for ticker, entries in merged.items():
            try:
                self._upsert_event(session, audit, ticker, entries, now)
                count += 1
            except Exception as exc:  # one bad ticker must not sink discovery
                logger.exception("discovery upsert failed for %s", ticker)
                audit.log("discovery", "upsert_failed", f"{ticker}: {exc}", level="ERROR")
        audit.log("discovery", "run_complete", f"{count} companies on watchlist")
        return count

    def _upsert_event(self, session: Session, audit: AuditService, ticker: str,
                      entries: list[CalendarEntry], now: datetime) -> None:
        company = session.query(Company).filter_by(ticker=ticker).first()
        if company is None:
            company = Company(ticker=ticker)
            session.add(company)
            session.flush()
        self._enrich_company(company)

        report_date = min(e.date for e in entries)           # earliest claimed date
        fy, fq = fiscal_period_for(entries, report_date)
        mkt_session = pick_session(entries)
        confidence, reason = schedule_confidence_for(entries)
        expected_at, win_start, win_end = estimate_release_window(report_date, mkt_session)

        event = session.query(EarningsEvent).filter_by(
            company_id=company.id, fiscal_year=fy, fiscal_quarter=fq).first()
        created = event is None
        if event is None:
            event = EarningsEvent(company_id=company.id, fiscal_year=fy, fiscal_quarter=fq)
            session.add(event)

        # Never regress an event that is already past detection
        if not created and event.state not in (EventState.DISCOVERED, EventState.SCHEDULED,
                                               EventState.MONITORING):
            return

        event.expected_date = datetime(report_date.year, report_date.month, report_date.day,
                                       tzinfo=UTC)
        event.session = mkt_session.value
        event.expected_release_at = expected_at
        event.window_start = win_start
        event.window_end = win_end
        event.schedule_confidence = confidence.value
        event.confidence_reason = reason
        event.sources = [{"provider": e.provider, "date": str(e.date),
                          "session": e.session.value} for e in entries]

        eps = [e.eps_estimate for e in entries if e.eps_estimate is not None]
        rev = [e.revenue_estimate for e in entries if e.revenue_estimate is not None]
        event.eps_estimate = sum(eps) / len(eps) if eps else None
        event.revenue_estimate = sum(rev) / len(rev) if rev else None
        session.flush()

        # Persist each provider's consensus datapoint for the band
        for entry in entries:
            for metric, value in (("eps", entry.eps_estimate),
                                  ("revenue", entry.revenue_estimate)):
                if value is None:
                    continue
                exists = session.query(Estimate).filter_by(
                    event_id=event.id, metric=metric, provider=entry.provider).first()
                if exists:
                    exists.value = float(value)
                    exists.retrieved_at = now
                else:
                    session.add(Estimate(event_id=event.id, metric=metric, period="current",
                                         value=float(value), provider=entry.provider))

        if created:
            assert_transition(EventState(event.state), EventState.SCHEDULED)
            event.state = EventState.SCHEDULED.value
            event.state_changed_at = now
            audit.log("discovery", "event_scheduled",
                      f"{ticker} FY{fy}Q{fq} {mkt_session.value} expected "
                      f"{expected_at.isoformat()} [{confidence.value}] {reason}",
                      event_id=event.id)
        else:
            audit.log("discovery", "event_reconciled",
                      f"{ticker} FY{fy}Q{fq} window {win_start.isoformat()}"
                      f"..{win_end.isoformat()} [{confidence.value}]",
                      event_id=event.id)

    def _enrich_company(self, company: Company) -> None:
        if company.name and company.cik:
            return
        for provider in self._profiles:
            try:
                profile = provider.profile(company.ticker)
            except (ProviderError, ProviderUnavailable):
                continue
            company.name = company.name or profile.name
            company.exchange = company.exchange or profile.exchange
            company.market_cap = company.market_cap or profile.market_cap
            company.avg_volume = company.avg_volume or profile.avg_volume
            company.sector = company.sector or profile.sector
            company.industry = company.industry or profile.industry
            company.ir_url = company.ir_url or profile.ir_url
            company.cik = company.cik or profile.cik
            break
        if not company.cik and self._sec is not None:
            try:
                company.cik = self._sec.cik_for_ticker(company.ticker)
            except ProviderError:
                pass
        company.liquidity_tier = liquidity_tier(company.market_cap, company.avg_volume)
