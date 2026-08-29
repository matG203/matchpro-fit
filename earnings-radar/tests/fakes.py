"""In-memory provider fakes for integration and regression tests."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.domain.enums import MarketSession, ReleaseSourceKind
from app.providers.base import (
    CalendarEntry,
    CompanyProfile,
    EarningsCalendarProvider,
    FilingHit,
    FilingProvider,
    NewsItem,
    NewswireProvider,
    NotifierProvider,
    PriceProvider,
    ProfileProvider,
    ProviderError,
    Quote,
)


class FakeCalendar(EarningsCalendarProvider):
    def __init__(self, name: str, entries: list[CalendarEntry]):
        self.name = name
        self._entries = entries

    def fetch_window(self, start: date, end: date) -> list[CalendarEntry]:
        return [e for e in self._entries if start <= e.date <= end]


class FakeProfile(ProfileProvider):
    def __init__(self, name: str, profiles: dict[str, CompanyProfile]):
        self.name = name
        self._profiles = profiles

    def profile(self, ticker: str) -> CompanyProfile:
        if ticker not in self._profiles:
            raise ProviderError(f"no profile for {ticker}")
        return self._profiles[ticker]


class FakePrice(PriceProvider):
    """Scripted quotes: each call pops the next price (last one repeats)."""

    def __init__(self, name: str, prices: list[float], prev_close: float | None = None,
                 closes: list[float] | None = None):
        self.name = name
        self._prices = list(prices)
        self._prev_close = prev_close
        self._closes = closes or []
        self.calls = 0

    def quote(self, ticker: str) -> Quote:
        self.calls += 1
        price = self._prices[0] if len(self._prices) == 1 else self._prices.pop(0)
        return Quote(ticker=ticker, price=price, prev_close=self._prev_close,
                     provider=self.name)

    def daily_closes(self, ticker: str, days: int) -> list[float]:
        if not self._closes:
            raise ProviderError(f"{self.name}: no history")
        return self._closes[-days:]


class FakeFilings(FilingProvider):
    def __init__(self, name: str = "fake_sec", hits: list[FilingHit] | None = None,
                 documents: dict[str, str] | None = None):
        self.name = name
        self._hits = hits or []
        self._documents = documents or {}

    def recent_filings(self, ticker: str, cik: str | None) -> list[FilingHit]:
        return [h for h in self._hits if h.ticker == ticker.upper()]

    def fetch_document_text(self, url: str) -> str:
        if url not in self._documents:
            raise ProviderError(f"404 {url}")
        return self._documents[url]


class FakeNewswire(NewswireProvider):
    def __init__(self, name: str = "fake_wire", items: list[NewsItem] | None = None,
                 fail: bool = False):
        self.name = name
        self._items = items or []
        self._fail = fail

    def recent_items(self, ticker: str, company_name: str) -> list[NewsItem]:
        if self._fail:
            raise ProviderError(f"{self.name} unreachable")
        return [i for i in self._items if i.ticker == ticker.upper()]


class FakeNotifier(NotifierProvider):
    def __init__(self, name: str = "fake_push", fail: bool = False):
        self.name = name
        self.sent: list[tuple[str, str, bool]] = []
        self._fail = fail

    def enabled(self) -> bool:
        return True

    def send(self, title: str, body: str, high_priority: bool = False) -> None:
        if self._fail:
            raise ProviderError(f"{self.name} send failed")
        self.sent.append((title, body, high_priority))


def calendar_entry(ticker: str, when: date, provider: str, *, session=MarketSession.AMC,
                   eps: float | None = None, revenue: float | None = None,
                   fy: int = 2026, fq: int = 2) -> CalendarEntry:
    return CalendarEntry(ticker=ticker, date=when, session=session, eps_estimate=eps,
                         revenue_estimate=revenue, fiscal_year=fy, fiscal_quarter=fq,
                         provider=provider, source_url=f"https://{provider}.test/calendar")


def news_item(ticker: str, title: str, url: str, minutes_ago: float = 1.0,
              source: ReleaseSourceKind = ReleaseSourceKind.BUSINESSWIRE) -> NewsItem:
    return NewsItem(ticker=ticker, title=title, url=url,
                    published_at_utc=datetime.now(UTC) - timedelta(minutes=minutes_ago),
                    source=source)


def filing_hit(ticker: str, url: str, minutes_ago: float = 1.0, form: str = "8-K",
               items: list[str] | None = None) -> FilingHit:
    return FilingHit(ticker=ticker, form_type=form,
                     accepted_at_utc=datetime.now(UTC) - timedelta(minutes=minutes_ago),
                     url=url, items=items or ["2.02", "9.01"],
                     description="Results of Operations and Financial Condition")
