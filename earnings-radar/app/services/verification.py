"""SourceVerificationService — a release is CONFIRMED only when the document
contains actual current-quarter financial results (spec §RELEASE DETECTION /
§RELEASE VERIFICATION).

Placeholders, scheduling announcements, previews and previous-quarter reports
are explicitly rejected.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Phrases that mark a document as NOT a results release
_PLACEHOLDER_PATTERNS = [
    r"will\s+(?:report|announce|release)\s+(?:its\s+)?(?:financial\s+)?results",
    r"to\s+(?:report|announce|release)\s+(?:its\s+)?(?:financial\s+)?(?:quarterly\s+)?results",
    r"invites?\s+(?:you|investors)\s+to",
    r"conference\s+call\s+(?:date\s+)?announcement",
    r"schedules?\s+(?:its\s+)?(?:earnings|results|conference)",
    r"to\s+host\s+(?:its\s+)?(?:earnings|investor)\s+(?:call|webcast|conference)",
    r"earnings\s+(?:date|call)\s+announcement",
    r"analyst\s+(?:preview|estimates|expectations)",
]

# Evidence of actual results
_RESULTS_PATTERNS = [
    r"reports?\s+(?:record\s+)?(?:financial\s+)?results",
    r"announces?\s+(?:record\s+)?(?:financial\s+)?results",
    r"three\s+months\s+ended",
    r"(?:revenue|net\s+income|net\s+loss)\s+(?:of|was|were)\s+\$",
    r"(?:diluted|basic)\s+(?:earnings|income|loss)\s+per\s+share",
    r"non-GAAP",
    r"results\s+of\s+operations",
]

_QUARTER_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4}


@dataclass
class VerificationResult:
    verified: bool
    reasons: list[str] = field(default_factory=list)
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    ticker_confirmed: bool = False
    document_type: str = ""


def infer_fiscal_period(text: str) -> tuple[int | None, int | None]:
    flat = re.sub(r"\s+", " ", text)
    m = re.search(
        r"(first|second|third|fourth)\s+quarter\s+(?:of\s+)?(?:fiscal\s+)?(?:year\s+)?(20\d{2})",
        flat, re.IGNORECASE)
    if m:
        return int(m.group(2)), _QUARTER_WORDS[m.group(1).lower()]
    m = re.search(r"\bQ([1-4])\s*(?:FY)?\s*(20\d{2})\b", flat, re.IGNORECASE)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.search(r"(?:fiscal\s+)?(20\d{2})\s+(first|second|third|fourth)\s+quarter",
                  flat, re.IGNORECASE)
    if m:
        return int(m.group(1)), _QUARTER_WORDS[m.group(2).lower()]
    return None, None


def verify_release_document(*, text: str, ticker: str, company_name: str,
                            expected_fy: int | None, expected_fq: int | None,
                            document_type: str = "") -> VerificationResult:
    result = VerificationResult(verified=False, document_type=document_type)
    flat = re.sub(r"\s+", " ", text)
    lowered = flat.lower()

    head = lowered[:4000]
    for pattern in _PLACEHOLDER_PATTERNS:
        if re.search(pattern, head, re.IGNORECASE):
            # A scheduling phrase only disqualifies when no actual results
            # follow (many releases mention the upcoming call too).
            if not any(re.search(p, lowered) for p in
                       (r"(?:revenue|net\s+income|net\s+loss)\s+(?:of|was|were)\s+\$",
                        r"three\s+months\s+ended")):
                result.reasons.append(f"placeholder/scheduling document ({pattern})")
                return result

    hits = [p for p in _RESULTS_PATTERNS if re.search(p, lowered, re.IGNORECASE)]
    if len(hits) < 2:
        result.reasons.append("no current-quarter financial results found in document")
        return result

    # Company identity
    name_token = (company_name or "").split(",")[0].split(" Inc")[0].strip().lower()
    result.ticker_confirmed = bool(
        re.search(rf"\b{re.escape(ticker)}\b", flat) or (name_token and name_token in lowered))
    if not result.ticker_confirmed:
        result.reasons.append("neither ticker nor company name found in document")
        return result

    # Fiscal period
    fy, fq = infer_fiscal_period(flat)
    result.fiscal_year, result.fiscal_quarter = fy, fq
    if expected_fq is not None and fq is not None and fq != expected_fq:
        # Fiscal-year labelling differs between providers and companies
        # (calendar vs fiscal year), so quarter mismatch is the reliable
        # "this is an old report" signal.
        result.reasons.append(
            f"fiscal quarter mismatch: document Q{fq} vs expected Q{expected_fq} "
            "— possible previous-quarter report")
        return result

    result.verified = True
    result.reasons.append(f"results evidence: {len(hits)} markers; identity confirmed"
                          + (f"; period Q{fq} FY{fy}" if fq else "; period not stated"))
    return result
