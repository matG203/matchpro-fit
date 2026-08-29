"""Catalyst domain enums: event taxonomy, source tiers, certainty, state."""
from __future__ import annotations

from enum import StrEnum


class SourceTier(StrEnum):
    """Spec §5 data-source hierarchy."""

    PRIMARY = "PRIMARY"                 # SEC, FDA, company IR, government award DBs
    NEWSWIRE = "NEWSWIRE"               # licensed real-time financial wire
    REPUTABLE_NEWS = "REPUTABLE_NEWS"   # established news organisations
    SECONDARY = "SECONDARY"             # forums, social, promo sites


# Source quality on 0-1. A low-quality source alone can never reach 9+ (§16).
SOURCE_TIER_QUALITY: dict[SourceTier, float] = {
    SourceTier.PRIMARY: 1.0,
    SourceTier.NEWSWIRE: 0.85,
    SourceTier.REPUTABLE_NEWS: 0.7,
    SourceTier.SECONDARY: 0.25,
}


class EventCategory(StrEnum):
    CONTRACT = "CONTRACT"
    MA = "MA"
    BIOTECH = "BIOTECH"
    GUIDANCE = "GUIDANCE"
    CAPITAL_ALLOCATION = "CAPITAL_ALLOCATION"
    FINANCING = "FINANCING"
    LEGAL = "LEGAL"
    REGULATORY = "REGULATORY"
    PRODUCT = "PRODUCT"
    OWNERSHIP = "OWNERSHIP"
    RESTRUCTURING = "RESTRUCTURING"
    ANALYST = "ANALYST"
    EARNINGS = "EARNINGS"          # routed to Earnings Sentinel
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class EventType(StrEnum):
    # ── Contracts (§10) ──
    GOVERNMENT_CONTRACT = "government_contract"
    COMMERCIAL_CONTRACT = "commercial_contract"
    CUSTOMER_WIN = "customer_win"
    LICENSING_DEAL = "licensing_deal"
    DISTRIBUTION_AGREEMENT = "distribution_agreement"
    SUPPLY_AGREEMENT = "supply_agreement"

    # ── M&A ──
    TAKEOVER_OFFER = "takeover_offer"
    MERGER_ANNOUNCEMENT = "merger_announcement"
    ACQUISITION = "acquisition"
    STRATEGIC_REVIEW = "strategic_review"
    ASSET_DISPOSAL = "asset_disposal"
    TENDER_OFFER = "tender_offer"
    DEAL_APPROVAL = "deal_approval"
    DEAL_TERMINATION = "deal_termination"

    # ── Biotech / pharma ──
    FDA_APPROVAL = "fda_approval"
    FDA_CRL = "fda_crl"                       # complete response letter
    FDA_ACCEPTANCE = "fda_acceptance"          # application accepted — NOT approval
    PDUFA_OUTCOME = "pdufa_outcome"
    LABEL_EXPANSION = "label_expansion"
    BREAKTHROUGH_DESIGNATION = "breakthrough_designation"
    PHASE_1_RESULT = "phase_1_result"
    PHASE_2_RESULT = "phase_2_result"
    PHASE_3_RESULT = "phase_3_result"
    CLINICAL_HOLD = "clinical_hold"
    CLINICAL_HOLD_LIFTED = "clinical_hold_lifted"
    TRIAL_INITIATION = "trial_initiation"
    TRIAL_TERMINATION = "trial_termination"

    # ── Guidance / financial ──
    GUIDANCE_RAISE = "guidance_raise"
    GUIDANCE_CUT = "guidance_cut"
    PROFIT_WARNING = "profit_warning"
    MATERIAL_REVENUE_UPDATE = "material_revenue_update"
    BACKLOG_UPDATE = "backlog_update"

    # ── Capital allocation ──
    BUYBACK_AUTHORISATION = "buyback_authorisation"
    BUYBACK_EXECUTED = "buyback_executed"
    SPECIAL_DIVIDEND = "special_dividend"
    DEBT_REPAYMENT = "debt_repayment"
    REFINANCING = "refinancing"

    # ── Financing (usually dilutive) ──
    EQUITY_OFFERING = "equity_offering"
    ATM_PROGRAMME = "atm_programme"
    CONVERTIBLE_DEBT = "convertible_debt"
    DEBT_RAISE = "debt_raise"
    STRATEGIC_INVESTMENT = "strategic_investment"
    PRIVATE_PLACEMENT = "private_placement"

    # ── Legal ──
    LAWSUIT_WIN = "lawsuit_win"
    LAWSUIT_LOSS = "lawsuit_loss"
    SETTLEMENT = "settlement"
    PATENT_RULING = "patent_ruling"
    INVESTIGATION_OPENED = "investigation_opened"
    INVESTIGATION_CLOSED = "investigation_closed"

    # ── Government / regulatory ──
    REGULATORY_CLEARANCE = "regulatory_clearance"
    PERMIT_LICENCE = "permit_licence"
    GOVERNMENT_FUNDING = "government_funding"
    GRANT = "grant"

    # ── Product / technology ──
    PRODUCT_LAUNCH = "product_launch"
    TECHNICAL_MILESTONE = "technical_milestone"
    STRATEGIC_PARTNERSHIP = "strategic_partnership"
    CUSTOMER_DEPLOYMENT = "customer_deployment"

    # ── Ownership ──
    ACTIVIST_13D = "activist_13d"
    PASSIVE_13G = "passive_13g"
    INSIDER_PURCHASE = "insider_purchase"

    # ── Restructuring ──
    BANKRUPTCY = "bankruptcy"
    BANKRUPTCY_EMERGENCE = "bankruptcy_emergence"
    DEBT_EXCHANGE = "debt_exchange"
    COST_RESTRUCTURING = "cost_restructuring"

    # ── Other ──
    ANALYST_ACTION = "analyst_action"
    EARNINGS_RELEASE = "earnings_release"
    OTHER_MATERIAL = "other_material"
    UNKNOWN = "unknown"


