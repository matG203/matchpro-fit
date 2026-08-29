"""ScoringService v1.0 — deterministic, conservative, versioned.

Produces the four scores (spec §SCORING MODEL):
  1. earnings_quality      "how good was the report?"
  2. market_confirmation   "does the market agree?"
  3. entry_score           "is it still a good place to enter?"
  4. final_trade_score     the number that gets pushed

The LLM supplies qualitative sub-scores; everything here — weighting, vetoes,
calibration, confidence, SCORE_REVIEW — is plain code and unit-tested.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import GuidanceStatus, ReactionPattern

SCORING_MODEL_VERSION = "1.0.0"

WEIGHTS = {
    "beat_quality": 0.25,
    "guidance": 0.25,
    "business_kpi": 0.15,
    "true_surprise": 0.15,
    "market_confirmation": 0.10,
    "entry": 0.10,
}

VETO_CAP = 8.9
SCORE_REVIEW_DROP_PCT = -3.0     # EQ>=9 and reaction below this → SCORE_REVIEW


@dataclass
class ScoringInputs:
    # From the LLM analysis (None when LLM unavailable → provisional score)
    llm_earnings_quality: float | None = None
    llm_guidance_score: float | None = None
    llm_business_kpi_score: float | None = None
    llm_true_surprise_score: float | None = None
    llm_confidence: float | None = None          # 0-100
    eps_dominated_by_one_offs: bool = False
    hidden_negative_count: int = 0
    guidance_status: GuidanceStatus = GuidanceStatus.NONE
    organic_guidance_change: bool | None = None

    # Deterministic surprise (conservative edge of the consensus band, %)
    eps_surprise_pct: float | None = None
    revenue_surprise_pct: float | None = None
    estimate_confidence: str = "LOW"             # HIGH / MEDIUM / LOW
    consensus_disagreement: bool = False

    # Market context
    reaction_pct: float | None = None            # vs pre-release price
    reaction_vs_prev_close_pct: float | None = None
    pre_run_1m_pct: float | None = None
    implied_move_pct: float | None = None
    reaction_pattern: ReactionPattern = ReactionPattern.NONE
    market_data_unresolved: bool = False

    # Data-quality factors for confidence
    release_source_quality: float = 1.0          # 0-1 (SEC-confirmed = 1.0)
    kpi_completeness: float = 0.5                # 0-1
    llm_fact_mismatch: bool = False


@dataclass
class ScoreResult:
    earnings_quality: float
    market_confirmation: float
    entry_score: float
    final_trade_score: float
    component_breakdown: dict = field(default_factory=dict)
    vetoes_applied: list[str] = field(default_factory=list)
    analysis_confidence: float = 0.0
    needs_verification: bool = False
    score_review: bool = False
    provisional: bool = False
    scoring_model_version: str = SCORING_MODEL_VERSION


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


# ─── Component scores ─────────────────────────────────────────────────────────


def beat_quality_score(inputs: ScoringInputs) -> float:
    """Deterministic surprise score, blended with the LLM's read of quality."""
    parts: list[float] = []
    if inputs.revenue_surprise_pct is not None:
        s = inputs.revenue_surprise_pct
        parts.append(_clamp(5.0 + s * 0.55))          # +8% revenue beat ≈ 9.4
    if inputs.eps_surprise_pct is not None:
        s = inputs.eps_surprise_pct
        parts.append(_clamp(5.0 + s * 0.18))          # +25% EPS beat ≈ 9.5
    deterministic = sum(parts) / len(parts) if parts else None

    if deterministic is not None and inputs.llm_earnings_quality is not None:
        score = 0.5 * deterministic + 0.5 * inputs.llm_earnings_quality
    elif deterministic is not None:
        score = deterministic
    elif inputs.llm_earnings_quality is not None:
        score = inputs.llm_earnings_quality
    else:
        score = 5.0
    if inputs.consensus_disagreement:
        score -= 0.4                                   # reduced conviction, spec §consensus
    if inputs.eps_dominated_by_one_offs:
        score = min(score, 6.5)                        # regression case 3
    return _clamp(score)


