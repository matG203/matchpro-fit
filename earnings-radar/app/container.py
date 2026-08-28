"""Composition root — builds providers and services from settings.

Adapters that lack credentials are simply omitted from their chain, so the
system runs (degraded, and honest about it in /health) with zero API keys.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import Settings, get_settings
from app.providers.base import (
    EarningsCalendarProvider,
    FilingProvider,
    NewswireProvider,
    NotifierProvider,
    PriceProvider,
    ProfileProvider,
)
from app.providers.finnhub import FinnhubProvider
from app.providers.fmp import FmpProvider
from app.providers.newswire import RssNewswireProvider
from app.providers.notifiers import NtfyNotifier, PushoverNotifier
from app.providers.sec_edgar import SecEdgarProvider
from app.services.analysis import EarningsAnalysisService
from app.services.discovery import EarningsDiscoveryService
from app.services.marketdata import MarketDataService
from app.services.monitor import ReleaseMonitorService
from app.services.notification import NotificationService
from app.services.pipeline import EarningsPipeline
from app.services.scheduler import SchedulerService

logger = logging.getLogger("earnings_radar.container")


@dataclass
class Container:
    settings: Settings
    calendars: list[EarningsCalendarProvider]
    profiles: list[ProfileProvider]
    prices: list[PriceProvider]
    filings: FilingProvider | None
    newswires: list[NewswireProvider]
    notifiers: list[NotifierProvider]
    discovery: EarningsDiscoveryService
    market: MarketDataService
    monitor: ReleaseMonitorService
    analysis: EarningsAnalysisService | None
    notifications: NotificationService
    pipeline: EarningsPipeline
    scheduler: SchedulerService

    def provider_status(self) -> dict[str, bool]:
        return {
            "sec_edgar": self.filings is not None,
            "finnhub": any(p.name == "finnhub" for p in self.calendars),
            "fmp": any(p.name == "fmp" for p in self.calendars),
            "newswire_rss": bool(self.newswires),
            "anthropic": self.analysis is not None,
            "notifiers": [n.name for n in self.notifiers if n.enabled()],
        }


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()

    finnhub = FinnhubProvider() if settings.finnhub_api_key else None
    fmp = FmpProvider() if settings.fmp_api_key else None

    calendars: list[EarningsCalendarProvider] = [p for p in (finnhub, fmp) if p]
    profiles: list[ProfileProvider] = [p for p in (fmp, finnhub) if p]
    prices: list[PriceProvider] = [p for p in (finnhub, fmp) if p]
    if not calendars:
        logger.warning("no earnings-calendar provider configured — discovery will be empty")

    sec = SecEdgarProvider()
    newswires: list[NewswireProvider] = [RssNewswireProvider()]

    notifiers: list[NotifierProvider] = [NtfyNotifier(), PushoverNotifier()]
    enabled_notifiers = [n for n in notifiers if n.enabled()]
    if not enabled_notifiers:
        logger.warning("no push channel configured — scores will be stored but not pushed")

    analysis = EarningsAnalysisService() if settings.anthropic_api_key else None
    if analysis is None:
        logger.warning("ANTHROPIC_API_KEY unset — provisional deterministic scoring only")

    discovery = EarningsDiscoveryService(calendars=calendars, profiles=profiles,
                                         sec=sec, settings=settings)
    market = MarketDataService(prices, conflict_threshold_pct=settings.price_conflict_pct)
    monitor = ReleaseMonitorService(filings=sec, newswires=newswires)
    notifications = NotificationService(
        notifiers,
        min_score=settings.min_notification_score,
        high_score_alert=settings.high_score_alert,
        min_confidence=settings.min_confidence_for_notification)
    pipeline = EarningsPipeline(settings=settings, monitor=monitor, filings=sec,
                                market=market, analysis=analysis,
                                notifications=notifications)
    scheduler = SchedulerService(settings=settings, discovery=discovery, pipeline=pipeline)

    return Container(settings=settings, calendars=calendars, profiles=profiles,
                     prices=prices, filings=sec, newswires=newswires, notifiers=notifiers,
                     discovery=discovery, market=market, monitor=monitor, analysis=analysis,
                     notifications=notifications, pipeline=pipeline, scheduler=scheduler)