EVENT_CATEGORY: dict[EventType, EventCategory] = {
    **{t: EventCategory.CONTRACT for t in (
        EventType.GOVERNMENT_CONTRACT, EventType.COMMERCIAL_CONTRACT,
        EventType.CUSTOMER_WIN, EventType.LICENSING_DEAL,
        EventType.DISTRIBUTION_AGREEMENT, EventType.SUPPLY_AGREEMENT)},
    **{t: EventCategory.MA for t in (
        EventType.TAKEOVER_OFFER, EventType.MERGER_ANNOUNCEMENT, EventType.ACQUISITION,
        EventType.STRATEGIC_REVIEW, EventType.ASSET_DISPOSAL, EventType.TENDER_OFFER,
        EventType.DEAL_APPROVAL, EventType.DEAL_TERMINATION)},
    **{t: EventCategory.BIOTECH for t in (
        EventType.FDA_APPROVAL, EventType.FDA_CRL, EventType.FDA_ACCEPTANCE,
        EventType.PDUFA_OUTCOME, EventType.LABEL_EXPANSION,
        EventType.BREAKTHROUGH_DESIGNATION, EventType.PHASE_1_RESULT,
        EventType.PHASE_2_RESULT, EventType.PHASE_3_RESULT, EventType.CLINICAL_HOLD,
        EventType.CLINICAL_HOLD_LIFTED, EventType.TRIAL_INITIATION,
        EventType.TRIAL_TERMINATION)},
    **{t: EventCategory.GUIDANCE for t in (
        EventType.GUIDANCE_RAISE, EventType.GUIDANCE_CUT, EventType.PROFIT_WARNING,
        EventType.MATERIAL_REVENUE_UPDATE, EventType.BACKLOG_UPDATE)},
    **{t: EventCategory.CAPITAL_ALLOCATION for t in (
        EventType.BUYBACK_AUTHORISATION, EventType.BUYBACK_EXECUTED,
        EventType.SPECIAL_DIVIDEND, EventType.DEBT_REPAYMENT, EventType.REFINANCING)},
    **{t: EventCategory.FINANCING for t in (
        EventType.EQUITY_OFFERING, EventType.ATM_PROGRAMME, EventType.CONVERTIBLE_DEBT,
        EventType.DEBT_RAISE, EventType.STRATEGIC_INVESTMENT,
        EventType.PRIVATE_PLACEMENT)},
    **{t: EventCategory.LEGAL for t in (
        EventType.LAWSUIT_WIN, EventType.LAWSUIT_LOSS, EventType.SETTLEMENT,
        EventType.PATENT_RULING, EventType.INVESTIGATION_OPENED,
        EventType.INVESTIGATION_CLOSED)},
    **{t: EventCategory.REGULATORY for t in (
        EventType.REGULATORY_CLEARANCE, EventType.PERMIT_LICENCE,
        EventType.GOVERNMENT_FUNDING, EventType.GRANT)},
    **{t: EventCategory.PRODUCT for t in (
        EventType.PRODUCT_LAUNCH, EventType.TECHNICAL_MILESTONE,
        EventType.STRATEGIC_PARTNERSHIP, EventType.CUSTOMER_DEPLOYMENT)},
    **{t: EventCategory.OWNERSHIP for t in (
        EventType.ACTIVIST_13D, EventType.PASSIVE_13G, EventType.INSIDER_PURCHASE)},
    **{t: EventCategory.RESTRUCTURING for t in (
        EventType.BANKRUPTCY, EventType.BANKRUPTCY_EMERGENCE, EventType.DEBT_EXCHANGE,
        EventType.COST_RESTRUCTURING)},
    EventType.ANALYST_ACTION: EventCategory.ANALYST,
    EventType.EARNINGS_RELEASE: EventCategory.EARNINGS,
    EventType.OTHER_MATERIAL: EventCategory.OTHER,
    EventType.UNKNOWN: EventCategory.UNKNOWN,
}


