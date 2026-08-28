"""ReleaseMonitorService — multi-source detection (spec §RELEASE DETECTION).

NEVER relies on one source. Polls small machine-readable indexes (SEC
submissions JSON, newswire RSS) rather than scraping IR pages, because a
stale IR homepage is exactly how a release gets missed.

Detection returns a candidate; verification (verification.py) decides whether
it is really a current-quarter results document.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.enums import ReleaseSourceKind
from app.domain.timeutil import utcnow
from app.providers.base import (
    FilingProvider,
    NewswireProvider,
    ProviderError,
    ProviderUnavailable,
)
from app.providers.sec_edgar import is_earnings_filing

logger = logging.getLogger("earnings_radar.monitor")

# Newswire headline keywords that suggest an actual results release
_RESULT_TITLE_HINTS = (
    "results", "reports", "announces", "earnings", "quarter", "financial",
)
# Headlines that are definitely NOT the release itself
_TITLE_EXCLUSIONS = (
    "to report", "will report", "to announce", "will announce", "to host",
    "conference call", "webcast", "date announcement", "schedules", "invites",
    "preview", "estimates",
)


@dataclass
class DetectionCandidate:
    source: ReleaseSourceKind
    url: str
    title: str = ""
    published_at_utc: datetime | None = None
    document_type: str = ""
    provider: str = ""


@dataclass
class DetectionAttempt:
    """What every check looked at — feeds the audit log verbatim."""

    checks: list[tuple[str, str]] = field(default_factory=list)   # (source, outcome)
    candidates: list[DetectionCandidate] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.candidates)


def looks_like_results_headline(title: str) -> bool:
    lowered = title.lower()
    if any(bad in lowered for bad in _TITLE_EXCLUSIONS):
        return False
    return any(hint in lowered for hint in _RESULT_TITLE_HINTS)


class ReleaseMonitorService:
    def __init__(self, filings: FilingProvider | None,
                 newswires: list[NewswireProvider],
                 window_start: datetime | None = None):
        self._filings = filings
        self._newswires = newswires
        self._window_start = window_start

    def check(self, *, ticker: str, company_name: str, cik: str | None,
              since: datetime) -> DetectionAttempt:
        """One detection sweep across every configured source.

        `since` bounds candidates to this reporting window so a previous
        quarter's 8-K can never be mistaken for today's release.
        """
        attempt = DetectionAttempt()

        # 1. SEC EDGAR — fastest authoritative index, best timestamps
        if self._filings is not None:
            try:
                hits = self._filings.recent_filings(ticker, cik)
                fresh = [h for h in hits
                         if h.accepted_at_utc >= since and is_earnings_filing(h)]
                attempt.checks.append(
                    ("SEC", f"{len(hits)} recent filings, {len(fresh)} earnings-relevant"))
                for hit in fresh:
                    attempt.candidates.append(DetectionCandidate(
                        source=ReleaseSourceKind.SEC, url=hit.url,
                        title=hit.description or hit.form_type,
                        published_at_utc=hit.accepted_at_utc,
                        document_type=hit.form_type, provider="sec_edgar"))
            except ProviderUnavailable as exc:
                attempt.checks.append(("SEC", f"unavailable: {exc}"))
            except ProviderError as exc:
                attempt.checks.append(("SEC", f"error: {exc}"))

        # 2. Newswires — often beat EDGAR by seconds, and cover non-filers
        for provider in self._newswires:
            try:
                items = provider.recent_items(ticker, company_name)
                fresh = [i for i in items
                         if (i.published_at_utc is None or i.published_at_utc >= since)
                         and looks_like_results_headline(i.title)]
                attempt.checks.append(
                    (provider.name, f"{len(items)} items, {len(fresh)} results-like"))
                for item in fresh:
                    attempt.candidates.append(DetectionCandidate(
                        source=item.source, url=item.url, title=item.title,
                        published_at_utc=item.published_at_utc,
                        document_type="PRESS_RELEASE", provider=provider.name))
            except ProviderUnavailable as exc:
                attempt.checks.append((provider.name, f"unavailable: {exc}"))
            except ProviderError as exc:
                attempt.checks.append((provider.name, f"error: {exc}"))

        return attempt

    @staticmethod
    def earliest_publication(candidates: list[DetectionCandidate]) -> datetime | None:
        """Earliest confirmed public timestamp across all sources
        (spec §EXACT PUBLICATION TIME)."""
        stamps = [c.published_at_utc for c in candidates if c.published_at_utc]
        return min(stamps) if stamps else None

    @staticmethod
    def detection_latency_ms(published_at: datetime | None,
                             detected_at: datetime | None = None) -> int | None:
        if published_at is None:
            return None
        detected_at = detected_at or utcnow()
        return int((detected_at - published_at).total_seconds() * 1000)
