"""Deduplication and event clustering (spec §12).

One real-world event is reported by the company, the SEC, two wires and five
syndicators within minutes. All of them must collapse into ONE cluster so the
event is scored once. The clustering signal is deliberately conservative:
same ticker, close in time, and strong textual/fact overlap.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

_WORD = re.compile(r"[a-z0-9]+")
# Words too common in financial headlines to carry any identifying signal.
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "by",
    "its", "it", "at", "as", "is", "are", "has", "have", "from", "that", "this",
    "inc", "corp", "corporation", "company", "ltd", "plc", "says", "said",
    "announces", "announced", "reports", "reported", "new", "will", "after",
}


def tokenise(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def extract_numbers(text: str) -> set[str]:
    """Money/quantity tokens are strong event fingerprints: a '$1.1 billion'
    contract reported by five outlets keeps that figure in every version."""
    out: set[str] = set()
    for match in re.finditer(
            r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(billion|million|bn|mn|b|m)?",
            text, re.IGNORECASE):
        num = match.group(1).replace(",", "")
        unit = (match.group(2) or "").lower()[:1]
        out.add(f"{float(num):g}{unit}")
    return out


@dataclass
class ClusterCandidate:
    cluster_key: str
    ticker: str
    headline: str
    tokens: set[str] = field(default_factory=set)
    numbers: set[str] = field(default_factory=set)
    earliest_public_at: datetime | None = None
    urls: set[str] = field(default_factory=set)
    accession_numbers: set[str] = field(default_factory=set)


@dataclass
class MatchResult:
    matched: bool
    similarity: float = 0.0
    reason: str = ""


def is_same_event(candidate: ClusterCandidate, *, ticker: str, headline: str,
                  body: str = "", published_at: datetime | None = None,
                  url: str = "", accession: str = "",
                  window: timedelta = timedelta(hours=36),
                  threshold: float = 0.42) -> MatchResult:
    """Decide whether an incoming item belongs to an existing cluster."""
    if ticker.upper() != candidate.ticker.upper():
        return MatchResult(False, 0.0, "different ticker")

    # Exact identifiers settle it immediately.
    if url and url in candidate.urls:
        return MatchResult(True, 1.0, "identical URL")
    if accession and accession in candidate.accession_numbers:
        return MatchResult(True, 1.0, "identical SEC accession number")

    if published_at and candidate.earliest_public_at:
        gap = abs(published_at - candidate.earliest_public_at)
        if gap > window:
            return MatchResult(False, 0.0, f"outside {window} window ({gap})")

    tokens = tokenise(f"{headline} {body[:600]}")
    similarity = jaccard(tokens, candidate.tokens)

    numbers = extract_numbers(f"{headline} {body[:1200]}")
    shared_numbers = numbers & candidate.numbers
    if shared_numbers:
        # A shared money figure is powerful corroboration.
        similarity = min(1.0, similarity + 0.25)

    headline_similarity = jaccard(tokenise(headline), tokenise(candidate.headline))
    if headline_similarity >= 0.65:
        similarity = max(similarity, headline_similarity)

    if similarity >= threshold:
        why = f"similarity {similarity:.2f}"
        if shared_numbers:
            why += f", shared figures {sorted(shared_numbers)}"
        return MatchResult(True, round(similarity, 3), why)
    return MatchResult(False, round(similarity, 3), f"similarity {similarity:.2f} below threshold")


def build_cluster_key(ticker: str, published_at: datetime | None, headline: str) -> str:
    """Stable-ish key for a new cluster: ticker + date + headline fingerprint."""
    day = (published_at or datetime.now(UTC)).strftime("%Y%m%d")
    tokens = sorted(tokenise(headline))[:4]
    fingerprint = "-".join(tokens) or "event"
    return f"{ticker.upper()}|{day}|{fingerprint}"[:120]
