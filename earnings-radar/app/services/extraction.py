"""Deterministic financial extraction from press-release text.

Best-effort regex/table extraction with per-fact confidence and source
attribution. The LLM sees these facts as evidence; it never replaces them.
Anything not found stays None — never guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ExtractedFact:
    metric: str
    value: float
    unit: str = "USD"
    confidence: float = 0.8
    method: str = "regex"
    snippet: str = ""


@dataclass
class ExtractionResult:
    facts: dict[str, ExtractedFact] = field(default_factory=dict)

    def value(self, metric: str) -> float | None:
        fact = self.facts.get(metric)
        return fact.value if fact else None


_MULTIPLIERS = {
    "billion": 1e9, "bn": 1e9, "b": 1e9,
    "million": 1e6, "mn": 1e6, "m": 1e6,
    "thousand": 1e3, "k": 1e3,
}

_MONEY = r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(billion|million|thousand|bn|mn|[bmk])?"

# Ordered patterns: first match wins per metric.
_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "revenue": [
        (rf"(?:total\s+)?(?:net\s+)?revenue[s]?\s+(?:of|was|were|increased[^$]*to|grew[^$]*to|rose[^$]*to)\s+{_MONEY}", 0.9),
        (rf"(?:total\s+)?(?:net\s+)?revenue[s]?[^.$]{{0,40}}?{_MONEY}", 0.6),
    ],
    "eps_diluted": [
        (r"diluted\s+(?:net\s+)?(?:income|earnings|loss)\s+per\s+share\s+(?:of|was|were)\s+\$?\(?(-?[0-9]+\.[0-9]+)\)?", 0.9),
        (r"diluted\s+EPS\s+(?:of|was)\s+\$?\(?(-?[0-9]+\.[0-9]+)\)?", 0.9),
        (r"(?:GAAP\s+)?diluted\s+(?:net\s+)?(?:income|earnings)\s+per\s+(?:diluted\s+)?share[^.$]{0,30}\$?\(?(-?[0-9]+\.[0-9]+)\)?", 0.7),
    ],
    "eps_adjusted": [
        (r"(?:non-GAAP|adjusted)\s+(?:diluted\s+)?(?:net\s+income\s+|earnings\s+)?per\s+(?:diluted\s+)?share\s+(?:of|was|were)\s+\$?\(?(-?[0-9]+\.[0-9]+)\)?", 0.9),
        (r"(?:non-GAAP|adjusted)\s+(?:diluted\s+)?EPS\s+(?:of|was)\s+\$?\(?(-?[0-9]+\.[0-9]+)\)?", 0.9),
    ],
    "operating_cash_flow": [
        (rf"(?:net\s+)?cash\s+(?:provided\s+by|from)\s+operat(?:ing|ions)\s+activities\s+(?:of|was|were)\s+{_MONEY}", 0.85),
        (rf"operating\s+cash\s+flow\s+(?:of|was)\s+{_MONEY}", 0.85),
    ],
    "free_cash_flow": [
        (rf"free\s+cash\s+flow\s+(?:of|was)\s+{_MONEY}", 0.85),
    ],
    "gross_margin_pct": [
        (r"gross\s+margin\s+(?:of|was|expanded\s+to|improved\s+to)\s+([0-9]+(?:\.[0-9]+)?)\s?%", 0.85),
    ],
    "operating_margin_pct": [
        (r"operating\s+margin\s+(?:of|was|expanded\s+to|improved\s+to)\s+([0-9]+(?:\.[0-9]+)?)\s?%", 0.85),
    ],
}


def extract_financials(text: str) -> ExtractionResult:
    result = ExtractionResult()
    flat = re.sub(r"\s+", " ", text)
    for metric, patterns in _PATTERNS.items():
        for pattern, confidence in patterns:
            match = re.search(pattern, flat, re.IGNORECASE)
            if not match:
                continue
            raw = match.group(1).replace(",", "")
            try:
                value = float(raw)
            except ValueError:
                continue
            if match.lastindex and match.lastindex >= 2 and match.group(2):
                value *= _MULTIPLIERS.get(match.group(2).lower(), 1.0)
            # Parenthesised EPS means a loss
            if "(" in match.group(0) and metric.startswith("eps"):
                value = -abs(value)
            unit = "%" if metric.endswith("_pct") else "USD"
            result.facts[metric] = ExtractedFact(
                metric=metric, value=value, unit=unit, confidence=confidence,
                snippet=match.group(0)[:200])
            break
    return result
