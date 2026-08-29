"""Financial Modeling Prep adapter. Free tier is 250 calls/day — a hard
DailyQuota keeps us inside it, and the adapter degrades to unavailable when
the budget is spent rather than silently failing discovery.
"""
from __future__ import annotations

from datetime import date

import httpx

from app.config import get_settings
from app.domain.enums import MarketSession
from app.providers.base import (
    CalendarEntry,
    CompanyProfile,
    DailyQuota,
    EarningsCalendarProvider,
    EstimateDTO,
    EstimatesProvider,
    PriceProvider,
    ProfileProvider,
    ProviderError,
    ProviderUnavailable,
    Quote,
    RateLimiter,
)

BASE = "https://financialmodelingprep.com/api/v3"

_SESSION_MAP = {"bmo": MarketSession.BMO, "amc": MarketSession.AMC}


class FmpProvider(EarningsCalendarProvider, EstimatesProvider, PriceProvider, ProfileProvider):
    name = "fmp"

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None,
                 daily_quota: int | None = None):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.fmp_api_key
        self._client = client or httpx.Client(timeout=10.0)
        self._limiter = RateLimiter(rate_per_second=2.0, burst=4)
        self._quota = DailyQuota(daily_quota or settings.fmp_daily_quota)

    def _get(self, path: str, **params):
        if not self._api_key:
            raise ProviderUnavailable("fmp: no API key configured")
        if not self._quota.consume():
            raise ProviderUnavailable("fmp: daily quota exhausted")
        self._limiter.acquire()
        params["apikey"] = self._api_key
        try:
            resp = self._client.get(f"{BASE}{path}", params=params)
            if resp.status_code == 429:
                raise ProviderError("fmp rate limited")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"fmp request failed ({path}): {exc}") from exc

    def fetch_window(self, start: date, end: date) -> list[CalendarEntry]:
        rows = self._get("/earning_calendar", **{"from": start.isoformat(),
                                                 "to": end.isoformat()})
        entries: list[CalendarEntry] = []
        for row in rows or []:
            try:
                d = date.fromisoformat(row["date"][:10])
            except (KeyError, ValueError):
                continue
            fiscal = row.get("fiscalDateEnding") or ""
            fy = int(fiscal[:4]) if len(fiscal) >= 4 and fiscal[:4].isdigit() else None
            fq = None
            if len(fiscal) >= 7 and fiscal[5:7].isdigit():
                fq = (int(fiscal[5:7]) - 1) // 3 + 1
            entries.append(
                CalendarEntry(
                    ticker=(row.get("symbol") or "").upper(),
                    date=d,
                    session=_SESSION_MAP.get((row.get("time") or "").lower(),
                                             MarketSession.UNKNOWN),
                    eps_estimate=row.get("epsEstimated"),
                    revenue_estimate=row.get("revenueEstimated"),
                    fiscal_year=fy,
                    fiscal_quarter=fq,
                    provider=self.name,
                    source_url=f"{BASE}/earning_calendar",
                )
            )
        return [e for e in entries if e.ticker]

    def fetch_estimates(self, ticker: str) -> list[EstimateDTO]:
        rows = self._get(f"/analyst-estimates/{ticker.upper()}", period="quarter", limit=2)
        out: list[EstimateDTO] = []
        for row in rows or []:
            if row.get("estimatedEpsAvg") is not None:
                out.append(EstimateDTO("eps", "current", float(row["estimatedEpsAvg"]), self.name))
            if row.get("estimatedRevenueAvg") is not None:
                out.append(EstimateDTO("revenue", "current",
                                       float(row["estimatedRevenueAvg"]), self.name))
            break  # newest row only
        return out

    def quote(self, ticker: str) -> Quote:
        rows = self._get(f"/quote/{ticker.upper()}")
        if not rows:
            raise ProviderError(f"fmp: empty quote for {ticker}")
        row = rows[0]
        price = row.get("price")
        if price is None:
            raise ProviderError(f"fmp: no price for {ticker}")
        return Quote(ticker=ticker.upper(), price=float(price),
                     prev_close=row.get("previousClose"), volume=row.get("volume"),
                     provider=self.name)

    def daily_closes(self, ticker: str, days: int) -> list[float]:
        data = self._get(f"/historical-price-full/{ticker.upper()}", timeseries=days + 5)
        hist = (data or {}).get("historical", [])
        closes = [float(r["close"]) for r in reversed(hist) if r.get("close") is not None]
        return closes[-days:]

    def profile(self, ticker: str) -> CompanyProfile:
        rows = self._get(f"/profile/{ticker.upper()}")
        if not rows:
            raise ProviderError(f"fmp: no profile for {ticker}")
        row = rows[0]
        return CompanyProfile(
            ticker=ticker.upper(),
            name=row.get("companyName", ""),
            exchange=row.get("exchangeShortName", ""),
            market_cap=row.get("mktCap"),
            avg_volume=row.get("volAvg"),
            sector=row.get("sector", ""),
            industry=row.get("industry", ""),
            ir_url=row.get("website", ""),
            cik=row.get("cik"),
        )
