"""Fast deterministic classification and pre-Claude screening (spec §10-11, §57).

The economics only work if the overwhelming majority of items die cheaply.
Target funnel (§75): 10,000 in → ~500 market-relevant → ~75 materially
interesting → ~15 deep-investigated → ~3 scoring 8+ → 0-1 scoring 9+.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.catalyst.enums import EventType, RejectReason, SourceTier

# Ordered: the first pattern to match wins, so put specific before generic.
_EVENT_PATTERNS: list[tuple[EventType, tuple[str, ...]]] = [
    # ── Biotech: approval vs acceptance is the classic trap (§27) ──
    (EventType.FDA_APPROVAL, (
        r"\bfda (?:has )?approv", r"\bapproved by the fda\b", r"\bgrants? (?:full )?approval\b",
        r"\bmarketing authorization granted\b")),
    (EventType.FDA_CRL, (
        r"\bcomplete response letter\b", r"\bcrl\b", r"\bfda (?:has )?declined\b")),
    (EventType.FDA_ACCEPTANCE, (
        r"\baccepts?(?:ed)? .{0,40}\b(?:nda|bla|application)\b",
        r"\bfiling acceptance\b", r"\baccepted for review\b", r"\bpdufa date\b")),
    (EventType.LABEL_EXPANSION, (r"\blabel expansion\b", r"\bexpanded indication\b")),
    (EventType.BREAKTHROUGH_DESIGNATION, (
        r"\bbreakthrough therapy\b", r"\bfast track designation\b",
        r"\borphan drug designation\b", r"\bpriority review\b")),
    (EventType.CLINICAL_HOLD_LIFTED, (r"\bclinical hold (?:has been )?lifted\b",)),
    (EventType.CLINICAL_HOLD, (r"\bclinical hold\b",)),
    (EventType.PHASE_3_RESULT, (r"\bphase\s*(?:3|iii)\b",)),
    (EventType.PHASE_2_RESULT, (r"\bphase\s*(?:2|ii)\b",)),
    (EventType.PHASE_1_RESULT, (r"\bphase\s*(?:1|i)\b",)),
    (EventType.TRIAL_TERMINATION, (r"\bdiscontinu\w+ (?:the )?(?:trial|study)\b",)),
    (EventType.TRIAL_INITIATION, (r"\b(?:initiat|dos\w+ (?:the )?first patient)\w*\b.{0,30}trial",)),

    # ── M&A ──
    (EventType.TAKEOVER_OFFER, (
        r"\bto (?:be )?acquir\w+ .{0,40}\bfor \$", r"\bbuyout offer\b", r"\btakeover (?:bid|offer)\b",
        r"\bproposal to acquire\b", r"\bagreed to be acquired\b")),
    (EventType.DEAL_APPROVAL, (
        r"\bantitrust clearance\b", r"\bhsr (?:waiting period )?(?:expired|clearance)\b",
        r"\bregulatory approval (?:for|of) the (?:merger|acquisition)\b",
        r"\bcleared (?:the )?(?:merger|acquisition|deal)\b")),
    (EventType.DEAL_TERMINATION, (r"\bterminat\w+ (?:the )?(?:merger|acquisition|agreement)\b",)),
    (EventType.MERGER_ANNOUNCEMENT, (r"\bmerger agreement\b", r"\bmerger of equals\b")),
    (EventType.ACQUISITION, (r"\bacquisition of\b", r"\bacquires?\b", r"\bto purchase\b")),
    (EventType.TENDER_OFFER, (r"\btender offer\b",)),
    (EventType.STRATEGIC_REVIEW, (
        r"\bstrategic (?:review|alternatives)\b", r"\bexploring (?:a )?sale\b")),
    (EventType.ASSET_DISPOSAL, (r"\bdivest\w*\b", r"\bsale of (?:its|the) .{0,30}(?:business|division)\b")),

    # ── Contracts ──
    (EventType.GOVERNMENT_CONTRACT, (
        r"\b(?:department of defen[cs]e|dod|nasa|department of energy|gsa|u\.?s\.? army|"
        r"u\.?s\.? navy|air force|space force|department of|federal)\b.{0,60}\b"
        r"(?:contract|award|task order|idiq)\b",
        r"\b(?:contract|award|task order)\b.{0,60}\b(?:department of|federal agency|u\.?s\.? government)\b")),
    (EventType.COMMERCIAL_CONTRACT, (
        r"\b(?:multi-?year )?(?:contract|agreement)\b.{0,40}\bvalued at\b",
        r"\bawarded a\b.{0,30}\bcontract\b", r"\bsigns? .{0,30}\bagreement\b",
        r"\bdefinitive agreement\b")),
    (EventType.CUSTOMER_WIN, (r"\bnew customer\b", r"\bselected by\b", r"\bwins? .{0,30}\border\b")),
    (EventType.SUPPLY_AGREEMENT, (r"\bsupply agreement\b",)),
    (EventType.DISTRIBUTION_AGREEMENT, (r"\bdistribution agreement\b",)),
    (EventType.LICENSING_DEAL, (r"\blicens\w+ agreement\b", r"\blicensing deal\b")),

    # ── Guidance ──
    (EventType.GUIDANCE_RAISE, (
        r"\brais\w+ (?:its |full-?year |fy\d* )?(?:guidance|outlook|forecast)\b",
        r"\bincreases? (?:its )?(?:guidance|outlook)\b", r"\bupgrades? (?:its )?outlook\b")),
    (EventType.GUIDANCE_CUT, (
        r"\b(?:lower|cut|reduc)\w* (?:its )?(?:guidance|outlook|forecast)\b",)),
    (EventType.PROFIT_WARNING, (r"\bprofit warning\b", r"\bwarns? on (?:profit|earnings)\b")),
    (EventType.BACKLOG_UPDATE, (r"\bbacklog\b",)),

    # ── Capital allocation ──
    (EventType.BUYBACK_EXECUTED, (
        r"\baccelerated share repurchase\b", r"\bcompleted .{0,30}repurchase\b",
        r"\bexecuted .{0,30}(?:buyback|repurchase)\b")),
    (EventType.BUYBACK_AUTHORISATION, (
        r"\b(?:authoriz|approv)\w+ .{0,40}(?:share )?(?:repurchase|buyback)\b",
        r"\bbuyback program\b", r"\brepurchase program\b")),
    (EventType.SPECIAL_DIVIDEND, (r"\bspecial dividend\b",)),
    (EventType.REFINANCING, (r"\brefinanc\w+\b",)),
    (EventType.DEBT_REPAYMENT, (r"\brepaid?\b.{0,20}\bdebt\b", r"\bdebt reduction\b")),

    # ── Financing (dilutive — usually NOT a positive catalyst) ──
    (EventType.EQUITY_OFFERING, (
        r"\bpublic offering\b", r"\bunderwritten offering\b", r"\bregistered direct offering\b",
        r"\bpricing of .{0,30}offering\b")),
    (EventType.ATM_PROGRAMME, (r"\bat-?the-?market\b", r"\batm program\b", r"\bshelf registration\b")),
    (EventType.CONVERTIBLE_DEBT, (r"\bconvertible (?:senior )?notes\b",)),
    (EventType.PRIVATE_PLACEMENT, (r"\bprivate placement\b", r"\bpipe (?:financing|deal)\b")),
    (EventType.STRATEGIC_INVESTMENT, (r"\bstrategic investment\b", r"\binvests? \$\d",)),

    # ── Legal ──
    (EventType.PATENT_RULING, (r"\bpatent\b.{0,40}\b(?:ruling|verdict|invalidat|upheld)\b",)),
    (EventType.LAWSUIT_WIN, (
        r"\bjury (?:awards?|verdict)\b", r"\bwins? .{0,30}(?:lawsuit|litigation|appeal)\b",
        r"\bcourt rules? in favor\b")),
    (EventType.SETTLEMENT, (r"\bsettle\w*\b.{0,40}\b(?:lawsuit|litigation|claims?)\b",)),
    (EventType.LAWSUIT_LOSS, (r"\bloses? .{0,30}(?:lawsuit|appeal)\b", r"\bfound liable\b")),
    (EventType.INVESTIGATION_CLOSED, (r"\binvestigation (?:has been )?closed\b",)),
    (EventType.INVESTIGATION_OPENED, (r"\b(?:sec|doj|ftc) investigation\b", r"\bsubpoena\b")),

    # ── Regulatory / government ──
    (EventType.REGULATORY_CLEARANCE, (r"\bregulatory (?:clearance|approval)\b", r"\bce mark\b")),
    (EventType.PERMIT_LICENCE, (r"\b(?:permit|licen[cs]e) (?:granted|awarded|approved)\b",)),
    (EventType.GOVERNMENT_FUNDING, (r"\bgovernment funding\b", r"\bfederal funding\b")),
    (EventType.GRANT, (r"\bawarded a .{0,20}grant\b", r"\bgrant funding\b")),

    # ── Ownership ──
    (EventType.ACTIVIST_13D, (r"\b13d\b", r"\bactivist (?:investor|stake)\b")),
    (EventType.PASSIVE_13G, (r"\b13g\b",)),
    (EventType.INSIDER_PURCHASE, (r"\binsider (?:buying|purchase)\b", r"\bceo (?:buys|purchased)\b")),

    # ── Product ──
    (EventType.STRATEGIC_PARTNERSHIP, (r"\bpartnership with\b", r"\bstrategic partnership\b",
                                       r"\bcollaboration with\b")),
    (EventType.PRODUCT_LAUNCH, (r"\blaunch\w*\b.{0,30}\b(?:product|platform|service)\b",
                                r"\bunveils?\b", r"\bintroduces?\b")),
    (EventType.CUSTOMER_DEPLOYMENT, (r"\bdeployment\b", r"\bgoes? live\b")),
    (EventType.TECHNICAL_MILESTONE, (r"\bmilestone\b",)),

    # ── Restructuring ──
    (EventType.BANKRUPTCY_EMERGENCE, (r"\bemerg\w+ from (?:chapter 11|bankruptcy)\b",)),
    (EventType.BANKRUPTCY, (r"\bchapter (?:11|7)\b", r"\bbankruptcy\b")),
    (EventType.COST_RESTRUCTURING, (r"\brestructuring (?:plan|program)\b", r"\blayoffs?\b")),

    # ── Analyst / earnings ──
    (EventType.ANALYST_ACTION, (
        r"\b(?:upgrades?|downgrades?)\b.{0,30}\bto\b", r"\bprice target\b",
        r"\binitiates? coverage\b", r"\breiterates?\b")),
    (EventType.EARNINGS_RELEASE, (
        r"\b(?:first|second|third|fourth) quarter .{0,20}results\b",
        r"\bq[1-4]\s*(?:fy)?\s*20\d{2}\b.{0,30}results\b",
        r"\breports? .{0,20}(?:quarter|full[- ]year|annual) .{0,10}results\b",
        r"\bearnings (?:report|release|results)\b")),
]

# Promotional / manipulation markers (§57).
_PROMO_PATTERNS = (
    r"\bpaid (?:advertisement|promotion)\b", r"\bsponsored content\b",
    r"\bcompensated\b.{0,40}\bshares\b", r"\bstock (?:alert|pick) of the (?:day|week)\b",
    r"\bnext \w+ to explode\b", r"\bcould soar \d+%", r"\bmulti-?bagger\b",
    r"\bdo not miss (?:out|this)\b", r"\bhuge news for investors\b",
    r"\brevolutionary blockchain\b", r"\bworld-?changing ai\b",
)

# Words that make an item obviously not company-specific market news.
_NOISE_PATTERNS = (
    r"\bwebinar\b", r"\bconference presentation\b", r"\bto present at\b",
    r"\bwill participate in\b", r"\binvestor day\b", r"\bnamed to\b.{0,30}\blist\b",
    r"\bappoints? .{0,30}(?:to its board|as director)\b",
    r"\bcelebrates?\b", r"\bsponsors?hip\b", r"\baward for excellence\b",
)


@dataclass
class Classification:
    event_type: EventType
    matched_pattern: str = ""
    is_promotional: bool = False
    is_noise: bool = False
    promo_markers: list[str] = field(default_factory=list)


def classify_event(headline: str, body: str = "") -> Classification:
    """Deterministic first-pass classification. Cheap and explainable."""
    text = f"{headline}\n{body[:4000]}".lower()

    promo = [p for p in _PROMO_PATTERNS if re.search(p, text)]
    noise = any(re.search(p, text) for p in _NOISE_PATTERNS)

    for event_type, patterns in _EVENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text):
                return Classification(event_type, pattern, bool(promo), noise, promo)

    return Classification(EventType.UNKNOWN, "", bool(promo), noise, promo)


@dataclass
class ScreenResult:
    """Outcome of the pre-Claude screen."""

    passed: bool
    reject_reason: RejectReason | None = None
    detail: str = ""
    deep_analysis_warranted: bool = False


# Event types that essentially never justify an expensive deep pass on their own.
_LOW_VALUE_TYPES = {
    EventType.ANALYST_ACTION, EventType.PASSIVE_13G, EventType.UNKNOWN,
}


def screen(*, classification: Classification, entity_confidence: float,
           source_tier: SourceTier, is_restatement: bool,
           min_entity_confidence: float = 0.7,
           allow_unknown_type: bool = False) -> ScreenResult:
    """Decide whether an item deserves the expensive path (§11).

    Everything rejected here is still stored — rejection is a recorded
    decision, not a silent drop.
    """
    if classification.is_promotional:
        return ScreenResult(False, RejectReason.PROMOTIONAL,
                            f"promotional markers: {classification.promo_markers}")

    if source_tier == SourceTier.SECONDARY:
        # Social/forum content alone can never trigger; it may corroborate later.
        return ScreenResult(False, RejectReason.SOCIAL_RUMOUR_ONLY,
                            "secondary-tier source only")

    if entity_confidence < min_entity_confidence:
        return ScreenResult(False, RejectReason.LOW_ENTITY_CONFIDENCE,
                            f"entity confidence {entity_confidence:.2f} < "
                            f"{min_entity_confidence:.2f}")

    if is_restatement:
        return ScreenResult(False, RejectReason.RECYCLED,
                            "restates previously public information")

    if classification.event_type == EventType.EARNINGS_RELEASE:
        return ScreenResult(False, RejectReason.EARNINGS_EVENT,
                            "earnings content — routed to Earnings Sentinel")

    if classification.is_noise:
        return ScreenResult(False, RejectReason.NOT_MATERIAL,
                            "routine corporate housekeeping")

    if classification.event_type == EventType.UNKNOWN and not allow_unknown_type:
        return ScreenResult(False, RejectReason.NOT_MATERIAL,
                            "no recognised material event type")

    deep = classification.event_type not in _LOW_VALUE_TYPES
    return ScreenResult(True, None, "passed screen", deep_analysis_warranted=deep)
