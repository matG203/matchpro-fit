"""Catalyst scoring engine (spec §64-76).

Seven independent components, then a weighted final score, then gates and caps.
All deterministic and versioned — Claude contributes bounded sub-judgements,
never the arithmetic.

The starting weights are the spec's heuristic (§72) and are explicitly
provisional: once enough outcome data exists they should be recalibrated
empirically, and the version bumped.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import ClassVar

from app.catalyst.enums import (
    CERTAINTY_VALUE,
    SOURCE_TIER_QUALITY,
    CatalystHalfLife,
    Certainty,
    EventType,
    SourceTier,
)

CATALYST_MODEL_VERSION = "1.0.0"

# §72 — starting heuristic only.
FINAL_WEIGHTS = {
    "catalyst_strength": 0.35,
    "surprise_novelty": 0.20,
    "move_amplification": 0.15,
    "reaction_room": 0.15,
    "confidence": 0.10,
    "execution_quality": 0.05,
}

# §65 — components of Catalyst Strength.
STRENGTH_WEIGHTS = {
    "economic_materiality": 0.30,
    "certainty": 0.15,
    "persistence": 0.10,
    "strategic_significance": 0.10,
    "fundamental_effect": 0.20,
    "source_quality": 0.05,
    "event_quality": 0.10,
}

# §66 — components of Surprise & Novelty.
SURPRISE_WEIGHTS = {
    "novelty": 0.30,
    "vs_prior_expectation": 0.30,
    "information_delta": 0.20,
    "no_price_runup": 0.10,
    "no_prior_signalling": 0.10,
}

VETO_CAP = 8.9
HALF_LIFE_PERSISTENCE = {
    CatalystHalfLife.STRUCTURAL: 10.0,
    CatalystHalfLife.DAYS: 7.0,
    CatalystHalfLife.HOURS: 4.5,
    CatalystHalfLife.MINUTES: 2.5,
    CatalystHalfLife.UNKNOWN: 5.0,
}

# Event types whose upside is structurally capped regardless of enthusiasm.
EVENT_TYPE_CAPS: dict[EventType, float] = {
    EventType.ANALYST_ACTION: 7.5,       # §74 — pure commentary
    EventType.PASSIVE_13G: 6.0,
    EventType.INSIDER_PURCHASE: 7.5,
    EventType.FDA_ACCEPTANCE: 8.0,       # acceptance ≠ approval
    EventType.BUYBACK_AUTHORISATION: 8.0,
    EventType.TRIAL_INITIATION: 7.0,
    EventType.PRODUCT_LAUNCH: 8.0,
    EventType.STRATEGIC_PARTNERSHIP: 8.4,
    EventType.TECHNICAL_MILESTONE: 7.5,
    EventType.UNKNOWN: 6.5,
}


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


@dataclass
class ScoringInputs:
    """Everything the scorer needs. Quantitative fields come from retrieval;
    the three llm_* fields are Claude's bounded judgement."""

    event_type: EventType = EventType.UNKNOWN
    certainty: Certainty = Certainty.SPECULATIVE
    source_tier: SourceTier = SourceTier.REPUTABLE_NEWS
    half_life: CatalystHalfLife = CatalystHalfLife.UNKNOWN

    # Deterministic engines
    materiality_score: float | None = None
    materiality_complete: bool = True
    materiality_missing: list[str] = field(default_factory=list)
    novelty_score: float | None = None
    is_restatement: bool = False
    information_delta_score: float | None = None
    pre_event_runup_pct: float | None = None
    had_prior_signalling: bool = False
    move_amplification: float | None = None
    reaction_room: float | None = None
    execution_quality: float | None = None
    negative_offset_severity: float = 0.0
    market_data_unresolved: bool = False
    entity_confidence: float = 1.0
    is_halted: bool = False

    # Claude's bounded contributions
    llm_event_quality: float | None = None
    llm_strategic_significance: float | None = None
    llm_confidence_adjustment: float = 0.0
    llm_invalidated: bool = False
    llm_invented_financials: bool = False

    # Freshness / data health
    event_age_seconds: float | None = None
    price_age_seconds: float | None = None
    corroborating_primary_sources: int = 0
    claude_available: bool = True
    analogue_sample_size: int = 0

    # ── persistence ───────────────────────────────────────────────────────────
    # Stored verbatim alongside every score. Two reasons: a re-score can replace
    # only the market-derived fields and leave Claude's judgement untouched
    # (so no second API call), and any past score can be explained exactly
    # rather than approximately.

    _ENUM_FIELDS: ClassVar[dict[str, type]] = {
        "event_type": EventType,
        "certainty": Certainty,
        "source_tier": SourceTier,
        "half_life": CatalystHalfLife,
    }

    def to_dict(self) -> dict:
        out: dict = {}
        for key, value in self.__dict__.items():
            out[key] = value.value if key in self._ENUM_FIELDS else value
        return out

    @classmethod
    def from_dict(cls, data: dict) -> ScoringInputs:
        """Rebuild from stored JSON, ignoring fields this version no longer has
        so an old row never crashes a newer scorer."""
        known = {f.name for f in fields(cls)}
        kwargs: dict = {}
        for key, value in (data or {}).items():
            if key not in known:
                continue
            enum_type = cls._ENUM_FIELDS.get(key)
            if enum_type is not None and value is not None:
                try:
                    kwargs[key] = enum_type(value)
                except ValueError:
                    continue
            else:
                kwargs[key] = value
        return cls(**kwargs)


