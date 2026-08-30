"""Live market context for Catalyst Sentinel.

This is the production implementation behind the pipeline's injected
`market_context_fn`. It answers four questions with real data:

  * **What was the price before this became public?**  Not "yesterday's close"
    and not "the price now" — the last print before the disclosure timestamp,
    taken from minute bars so it works pre-market and after hours.
  * **What has the market as a whole done since then?**  The same window on a
    benchmark (and a sector ETF where the company's sector is known), so a
    stock that rose 3% on a day the market rose 3% scores nothing.
  * **Can this stock move violently?**  Free float, short interest with its
    settlement date, relative volume, ATR.
  * **Are the prices usable at all?**  Spread, session, and how long it has
    been since the last print.

Design rules carried over from the rest of the system:

  * Every field is optional. A provider that cannot answer leaves `None`, and
    the scoring engines cap themselves and say why. Nothing is invented.
  * One failing call never takes down the context — each block is guarded
    independently, so a missing short-interest entitlement still leaves the
    price and benchmark analysis intact.
  * Results are computed against a supplied `now`, so the whole thing is
    testable with a fake provider and no clock dependence.
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.catalyst import amplification as amp
from app.catalyst.enums import HaltState
from app.catalyst.pipeline import MarketContextInputs
from app.config import Settings
from app.domain.timeutil import ensure_utc
from app.providers.base import (
    Bar,
    BarProvider,
    MarketStructureProvider,
    ProviderError,
    ProviderUnavailable,
)

logger = logging.getLogger("earnings_radar.catalyst.market")

# Sector proxies. A sector comparator strips out both the market move and the
# industry move, leaving something closer to company-specific performance —
# which is what an abnormal move is supposed to measure (§50).
SECTOR_ETFS: dict[str, str] = {
    "technology": "XLK",
    "information technology": "XLK",
    "healthcare": "XLV",
    "health care": "XLV",
    "financial": "XLF",
    "financial services": "XLF",
    "financials": "XLF",
    "energy": "XLE",
    "industrials": "XLI",
    "industrial": "XLI",
    "consumer discretionary": "XLY",
    "consumer cyclical": "XLY",
    "consumer staples": "XLP",
    "consumer defensive": "XLP",
    "utilities": "XLU",
    "real estate": "XLRE",
    "materials": "XLB",
    "basic materials": "XLB",
    "communication services": "XLC",
    "biotechnology": "XBI",
}


def sector_etf(sector: str | None, industry: str | None = None) -> str | None:
    """Map a sector/industry string onto a tradeable proxy, or None."""
    for candidate in (sector, industry):
        if not candidate:
            continue
        key = candidate.strip().lower()
        if key in SECTOR_ETFS:
            return SECTOR_ETFS[key]
        for name, etf in SECTOR_ETFS.items():
            if name in key:
                return etf
    return None


@dataclass
class CompanyHints:
    """What the caller already knows, so we do not re-fetch it."""

    sector: str = ""
    industry: str = ""
    annual_revenue: float | None = None


def price_at(bars: list[Bar], when: datetime, *,
             completed_only: bool = False) -> float | None:
    """Closing price of the relevant bar at `when`, or None.

    By default this is the bar *containing* `when` — what you want for a
    forward horizon ("the price 5 minutes after the news").

    With `completed_only`, the bar containing `when` is excluded and the last
    bar that had already closed is used instead. That is the only correct
    baseline for an event: the minute in which news breaks already contains
    the reaction, so measuring the move from its close would quietly erase
    most of it. A bar's end is taken from the next bar's start, and the final
    bar is treated as still open, because nothing here can prove otherwise.

    Returns None rather than reaching forward for the nearest available price.
    """
    if not bars:
        return None
    when = ensure_utc(when)
    chosen: float | None = None
    for index, bar in enumerate(bars):
        if ensure_utc(bar.start_utc) > when:
            break
        if completed_only:
            following = bars[index + 1] if index + 1 < len(bars) else None
            if following is None or ensure_utc(following.start_utc) > when:
                break               # this bar is still open at `when`
        chosen = bar.close
    return chosen


def atr_pct(bars: list[Bar], periods: int = 14) -> float | None:
    """Average true range as a percentage of price (§3).

    True range, not the naive high−low, so gaps between sessions count — which
    for a catalyst stock is most of the movement.
    """
    if len(bars) < periods + 1:
        return None
    ranges: list[float] = []
    for previous, current in zip(bars[-periods - 1:-1], bars[-periods:], strict=True):
        true_range = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close))
        ranges.append(true_range)
    last_close = bars[-1].close
    if not ranges or not last_close:
        return None
    return round(sum(ranges) / len(ranges) / last_close * 100, 3)


def realised_volatility_pct(bars: list[Bar]) -> float | None:
    """Standard deviation of daily returns — the typical day, in percent."""
    closes = [b.close for b in bars if b.close]
    if len(closes) < 5:
        return None
    # Deliberately offset by one — pairing each close with the next.
    returns = [(b - a) / a * 100 for a, b in zip(closes, closes[1:], strict=False) if a]
    if len(returns) < 4:
        return None
    return round(statistics.pstdev(returns), 3)


def runup_pct(bars: list[Bar], reference_price: float | None) -> float | None:
    """How far the stock had already travelled before the event (§37)."""
    if reference_price is None or not bars:
        return None
    base = bars[0].close
    if not base:
        return None
    return round((reference_price - base) / base * 100, 3)


class CatalystMarketDataService:
    """Builds a `MarketContextInputs` for one ticker at one instant."""

    def __init__(self, *, bars: BarProvider | None,
                 structure: MarketStructureProvider | None,
                 settings: Settings,
                 float_providers: list | None = None):
        self._bars = bars
        self._structure = structure
        self._settings = settings
        self._float_providers = list(float_providers or [])

    @property
    def available(self) -> bool:
        return self._bars is not None and self._structure is not None

    def context(self, ticker: str, now: datetime, *,
                event_at: datetime | None = None,
                hints: CompanyHints | None = None) -> MarketContextInputs:
        """Full decision-time context.

        `event_at` is when the catalyst became public. Without it there is no
        honest "before" price, so the move is left unmeasured rather than
        guessed at from an arbitrary baseline.
        """
        now = ensure_utc(now)
        hints = hints or CompanyHints()
        session = amp.market_session(now)
        delay = max(0.0, float(self._settings.market_data_delay_seconds))
        observable_through = now - timedelta(seconds=delay)

        context = MarketContextInputs(
            structure=amp.MarketStructure(session=session, halt_state=HaltState.UNKNOWN),
            price_captured_at=now,
            observable_through=observable_through,
            data_delay_seconds=delay)

        if event_at is not None:
            # The move is visible only once the feed can show a print made
            # after the disclosure. Until then a 0% reading means "we cannot
            # see it yet", not "it has not moved" — opposite conclusions.
            context.move_observable = observable_through > ensure_utc(event_at)

        if not self.available:
            return context

        ticker = ticker.upper()
        snapshot = self._safe(lambda: self._structure.snapshot(ticker), f"snapshot {ticker}")
        details = self._safe(lambda: self._structure.details(ticker), f"details {ticker}")
        daily = self._safe(lambda: self._bars.daily_bars(
            ticker, max(self._settings.catalyst_atr_days + 6,
                        self._settings.catalyst_runup_lookback_days + 6)),
            f"daily bars {ticker}") or []

        # Price reasoning runs against what the feed can actually show, not
        # against wall-clock now; structure reasoning still needs the real now
        # to judge staleness and session.
        self._fill_prices(context, ticker, observable_through, event_at, snapshot, daily)
        self._fill_comparators(context, observable_through, event_at, hints)
        self._fill_structure(context, ticker, now, snapshot, details, daily)

        if not context.move_observable:
            # Do not publish a "current" price that predates the news; it would
            # produce a 0% move that looks like a measurement.
            context.price_now = None
        return context

    def as_context_fn(self):
        """Adapter matching the pipeline's `market_context_fn` contract."""

        def fetch(ticker: str, now: datetime, event_at: datetime | None = None,
                  sector: str = "", industry: str = "") -> MarketContextInputs:
            return self.context(ticker, now, event_at=event_at,
                                hints=CompanyHints(sector=sector, industry=industry))

        return fetch

    # ── price points ──────────────────────────────────────────────────────────

    def _fill_prices(self, context: MarketContextInputs, ticker: str,
                     observable_through: datetime, event_at: datetime | None,
                     snapshot, daily: list[Bar]) -> None:
        if snapshot is not None and snapshot.price:
            context.price_now = snapshot.price

        if event_at is None:
            return
        event_at = ensure_utc(event_at)

        minutes = self._intraday(ticker, event_at, observable_through)
        context.price_before = price_at(minutes, event_at, completed_only=True)
        if context.price_before is None and snapshot is not None:
            # Before the first print of the day there is no intraday bar to use;
            # the previous close is the honest baseline in that case.
            context.price_before = snapshot.prev_close

        if context.price_now is None and minutes:
            context.price_now = minutes[-1].close

        lookback = self._settings.catalyst_runup_lookback_days
        window = [b for b in daily if ensure_utc(b.start_utc) <= event_at][-lookback:]
        context.pre_event_runup_pct = runup_pct(window, context.price_before)

    def _intraday(self, ticker: str, event_at: datetime,
                  observable_through: datetime) -> list[Bar]:
        """Minute bars spanning the disclosure, with a margin either side.

        The margin matters: a stock that had not traded for twenty minutes when
        the news hit has no bar at the disclosure minute, and the last print
        before it is the correct baseline.
        """
        start = event_at - timedelta(hours=6)
        end = observable_through + timedelta(minutes=1)
        return self._safe(
            lambda: self._bars.bars(ticker, start=start, end=end, timespan="minute"),
            f"minute bars {ticker}") or []

    def _fill_comparators(self, context: MarketContextInputs,
                          observable_through: datetime,
                          event_at: datetime | None, hints: CompanyHints) -> None:
        if event_at is None:
            return
        event_at = ensure_utc(event_at)

        benchmark = self._settings.benchmark_ticker
        if benchmark:
            before, after = self._window_prices(benchmark, event_at, observable_through)
            context.benchmark_before, context.benchmark_now = before, after

        etf = sector_etf(hints.sector, hints.industry)
        if etf and etf != benchmark:
            before, after = self._window_prices(etf, event_at, observable_through)
            context.sector_before, context.sector_now = before, after

    def _window_prices(self, ticker: str, event_at: datetime,
                       observable_through: datetime) -> tuple[float | None, float | None]:
        """(price at the event, price now) for a comparator instrument.

        Both come from the same bar series, so the two ends of the comparison
        are measured the same way — mixing a bar close with a live quote would
        introduce a spurious difference of its own.
        """
        bars = self._safe(
            lambda: self._bars.bars(ticker, start=event_at - timedelta(hours=6),
                                    end=observable_through + timedelta(minutes=1),
                                    timespan="minute"),
            f"comparator bars {ticker}") or []
        if not bars:
            return None, None
        return price_at(bars, event_at, completed_only=True), bars[-1].close

    # ── market structure ──────────────────────────────────────────────────────

    def _fill_structure(self, context: MarketContextInputs, ticker: str, now: datetime,
                        snapshot, details, daily: list[Bar]) -> None:
        structure = context.structure

        if snapshot is not None:
            structure.spread_pct = snapshot.spread_pct()
            structure.share_price = snapshot.price
            if snapshot.last_trade_at is not None:
                # Staleness means silence *beyond* the feed's own delay. On a
                # 15-minute plan every healthy quote is 15 minutes old, so
                # measuring raw age would flag every stock as halted.
                age = (now - ensure_utc(snapshot.last_trade_at)).total_seconds()
                structure.quote_stale_seconds = max(
                    0.0, age - self._settings.market_data_delay_seconds)

        if details is not None:
            structure.market_cap = details.market_cap
            structure.shares_outstanding = details.shares_outstanding
            if structure.market_cap is None and (
                    details.shares_outstanding and structure.share_price):
                structure.market_cap = details.shares_outstanding * structure.share_price

        structure.free_float_shares = self._free_float(ticker)

        if daily:
            structure.atr_pct = atr_pct(daily, self._settings.catalyst_atr_days)
            structure.realised_volatility_pct = realised_volatility_pct(daily)
            volumes = [b.volume for b in daily[-20:] if b.volume]
            closes = [b.close for b in daily[-20:] if b.close]
            if volumes and closes:
                avg_volume = sum(volumes) / len(volumes)
                avg_close = sum(closes) / len(closes)
                structure.avg_dollar_volume = round(avg_volume * avg_close, 2)
                if snapshot is not None and snapshot.day_volume:
                    structure.relative_volume = amp.relative_volume(
                        snapshot.day_volume, avg_volume, now)

        self._fill_short_interest(structure, ticker, now)

    def _free_float(self, ticker: str) -> float | None:
        """Free float from whichever provider carries it — None if none does.

        Shares outstanding is never substituted here; the amplification engine
        depends on the two being different things (§43).
        """
        for provider in self._float_providers:
            getter = getattr(provider, "free_float_shares", None)
            if getter is None:
                continue
            value = self._safe(lambda g=getter: g(ticker),
                               f"free float {ticker}")
            if value:
                return float(value)
        return None

    def _fill_short_interest(self, structure: amp.MarketStructure, ticker: str,
                             now: datetime) -> None:
        short = self._safe(lambda: self._structure.short_interest(ticker),
                           f"short interest {ticker}")
        if short is None or not short.short_interest_shares:
            return

        structure.days_to_cover = short.days_to_cover
        if short.settlement_date is not None:
            # A settlement date is a date, not an instant. Anchoring it to
            # midnight makes the figure look slightly older than it is, which
            # is the safe direction: freshness confidence errs downwards.
            structure.short_interest_as_of = datetime.combine(
                short.settlement_date, datetime.min.time(), tzinfo=UTC)

        if structure.free_float_shares:
            structure.short_percent_float = round(
                short.short_interest_shares / structure.free_float_shares * 100, 3)
        if structure.shares_outstanding:
            structure.short_percent_shares_outstanding = round(
                short.short_interest_shares / structure.shares_outstanding * 100, 3)

    # ── plumbing ──────────────────────────────────────────────────────────────

    @staticmethod
    def _safe(call, description: str):
        """Run one provider call; a failure degrades that field, not the run."""
        try:
            return call()
        except ProviderUnavailable as exc:
            logger.debug("market data unavailable (%s): %s", description, exc)
        except ProviderError as exc:
            logger.warning("market data failed (%s): %s", description, exc)
        except Exception:
            logger.exception("unexpected market-data error (%s)", description)
        return None
