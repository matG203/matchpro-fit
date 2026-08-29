"""Move Amplification and Execution Quality (spec §42-47, §67, §70).

Two deliberately separate questions:

  MOVE_AMPLIFICATION — is this stock's market structure conducive to a violent
                       move? (small float, heavy short interest, thin supply)
  EXECUTION_QUALITY  — are the displayed prices actually usable? (spread,
                       liquidity, halt state, session)

They must not be merged: terrible liquidity amplifies percentage moves AND
makes the quote meaningless. Rewarding illiquidity in a single blended score
would systematically favour untradeable microcaps (§46).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.catalyst.enums import HaltState
from app.domain.timeutil import NEW_YORK


@dataclass
class MarketStructure:
    """As at decision time. None means unknown — never assumed."""

    market_cap: float | None = None
    free_float_shares: float | None = None
    shares_outstanding: float | None = None
    share_price: float | None = None
    avg_dollar_volume: float | None = None
    relative_volume: float | None = None
    spread_pct: float | None = None
    short_percent_float: float | None = None
    days_to_cover: float | None = None
    short_interest_as_of: datetime | None = None
    realised_volatility_pct: float | None = None
    atr_pct: float | None = None
    session: str = "unknown"
    halt_state: HaltState = HaltState.UNKNOWN

    def float_value(self) -> float | None:
        """Free-float market value. Falls back to nothing — shares outstanding
        is NOT free float (§43)."""
        if self.free_float_shares and self.share_price:
            return self.free_float_shares * self.share_price
        return None

    def missing(self) -> list[str]:
        names = ("market_cap", "free_float_shares", "avg_dollar_volume",
                 "short_percent_float", "relative_volume")
        return [n for n in names if getattr(self, n) is None]


@dataclass
class AmplificationResult:
    score: float
    components: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)


def short_interest_freshness(as_of: datetime | None, now: datetime) -> tuple[float, float | None]:
    """Published short interest lags reality by up to a month (§44).

    Returns (confidence 0-1, staleness in days). Never pretend stale data
    is live.
    """
    if as_of is None:
        return 0.0, None
    stale_days = (now - as_of).total_seconds() / 86400
    if stale_days < 0:
        return 0.0, stale_days
    if stale_days <= 7:
        return 1.0, stale_days
    if stale_days <= 21:
        return 0.7, stale_days
    if stale_days <= 45:
        return 0.4, stale_days
    return 0.15, stale_days


def _float_score(structure: MarketStructure) -> float | None:
    """Small tradeable supply reacts more violently (§43)."""
    float_value = structure.float_value()
    if float_value is None:
        return None
    if float_value <= 50e6:
        return 10.0
    if float_value <= 200e6:
        return 8.5
    if float_value <= 1e9:
        return 6.5
    if float_value <= 10e9:
        return 4.0
    return 2.0


def _market_cap_score(market_cap: float | None) -> float | None:
    if market_cap is None:
        return None
    if market_cap <= 300e6:
        return 9.5
    if market_cap <= 2e9:
        return 8.0
    if market_cap <= 10e9:
        return 6.0
    if market_cap <= 100e9:
        return 3.5
    return 2.0


def _short_score(structure: MarketStructure, now: datetime) -> tuple[float | None, float, str]:
    confidence, stale_days = short_interest_freshness(structure.short_interest_as_of, now)
    if structure.short_percent_float is None or confidence == 0.0:
        return None, 0.0, "short interest unavailable"

    pct = structure.short_percent_float
    if pct >= 30:
        raw = 10.0
    elif pct >= 20:
        raw = 8.5
    elif pct >= 10:
        raw = 6.5
    elif pct >= 5:
        raw = 4.5
    else:
        raw = 2.0

    if structure.days_to_cover and structure.days_to_cover >= 5:
        raw = min(10.0, raw + 1.0)

    note = f"short interest {pct:.1f}% of float"
    if stale_days is not None:
        note += f", as of {stale_days:.0f} days ago (confidence {confidence:.0%})"
    # Blend toward neutral in proportion to staleness rather than trusting it.
    adjusted = 5.0 + (raw - 5.0) * confidence
    return adjusted, confidence, note


def _volume_score(structure: MarketStructure) -> float | None:
    """Relative volume confirms the market is engaging (§45)."""
    if structure.relative_volume is None:
        return None
    rvol = structure.relative_volume
    if rvol >= 10:
        return 10.0
    if rvol >= 5:
        return 8.5
    if rvol >= 3:
        return 7.0
    if rvol >= 1.5:
        return 5.5
    return 3.0


def assess_amplification(structure: MarketStructure,
                         now: datetime | None = None) -> AmplificationResult:
    """How conducive is this stock's market structure to a sharp move?

    A 10 means genuinely unusual conditions — tiny float, heavy shorting,
    volume already exploding — not merely "a small company".
    """
    now = now or datetime.now(NEW_YORK)
    components: dict[str, float] = {}
    notes: list[str] = []

    float_score = _float_score(structure)
    if float_score is not None:
        components["free_float"] = float_score
        notes.append(f"free-float value ≈ ${structure.float_value():,.0f}")
    else:
        notes.append("free float unavailable — shares outstanding is NOT a substitute")

    cap_score = _market_cap_score(structure.market_cap)
    if cap_score is not None:
        components["market_cap"] = cap_score

    short_score, short_conf, short_note = _short_score(structure, now)
    if short_score is not None:
        components["short_interest"] = short_score
        notes.append(short_note)
    else:
        notes.append(short_note)

    volume_score = _volume_score(structure)
    if volume_score is not None:
        components["relative_volume"] = volume_score
        notes.append(f"relative volume {structure.relative_volume:.1f}×")

    if structure.realised_volatility_pct or structure.atr_pct:
        vol = structure.atr_pct or structure.realised_volatility_pct
        components["volatility"] = min(10.0, max(1.0, vol / 1.2))
        notes.append(f"typical daily range ≈ {vol:.1f}%")

    if not components:
        return AmplificationResult(
            score=5.0, notes=["no market-structure data available — neutral 5.0"],
            missing_inputs=structure.missing())

    # Weighted, with float and short interest carrying most of the signal.
    weights = {
        "free_float": 0.32, "market_cap": 0.18, "short_interest": 0.25,
        "relative_volume": 0.15, "volatility": 0.10,
    }
    available = {k: v for k, v in components.items() if k in weights}
    total_weight = sum(weights[k] for k in available)
    score = sum(components[k] * weights[k] for k in available) / total_weight

    # Non-linear top end (§67): a 10 requires several conditions to coincide.
    strong = sum(1 for k, v in available.items() if v >= 8.0)
    if strong >= 3:
        score = min(10.0, score + 0.8)
        notes.append("multiple amplifying conditions coincide")
    elif strong <= 1 and score > 8.0:
        score = 8.0
        notes.append("only one strong amplifier — capped at 8.0")

    missing = structure.missing()
    if missing:
        score = min(score, 7.5)
        notes.append(f"capped at 7.5: missing {', '.join(missing)}")

    return AmplificationResult(round(min(score, 10.0), 2), components, notes, missing)


@dataclass
class ExecutionQuality:
    score: float
    tradeable: bool
    notes: list[str] = field(default_factory=list)


def assess_execution_quality(structure: MarketStructure) -> ExecutionQuality:
    """Are the displayed prices meaningful (§47)?

    This says nothing about whether the catalyst is good — only whether the
    market information we are reacting to can be trusted.
    """
    notes: list[str] = []
    score = 7.0
    tradeable = True

    if structure.halt_state in (HaltState.NEWS_PENDING, HaltState.LULD,
                                HaltState.REGULATORY):
        return ExecutionQuality(
            0.0, False,
            [f"stock halted ({structure.halt_state.value}) — quotes are not actionable"])

    if structure.spread_pct is not None:
        if structure.spread_pct >= 5:
            score -= 4.0
            tradeable = False
            notes.append(f"spread {structure.spread_pct:.1f}% — quote effectively unusable")
        elif structure.spread_pct >= 1.5:
            score -= 2.0
            notes.append(f"wide spread {structure.spread_pct:.1f}%")
        elif structure.spread_pct <= 0.3:
            score += 1.5
            notes.append(f"tight spread {structure.spread_pct:.2f}%")
    else:
        score -= 1.0
        notes.append("spread unknown")

    if structure.avg_dollar_volume is not None:
        if structure.avg_dollar_volume < 500_000:
            score -= 3.0
            tradeable = False
            notes.append(
                f"average dollar volume ${structure.avg_dollar_volume:,.0f} — very thin")
        elif structure.avg_dollar_volume < 5_000_000:
            score -= 1.0
            notes.append("modest average dollar volume")
        elif structure.avg_dollar_volume >= 50_000_000:
            score += 1.5
            notes.append("deep average dollar volume")
    else:
        score -= 1.0
        notes.append("average dollar volume unknown")

    if structure.session in ("pre", "post", "extended"):
        score -= 1.5
        notes.append(f"{structure.session}-market session — thinner book, wider quotes")

    if structure.share_price is not None and structure.share_price < 1.0:
        score -= 2.0
        notes.append(f"sub-$1 share price (${structure.share_price:.2f})")

    return ExecutionQuality(round(max(0.0, min(score, 10.0)), 2), tradeable, notes)


def market_session(at: datetime) -> str:
    """US equity session for a UTC/aware timestamp."""
    local = at.astimezone(NEW_YORK)
    if local.weekday() >= 5:
        return "closed"
    open_time = local.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = local.replace(hour=16, minute=0, second=0, microsecond=0)
    pre_start = local.replace(hour=4, minute=0, second=0, microsecond=0)
    post_end = local.replace(hour=20, minute=0, second=0, microsecond=0)
    if open_time <= local < close_time:
        return "regular"
    if pre_start <= local < open_time:
        return "pre"
    if close_time <= local < post_end:
        return "post"
    return "closed"


def relative_volume(current_volume: float | None, avg_daily_volume: float | None,
                    at: datetime) -> float | None:
    """Volume vs what would be expected by this time of day (§45)."""
    if not current_volume or not avg_daily_volume:
        return None
    local = at.astimezone(NEW_YORK)
    open_time = local.replace(hour=9, minute=30, second=0, microsecond=0)
    elapsed = (local - open_time).total_seconds()
    session_seconds = 6.5 * 3600
    if elapsed <= 0:
        # Pre-market: compare against a nominal 5% of a normal day.
        expected = avg_daily_volume * 0.05
    else:
        fraction = min(max(elapsed / session_seconds, 0.02), 1.0)
        expected = avg_daily_volume * fraction
    if expected <= 0:
        return None
    return round(current_volume / expected, 2)


def default_analogue_move_pct(structure: MarketStructure) -> float | None:
    """Fallback expectation when no historical analogue exists yet.

    Deliberately crude and explicitly labelled: a placeholder until the
    analogue engine has real data (§40). Scaled off the stock's own normal
    move rather than a universal constant.
    """
    normal = structure.atr_pct or structure.realised_volatility_pct
    if normal is None:
        return None
    return round(normal * 3.0, 2)


def timedelta_minutes(earlier: datetime, later: datetime) -> float:
    return max((later - earlier), timedelta(0)).total_seconds() / 60.0