@dataclass
class CatalystScoreResult:
    catalyst_strength: float
    surprise_novelty: float
    move_amplification: float
    reaction_room: float
    confidence: float
    execution_quality: float
    negative_offset_severity: float
    upside_catalyst_score: float
    fundamental_impact: float
    immediate_reaction_potential: float
    component_breakdown: dict = field(default_factory=dict)
    caps_applied: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)
    model_version: str = CATALYST_MODEL_VERSION
    rejected: bool = False
    reject_reason: str = ""

    @property
    def band(self) -> str:
        return alert_band(self.upside_catalyst_score)


def alert_band(score: float) -> str:
    """§76 alert classification."""
    if score >= 9.5:
        return "EXCEPTIONAL"
    if score >= 9.0:
        return "PUSH"
    if score >= 8.5:
        return "VERY_STRONG"
    if score >= 8.0:
        return "INTERESTING"
    if score >= 7.0:
        return "STORE"
    return "IGNORE"


# ── Component 1: Catalyst Strength (§65) ─────────────────────────────────────


def catalyst_strength(inputs: ScoringInputs) -> tuple[float, dict]:
    parts: dict[str, float] = {}

    parts["economic_materiality"] = (
        inputs.materiality_score if inputs.materiality_score is not None else 3.0)
    parts["certainty"] = CERTAINTY_VALUE[inputs.certainty] * 10.0
    parts["persistence"] = HALF_LIFE_PERSISTENCE[inputs.half_life]
    parts["strategic_significance"] = (
        inputs.llm_strategic_significance if inputs.llm_strategic_significance is not None else 5.0)
    parts["source_quality"] = SOURCE_TIER_QUALITY[inputs.source_tier] * 10.0
    parts["event_quality"] = (
        inputs.llm_event_quality if inputs.llm_event_quality is not None else 5.0)

    # Fundamental earnings/cash-flow effect: materiality weighted by how
    # certain it is that the money actually arrives.
    if inputs.materiality_score is not None:
        parts["fundamental_effect"] = (
            inputs.materiality_score * CERTAINTY_VALUE[inputs.certainty])
    else:
        parts["fundamental_effect"] = 3.0

    score = sum(parts[k] * w for k, w in STRENGTH_WEIGHTS.items())
    return round(_clamp(score), 2), parts


# ── Component 2: Surprise & Novelty (§66) ────────────────────────────────────


def surprise_novelty(inputs: ScoringInputs) -> tuple[float, dict]:
    parts: dict[str, float] = {}

    parts["novelty"] = inputs.novelty_score if inputs.novelty_score is not None else 5.0

    # Difference vs prior expectation: proxied by certainty advance and by
    # whether the market had been signalled in advance.
    expectation = 5.0
    if inputs.is_restatement:
        expectation = 0.5
    elif inputs.information_delta_score is not None:
        expectation = inputs.information_delta_score
    elif inputs.novelty_score is not None:
        expectation = inputs.novelty_score * 0.85
    parts["vs_prior_expectation"] = expectation

    parts["information_delta"] = (
        inputs.information_delta_score if inputs.information_delta_score is not None
        else parts["novelty"] * 0.8)

    runup = inputs.pre_event_runup_pct
    if runup is None:
        parts["no_price_runup"] = 5.0
    elif runup <= 0:
        parts["no_price_runup"] = 10.0
    else:
        # 20%+ run-up into the event → the market already knew something.
        parts["no_price_runup"] = _clamp(10.0 - runup / 2.0)

    parts["no_prior_signalling"] = 3.0 if inputs.had_prior_signalling else 9.0

    score = sum(parts[k] * w for k, w in SURPRISE_WEIGHTS.items())
    return round(_clamp(score), 2), parts