_GUIDANCE_BASE = {
    GuidanceStatus.RAISED: 8.0,
    GuidanceStatus.NARROWED: 6.5,
    GuidanceStatus.MAINTAINED: 5.5,
    GuidanceStatus.NONE: 5.0,
    GuidanceStatus.LOWERED: 2.0,
}


def guidance_score(inputs: ScoringInputs) -> float:
    base = _GUIDANCE_BASE[inputs.guidance_status]
    if inputs.llm_guidance_score is not None:
        base = 0.4 * base + 0.6 * inputs.llm_guidance_score
    if inputs.guidance_status == GuidanceStatus.RAISED and inputs.organic_guidance_change is False:
        base -= 1.5                                    # acquisition/FX-driven raise
    return _clamp(base)


def true_surprise_score(inputs: ScoringInputs) -> float:
    score = inputs.llm_true_surprise_score if inputs.llm_true_surprise_score is not None else 5.0
    # A big pre-earnings run means the market's true hurdle was above published
    # consensus — shave credit deterministically even if the LLM was generous.
    if inputs.pre_run_1m_pct is not None and inputs.pre_run_1m_pct > 10.0:
        score -= min((inputs.pre_run_1m_pct - 10.0) * 0.08, 2.0)
    return _clamp(score)


def market_confirmation_score(inputs: ScoringInputs) -> float:
    if inputs.market_data_unresolved or inputs.reaction_pct is None:
        return 5.0                                     # neutral; veto + confidence handle it
    r = inputs.reaction_pct
    if inputs.implied_move_pct and inputs.implied_move_pct > 0:
        ratio = r / inputs.implied_move_pct
        score = 5.0 + _clamp(ratio, -2.0, 2.0) * 2.25  # ±2x implied → 0.5/9.5
    else:
        score = 5.0 + _clamp(r, -15.0, 15.0) * 0.3     # +10% → 8.0, -10% → 2.0
    if inputs.reaction_pattern == ReactionPattern.POST_EARNINGS_REVERSAL:
        score -= 2.5
    elif inputs.reaction_pattern == ReactionPattern.POST_EARNINGS_MOMENTUM and r > 0:
        score += 1.0
    # The dual-baseline check: down after-hours but still above yesterday's
    # close is not a rejection (spec §PRE-EARNINGS CONTEXT).
    if r < 0 and inputs.reaction_vs_prev_close_pct is not None \
            and inputs.reaction_vs_prev_close_pct > 0:
        score += 1.0
    return _clamp(score)


def entry_score(inputs: ScoringInputs) -> float:
    score = 7.5
    r = inputs.reaction_pct
    if r is not None:
        if r > 3.0:
            score -= (r - 3.0) * 0.18                  # +27% move → ≈3.2 entry
        elif r < -5.0:
            score -= (abs(r) - 5.0) * 0.10             # falling knife penalty
    if inputs.pre_run_1m_pct is not None and inputs.pre_run_1m_pct > 10.0:
        score -= min((inputs.pre_run_1m_pct - 10.0) * 0.05, 1.5)
    if inputs.market_data_unresolved:
        score = min(score, 5.0)
    return _clamp(score)


# ─── Vetoes (spec §9+ VETO RULES) ────────────────────────────────────────────


