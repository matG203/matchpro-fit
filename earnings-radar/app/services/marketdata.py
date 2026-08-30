"""MarketDataService — pre-earnings context, reaction capture, spike/fade
classification and cross-provider validation.

Pure analytics live at module level (testable without a DB or network);
the service wires them to price providers and persistence.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.domain.enums import ReactionPattern
from app.providers.base import (
    AllProvidersFailed,
    FallbackChain,
    PriceProvider,
    ProviderError,
    ProviderUnavailable,
    Quote,
)

logger = logging.getLogger("earnings_radar.marketdata")


@dataclass
class ReactionPoint:
    minutes_after: float
    pct_change: float          # vs pre-release price


@dataclass
class MarketContextData:
    prev_close: float | None = None
    pre_release_price: float | None = None
    run_5d_pct: float | None = None
    run_1m_pct: float | None = None
    run_3m_pct: float | None = None
    implied_move_pct: float | None = None       # Phase 2; never fabricated
    reaction_points: list[ReactionPoint] = field(default_factory=list)
    initial_reaction_pct: float | None = None
    current_reaction_pct: float | None = None
    reaction_vs_prev_close_pct: float | None = None
    reaction_pattern: ReactionPattern = ReactionPattern.NONE
    unresolved: bool = False
    notes: list[str] = field(default_factory=list)


# ─── Pure analytics ───────────────────────────────────────────────────────────


def pct_change(from_price: float, to_price: float) -> float:
    return (to_price - from_price) / from_price * 100


def compute_runs(closes: list[float]) -> tuple[float | None, float | None, float | None]:
    """(5d, 1m≈21 sessions, 3m≈63 sessions) % runs from a list of daily
    closes, oldest→newest, ending at the pre-earnings close."""
    def run(days: int) -> float | None:
        if len(closes) <= days:
            return None
        return pct_change(closes[-days - 1], closes[-1])

    return run(5), run(21), run(63)


def classify_reaction(points: list[ReactionPoint]) -> ReactionPattern:
    """Spike-and-fade / momentum detection (spec §SPIKE AND FADE)."""
    if len(points) < 2:
        return ReactionPattern.NONE
    ordered = sorted(points, key=lambda p: p.minutes_after)
    initial = ordered[0].pct_change
    latest = ordered[-1].pct_change
    if abs(initial) >= 5.0 and abs(latest) <= abs(initial) * 0.4:
        return ReactionPattern.POST_EARNINGS_REVERSAL
    if initial > 0 and latest >= initial + 3.0:
        return ReactionPattern.POST_EARNINGS_MOMENTUM
    if initial < 0 and latest <= initial - 3.0:
        return ReactionPattern.POST_EARNINGS_MOMENTUM     # momentum down is also momentum
    return ReactionPattern.NONE


def quotes_conflict(move_a_pct: float, move_b_pct: float, threshold_pct: float) -> bool:
    """Two providers disagree materially on the post-release move
    (regression case 5)."""
    return abs(move_a_pct - move_b_pct) > threshold_pct


# ─── Service ──────────────────────────────────────────────────────────────────


class MarketDataService:
    def __init__(self, price_providers: list[PriceProvider], conflict_threshold_pct: float,
                 health_cb=None, data_delay_seconds: float = 0.0):
        self._providers = price_providers
        self._threshold = conflict_threshold_pct
        self._chain = FallbackChain("price", health_cb=health_cb)
        # How far behind live the feed is. On a delayed plan a quote taken two
        # minutes after a release still shows the pre-release price.
        self._delay_seconds = max(0.0, data_delay_seconds)

    def snapshot_quote(self, ticker: str) -> Quote:
        quote, _ = self._chain.call(self._providers, "quote", ticker)
        return quote

    def pre_earnings_context(self, ticker: str) -> MarketContextData:
        ctx = MarketContextData()
        try:
            quote = self.snapshot_quote(ticker)
            ctx.pre_release_price = quote.price
            ctx.prev_close = quote.prev_close
        except AllProvidersFailed as exc:
            ctx.notes.append(f"pre-earnings quote unavailable: {exc.errors}")
        try:
            closes, _ = self._chain.call(self._providers, "daily_closes", ticker, 70)
            if closes:
                ctx.run_5d_pct, ctx.run_1m_pct, ctx.run_3m_pct = compute_runs(closes)
                if ctx.prev_close is None:
                    ctx.prev_close = closes[-1]
        except AllProvidersFailed as exc:
            ctx.notes.append(f"historical closes unavailable: {exc.errors}")
        return ctx

    def capture_reaction(self, ticker: str, ctx: MarketContextData,
                         minutes_after: float) -> MarketContextData:
        """Capture one post-release point, cross-checking providers when the
        move looks extreme."""
        if ctx.pre_release_price is None:
            ctx.unresolved = True
            ctx.notes.append("no pre-release price — reaction cannot be measured")
            return ctx

        if minutes_after * 60 < self._delay_seconds:
            # The feed still shows pre-release prices, so any quote taken now
            # would read as a 0% reaction — and be recorded as the market
            # declining to confirm a good report. Withhold instead: the later
            # capture points measure it properly once the data catches up.
            ctx.unresolved = True
            ctx.notes.append(
                f"{self._delay_seconds / 60:.0f}-minute delayed feed — reaction at "
                f"+{minutes_after:.0f}m is not visible yet; market confirmation withheld")
            return ctx

        moves: dict[str, float] = {}
        for provider in self._providers:
            try:
                quote = provider.quote(ticker)
                moves[provider.name] = pct_change(ctx.pre_release_price, quote.price)
            except (ProviderError, ProviderUnavailable) as exc:
                # A silent drop here would let one dead feed masquerade as
                # agreement between the survivors.
                ctx.notes.append(f"{provider.name} post-release quote failed: {exc}")
                logger.warning("post-release quote failed for %s via %s: %s",
                               ticker, provider.name, exc)
        if not moves:
            ctx.unresolved = True
            ctx.notes.append("no price provider returned a post-release quote")
            return ctx

        values = list(moves.values())
        primary = values[0]
        if len(values) >= 2 and quotes_conflict(values[0], values[1], self._threshold):
            ctx.unresolved = True
            ctx.notes.append(
                f"price providers conflict: {moves} — market confirmation withheld")
            return ctx

        ctx.unresolved = False
        ctx.reaction_points.append(ReactionPoint(minutes_after, primary))
        if ctx.initial_reaction_pct is None:
            ctx.initial_reaction_pct = primary
        ctx.current_reaction_pct = primary
        if ctx.prev_close:
            post_price = ctx.pre_release_price * (1 + primary / 100)
            ctx.reaction_vs_prev_close_pct = pct_change(ctx.prev_close, post_price)
        ctx.reaction_pattern = classify_reaction(ctx.reaction_points)
        return ctx