# ── Component 5: Confidence (§69) ────────────────────────────────────────────


def confidence_score(inputs: ScoringInputs) -> tuple[float, dict]:
    parts: dict[str, float] = {}

    parts["source_reliability"] = SOURCE_TIER_QUALITY[inputs.source_tier] * 10.0
    parts["entity_mapping"] = _clamp(inputs.entity_confidence * 10.0)
    parts["data_completeness"] = 10.0 if inputs.materiality_complete else 5.0

    if inputs.event_age_seconds is None:
        parts["freshness"] = 5.0
    elif inputs.event_age_seconds <= 300:
        parts["freshness"] = 10.0
    elif inputs.event_age_seconds <= 1800:
        parts["freshness"] = 8.0
    elif inputs.event_age_seconds <= 7200:
        parts["freshness"] = 6.0
    else:
        parts["freshness"] = 3.0

    parts["corroboration"] = _clamp(4.0 + inputs.corroborating_primary_sources * 3.0)
    parts["model_available"] = 10.0 if inputs.claude_available else 4.0

    # Analogue evidence: no sample means no empirical grounding (§69).
    if inputs.analogue_sample_size >= 20:
        parts["historical_grounding"] = 9.0
    elif inputs.analogue_sample_size >= 5:
        parts["historical_grounding"] = 6.5
    else:
        parts["historical_grounding"] = 4.0

    score = sum(parts.values()) / len(parts)
    score += inputs.llm_confidence_adjustment

    if inputs.market_data_unresolved:
        score *= 0.8
        parts["market_data_unresolved_penalty"] = -2.0
    if inputs.llm_invented_financials:
        score *= 0.6
        parts["invented_financials_penalty"] = -4.0

    return round(_clamp(score), 2), parts


# ── Hard gates and caps (§73-74) ─────────────────────────────────────────────


def apply_gates_and_caps(score: float, inputs: ScoringInputs,
                         components: dict[str, float]) -> tuple[float, list[str], list[str]]:
    caps: list[str] = []
    gates: list[str] = []

    event_cap = EVENT_TYPE_CAPS.get(inputs.event_type)
    if event_cap is not None and score > event_cap:
        score = event_cap
        caps.append(f"event type {inputs.event_type.value} capped at {event_cap}")

    if inputs.source_tier not in (SourceTier.PRIMARY, SourceTier.NEWSWIRE) and score >= 9.0:
        score = VETO_CAP
        caps.append("source not primary/newswire — cannot reach 9+")
        gates.append("source_quality")

    if inputs.certainty in (Certainty.INTENT, Certainty.SPECULATIVE) and score > 8.0:
        score = 8.0
        caps.append(f"{inputs.certainty.value.lower()} commitment capped at 8.0")

    # Gates record a fact about the event and are reported whether or not the
    # cap happens to bind — otherwise the dashboard cannot explain a low score.
    if not inputs.materiality_complete:
        gates.append("data_completeness")
        if score > 8.4:
            score = 8.4
            caps.append(
                f"incomplete materiality data {inputs.materiality_missing} capped at 8.4")

    if inputs.market_data_unresolved:
        gates.append("price_current")
        if score > 8.4:
            score = 8.4
            caps.append("price data unresolved — cannot confirm the move is still available")

    if inputs.reaction_room is not None and inputs.reaction_room < 3.0:
        gates.append("reaction_room")
        if score > 8.4:
            score = 8.4
            caps.append(
                f"reaction room {inputs.reaction_room:.1f} — stock largely repriced already")

    severity = inputs.negative_offset_severity
    if severity >= 8.0:
        score = min(score, 6.0)
        caps.append(f"severe negative offset ({severity:.1f}) — heavily capped")
        gates.append("negative_offsets")
    elif severity >= 6.0:
        score = min(score, 7.5)
        caps.append(f"material negative offset ({severity:.1f})")
        gates.append("negative_offsets")
    elif severity >= 4.0:
        score = min(score, VETO_CAP)
        caps.append(f"moderate negative offset ({severity:.1f}) — cannot reach 9+")

    if not inputs.claude_available:
        gates.append("claude_review")
        if score >= 9.0:
            score = VETO_CAP
            caps.append("adversarial review unavailable — not fully validated")

    if inputs.is_halted:
        gates.append("halt")
        if score > 8.4:
            score = 8.4
            caps.append("stock halted — price-sensitive alert withheld pending resumption")

    if inputs.entity_confidence < 0.85 and score >= 9.0:
        score = VETO_CAP
        caps.append(f"entity confidence {inputs.entity_confidence:.2f} below 0.85")
        gates.append("entity_confidence")

    # 9.5+ demands everything simultaneously (§73).
    if score >= 9.5:
        requirements = {
            "primary source": inputs.source_tier == SourceTier.PRIMARY,
            "high novelty": (inputs.novelty_score or 0) >= 8.0,
            "complete data": inputs.materiality_complete,
            "no meaningful offset": severity < 3.0,
            "reaction room": (inputs.reaction_room or 0) >= 6.0,
            "executed certainty": inputs.certainty in (Certainty.EXECUTED, Certainty.BINDING),
        }
        unmet = [name for name, ok in requirements.items() if not ok]
        if unmet:
            score = 9.4
            caps.append(f"9.5+ requires all of: unmet {unmet}")

    return round(_clamp(score), 2), caps, gates


