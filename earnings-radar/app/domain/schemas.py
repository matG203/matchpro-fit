"""Strict schema for the LLM analysis output (spec §LLM OUTPUT FORMAT).

The model is called through the Anthropic structured-outputs API with this
Pydantic class, so the response is schema-constrained at generation time and
re-validated here server-side. Unknown values must be null — never guessed.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import GrowthDirection, GuidanceStatus


class FactCheck(BaseModel):
    """A numeric fact the model echoes back so we can cross-check it against
    the deterministic extraction (anti-hallucination)."""

    model_config = ConfigDict(extra="forbid")

    eps_actual: float | None = None
    eps_expected: float | None = None
    revenue_actual: float | None = None
    revenue_expected: float | None = None


class AnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str

    # Sub-scores, 0.0-10.0. These feed the deterministic ScoringService —
    # the LLM does NOT produce the final trade score.
    earnings_quality: float = Field(ge=0, le=10)
    guidance_score: float = Field(ge=0, le=10)
    business_kpi_score: float = Field(ge=0, le=10)
    true_surprise_score: float = Field(
        ge=0, le=10,
        description="Surprise vs what the market had TRULY priced in, accounting "
                    "for pre-earnings run and pre-announced news",
    )

    guidance_status: GuidanceStatus
    guidance_notes: str | None = None
    organic_guidance_change: bool | None = Field(
        default=None,
        description="False when a guidance raise is mostly acquisition/FX/accounting",
    )
    growth_direction: GrowthDirection

    pre_announced_news: list[str] = Field(
        default_factory=list,
        description="Bullish items in the release that were ALREADY public before "
                    "earnings (tag PREVIOUSLY_KNOWN items here)",
    )
    positives: list[str] = Field(default_factory=list)
    negatives: list[str] = Field(default_factory=list)
    hidden_negatives: list[str] = Field(
        default_factory=list,
        description="Strongest bear arguments hidden inside this report",
    )
    one_off_items: list[str] = Field(
        default_factory=list,
        description="Tax valuation releases, impairments, gains on sale, crypto "
                    "fair-value moves, settlements — anything non-operating",
    )
    eps_dominated_by_one_offs: bool = False

    bull_case: str
    bear_case: str
    reasoning_summary: str

    facts: FactCheck

    confidence: float = Field(ge=0, le=100, description="Model's own confidence, 0-100")
    verdict: str = Field(description="Short label, e.g. STRONG_BEAT_AND_RAISE, "
                                     "STRONG_BELOW_9, MIXED, WEAK")
