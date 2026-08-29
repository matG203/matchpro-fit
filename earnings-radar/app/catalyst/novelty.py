"""Novelty engine (spec §13-15).

The single most common false positive in news-driven trading is yesterday's
announcement rewritten as today's headline. This module answers three separate
questions:

  1. When did this information FIRST become public?
  2. Is this item adding anything, or restating what was already known?
  3. If the topic is not new, how much UNCERTAINTY has been removed?

(3) is the information delta. "Named preferred bidder" → "contract signed" is
new information even though the contract was already public knowledge, because
the probability of it happening moved decisively toward 1.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.catalyst.dedup import jaccard, tokenise
from app.catalyst.enums import CERTAINTY_VALUE, Certainty

# Phrases that mark commentary ABOUT news rather than the news itself (§14).
_COMMENTARY_MARKERS = (
    "could transform", "what it means", "why the", "here's why", "analysis:",
    "explained", "what to know", "3 reasons", "5 reasons", "should you buy",
    "is it too late", "deep dive", "takeaways", "recap", "in case you missed",
    "following the announcement", "after announcing", "reacted to",
)

# Language certainty ladder (§17). Order matters — first match wins.
_CERTAINTY_PATTERNS: list[tuple[Certainty, tuple[str, ...]]] = [
    (Certainty.EXECUTED, (
        r"\bhas been awarded\b", r"\bwas awarded\b", r"\bhas entered into a definitive\b",
        r"\bdefinitive agreement\b", r"\bfda approved\b", r"\bapproval of\b",
        r"\bhas approved\b", r"\btransaction (?:has )?closed\b", r"\bcompleted the acquisition\b",
        r"\bcontract (?:was |has been )?executed\b", r"\breceived payment\b",
        r"\bhas received\b", r"\bhas signed\b", r"\bhas completed\b",
    )),
    (Certainty.BINDING, (
        r"\bbinding\b", r"\bfirm order\b", r"\bhas committed\b", r"\bcommitted to purchase\b",
        r"\bentered into an agreement\b", r"\bhas agreed to\b",
    )),
    (Certainty.CONDITIONAL, (
        r"\bsubject to\b", r"\bpending (?:regulatory |shareholder )?approval\b",
        r"\bconditional (?:upon|on)\b", r"\bexpected to close\b", r"\bonce approved\b",
    )),
    (Certainty.INTENT, (
        r"\bmemorandum of understanding\b", r"\bmou\b", r"\bletter of intent\b",
        r"\bnon-?binding\b", r"\bpreferred bidder\b", r"\bselected as\b",
        r"\bintends to\b", r"\bplans to\b", r"\bin discussions\b", r"\bexploring\b",
        r"\bframework agreement\b", r"\bteaming agreement\b",
    )),
    (Certainty.SPECULATIVE, (
        r"\bcould\b", r"\bmay\b", r"\bpotential(?:ly)?\b", r"\bup to\b", r"\bexpects to\b",
        r"\brumou?r\b", r"\breportedly\b", r"\bsources say\b", r"\bpeople familiar\b",
    )),
]


def detect_certainty(text: str) -> tuple[Certainty, str]:
    """Classify commitment language. Returns (certainty, matched evidence)."""
    lowered = text.lower()
    for certainty, patterns in _CERTAINTY_PATTERNS:
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                start = max(0, match.start() - 60)
                return certainty, lowered[start:match.end() + 60].strip()
    return Certainty.SPECULATIVE, "no explicit commitment language found"


def looks_like_commentary(headline: str) -> bool:
    lowered = headline.lower()
    return any(marker in lowered for marker in _COMMENTARY_MARKERS)


@dataclass
class PriorMention:
    """Something already public about this topic before the current item."""

    published_at: datetime
    headline: str
    certainty: Certainty = Certainty.SPECULATIVE
    source: str = ""


@dataclass
class NoveltyResult:
    novelty_score: float                       # 0-10
    is_restatement: bool
    earliest_known_public_at: datetime | None
    prior_mention_count: int
    certainty_before: float | None
    certainty_after: float
    information_delta: str
    notes: list[str] = field(default_factory=list)


def assess_novelty(*, headline: str, body: str = "", published_at: datetime,
                   prior_mentions: list[PriorMention] | None = None,
                   similarity_threshold: float = 0.55,
                   lookback: timedelta = timedelta(days=45)) -> NoveltyResult:
    """Score how much genuinely new information this item carries."""
    prior_mentions = [
        m for m in (prior_mentions or [])
        if m.published_at <= published_at and published_at - m.published_at <= lookback
    ]
    notes: list[str] = []
    current_certainty, evidence = detect_certainty(f"{headline}. {body[:2000]}")
    certainty_after = CERTAINTY_VALUE[current_certainty]

    if not prior_mentions:
        score = 10.0
        if looks_like_commentary(headline):
            # Commentary with no traceable prior mention is still suspicious.
            score = 5.5
            notes.append("headline reads as commentary; no prior mention found in window")
        return NoveltyResult(
            novelty_score=score, is_restatement=False,
            earliest_known_public_at=published_at, prior_mention_count=0,
            certainty_before=None, certainty_after=certainty_after,
            information_delta="no prior public mention found — treated as first disclosure",
            notes=notes)

    tokens = tokenise(f"{headline} {body[:600]}")
    similarities = [(m, jaccard(tokens, tokenise(m.headline))) for m in prior_mentions]
    similarities.sort(key=lambda pair: -pair[1])
    closest, best_similarity = similarities[0]

    earliest = min(m.published_at for m in prior_mentions)
    certainty_before = max(CERTAINTY_VALUE[m.certainty] for m in prior_mentions)
    delta_certainty = certainty_after - certainty_before

    # Same topic, and commitment has not advanced → recycled reporting (§14).
    topic_overlap = best_similarity >= similarity_threshold
    if topic_overlap and delta_certainty <= 0.05:
        notes.append(
            f"matches prior item {closest.published_at:%Y-%m-%d} "
            f"(similarity {best_similarity:.2f}) with no certainty advance")
        if looks_like_commentary(headline):
            notes.append("commentary about an existing announcement")
        return NoveltyResult(
            novelty_score=0.5, is_restatement=True,
            earliest_known_public_at=earliest, prior_mention_count=len(prior_mentions),
            certainty_before=certainty_before, certainty_after=certainty_after,
            information_delta="no new information — restates previously public material",
            notes=notes)

    if topic_overlap and delta_certainty > 0.05:
        # Known topic, but uncertainty has genuinely fallen (§15).
        score = 2.0 + min(delta_certainty, 1.0) * 7.0
        delta_text = (
            f"topic previously public ({closest.published_at:%Y-%m-%d}); certainty moved "
            f"{certainty_before:.2f} → {certainty_after:.2f} "
            f"({current_certainty.value.lower()}): {evidence[:160]}")
        notes.append("incremental information: uncertainty reduced on a known topic")
        return NoveltyResult(
            novelty_score=round(min(score, 9.0), 2), is_restatement=False,
            earliest_known_public_at=earliest, prior_mention_count=len(prior_mentions),
            certainty_before=certainty_before, certainty_after=certainty_after,
            information_delta=delta_text, notes=notes)

    # Prior mentions exist but on a different topic — this is new.
    notes.append(f"{len(prior_mentions)} prior items found, none on this topic "
                 f"(best similarity {best_similarity:.2f})")
    return NoveltyResult(
        novelty_score=9.0, is_restatement=False,
        earliest_known_public_at=published_at, prior_mention_count=len(prior_mentions),
        certainty_before=certainty_before, certainty_after=certainty_after,
        information_delta="distinct from prior coverage — treated as new information",
        notes=notes)
