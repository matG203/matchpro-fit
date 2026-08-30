"""Polygon.io adapter: real-time and extended-hours prices, bars, reference
data and short interest.

Chosen over the free tiers because catalysts break pre-market and after hours,
and a delayed consolidated quote cannot tell you what a stock is doing at
07:12 New York time. Three capabilities matter here:

  * minute bars covering 04:00–20:00 ET, so an event can be priced at the
    moment it became public rather than at "now";
  * a snapshot carrying bid/ask, so Execution Quality has a real spread;
  * reference data and short interest for Move Amplification.

What Polygon does **not** publish is free float. This adapter therefore
returns ``None`` for it rather than substituting shares outstanding — the
distinction the amplification engine depends on (§43). Free float is sourced
separately (see ``FmpProvider.free_float_shares``); when nothing supplies it,
amplification caps itself and says so.

Rate limits: paid plans are effectively unlimited, but this stays self-throttled
so a runaway loop cannot hammer the API. Reference data is cached for a day and
snapshots for a few seconds — a catalyst pipeline can ask for the same ticker
several times in one pass.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx

from app.config import get_settings
from app.providers.base import (
    Bar,
    BarProvider,
    MarketStructureProvider,
    PriceProvider,
    ProviderError,
    ProviderUnavailable,
    Quote,
    RateLimiter,
    ShortInterest,
    Snapshot,
    TickerDetails,
    TTLCache,
)

BASE = "https://api.polygon.io"

# Polygon timestamps: aggregates are epoch milliseconds, trades/quotes in the
# snapshot are epoch nanoseconds.
_MS = 1_000
_NS = 1_000_000_000


def _from_ms(value) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(float(value) / _MS, tz=UTC)


def _from_ns(value) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(float(value) / _NS, tz=UTC)


class PolygonProvider(PriceProvider, BarProvider, MarketStructureProvider):
    name = "polygon"

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None,
                 *, rate_per_second: float = 8.0):
        self._api_key = api_key if api_key is not None else get_settings().polygon_api_key
        self._client = client or httpx.Client(timeout=15.0)
        self._limiter = RateLimiter(rate_per_second=rate_per_second, burst=10)
        self._reference_cache = TTLCache(ttl_seconds=86400.0, max_items=4096)
        self._snapshot_cache = TTLCache(ttl_seconds=5.0, max_items=1024)

    def enabled(self) -> bool:
        return bool(self._api_key)

    # ── transport ─────────────────────────────────────────────────────────────

    def _get(self, path: str, **params) -> dict:
        if not self._api_key:
            raise ProviderUnavailable("polygon: no API key configured")
        self._limiter.acquire()
        params["apiKey"] = self._api_key
        try:
            resp = self._client.get(f"{BASE}{path}", params=params)
            if resp.status_code == 429:
                raise ProviderError("polygon rate limited")
            if resp.status_code == 403:
                # Wrong plan for this endpoint — permanent, so do not retry it.
                raise ProviderUnavailable(f"polygon: not entitled to {path}")
            if resp.status_code == 404:
                raise ProviderError(f"polygon: no data for {path}")
            resp.raise_for_status()
            return resp.json() or {}
        except httpx.HTTPError as exc:
            raise ProviderError(f"polygon request failed ({path}): {exc}") from exc

    # ── prices ────────────────────────────────────────────────────────────────

    def quote(self, ticker: str) -> Quote:
        snap = self.snapshot(ticker)
        if snap.price is None:
            raise ProviderError(f"polygon: empty snapshot for {ticker}")
        return Quote(ticker=snap.ticker, price=snap.price, prev_close=snap.prev_close,
                     volume=snap.day_volume, as_of=snap.last_trade_at, provider=self.name)

    def daily_closes(self, ticker: str, days: int) -> list[float]:
        return [b.close for b in self.daily_bars(ticker, days)]

    # ── bars ──────────────────────────────────────────────────────────────────

    def bars(self, ticker: str, *, start: datetime, end: datetime,
             timespan: str = "minute", multiplier: int = 1,
             limit: int = 5000) -> list[Bar]:
        """Bars between two instants, oldest first.

        ``adjusted=false`` because we are measuring a move over minutes or
        hours: split adjustment is irrelevant intraday and only introduces a
        discrepancy against the live quote.
        """
        start_ms = int(start.timestamp() * _MS)
        end_ms = int(end.timestamp() * _MS)
        data = self._get(
            f"/v2/aggs/ticker/{ticker.upper()}/range/{multiplier}/{timespan}/"
            f"{start_ms}/{end_ms}",
            adjusted="false", sort="asc", limit=limit)
        return [self._to_bar(row) for row in (data.get("results") or [])]

    def daily_bars(self, ticker: str, days: int) -> list[Bar]:
        end = datetime.now(UTC)
        # Over-fetch: weekends and holidays are not trading days.
        start = end - timedelta(days=int(days * 1.7) + 10)
        data = self._get(
            f"/v2/aggs/ticker/{ticker.upper()}/range/1/day/"
            f"{start.date().isoformat()}/{end.date().isoformat()}",
            adjusted="true", sort="asc", limit=5000)
        bars = [self._to_bar(row) for row in (data.get("results") or [])]
        return bars[-days:]

    @staticmethod
    def _to_bar(row: dict) -> Bar:
        return Bar(
            start_utc=_from_ms(row.get("t")) or datetime.now(UTC),
            open=float(row.get("o") or 0.0), high=float(row.get("h") or 0.0),
            low=float(row.get("l") or 0.0), close=float(row.get("c") or 0.0),
            volume=float(row.get("v") or 0.0),
            vwap=float(row["vw"]) if row.get("vw") is not None else None,
            trades=int(row["n"]) if row.get("n") is not None else None)

    # ── structure ─────────────────────────────────────────────────────────────

    def snapshot(self, ticker: str) -> Snapshot:
        key = ticker.upper()
        cached = self._snapshot_cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        data = self._get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{key}")
        node = data.get("ticker") or {}
        if not node:
            raise ProviderError(f"polygon: no snapshot for {ticker}")

        day = node.get("day") or {}
        prev = node.get("prevDay") or {}
        minute = node.get("min") or {}
        last_trade = node.get("lastTrade") or {}
        last_quote = node.get("lastQuote") or {}

        # Outside regular hours `day` is empty and the last minute bar is the
        # only thing that reflects extended-hours trading, so fall through in
        # that order rather than reporting a stale regular-session close.
        price = last_trade.get("p") or minute.get("c") or day.get("c") or None

        snap = Snapshot(
            ticker=key,
            price=float(price) if price else None,
            prev_close=float(prev["c"]) if prev.get("c") else None,
            day_volume=float(day["v"]) if day.get("v") else (
                float(minute["av"]) if minute.get("av") else None),
            day_open=float(day["o"]) if day.get("o") else None,
            day_high=float(day["h"]) if day.get("h") else None,
            day_low=float(day["l"]) if day.get("l") else None,
            bid=float(last_quote["p"]) if last_quote.get("p") else None,
            ask=float(last_quote["P"]) if last_quote.get("P") else None,
            last_trade_at=_from_ns(last_trade.get("t")),
            last_quote_at=_from_ns(last_quote.get("t")),
            provider=self.name)
        self._snapshot_cache.put(key, snap)
        return snap

    def details(self, ticker: str) -> TickerDetails:
        key = f"details:{ticker.upper()}"
        cached = self._reference_cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        data = self._get(f"/v3/reference/tickers/{ticker.upper()}")
        row = data.get("results") or {}
        if not row:
            raise ProviderError(f"polygon: no reference data for {ticker}")

        shares = (row.get("weighted_shares_outstanding")
                  or row.get("share_class_shares_outstanding"))
        details = TickerDetails(
            ticker=ticker.upper(),
            name=row.get("name", ""),
            market_cap=float(row["market_cap"]) if row.get("market_cap") else None,
            shares_outstanding=float(shares) if shares else None,
            # Polygon does not publish free float; leaving it None is correct.
            free_float_shares=None,
            primary_exchange=row.get("primary_exchange", ""),
            sic_description=row.get("sic_description", ""),
            active=bool(row.get("active", True)),
            provider=self.name)
        self._reference_cache.put(key, details)
        return details

    def short_interest(self, ticker: str) -> ShortInterest:
        key = f"si:{ticker.upper()}"
        cached = self._reference_cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        data = self._get("/stocks/v1/short-interest", ticker=ticker.upper(),
                         limit=1, sort="settlement_date.desc")
        rows = data.get("results") or []
        if not rows:
            raise ProviderError(f"polygon: no short interest for {ticker}")
        row = rows[0]

        settlement = None
        raw_date = row.get("settlement_date")
        if raw_date:
            try:
                settlement = date.fromisoformat(str(raw_date)[:10])
            except ValueError:
                settlement = None

        result = ShortInterest(
            ticker=ticker.upper(),
            settlement_date=settlement,
            short_interest_shares=(
                float(row["short_interest"]) if row.get("short_interest") else None),
            avg_daily_volume=(
                float(row["avg_daily_volume"]) if row.get("avg_daily_volume") else None),
            days_to_cover=(
                float(row["days_to_cover"]) if row.get("days_to_cover") else None),
            provider=self.name)
        self._reference_cache.put(key, result)
        return result

    # ── market status ─────────────────────────────────────────────────────────

    def market_status(self) -> dict:
        """Exchange-level status. Note this is the *market*, not a per-ticker
        halt: Polygon publishes individual halts over its websocket only, so
        halt state is inferred conservatively upstream rather than claimed."""
        return self._get("/v1/marketstatus/now")
