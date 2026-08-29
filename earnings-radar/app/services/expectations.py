"""ExpectationsService — consensus bands, never the friendliest number.

When providers disagree, the beat is scored against the band's least
favourable edge and estimate_confidence drops (spec §EXPECTATIONS ENGINE,
regression case 6).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.providers.base import EstimateDTO

# Band width (as % of midpoint) beyond which providers "significantly disagree"
DISAGREEMENT_PCT = {"eps": 8.0, "revenue": 2.0}
_DEFAULT_DISAGREEMENT_PCT = 5.0


@dataclass
class ConsensusBand:
    metric: str
    low: float
    high: float
    mid: float
    providers: list[str] = field(default_factory=list)
    disagreement: bool = False

    @property
    def width_pct(self) -> float:
        return abs(self.high - self.low) / abs(self.mid) * 100 if self.mid else 0.0


@dataclass
class Expectations:
    bands: dict[str, ConsensusBand] = field(default_factory=dict)
    estimate_confidence: str = "LOW"          # HIGH / MEDIUM / LOW
    notes: list[str] = field(default_factory=list)

    def band(self, metric: str) -> ConsensusBand | None:
        return self.bands.get(metric)


def build_expectations(estimates: list[EstimateDTO]) -> Expectations:
    by_metric: dict[str, list[EstimateDTO]] = {}
    for est in estimates:
        by_metric.setdefault(est.metric, []).append(est)

    exp = Expectations()
    for metric, rows in by_metric.items():
        values = [r.value for r in rows]
        low, high = min(values), max(values)
        mid = sum(values) / len(values)
        band = ConsensusBand(metric=metric, low=low, high=high, mid=mid,
                             providers=sorted({r.provider for r in rows}))
        threshold = DISAGREEMENT_PCT.get(metric, _DEFAULT_DISAGREEMENT_PCT)
        if len(band.providers) > 1 and band.width_pct > threshold:
            band.disagreement = True
            exp.notes.append(
                f"{metric} consensus disagreement: {low:g}–{high:g} "
                f"({band.width_pct:.1f}% wide) across {', '.join(band.providers)}")
        exp.bands[metric] = band

    core = [exp.bands.get("eps"), exp.bands.get("revenue")]
    have_core = [b for b in core if b is not None]
    multi = [b for b in have_core if len(b.providers) >= 2 and not b.disagreement]
    if len(have_core) == 2 and len(multi) == 2:
        exp.estimate_confidence = "HIGH"
    elif have_core and not any(b.disagreement for b in have_core):
        exp.estimate_confidence = "MEDIUM"
    else:
        exp.estimate_confidence = "LOW"
        if not have_core:
            exp.notes.append("no EPS/revenue consensus retrieved")
    return exp


def surprise_pct_vs_band(actual: float, band: ConsensusBand) -> tuple[float, float]:
    """Return (conservative_surprise_pct, favourable_surprise_pct).

    conservative = the smallest surprise any provider's number supports (a
    beat measured against the highest estimate; a miss at its most severe).
    Scoring always uses the conservative figure, so provider disagreement can
    never be resolved in the bullish direction (regression case 6).
    """
    def pct(base: float) -> float:
        if abs(base) < 1e-9:
            # Percentage surprise is meaningless against a ~zero base (EPS
            # near break-even); callers fall back to absolute comparison.
            return 0.0
        return (actual - base) / abs(base) * 100

    edges = [pct(band.low), pct(band.high)]
    return min(edges), max(edges)