# ── Final assembly (§72) ─────────────────────────────────────────────────────


def compute_catalyst_score(inputs: ScoringInputs) -> CatalystScoreResult:
    strength, strength_parts = catalyst_strength(inputs)
    surprise, surprise_parts = surprise_novelty(inputs)
    confidence, confidence_parts = confidence_score(inputs)

    amplification = inputs.move_amplification if inputs.move_amplification is not None else 5.0
    room = inputs.reaction_room if inputs.reaction_room is not None else 5.0
    execution = inputs.execution_quality if inputs.execution_quality is not None else 5.0

    components = {
        "catalyst_strength": strength,
        "surprise_novelty": surprise,
        "move_amplification": amplification,
        "reaction_room": room,
        "confidence": confidence,
        "execution_quality": execution,
    }

    # Hard rejections before any arithmetic matters.
    if inputs.llm_invalidated:
        return CatalystScoreResult(
            strength, surprise, amplification, room, confidence, execution,
            inputs.negative_offset_severity, 0.0, 0.0, 0.0,
            component_breakdown=components, rejected=True,
            reject_reason="adversarial review invalidated the candidate")
    if inputs.is_restatement:
        return CatalystScoreResult(
            strength, surprise, amplification, room, confidence, execution,
            inputs.negative_offset_severity, 0.0, 0.0, 0.0,
            component_breakdown=components, rejected=True,
            reject_reason="restates previously public information")

    raw = sum(components[k] * w for k, w in FINAL_WEIGHTS.items())

    # Negative offsets bite before the caps, so a severe flaw drags the score
    # down rather than merely capping an otherwise glowing number.
    penalty = (inputs.negative_offset_severity / 10.0) ** 1.5 * 4.0
    raw -= penalty

    final, caps, gates = apply_gates_and_caps(raw, inputs, components)

    # §54 — fundamental impact and immediate reaction potential are different
    # questions and are reported separately.
    fundamental = round(_clamp(
        0.6 * strength + 0.4 * HALF_LIFE_PERSISTENCE[inputs.half_life]), 2)
    immediate = round(_clamp(
        0.35 * surprise + 0.35 * amplification + 0.30 * room), 2)

    breakdown = {
        **{k: round(v, 2) for k, v in components.items()},
        "raw_weighted": round(raw + penalty, 3),
        "negative_offset_penalty": round(-penalty, 3),
        "strength_parts": {k: round(v, 2) for k, v in strength_parts.items()},
        "surprise_parts": {k: round(v, 2) for k, v in surprise_parts.items()},
        "confidence_parts": {k: round(v, 2) for k, v in confidence_parts.items()},
    }

    return CatalystScoreResult(
        catalyst_strength=strength,
        surprise_novelty=surprise,
        move_amplification=round(amplification, 2),
        reaction_room=round(room, 2),
        confidence=confidence,
        execution_quality=round(execution, 2),
        negative_offset_severity=round(inputs.negative_offset_severity, 2),
        upside_catalyst_score=final,
        fundamental_impact=fundamental,
        immediate_reaction_potential=immediate,
        component_breakdown=breakdown,
        caps_applied=caps,
        gates_failed=gates,
    )
