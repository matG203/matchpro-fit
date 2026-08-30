"""Abnormal move measurement and Reaction Room (spec §3, §37-39, §50-51).

"Skyrocket" is defined relative to the stock's own normal behaviour, not as a
raw percentage. +6% in Microsoft is an enormous abnormal event; +6% in a
volatile microcap is a Tuesday.

Reaction Room answers the question that stops us chasing: given how far this
has already moved versus what comparable events historically produced, how
much of the move might still be ahead?
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.catalyst.enums import HaltState


def pct_change(from_price: float, to_price: float) -> float:
    if not from_price:
        return 0.0
    return (to_price - from_price) / from_price * 100


@dataclass
class PricePoint:
    label: str
    offset_seconds: float
    price: float | None = None
    volume: float | None = None
    benchmark_price: float | None = None
    sector_price: float | None = None
    captured_at: datetime | None = None


@dataclass
class AbnormalMove:
    raw_move_pct: float | None = None
    benchmark_move_pct: float | None = None
    sector_move_pct: float | None = None
    abnormal_move_pct: float | None = None
    move_multiple: float | None = None      # move ÷ normal expected move
    basis: str = ""
    notes: list[str] = field(default_factory=list)


def normal_expected_move_pct(*, realised_volatility_pct: float | None = None,
                             atr_pct: float | None = None,
                             implied_move_pct: float | None = None) -> tuple[float | None, str]:
    """Best available estimate of a normal move for this stock (§3).

    Preference order: options-implied (forward-looking) → ATR → realised vol.
    Never fabricated — returns None when nothing is available.
    """
    if implied_move_pct is not None and implied_move_pct > 0:
        return implied_move_pct, "options_implied"
    if atr_pct is not None and atr_pct > 0:
        return atr_pct, "atr"
    if realised_volatility_pct is not None and realised_volatility_pct > 0:
        return realised_volatility_pct, "realised_volatility"
    return None, "unavailable"


def compute_abnormal_move(*, price_before: float | None, price_now: float | None,
                          benchmark_before: float | None = None,
                          benchmark_now: float | None = None,
                          sector_before: float | None = None,
                          sector_now: float | None = None,
                          normal_move_pct: float | None = None,
                          normal_basis: str = "") -> AbnormalMove:
    """Benchmark-adjusted, volatility-normalised move (§3, §50)."""
    result = AbnormalMove(basis=normal_basis)
    if price_before is None or price_now is None:
        result.notes.append("price unavailable — move cannot be measured")
        return result

    result.raw_move_pct = round(pct_change(price_before, price_now), 3)

    if benchmark_before and benchmark_now:
        result.benchmark_move_pct = round(pct_change(benchmark_before, benchmark_now), 3)
    if sector_before and sector_now:
        result.sector_move_pct = round(pct_change(sector_before, sector_now), 3)

    # Prefer sector as the comparator when available: it strips out both market
    # and industry moves, leaving company-specific performance.
    comparator = result.sector_move_pct
    comparator_name = "sector"
    if comparator is None:
        comparator = result.benchmark_move_pct
        comparator_name = "market"
    if comparator is not None:
        result.abnormal_move_pct = round(result.raw_move_pct - comparator, 3)
        result.notes.append(f"adjusted against {comparator_name} ({comparator:+.2f}%)")
    else:
        result.abnormal_move_pct = result.raw_move_pct
        result.notes.append("no benchmark available — raw move used as abnormal move")

    if normal_move_pct:
        result.move_multiple = round(abs(result.abnormal_move_pct) / normal_move_pct, 2)
        result.notes.append(
            f"{result.move_multiple:.2f}× a normal move ({normal_move_pct:.2f}%, {normal_basis})")
    else:
        result.notes.append("no volatility estimate — move cannot be normalised")

    return result


@dataclass
class ReactionRoom:
    score: float
    move_since_disclosure_pct: float | None = None
    abnormal_move_pct: float | None = None
    analogue_expected_move_pct: float | None = None
    pre_event_runup_pct: float | None = None
    unresolved: bool = False
    notes: list[str] = field(default_factory=list)


def assess_reaction_room(*, abnormal: AbnormalMove,
                         analogue_expected_move_pct: float | None,
                         pre_event_runup_pct: float | None = None,
                         minutes_since_disclosure: float | None = None,
                         halt_state: HaltState = HaltState.NONE,
                         volume_multiple: float | None = None,
                         prices_stale: bool = False,
                         move_observable: bool = True,
                         data_delay_seconds: float = 0.0) -> ReactionRoom:
    """How much of the plausible move may remain (§39, §68).

    The analogue median is contextual evidence, never a price target.
    """
    notes: list[str] = []

    if not move_observable:
        # The most dangerous case on a delayed feed. The measured move is 0%,
        # which would otherwise score as "untouched — all the room is still
        # there" on a stock that may already have run 60%. Scoring the absence
        # of evidence as evidence of absence would invert the signal exactly
        # when we know least, so this is unresolved until the data arrives.
        minutes = data_delay_seconds / 60
        return ReactionRoom(
            score=5.0, unresolved=True,
            notes=[f"{minutes:.0f}-minute delayed feed — the move since disclosure is "
                   "not visible yet; re-scored when the data arrives"])

    if abnormal.abnormal_move_pct is None:
        return ReactionRoom(score=5.0, unresolved=True,
                            notes=["price data unavailable — reaction room unresolved"])

    if prices_stale:
        # Same consequence as a halt: we are measuring against a price the
        # market is not currently making.
        return ReactionRoom(
            score=5.0, abnormal_move_pct=abnormal.abnormal_move_pct, unresolved=True,
            notes=["tape has stopped — reaction room unresolved until trading resumes"])

    if halt_state in (HaltState.NEWS_PENDING, HaltState.LULD, HaltState.REGULATORY):
        # Displayed prices are meaningless mid-halt; treat as unresolved and
        # re-assess on resumption (§48).
        return ReactionRoom(
            score=5.0, abnormal_move_pct=abnormal.abnormal_move_pct, unresolved=True,
            notes=[f"stock halted ({halt_state.value}) — reaction room re-assessed on resumption"])

    moved = abnormal.abnormal_move_pct

    if analogue_expected_move_pct and analogue_expected_move_pct > 0:
        consumed = moved / analogue_expected_move_pct
        remaining = max(0.0, 1.0 - consumed)
        score = remaining * 10.0
        notes.append(
            f"abnormal move {moved:+.1f}% vs analogue expectation "
            f"{analogue_expected_move_pct:.1f}% — {consumed:.0%} of the historical "
            f"move already realised")
        if consumed >= 1.0:
            notes.append("move has already met or exceeded comparable events")
    elif abnormal.move_multiple is not None:
        # No analogue: fall back on volatility multiples. Beyond ~3x a normal
        # move, most of the repricing has typically happened.
        remaining = max(0.0, 1.0 - abnormal.move_multiple / 3.0)
        score = remaining * 10.0
        notes.append(
            f"no analogue available — using volatility multiple {abnormal.move_multiple:.2f}×")
    else:
        score = 5.0
        notes.append("neither analogue nor volatility estimate available — neutral 5.0")

    # A large pre-event run-up means the market was already positioning (§37).
    if pre_event_runup_pct and pre_event_runup_pct > 5:
        penalty = min(pre_event_runup_pct / 10.0, 3.0)
        score -= penalty
        notes.append(
            f"pre-event run-up {pre_event_runup_pct:+.1f}% — anticipation already in the price "
            f"(-{penalty:.1f})")

    # Volume explosion means the market has already recognised it (§45).
    if volume_multiple and volume_multiple >= 5:
        score -= 1.0
        notes.append(f"volume already {volume_multiple:.1f}× normal — recognition well advanced")

    # Time decay: the further from disclosure, the less room is plausibly left.
    if minutes_since_disclosure is not None and minutes_since_disclosure > 60:
        decay = min((minutes_since_disclosure - 60) / 120.0, 2.0)
        score -= decay
        notes.append(
            f"{minutes_since_disclosure:.0f} minutes since disclosure (-{decay:.1f})")

    return ReactionRoom(
        score=round(max(0.0, min(score, 10.0)), 2),
        move_since_disclosure_pct=abnormal.raw_move_pct,
        abnormal_move_pct=abnormal.abnormal_move_pct,
        analogue_expected_move_pct=analogue_expected_move_pct,
        pre_event_runup_pct=pre_event_runup_pct,
        notes=notes)
