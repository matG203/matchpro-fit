"""NewsProvider interface plus a mock implementation.

The interface is deliberately provider-agnostic (spec §7) — Benzinga, another
licensed wire, or an internal feed can be dropped in without touching the
pipeline. The mock exists so the whole system is testable and runnable with no
credentials at all (§117).
"""
from __future__ import annotations

import abc
import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from app.catalyst.enums import SourceTier
from app.domain.timeutil import utcnow


@dataclass
class NewsArticle:
    """One inbound item. `article_id` must be stable per provider so revisions
    of the same story can be matched rather than duplicated."""

    provider: str
    article_id: str
    headline: str
    body: str = ""
    tickers: list[str] = field(default_factory=list)
    author: str = ""
    source_tier: SourceTier = SourceTier.REPUTABLE_NEWS
    source_url: str = ""
    original_source: str = ""
    provider_tags: list[str] = field(default_factory=list)
    provider_channel: str = ""
    published_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None
    received_at_utc: datetime | None = None

    def content_hash(self) -> str:
        """Hash of the meaningful content — used to spot material revisions."""
        blob = f"{self.headline.strip().lower()}|{self.body.strip().lower()}"
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


class NewsProvider(abc.ABC):
    name: str = "news"
    tier: SourceTier = SourceTier.REPUTABLE_NEWS

    @abc.abstractmethod
    def fetch_since(self, since: datetime) -> list[NewsArticle]:
        """Return items published/updated at or after `since`."""

    def enabled(self) -> bool:
        return True


class MockNewsProvider(NewsProvider):
    """Scripted feed for tests, demos and running without credentials.

    Articles are supplied up front; `fetch_since` filters by timestamp exactly
    as a real provider would, so pipeline behaviour is identical.
    """

    name = "mock_news"
    tier = SourceTier.NEWSWIRE

    def __init__(self, articles: list[NewsArticle] | None = None,
                 tier: SourceTier | None = None):
        self._articles = list(articles or [])
        if tier is not None:
            self.tier = tier

    def add(self, article: NewsArticle) -> None:
        self._articles.append(article)

    def fetch_since(self, since: datetime) -> list[NewsArticle]:
        out: list[NewsArticle] = []
        for article in self._articles:
            stamp = article.published_at_utc or article.received_at_utc or utcnow()
            if stamp >= since:
                out.append(article)
        return out
