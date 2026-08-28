"""Deterministic guidance-range classification (spec §GUIDANCE ENGINE).

Distinguishes a genuine raise from a bottom-end narrowing — the spec's
"$10.0–10.5bn → $10.2–10.5bn is NOT a major raise" case.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import GuidanceStatus

_EPS = 1e-9


@dataclass
class GuidanceComparison:
    status: GuidanceStatus
    magnitude_pct: float          # midpoint change vs old midpoint
    note: str


def classify_guidance(old_low: float | None, old_high: float | None,
                      new_low: float | None, new_high: float | None) -> GuidanceComparison:
    if new_low is None and new_high is None:
        return GuidanceComparison(GuidanceStatus.NONE, 0.0, "no new guidance given")
    if old_low is None and old_high is None:
        return GuidanceComparison(GuidanceStatus.NONE, 0.0, "no prior guidance to compare")

    ol = old_low if old_low is not None else old_high
    oh = old_high if old_high is not None else old_low
    nl = new_low if new_low is not None else new_high
    nh = new_high if new_high is not None else new_low
    assert ol is not None and oh is not None and nl is not None and nh is not None

    old_mid = (ol + oh) / 2
    new_mid = (nl + nh) / 2
    magnitude = ((new_mid - old_mid) / abs(old_mid) * 100) if abs(old_mid) > _EPS else 0.0

    low_up = nl > ol + _EPS
    low_down = nl < ol - _EPS
    high_up = nh > oh + _EPS
    high_down = nh < oh - _EPS

    if not (low_up or low_down or high_up or high_down):
        return GuidanceComparison(GuidanceStatus.MAINTAINED, 0.0, "guidance unchanged")

    if (low_down or high_down) and not (low_up or high_up):
        return GuidanceComparison(GuidanceStatus.LOWERED, magnitude, "guidance lowered")
    if low_down and high_up or high_down and low_up:
        # widened / mixed — treat by midpoint, flag it
        status = GuidanceStatus.RAISED if magnitude > 0 else GuidanceStatus.LOWERED
        return GuidanceComparison(status, magnitude, "range widened/mixed; classified by midpoint")

    if low_up and high_up:
        return GuidanceComparison(GuidanceStatus.RAISED, magnitude, "full-range raise")
    if low_up and not high_up:
        return GuidanceComparison(
            GuidanceStatus.NARROWED, magnitude,
            "bottom-end increase only — modest, not a major raise")
    # high_up only: top-end lift
    return GuidanceComparison(GuidanceStatus.RAISED, magnitude, "top-end increase")
