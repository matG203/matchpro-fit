"""Application settings. Everything env-driven; see .env.example."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "sqlite:///earnings_radar.db"

    # LLM
    anthropic_api_key: str = ""
    analysis_model: str = "claude-opus-5"
    analysis_max_retries: int = 2
    analysis_timeout_seconds: float = 120.0

    # Providers
    finnhub_api_key: str = ""
    fmp_api_key: str = ""
    fmp_daily_quota: int = 240  # free tier is 250/day; keep headroom
    polygon_api_key: str = ""
    # Polygon rebranded to Massive in July 2026; api.polygon.io still serves the
    # same API with the same keys. Configurable so a future endpoint move is a
    # settings change rather than a code change.
    polygon_base_url: str = "https://api.polygon.io"
    sec_user_agent: str = "Earnings Radar (contact@example.com)"

    # Notifications
    ntfy_topic: str = ""
    ntfy_server: str = "https://ntfy.sh"
    pushover_user_key: str = ""
    pushover_app_token: str = ""
    min_notification_score: float = 0.0
    high_score_alert: float = 9.0
    min_confidence_for_notification: float = 75.0
    notify_provisional_on_llm_failure: bool = True

    # Timezones / scheduling
    local_tz: str = "Europe/London"
    market_tz: str = "America/New_York"
    discovery_times: str = "05:00,09:00,13:00,18:00,20:00"

    # Adaptive monitoring (minutes unless stated)
    monitor_wake_before_minutes: int = 60
    monitor_far_interval_seconds: int = 300      # 60-15 min before
    monitor_near_interval_seconds: int = 60      # 15-0 min before
    monitor_burst_interval_seconds: int = 20     # release -> +30 min (>=15s SEC etiquette)
    monitor_burst_window_minutes: int = 30
    monitor_cooldown_interval_seconds: int = 60  # +30 -> +120 min
    monitor_late_interval_seconds: int = 300     # beyond +120 min
    delayed_grace_minutes: int = 240             # then DELAYED_OR_UNVERIFIED

    # Market data validation
    price_conflict_pct: float = 5.0  # % points of move disagreement -> unresolved

    # Scoring
    scoring_model_version: str = "1.0.0"

    # ── Catalyst Sentinel (spec §111) ────────────────────────────────────────
    catalyst_sentinel_enabled: bool = True
    catalyst_push_score: float = 9.0
    catalyst_extreme_score: float = 9.5
    catalyst_store_score: float = 7.0
    catalyst_min_confidence: float = 7.0          # 0-10, distinct from earnings 0-100
    catalyst_fast_model: str = "claude-haiku-4-5"
    catalyst_deep_analysis_threshold: float = 5.0

    min_source_quality: float = 0.5
    min_entity_confidence: float = 0.7
    catalyst_min_market_cap: float = 50_000_000.0
    catalyst_min_share_price: float = 1.0
    catalyst_min_avg_dollar_volume: float = 500_000.0
    allow_otc: bool = False

    news_max_age_seconds: float = 3600.0
    price_max_age_seconds: float = 120.0
    reaction_room_min_alert: float = 3.0
    max_negative_offset_for_alert: float = 6.0

    catalyst_poll_seconds: int = 30
    benzinga_api_key: str = ""

    # ── Free newswire firehoses ──────────────────────────────────────────────
    #
    # The public RSS feeds of GlobeNewswire, Business Wire and PR Newswire.
    # No key and no cost; the trade against a licensed feed is detection
    # latency, bounded by CATALYST_POLL_SECONDS rather than being unknown.
    wire_feeds_enabled: bool = True
    # Extra feeds, comma-separated. Either "url" or "url|Source Name". These
    # are tiered NEWSWIRE, not PRIMARY: we can vouch for the three built-in
    # wires' content, not for an arbitrary feed's.
    wire_feed_urls: str = ""
    # Only the built-in wires, without the extras. Useful for reverting.
    wire_use_default_feeds: bool = True
    # Release pages fetched per sweep to recover the body (and with it the
    # "(NASDAQ: ABC)" tag the RSS summary usually omits). A ceiling, not a
    # target: a normal sweep fetches one or two.
    wire_max_body_fetches: int = 25
    wire_body_chars: int = 40_000
    # Some wires sit behind bot filtering that rejects unfamiliar agents
    # inconsistently — PR Newswire has served a feed and then 404'd the same
    # URL minutes later. Settable so a blocked deployment can be fixed without
    # a code change. Empty uses the default in app.providers.wires.
    wire_user_agent: str = ""

    def wire_feed_list(self) -> list[tuple[str, str]]:
        """Parse WIRE_FEED_URLS into (url, source name) pairs."""
        out: list[tuple[str, str]] = []
        for raw in (self.wire_feed_urls or "").split(","):
            raw = raw.strip()
            if not raw:
                continue
            url, _, label = raw.partition("|")
            url = url.strip()
            if not url:
                continue
            out.append((url, label.strip() or url))
        return out

    # Catalyst market data
    #
    # How far behind live the price feed is. Polygon's Stocks Starter plan is
    # 15 minutes delayed; Advanced is real-time. Setting this to 0 is the
    # entire Starter → Advanced upgrade — no code changes. It is not cosmetic:
    # the system uses it to tell "the stock has not moved" apart from "we
    # cannot see the move yet", which are opposite conclusions.
    market_data_delay_seconds: float = 900.0
    benchmark_ticker: str = "SPY"
    catalyst_runup_lookback_days: int = 10
    catalyst_atr_days: int = 14
    catalyst_max_universe: int = 400
    # Filings newer than this are still worth pricing and scoring.
    catalyst_filing_lookback_minutes: int = 90

    # Outcome capture
    outcome_capture_enabled: bool = True
    outcome_capture_interval_seconds: int = 300
    outcome_capture_window_days: int = 5

    # Re-scoring. On a delayed feed a catalyst is first scored before its move
    # is visible; this pass revisits it once the data arrives. Harmless on a
    # real-time feed, where there is normally nothing to revisit.
    rescore_enabled: bool = True
    rescore_interval_seconds: int = 120
    rescore_window_hours: int = 6

    def discovery_time_list(self) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        for part in self.discovery_times.split(","):
            part = part.strip()
            if not part:
                continue
            hh, mm = part.split(":")
            out.append((int(hh), int(mm)))
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