def collect_vetoes(inputs: ScoringInputs, earnings_quality: float) -> list[str]:
    vetoes: list[str] = []
    if inputs.guidance_status == GuidanceStatus.LOWERED:
        vetoes.append("guidance cut")
    if inputs.eps_dominated_by_one_offs:
        vetoes.append("earnings dominated by one-off accounting items")
    if inputs.market_data_unresolved:
        vetoes.append("contradictory/unavailable live price feeds")
    if inputs.estimate_confidence == "LOW" or inputs.consensus_disagreement:
        vetoes.append("low-confidence consensus")
    if inputs.reaction_pattern == ReactionPattern.POST_EARNINGS_REVERSAL:
        vetoes.append("strong post-release market rejection (spike and fade)")
    if inputs.reaction_pct is not None and inputs.reaction_pct <= -5.0:
        vetoes.append("material post-release decline")
    if inputs.pre_run_1m_pct is not None and inputs.pre_run_1m_pct > 25.0:
        vetoes.append("massive pre-earnings run")
    if inputs.reaction_pct is not None and inputs.reaction_pct > 20.0:
        vetoes.append("extreme current-price extension")
    if inputs.hidden_negative_count >= 3:
        vetoes.append("multiple unresolved hidden negatives")
    if inputs.llm_fact_mismatch:
        vetoes.append("LLM/deterministic fact mismatch")
    return vetoes


def needs_score_review(earnings_quality: float, inputs: ScoringInputs) -> bool:
    """Market-disagreement safety rule: great report + falling stock."""
    return (earnings_quality >= 9.0
            and inputs.reaction_pct is not None
            and inputs.reaction_pct <= SCORE_REVIEW_DROP_PCT)


# ─── Confidence ───────────────────────────────────────────────────────────────

_ESTIMATE_CONF = {"HIGH": 1.0, "MEDIUM": 0.85, "LOW": 0.6}


def analysis_confidence(inputs: ScoringInputs) -> float:
    conf = 100.0
    conf *= _clamp(inputs.release_source_quality, 0.0, 1.0)
    conf *= _ESTIMATE_CONF.get(inputs.estimate_confidence, 0.6)
    if inputs.market_data_unresolved:
        conf *= 0.75
    conf *= 0.7 + 0.3 * _clamp(inputs.kpi_completeness, 0.0, 1.0)
    if inputs.llm_fact_mismatch:
        conf *= 0.7
    if inputs.llm_confidence is not None:
        conf = min(conf, inputs.llm_confidence * 1.05)
    if inputs.llm_earnings_quality is None:
        conf *= 0.7                                    # provisional, no LLM pass
    return round(_clamp(conf, 0.0, 100.0), 1)


# ─── Final assembly ───────────────────────────────────────────────────────────


def compute_scores(inputs: ScoringInputs, *, min_confidence: float = 75.0) -> ScoreResult:
    components = {
        "beat_quality": beat_quality_score(inputs),
        "guidance": guidance_score(inputs),
        "business_kpi": (inputs.llm_business_kpi_score
                         if inputs.llm_business_kpi_score is not None else 5.0),
        "true_surprise": true_surprise_score(inputs),
        "market_confirmation": market_confirmation_score(inputs),
        "entry": entry_score(inputs),
    }

    eq = (inputs.llm_earnings_quality
          if inputs.llm_earnings_quality is not None else components["beat_quality"])

    final = sum(WEIGHTS[k] * v for k, v in components.items())

    vetoes = collect_vetoes(inputs, eq)
    if vetoes:
        final = min(final, VETO_CAP)

    review = needs_score_review(eq, inputs)
    if review:
        final = min(final, VETO_CAP)

    # Conservative calibration: 9.5+ additionally requires clean market
    # confirmation and no consensus doubts; 10.0 effectively unreachable.
    if final >= 9.5 and (components["market_confirmation"] < 8.0
                         or inputs.estimate_confidence != "HIGH"):
        final = 9.4
    final = min(final, 9.9)

    conf = analysis_confidence(inputs)

    return ScoreResult(
        earnings_quality=round(_clamp(eq), 1),
        market_confirmation=round(components["market_confirmation"], 1),
        entry_score=round(components["entry"], 1),
        final_trade_score=round(_clamp(final), 1),
        component_breakdown={k: round(v, 2) for k, v in components.items()},
        vetoes_applied=vetoes,
        analysis_confidence=conf,
        needs_verification=conf < min_confidence,
        score_review=review,
        provisional=inputs.llm_earnings_quality is None,
    )