def category_for(event_type: EventType) -> EventCategory:
    return EVENT_CATEGORY.get(event_type, EventCategory.UNKNOWN)


class Certainty(StrEnum):
    """Language certainty (§17) — how committed is the announcement?"""

    EXECUTED = "EXECUTED"        # "definitive agreement", "awarded", "approved", "closed"
    BINDING = "BINDING"          # binding but not yet completed
    CONDITIONAL = "CONDITIONAL"  # subject to approvals/conditions
    INTENT = "INTENT"            # MOU, LOI, preferred bidder, non-binding
    SPECULATIVE = "SPECULATIVE"  # "expects", "could", "potential", rumour


CERTAINTY_VALUE: dict[Certainty, float] = {
    Certainty.EXECUTED: 1.0,
    Certainty.BINDING: 0.85,
    Certainty.CONDITIONAL: 0.6,
    Certainty.INTENT: 0.3,
    Certainty.SPECULATIVE: 0.12,
}


class CatalystState(StrEnum):
    INGESTED = "INGESTED"
    CLUSTERED = "CLUSTERED"
    RESOLVED = "RESOLVED"
    CLASSIFIED = "CLASSIFIED"
    REJECTED = "REJECTED"
    ROUTED_TO_EARNINGS = "ROUTED_TO_EARNINGS"
    ANALYSING = "ANALYSING"
    QUANTIFIED = "QUANTIFIED"
    INVESTIGATED = "INVESTIGATED"
    SCORED = "SCORED"
    ALERTED = "ALERTED"
    SUPERSEDED = "SUPERSEDED"
    FAILED = "FAILED"


class HaltState(StrEnum):
    NONE = "NONE"
    NEWS_PENDING = "NEWS_PENDING"
    LULD = "LULD"
    REGULATORY = "REGULATORY"
    UNKNOWN = "UNKNOWN"


class CatalystHalfLife(StrEnum):
    """§53 — how long the catalyst's effect plausibly persists."""

    MINUTES = "MINUTES"
    HOURS = "HOURS"
    DAYS = "DAYS"
    STRUCTURAL = "STRUCTURAL"
    UNKNOWN = "UNKNOWN"


class RejectReason(StrEnum):
    LOW_ENTITY_CONFIDENCE = "LOW_ENTITY_CONFIDENCE"
    DUPLICATE = "DUPLICATE"
    RECYCLED = "RECYCLED"
    STALE = "STALE"
    NOT_MATERIAL = "NOT_MATERIAL"
    SOCIAL_RUMOUR_ONLY = "SOCIAL_RUMOUR_ONLY"
    PROMOTIONAL = "PROMOTIONAL"
    EXCLUDED_SECURITY = "EXCLUDED_SECURITY"
    EARNINGS_EVENT = "EARNINGS_EVENT"
    CLAUDE_INVALIDATED = "CLAUDE_INVALIDATED"
