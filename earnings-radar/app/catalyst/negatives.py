"""Negative-offset and dilution engines (spec §30, §58).

Every apparently positive event is searched for the thing that undoes it:
a $500m contract with $5m guaranteed, an approval with a restrictive label,
a strong trial with a serious adverse event, a catalyst landing on a company
that must raise equity next quarter.

Deterministic detection here; Claude adds what only reading can find.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.catalyst.enums import Certainty, EventType
from app.catalyst.materiality import CompanyFinancials


@dataclass
class Offset:
    description: str
    severity: float          # 0-10, 10 = may overwhelm the positive
    source: str = "engine"   # engine | claude
    evidence: str = ""


@dataclass
class DilutionAssessment:
    potential_dilution_pct: float | None = None
    cash_runway_quarters: float | None = None
    needs_capital: bool | None = None
    notes: list[str] = field(default_factory=list)


# Textual markers of common offsets.
_OFFSET_PATTERNS: list[tuple[str, float, str]] = [
    (r"\bsubject to (?:the )?(?:successful )?completion\b", 2.5, "completion conditions attached"),
    (r"\bno (?:minimum|guaranteed) (?:order|purchase|volume)\b", 6.0,
     "no guaranteed order volume"),
    (r"\bnon-?binding\b", 5.5, "non-binding arrangement"),
    (r"\bmemorandum of understanding\b", 5.0, "MOU rather than a contract"),
    (r"\bletter of intent\b", 5.0, "letter of intent only"),
    (r"\bup to \$", 3.5, "'up to' framing — headline is a ceiling, not a commitment"),
    (r"\bunfunded\b", 6.0, "unfunded award"),
    (r"\bmultiple[- ]award\b|\bmulti[- ]award\b", 5.0,
     "multi-award vehicle — value shared with competitors"),
    (r"\bidiq\b|\bindefinite delivery\b", 4.5, "IDIQ vehicle — orders not guaranteed"),
    (r"\bpilot (?:program|project|phase)\b", 4.5, "pilot rather than production deployment"),
    (r"\bproof of concept\b", 4.5, "proof of concept only"),
    (r"\bunpaid\b", 5.5, "unpaid engagement"),
    (r"\bat-?the-?market (?:offering|program)\b", 6.0, "ATM programme — ongoing dilution"),
    (r"\bshelf registration\b", 4.0, "shelf registration in place — dilution capacity"),
    (r"\bconcurrent(?:ly)? .{0,30}offering\b", 7.5,
     "simultaneous equity offering alongside the news"),
    (r"\bgoing concern\b", 8.5, "going-concern warning"),
    (r"\bsubstantial doubt\b", 8.5, "substantial doubt about continuing as a going concern"),
    (r"\breverse (?:stock )?split\b", 6.0, "reverse split — often precedes dilution"),
    (r"\bserious adverse event\b", 8.0, "serious adverse event reported"),
    (r"\bdeaths?\b.{0,40}\b(?:trial|study|arm)\b", 8.0, "deaths reported in trial"),
    (r"\bdid not (?:meet|achieve)\b.{0,40}\bprimary endpoint\b", 9.0,
     "primary endpoint not met"),
    (r"\bmissed (?:the )?primary endpoint\b", 9.0, "primary endpoint missed"),
    (r"\bpost-?hoc\b", 6.0, "post-hoc analysis rather than pre-specified"),
    (r"\bsubgroup analysis\b", 5.5, "result rests on a subgroup, not the full population"),
    (r"\bboxed warning\b", 7.0, "boxed warning on the label"),
    (r"\brestricted label\b|\blimited to patients\b", 6.0, "restrictive label"),
    (r"\bappeal\b", 4.5, "subject to appeal"),
    (r"\bterminat\w+ (?:the )?agreement\b", 7.0, "an agreement is being terminated"),
    (r"\bcustomer concentration\b", 4.0, "customer concentration risk"),
    (r"\bdelayed?\b.{0,30}\b(?:launch|approval|delivery)\b", 5.0, "delay disclosed"),
]


def detect_textual_offsets(text: str) -> list[Offset]:
    """Scan the release for offset language."""
    lowered = (text or "").lower()
    found: list[Offset] = []
    seen: set[str] = set()
    for pattern, severity, description in _OFFSET_PATTERNS:
        match = re.search(pattern, lowered)
        if not match or description in seen:
            continue
        seen.add(description)
        start = max(0, match.start() - 70)
        found.append(Offset(description=description, severity=severity,
                            evidence=lowered[start:match.end() + 70].strip()))
    return found


def assess_dilution(financials: CompanyFinancials, *,
                    quarterly_burn: float | None = None,
                    shelf_capacity: float | None = None,
                    atm_active: bool | None = None) -> DilutionAssessment:
    """§30 — a great catalyst on a company that must raise equity imminently is
    materially less attractive."""
    assessment = DilutionAssessment()

    if financials.cash is not None and quarterly_burn and quarterly_burn > 0:
        assessment.cash_runway_quarters = round(financials.cash / quarterly_burn, 1)
        if assessment.cash_runway_quarters < 4:
            assessment.needs_capital = True
            assessment.notes.append(
                f"cash runway ≈ {assessment.cash_runway_quarters:.1f} quarters — "
                "financing likely within a year")
        else:
            assessment.needs_capital = False

    if shelf_capacity and financials.market_cap:
        assessment.potential_dilution_pct = round(
            shelf_capacity / financials.market_cap * 100, 1)
        assessment.notes.append(
            f"shelf capacity is {assessment.potential_dilution_pct:.1f}% of market cap")

    if atm_active:
        assessment.notes.append("ATM programme active — dilution can occur into any rally")

    return assessment


def dilution_offsets(assessment: DilutionAssessment) -> list[Offset]:
    offsets: list[Offset] = []
    runway = assessment.cash_runway_quarters
    if runway is not None and runway < 2:
        offsets.append(Offset("cash runway under two quarters — near-term financing very likely",
                              8.0, evidence=f"runway {runway:.1f}q"))
    elif runway is not None and runway < 4:
        offsets.append(Offset("cash runway under a year — financing risk into any strength",
                              5.5, evidence=f"runway {runway:.1f}q"))
    if assessment.potential_dilution_pct and assessment.potential_dilution_pct >= 25:
        offsets.append(Offset(
            f"shelf capacity equals {assessment.potential_dilution_pct:.0f}% of market cap",
            6.0))
    return offsets


def structural_offsets(*, event_type: EventType, certainty: Certainty,
                       materiality_missing: list[str],
                       is_extension: bool | None = None) -> list[Offset]:
    """Offsets implied by the event's own structure rather than its wording."""
    offsets: list[Offset] = []

    if certainty in (Certainty.INTENT, Certainty.SPECULATIVE):
        offsets.append(Offset(
            f"commitment level is {certainty.value.lower()} — the economics may never materialise",
            6.5 if certainty == Certainty.SPECULATIVE else 5.0))

    if event_type in (EventType.EQUITY_OFFERING, EventType.ATM_PROGRAMME,
                      EventType.CONVERTIBLE_DEBT, EventType.PRIVATE_PLACEMENT):
        offsets.append(Offset("event is itself dilutive financing", 7.0))

    if event_type == EventType.FDA_ACCEPTANCE:
        offsets.append(Offset(
            "application acceptance is a procedural step, not an approval decision", 5.0))

    if event_type == EventType.BUYBACK_AUTHORISATION:
        offsets.append(Offset(
            "authorisation grants permission to repurchase; it is not a purchase", 4.0))

    if event_type == EventType.PASSIVE_13G:
        offsets.append(Offset("passive 13G filing implies no activist intent", 5.0))

    if is_extension:
        offsets.append(Offset("extension of existing business — incremental value limited", 4.0))

    if materiality_missing:
        offsets.append(Offset(
            f"materiality incomplete — missing {', '.join(materiality_missing)}", 3.0))

    return offsets


def aggregate_severity(offsets: list[Offset]) -> float:
    """Combine offsets into a single 0-10 severity.

    The worst offset dominates; additional ones add diminishing weight, so
    three mild caveats never outweigh one fatal flaw.
    """
    if not offsets:
        return 0.0
    ranked = sorted((o.severity for o in offsets), reverse=True)
    total = ranked[0]
    for i, severity in enumerate(ranked[1:], start=1):
        total += severity * (0.35 ** i)
    return round(min(total, 10.0), 2)
