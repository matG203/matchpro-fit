"""Finnhub adapter: earnings calendar, consensus estimates, quotes, profile.

Free tier: 60 calls/min. Self-throttled below that.
"""
from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta

import httpx

from app.config import get_settings
from app.domain.enums import MarketSession
from app.providers.base import (
    CalendarEntry,
    CompanyProfile,
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

BASE = "https://finnhub.io/api/v1"

_SESSION_MAP = {"bmo": MarketSession.BMO, "amc": MarketSession.AMC, "dmh": MarketSession.INTRADAY}


class FinnhubProvider(EarningsCalendarProvider, EstimatesProvider, PriceProvider, ProfileProvider):
    name = "finnhub"

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None):
        self._api_key = api_key if api_key is not None else get_settings().finnhub_api_key
        self._client = client or httpx.Client(timeout=10.0)
        self._limiter = RateLimiter(rate_per_second=0.8, burst=5)

    def _get(self, path: str, **params) -> dict | list:
        if not self._api_key:
            raise ProviderUnavailable("finnhub: no API key configured")
        self._limiter.acquire()
        params["token"] = self._api_key
        try:
            resp = self._client.get(f"{BASE}{path}", params=params)
            if resp.status_code == 429:
                raise ProviderError("finnhub rate limited")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"finnhub request failed ({path}): {exc}") from exc

    # ── calendar ──────────────────────────────────────────────────────────────

    def fetch_window(self, start: date, end: date) -> list[CalendarEntry]:
        data = self._get("/calendar/earnings", **{"from": start.isoformat(), "to": end.isoformat()})
        entries: list[CalendarEntry] = []
        for row in (data or {}).get("earningsCalendar", []):
            try:
                d = date.fromisoformat(row["date"])
            except (KeyError, ValueError):
                continue
            entries.append(
                CalendarEntry(
                    ticker=(row.get("symbol") or "").upper(),
                    date=d,
                    session=_SESSION_MAP.get((row.get("hour") or "").lower(),
                                             MarketSession.UNKNOWN),
                    eps_estimate=row.get("epsEstimate"),
                    revenue_estimate=row.get("revenueEstimate"),
                    fiscal_year=row.get("year"),
                    fiscal_quarter=row.get("quarter"),
                    provider=self.name,
                    source_url=f"{BASE}/calendar/earnings",
                )
            )
        return [e for e in entries if e.ticker]

    # ── estimates ─────────────────────────────────────────────────────────────

    def fetch_estimates(self, ticker: str) -> list[EstimateDTO]:
        out: list[EstimateDTO] = []
        # The free calendar rows already carry current-quarter consensus; the
        # dedicated endpoints below are premium-gated on some plans, so treat
        # missing data as "no estimates", not an error.
        today = date.today()
        for row in (self._get("/calendar/earnings",
                              **{"from": (today - timedelta(days=7)).isoformat(),
                                 "to": (today + timedelta(days=7)).isoformat(),
                                 "symbol": ticker}) or {}).get("earningsCalendar", []):
            if (row.get("symbol") or "").upper() != ticker.upper():
                continue
            if row.get("epsEstimate") is not None:
                out.append(EstimateDTO("eps", "current", float(row["epsEstimate"]), self.name))
            if row.get("revenueEstimate") is not None:
                out.append(EstimateDTO("revenue", "current", float(row["revenueEstimate"]),
                                       self.name))
        return out

    # ── prices ────────────────────────────────────────────────────────────────

    def quote(self, ticker: str) -> Quote:
        data = self._get("/quote", symbol=ticker)
        price = data.get("c")
        if not price:
            raise ProviderError(f"finnhub: empty quote for {ticker}")
        as_of = None
        if data.get("t"):
            as_of = datetime.fromtimestamp(data["t"], tz=UTC)
        return Quote(ticker=ticker.upper(), price=float(price),
                     prev_close=data.get("pc"), as_of=as_of, provider=self.name)

    def daily_closes(self, ticker: str, days: int) -> list[float]:
        now = int(time.time())
        data = self._get("/stock/candle", symbol=ticker, resolution="D",
                         **{"from": now - days * 86400 - 86400 * 5, "to": now})
        if data.get("s") != "ok":
            raise ProviderError(f"finnhub: no candles for {ticker}")
        return [float(c) for c in data.get("c", [])][-days:]

    # ── profile ───────────────────────────────────────────────────────────────

    def profile(self, ticker: str) -> CompanyProfile:
        data = self._get("/stock/profile2", symbol=ticker)
        if not data:
            raise ProviderError(f"finnhub: no profile for {ticker}")
        market_cap = data.get("marketCapitalization")
        return CompanyProfile(
            ticker=ticker.upper(),
            name=data.get("name", ""),
            exchange=data.get("exchange", ""),
            # Finnhub reports market cap in millions
            market_cap=float(market_cap) * 1e6 if market_cap else None,
            industry=data.get("finnhubIndustry", ""),
            ir_url=data.get("weburl", ""),
        )
