"""Composition root — builds providers and services from settings.

Adapters that lack credentials are simply omitted from their chain, so the
system runs (degraded, and honest about it in /health) with zero API keys.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

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
from app.providers.polygon import PolygonProvider
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
class CatalystStack:
    """Catalyst Sentinel components. Present even when disabled so /health can
    report honestly on why nothing is running."""

    enabled: bool
    news_providers: list = field(default_factory=list)
    investigator: object | None = None
    notifier: object | None = None
    pipeline: object | None = None
    market: object | None = None
    poller: object | None = None
    outcomes: object | None = None
    rescore: object | None = None

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "news_providers": [p.name for p in self.news_providers],
            "investigator": self.investigator is not None,
            "notification_channels": (
                self.notifier.channels if self.notifier is not None else []),
            "market_data": bool(self.market is not None and self.market.available),
            "polling": self.poller is not None,
            "outcome_capture": bool(
                self.outcomes is not None and self.outcomes.available),
            "rescore": bool(self.rescore is not None and self.rescore.available),
        }


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
    catalyst: CatalystStack
    earnings_rescore: object | None = None

    def provider_status(self) -> dict[str, bool]:
        return {
            "sec_edgar": self.filings is not None,
            "finnhub": any(p.name == "finnhub" for p in self.calendars),
            "fmp": any(p.name == "fmp" for p in self.calendars),
            "polygon": any(p.name == "polygon" for p in self.prices),
            "newswire_rss": bool(self.newswires),
            "anthropic": self.analysis is not None,
            "notifiers": [n.name for n in self.notifiers if n.enabled()],
            "catalyst": self.catalyst.status(),
            "earnings_rescore": bool(
                self.earnings_rescore is not None and self.earnings_rescore.available),
        }


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()

    finnhub = FinnhubProvider() if settings.finnhub_api_key else None
    fmp = FmpProvider() if settings.fmp_api_key else None
    polygon = PolygonProvider() if settings.polygon_api_key else None

    calendars: list[EarningsCalendarProvider] = [p for p in (finnhub, fmp) if p]
    profiles: list[ProfileProvider] = [p for p in (fmp, finnhub) if p]
    # Polygon leads the price chain: real-time and extended-hours quotes matter
    # most precisely when the free feeds are stalest.
    prices: list[PriceProvider] = [p for p in (polygon, finnhub, fmp) if p]
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
    market = MarketDataService(prices, conflict_threshold_pct=settings.price_conflict_pct,
                               data_delay_seconds=settings.market_data_delay_seconds)
    monitor = ReleaseMonitorService(filings=sec, newswires=newswires)
    notifications = NotificationService(
        notifiers,
        min_score=settings.min_notification_score,
        high_score_alert=settings.high_score_alert,
        min_confidence=settings.min_confidence_for_notification)
    pipeline = EarningsPipeline(settings=settings, monitor=monitor, filings=sec,
                                market=market, analysis=analysis,
                                notifications=notifications)

    catalyst = _build_catalyst(settings, notifiers, analysis is not None,
                               polygon=polygon, fmp=fmp, sec=sec)

    # Earnings land after the close, so their reaction is invisible on a
    # delayed feed at the moment of scoring. Without this pass the veto for
    # unavailable prices would never lift and no release could reach 9+.
    from app.services.rescore import EarningsRescoreService
    earnings_rescore = EarningsRescoreService(
        settings=settings, market=market if prices else None,
        notifications=notifications)

    scheduler = SchedulerService(settings=settings, discovery=discovery, pipeline=pipeline,
                                 catalyst_poller=catalyst.poller,
                                 outcomes=catalyst.outcomes,
                                 rescore=catalyst.rescore,
                                 earnings_rescore=earnings_rescore)

    return Container(settings=settings, calendars=calendars, profiles=profiles,
                     prices=prices, filings=sec, newswires=newswires, notifiers=notifiers,
                     discovery=discovery, market=market, monitor=monitor, analysis=analysis,
                     notifications=notifications, pipeline=pipeline, scheduler=scheduler,
                     catalyst=catalyst, earnings_rescore=earnings_rescore)


def _build_catalyst(settings: Settings, notifiers: list[NotifierProvider],
                    llm_available: bool, *, polygon=None, fmp=None,
                    sec=None) -> CatalystStack:
    """Assemble Catalyst Sentinel. Runs with a mock news feed when no wire is
    configured, so the subsystem is exercisable without credentials."""
    from app.catalyst.alerts import CatalystNotifier
    from app.catalyst.enums import SourceTier
    from app.catalyst.investigator import CatalystInvestigator
    from app.catalyst.pipeline import CatalystPipeline
    from app.providers.news import MockNewsProvider
    from app.providers.wires import DEFAULT_WIRE_FEEDS, WireFeed, WireFirehoseProvider
    from app.services.catalyst_market import CatalystMarketDataService
    from app.services.catalyst_poller import CatalystPollingService
    from app.services.outcomes import OutcomeCaptureService
    from app.services.rescore import RescoreService

    if not settings.catalyst_sentinel_enabled:
        logger.info("Catalyst Sentinel disabled by configuration")
        return CatalystStack(enabled=False)

    news_providers: list = []
    if settings.benzinga_api_key:
        # A licensed wire would be constructed here; the interface is ready.
        logger.info("Benzinga key present — real news provider not yet implemented")

    # The free wires. These carry the catalysts EDGAR cannot see in time: an
    # FDA decision, Phase 2/3 topline data, a contract award or a guidance
    # change all cross the wire first and are 8-K'd afterwards.
    if settings.wire_feeds_enabled:
        feeds = list(DEFAULT_WIRE_FEEDS) if settings.wire_use_default_feeds else []
        feeds += [WireFeed(url=url, source=label, tier=SourceTier.NEWSWIRE)
                  for url, label in settings.wire_feed_list()]
        if feeds:
            news_providers.append(WireFirehoseProvider(
                feeds=feeds,
                max_body_fetches=settings.wire_max_body_fetches,
                body_chars=settings.wire_body_chars,
                user_agent=settings.wire_user_agent))
            logger.info("newswire firehoses enabled: %s",
                        ", ".join(f.source for f in feeds))
        else:
            logger.warning("WIRE_FEEDS_ENABLED is on but no feeds are configured")

    if not news_providers:
        news_providers.append(MockNewsProvider())
        logger.warning(
            "no news feed configured — Catalyst Sentinel running on the mock "
            "provider; SEC filings remain the live primary source")

    investigator = CatalystInvestigator() if llm_available else None
    if investigator is None:
        logger.warning("ANTHROPIC_API_KEY unset — catalyst adversarial review unavailable")

    # Free float is the one structure input Polygon does not publish, so it is
    # sourced from FMP when that key exists. Neither is required: absent both,
    # amplification caps itself and records what was missing.
    market_data = CatalystMarketDataService(
        bars=polygon, structure=polygon, settings=settings,
        float_providers=[p for p in (fmp,) if p])
    if not market_data.available:
        logger.warning(
            "POLYGON_API_KEY unset — catalyst market data unavailable; move "
            "amplification and reaction room will run without price inputs")
    elif settings.market_data_delay_seconds > 0:
        logger.info(
            "price feed is %.0f minutes delayed — catalysts are scored "
            "provisionally on arrival and re-scored once the move becomes "
            "visible; set MARKET_DATA_DELAY_SECONDS=0 on a real-time plan",
            settings.market_data_delay_seconds / 60)

    notifier = CatalystNotifier(notifiers)
    pipeline = CatalystPipeline(
        settings=settings, investigator=investigator, notifier=notifier,
        market_context_fn=market_data.as_context_fn() if market_data.available else None)

    poller = CatalystPollingService(pipeline=pipeline, sec=sec,
                                    news_providers=news_providers, settings=settings)
    outcomes = OutcomeCaptureService(bars=polygon, settings=settings)
    rescore = RescoreService(
        settings=settings, notifier=notifier,
        market_context_fn=market_data.as_context_fn() if market_data.available else None)

    return CatalystStack(enabled=True, news_providers=news_providers,
                         investigator=investigator, notifier=notifier, pipeline=pipeline,
                         market=market_data, poller=poller, outcomes=outcomes,
                         rescore=rescore)
