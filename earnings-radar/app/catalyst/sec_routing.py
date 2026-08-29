"""SEC filing routing (spec §6).

Fast, deterministic triage over filing metadata so we do NOT deep-analyse every
filing. Item codes carry most of the signal: an 8-K Item 1.01 is a material
definitive agreement, 2.02 is results (Earnings Sentinel's job), 5.02 is a
management change. Routing happens before any document download.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.catalyst.enums import EventType

# Forms worth monitoring at all (§6).
MONITORED_FORMS = {
    "8-K", "8-K/A", "6-K", "6-K/A",
    "10-Q", "10-Q/A", "10-K", "10-K/A",
    "S-4", "S-3", "S-1", "424B1", "424B2", "424B3", "424B4", "424B5",
    "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A",
    "SC TO-T", "SC TO-I", "SC 14D9",
    "3", "4", "5",
    "DEFM14A", "PREM14A",
}

# 8-K item code → (event type, worth deep analysis?)
ITEM_ROUTING: dict[str, tuple[EventType, bool]] = {
    "1.01": (EventType.COMMERCIAL_CONTRACT, True),    # material definitive agreement
    "1.02": (EventType.OTHER_MATERIAL, True),         # termination of agreement
    "1.03": (EventType.BANKRUPTCY, True),
    "2.01": (EventType.ACQUISITION, True),            # completion of acquisition/disposition
    "2.02": (EventType.EARNINGS_RELEASE, False),      # → Earnings Sentinel
    "2.03": (EventType.DEBT_RAISE, True),
    "2.04": (EventType.OTHER_MATERIAL, True),
    "2.05": (EventType.COST_RESTRUCTURING, True),
    "2.06": (EventType.OTHER_MATERIAL, True),         # material impairment
    "3.01": (EventType.OTHER_MATERIAL, True),         # delisting notice
    "3.02": (EventType.EQUITY_OFFERING, True),        # unregistered equity sale
    "4.01": (EventType.OTHER_MATERIAL, True),         # auditor change
    "4.02": (EventType.OTHER_MATERIAL, True),         # non-reliance on financials
    "5.01": (EventType.OTHER_MATERIAL, True),         # change in control
    "5.02": (EventType.OTHER_MATERIAL, True),         # director/officer changes
    "7.01": (EventType.OTHER_MATERIAL, True),         # Reg FD
    "8.01": (EventType.OTHER_MATERIAL, True),         # other material events
}

FORM_ROUTING: dict[str, tuple[EventType, bool]] = {
    "SC 13D": (EventType.ACTIVIST_13D, True),
    "SC 13D/A": (EventType.ACTIVIST_13D, True),
    "SC 13G": (EventType.PASSIVE_13G, False),
    "SC 13G/A": (EventType.PASSIVE_13G, False),
    "SC TO-T": (EventType.TENDER_OFFER, True),
    "SC TO-I": (EventType.TENDER_OFFER, True),
    "SC 14D9": (EventType.TENDER_OFFER, True),
    "S-4": (EventType.MERGER_ANNOUNCEMENT, True),
    "DEFM14A": (EventType.MERGER_ANNOUNCEMENT, True),
    "PREM14A": (EventType.MERGER_ANNOUNCEMENT, True),
    "S-3": (EventType.ATM_PROGRAMME, True),          # shelf — dilution watch
    "S-1": (EventType.EQUITY_OFFERING, True),
    "424B1": (EventType.EQUITY_OFFERING, True),
    "424B2": (EventType.EQUITY_OFFERING, True),
    "424B3": (EventType.EQUITY_OFFERING, True),
    "424B4": (EventType.EQUITY_OFFERING, True),
    "424B5": (EventType.EQUITY_OFFERING, True),
    "4": (EventType.INSIDER_PURCHASE, False),        # most Form 4s are routine
    "10-Q": (EventType.EARNINGS_RELEASE, False),
    "10-K": (EventType.EARNINGS_RELEASE, False),
}


@dataclass
class FilingRoute:
    monitored: bool
    event_type: EventType
    deep_analysis: bool
    route_to_earnings: bool
    reason: str


def route_filing(form_type: str, items: list[str] | None = None,
                 description: str = "") -> FilingRoute:
    """Decide what to do with a filing from its metadata alone."""
    form = (form_type or "").strip().upper()
    items = [i.strip() for i in (items or []) if i.strip()]

    if form not in MONITORED_FORMS:
        return FilingRoute(False, EventType.UNKNOWN, False, False,
                           f"form {form or '?'} not monitored")

    if form.startswith(("8-K", "6-K")):
        # An 8-K can carry several items; take the most actionable.
        best: FilingRoute | None = None
        for item in items:
            code = item.split()[0] if item else ""
            for prefix, (event_type, deep) in ITEM_ROUTING.items():
                if not code.startswith(prefix):
                    continue
                route = FilingRoute(
                    monitored=True, event_type=event_type, deep_analysis=deep,
                    route_to_earnings=event_type == EventType.EARNINGS_RELEASE,
                    reason=f"{form} item {prefix}")
                if best is None or (route.deep_analysis and not best.deep_analysis):
                    best = route
        if best is not None:
            return best
        # No recognised item — a 6-K rarely carries item codes at all.
        blob = description.lower()
        if any(k in blob for k in ("results of operations", "financial results", "earnings")):
            return FilingRoute(True, EventType.EARNINGS_RELEASE, False, True,
                               f"{form} description indicates results")
        return FilingRoute(True, EventType.OTHER_MATERIAL, True, False,
                           f"{form} with no recognised item code")

    event_type, deep = FORM_ROUTING.get(form, (EventType.OTHER_MATERIAL, True))
    return FilingRoute(
        monitored=True, event_type=event_type, deep_analysis=deep,
        route_to_earnings=event_type == EventType.EARNINGS_RELEASE,
        reason=f"form {form}")
