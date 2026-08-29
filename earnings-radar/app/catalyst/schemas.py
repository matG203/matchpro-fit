"""Strict Claude schemas for Catalyst Sentinel (spec §61-63).

Two passes:
  FastTriage  — cheap classification + obvious-negative screen; decides whether
                deep analysis is worth the cost/latency.
  DeepInvestigation — adversarial review. Facts FIRST, interpretation after.

Every numeric field is optional and defaults to None. Claude must never invent
a financial quantity: unknown means null, and the quantitative engines supply
real figures from providers.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.catalyst.enums import Certainty, EventType


class FastTriage(BaseModel):
    """Cheap first pass. Kills routine articles before deep reasoning (§11, §95)."""

    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    is_company_specific: bool = Field(
        description="False for macro/sector commentary that names the company in passing")
    is_new_information: bool = Field(
        description="False if this merely restates a previously public announcement")
    is_promotional: bool = Field(
        description="True for paid promotion, pump-style PR, vague hype with no economics")
    restates_earnings_release: bool = Field(
        default=False,
        description="True if this is derivative coverage of an earnings release")
    warrants_deep_analysis: bool
    reason: str


class ExtractedFact(BaseModel):
    """One atomic fact with provenance. No interpretation."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="e.g. headline_value, guaranteed_value, term_years")
    value_text: str = Field(description="verbatim as stated in the source")
    value_number: float | None = None
    unit: str | None = Field(default=None, description="USD, years, percent, patients...")
    quote: str = Field(description="exact supporting sentence from the document")


class ContractTerms(BaseModel):
    """§20 — contracts are the most deceptive headline class."""

    model_config = ConfigDict(extra="forbid")

    headline_value: float | None = None
    guaranteed_value: float | None = Field(
        default=None, description="minimum committed — null if not stated, NEVER guessed")
    funded_value: float | None = None
    ceiling_value: float | None = None
    term_years: float | None = None
    single_award: bool | None = Field(
        default=None, description="False for multi-award IDIQ/framework vehicles")
    competitors_on_vehicle: int | None = None
    binding: bool | None = None
    customer: str | None = None
    is_extension_of_existing: bool | None = None


class TrialResult(BaseModel):
    """§24-26 — clinical results need structure, not sentiment."""

    model_config = ConfigDict(extra="forbid")

    phase: str | None = None
    indication: str | None = None
    primary_endpoint_met: bool | None = None
    primary_endpoint_description: str | None = None
    p_value: float | None = None
    effect_size: str | None = None
    patient_count: int | None = None
    is_subgroup_analysis: bool | None = Field(
        default=None, description="True if headline result is a subgroup, not full population")
    is_prespecified: bool | None = None
    serious_adverse_events: bool | None = None
    safety_notes: str | None = None
    secondary_endpoints_missed: bool | None = None


class DealTerms(BaseModel):
    """§22-23 — M&A."""

    model_config = ConfigDict(extra="forbid")

    is_target: bool | None = Field(default=None, description="True if this company is acquired")
    offer_price_per_share: float | None = None
    consideration_type: str | None = Field(default=None, description="cash | stock | mixed")
    purchase_price_total: float | None = None
    financing_secured: bool | None = None
    regulatory_conditions: str | None = None
    break_fee: float | None = None
    expected_close: str | None = None
    competing_bid: bool | None = None


class NegativeOffset(BaseModel):
    """§58 — the counterweight to every apparent positive."""

    model_config = ConfigDict(extra="forbid")

    description: str
    severity: float = Field(ge=0, le=10, description="10 = may overwhelm the positive")
    evidence_quote: str | None = None


class DeepInvestigation(BaseModel):
    """Adversarial review (§60, §62). Claude's job is to try to DISPROVE the thesis."""

    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    summary: str = Field(description="plain-English, one or two sentences")

    # ── Facts first (§61) ──
    facts: list[ExtractedFact] = Field(default_factory=list)
    contract_terms: ContractTerms | None = None
    trial_result: TrialResult | None = None
    deal_terms: DealTerms | None = None

    # ── Novelty / information delta (§13-15) ──
    new_information: str = Field(description="what is genuinely new right now")
    previously_known_information: str = Field(
        description="what the market already knew before this item")
    incremental_information: str = Field(
        description="what changed — especially uncertainty removed")
    is_restatement: bool = Field(
        default=False, description="True if this adds nothing to prior public information")

    # ── Certainty & quality ──
    certainty: Certainty
    certainty_evidence: str | None = None
    source_quality: float = Field(ge=0, le=1)
    entity_mapping_correct: bool = True

    # ── Adversarial output ──
    positive_factors: list[str] = Field(default_factory=list)
    negative_offsets: list[NegativeOffset] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    adversarial_findings: list[str] = Field(
        default_factory=list,
        description="the strongest arguments that this is NOT a major catalyst")

    # ── Judgement (bounded; the deterministic engine owns the final score) ──
    event_quality: float = Field(
        ge=0, le=10, description="quality of the event ITSELF, ignoring price and market structure")
    strategic_significance: float = Field(ge=0, le=10)
    confidence_adjustment: float = Field(
        default=0.0, ge=-2.0, le=1.0,
        description="adjustment to analysis confidence; positive only when unusually well evidenced")

    invalidate: bool = Field(
        default=False, description="True if this should not be alerted at all")
    invalidation_reason: str | None = None
    requires_quant_rerun: bool = False
    sources: list[str] = Field(default_factory=list)
