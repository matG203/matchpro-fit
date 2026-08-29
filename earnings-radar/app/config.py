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
