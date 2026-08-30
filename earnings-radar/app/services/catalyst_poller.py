"""Continuous catalyst detection.

Two independent inbound streams, both feeding the same pipeline:

  **SEC filings** — the live primary source. Polling the submissions JSON for
  every watched company would cost hundreds of requests a sweep and breach
  SEC's access guidance within seconds. Instead this uses EDGAR's latest-filings
  feed: one request tells us who filed in the last few minutes, and only those
  companies get a second call for item codes and the document. A sweep over a
  400-name universe is typically one request, occasionally a handful.

  **News providers** — whatever wire is configured (the mock, until a licensed
  feed exists). Each provider is asked only for items newer than the last one
  it returned, so a slow provider cannot make us re-process its backlog.

Everything is idempotent. The pipeline deduplicates on `(provider, article_id)`
and again on the event cluster, so re-seeing a filing is cheap and harmless —
which matters, because the safe failure mode for a poller is to repeat work,
never to skip it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.catalyst.enums import SourceTier
from app.catalyst.pipeline import CatalystPipeline
from app.catalyst.sec_routing import MONITORED_FORMS, route_filing
from app.config import Settings
from app.db.catalyst_models import NewsItem
from app.db.models import Company
from app.domain.timeutil import utcnow
from app.providers.base import ProviderError, ProviderUnavailable
from app.providers.news import NewsArticle, NewsProvider
from app.providers.sec_edgar import SecEdgarProvider
from app.services.audit import AuditService

logger = logging.getLogger("earnings_radar.catalyst.poller")

# Skip the document fetch for forms whose routing decision needs no text and
# whose volume is high (Form 4s alone are thousands a day).
_METADATA_ONLY_FORMS = {"3", "4", "5", "SC 13G", "SC 13G/A"}


@dataclass
class PollResult:
    filings_seen: int = 0
    filings_processed: int = 0
    articles_seen: int = 0
    articles_processed: int = 0
    scored: int = 0
    alerted: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"filings {self.filings_processed}/{self.filings_seen}, "
                f"articles {self.articles_processed}/{self.articles_seen}, "
                f"scored {self.scored}, alerted {self.alerted}")


class CatalystPollingService:
    def __init__(self, *, pipeline: CatalystPipeline, sec: SecEdgarProvider | None,
                 news_providers: list[NewsProvider], settings: Settings):
        self._pipeline = pipeline
        self._sec = sec
        self._news = list(news_providers or [])
        self._settings = settings
        # Per-stream high-water marks. Held in memory deliberately: on restart
        # we re-read the recent window and the pipeline's dedup absorbs it,
        # which is safer than persisting a cursor that could skip a filing.
        self._seen_accessions: set[str] = set()
        self._news_cursor: dict[str, datetime] = {}
        self.last_poll_at: datetime | None = None
        self.last_result: PollResult | None = None

    # ── universe ──────────────────────────────────────────────────────────────

    def universe(self, session: Session) -> dict[str, Company]:
        """CIK → company, for everything we know about.

        Companies arrive from earnings discovery, so the universe grows as the
        calendar is walked. A filing from a company we have never seen is
        ignored rather than guessed at — entity resolution would have no name
        to match against anyway.
        """
        rows = (session.query(Company)
                .filter(Company.cik.isnot(None))
                .limit(self._settings.catalyst_max_universe).all())
        return {str(c.cik).zfill(10): c for c in rows if c.cik}

    # ── main sweep ────────────────────────────────────────────────────────────

    def poll(self, session: Session, now: datetime | None = None) -> PollResult:
        now = now or utcnow()
        result = PollResult()
        self.last_poll_at = now

        self._poll_filings(session, now, result)
        self._poll_news(session, now, result)

        self.last_result = result
        if result.filings_processed or result.articles_processed:
            AuditService(session).log("catalyst", "poll", result.summary(), level="INFO")
        return result

    # ── SEC stream ────────────────────────────────────────────────────────────

    def _poll_filings(self, session: Session, now: datetime, result: PollResult) -> None:
        if self._sec is None:
            return
        try:
            entries = self._sec.latest_filings(count=100)
        except (ProviderError, ProviderUnavailable) as exc:
            result.errors.append(f"sec feed: {exc}")
            logger.warning("EDGAR feed unavailable: %s", exc)
            return

        universe = self.universe(session)
        cutoff = now - timedelta(minutes=self._settings.catalyst_filing_lookback_minutes)

        for entry in entries:
            result.filings_seen += 1
            if entry.form_type not in MONITORED_FORMS:
                continue
            company = universe.get(entry.cik)
            if company is None:
                continue
            if entry.accepted_at_utc is not None and entry.accepted_at_utc < cutoff:
                continue
            try:
                if self._process_filer(session, company, entry.form_type, now, result):
                    result.filings_processed += 1
            except Exception as exc:
                logger.exception("filing processing failed for %s", company.ticker)
                result.errors.append(f"{company.ticker}: {exc}")

    def _process_filer(self, session: Session, company: Company, form_type: str,
                       now: datetime, result: PollResult) -> bool:
        """Second stage: pull this filer's recent filings for item codes."""
        try:
            hits = self._sec.recent_filings(company.ticker, company.cik,
                                            forms_filter=MONITORED_FORMS)
        except (ProviderError, ProviderUnavailable) as exc:
            result.errors.append(f"{company.ticker} submissions: {exc}")
            return False

        cutoff = now - timedelta(minutes=self._settings.catalyst_filing_lookback_minutes)
        processed = False
        for hit in hits:
            if hit.accepted_at_utc < cutoff:
                continue
            accession = hit.url
            if accession in self._seen_accessions:
                continue

            route = route_filing(hit.form_type, hit.items, hit.description)
            if not route.monitored or route.route_to_earnings:
                # Item 2.02 and the periodic reports belong to Earnings
                # Sentinel; double-counting them here would produce two
                # competing scores for one event (§108).
                self._seen_accessions.add(accession)
                continue

            article = self._filing_to_article(company, hit, route)
            self._seen_accessions.add(accession)
            outcome = self._pipeline.process(session, article, now=now)
            processed = True
            if outcome.score is not None:
                result.scored += 1
            if outcome.alerted:
                result.alerted += 1
        return processed

    def _filing_to_article(self, company: Company, hit, route) -> NewsArticle:
        body = ""
        if hit.form_type not in _METADATA_ONLY_FORMS:
            try:
                body = self._sec.fetch_document_text(hit.url)[:200_000]
            except (ProviderError, ProviderUnavailable) as exc:
                logger.info("could not fetch %s for %s: %s", hit.url, company.ticker, exc)

        items = ", ".join(hit.items) if hit.items else route.reason
        headline = (hit.description or f"{company.name or company.ticker} filed "
                                       f"{hit.form_type} ({items})")
        return NewsArticle(
            provider="sec_edgar",
            article_id=hit.url,
            headline=headline[:400],
            body=body,
            tickers=[company.ticker],
            source_tier=SourceTier.PRIMARY,
            source_url=hit.url,
            original_source="SEC EDGAR",
            provider_tags=list(hit.items),
            provider_channel=hit.form_type,
            published_at_utc=hit.accepted_at_utc,
            received_at_utc=utcnow())

    # ── news stream ───────────────────────────────────────────────────────────

    def _poll_news(self, session: Session, now: datetime, result: PollResult) -> None:
        for provider in self._news:
            if not provider.enabled():
                continue
            since = self._news_cursor.get(
                provider.name, now - timedelta(seconds=self._settings.news_max_age_seconds))
            try:
                articles = provider.fetch_since(since)
            except (ProviderError, ProviderUnavailable) as exc:
                result.errors.append(f"{provider.name}: {exc}")
                continue

            newest = since
            for article in articles:
                result.articles_seen += 1
                stamp = article.published_at_utc or article.received_at_utc or now
                newest = max(newest, stamp)
                if self._already_ingested(session, article):
                    continue
                try:
                    outcome = self._pipeline.process(session, article, now=now)
                except Exception as exc:
                    logger.exception("news processing failed (%s)", article.article_id)
                    result.errors.append(f"{provider.name}/{article.article_id}: {exc}")
                    continue
                result.articles_processed += 1
                if outcome.score is not None:
                    result.scored += 1
                if outcome.alerted:
                    result.alerted += 1
            self._news_cursor[provider.name] = newest

    @staticmethod
    def _already_ingested(session: Session, article: NewsArticle) -> bool:
        """Skip only unchanged repeats — a revised story is new information."""
        row = (session.query(NewsItem)
               .filter_by(provider=article.provider, article_id=article.article_id)
               .first())
        return row is not None and row.content_hash == article.content_hash()
