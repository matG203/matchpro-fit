"""SQLAlchemy models — schema documented in ARCHITECTURE.md §4."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.enums import EventState
from app.domain.timeutil import utcnow


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    exchange: Mapped[str] = mapped_column(String(32), default="")
    cik: Mapped[str | None] = mapped_column(String(10), index=True)
    market_cap: Mapped[float | None] = mapped_column(Float)
    avg_volume: Mapped[float | None] = mapped_column(Float)
    liquidity_tier: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    sector: Mapped[str] = mapped_column(String(64), default="")
    industry: Mapped[str] = mapped_column(String(128), default="")
    ir_url: Mapped[str] = mapped_column(String(512), default="")
    kpi_profile: Mapped[dict] = mapped_column(JSON, default=dict)

    events: Mapped[list[EarningsEvent]] = relationship(back_populates="company")


class EarningsEvent(TimestampMixin, Base):
    __tablename__ = "earnings_events"
    __table_args__ = (UniqueConstraint("company_id", "fiscal_year", "fiscal_quarter"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer)
    fiscal_quarter: Mapped[int] = mapped_column(Integer)

    expected_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    expected_release_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    call_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    schedule_confidence: Mapped[str] = mapped_column(String(8), default="LOW")
    confidence_reason: Mapped[str] = mapped_column(Text, default="")

    eps_estimate: Mapped[float | None] = mapped_column(Float)
    revenue_estimate: Mapped[float | None] = mapped_column(Float)

    state: Mapped[str] = mapped_column(String(32), default=EventState.DISCOVERED, index=True)
    state_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    monitor_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sources: Mapped[list] = mapped_column(JSON, default=list)

    company: Mapped[Company] = relationship(back_populates="events")
    release: Mapped[Release | None] = relationship(back_populates="event", uselist=False)


class Release(TimestampMixin, Base):
    __tablename__ = "releases"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("earnings_events.id"), index=True)

    published_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detection_latency_ms: Mapped[int | None] = mapped_column(Integer)

    document_type: Mapped[str] = mapped_column(String(32), default="")
    primary_url: Mapped[str] = mapped_column(String(1024), default="")
    document_text: Mapped[str] = mapped_column(Text, default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_notes: Mapped[str] = mapped_column(Text, default="")

    event: Mapped[EarningsEvent] = relationship(back_populates="release")
    source_rows: Mapped[list[ReleaseSource]] = relationship(back_populates="release")


class ReleaseSource(Base):
    __tablename__ = "release_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("releases.id"), index=True)
    source: Mapped[str] = mapped_column(String(32))
    url: Mapped[str] = mapped_column(String(1024))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at_claimed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    release: Mapped[Release] = relationship(back_populates="source_rows")


class Estimate(Base):
    __tablename__ = "estimates"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("earnings_events.id"), index=True)
    metric: Mapped[str] = mapped_column(String(48))          # eps, revenue, next_q_revenue...
    period: Mapped[str] = mapped_column(String(16), default="current")
    value: Mapped[float] = mapped_column(Float)
    provider: Mapped[str] = mapped_column(String(32))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)


class ExtractedFinancial(Base):
    __tablename__ = "extracted_financials"

    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("releases.id"), index=True)
    metric: Mapped[str] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16), default="")
    period: Mapped[str] = mapped_column(String(16), default="current")
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    method: Mapped[str] = mapped_column(String(16), default="regex")


class KpiValue(Base):
    __tablename__ = "kpi_values"

    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("releases.id"), index=True)
    kpi_name: Mapped[str] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16), default="")
    yoy_growth: Mapped[float | None] = mapped_column(Float)
    qoq_growth: Mapped[float | None] = mapped_column(Float)
    prior_values: Mapped[list] = mapped_column(JSON, default=list)
    growth_direction: Mapped[str] = mapped_column(String(16), default="UNKNOWN")


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("earnings_events.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # prev_close/pre_release/post_1m/...
    price: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    provider: Mapped[str] = mapped_column(String(32), default="")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketContext(Base):
    """Derived per-event market context & reaction summary."""

    __tablename__ = "market_contexts"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("earnings_events.id"), unique=True)
    prev_close: Mapped[float | None] = mapped_column(Float)
    pre_release_price: Mapped[float | None] = mapped_column(Float)
    run_5d_pct: Mapped[float | None] = mapped_column(Float)
    run_1m_pct: Mapped[float | None] = mapped_column(Float)
    run_3m_pct: Mapped[float | None] = mapped_column(Float)
    implied_move_pct: Mapped[float | None] = mapped_column(Float)
    initial_reaction_pct: Mapped[float | None] = mapped_column(Float)
    current_reaction_pct: Mapped[float | None] = mapped_column(Float)
    reaction_vs_prev_close_pct: Mapped[float | None] = mapped_column(Float)
    reaction_pattern: Mapped[str] = mapped_column(String(32), default="NONE")
    unresolved: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class Analysis(TimestampMixin, Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("releases.id"), index=True)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16), default="1.0")
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    earnings_quality: Mapped[float | None] = mapped_column(Float)
    guidance_score: Mapped[float | None] = mapped_column(Float)
    business_kpi_score: Mapped[float | None] = mapped_column(Float)
    true_surprise_score: Mapped[float | None] = mapped_column(Float)
    guidance_status: Mapped[str] = mapped_column(String(16), default="NONE")
    growth_direction: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    confidence: Mapped[float | None] = mapped_column(Float)
    verdict: Mapped[str] = mapped_column(String(64), default="")
    bull_case: Mapped[str] = mapped_column(Text, default="")
    bear_case: Mapped[str] = mapped_column(Text, default="")
    reasoning_summary: Mapped[str] = mapped_column(Text, default="")
    hidden_negatives: Mapped[list] = mapped_column(JSON, default=list)
    pre_announced: Mapped[list] = mapped_column(JSON, default=list)
    one_off_items: Mapped[list] = mapped_column(JSON, default=list)


class Score(TimestampMixin, Base):
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("release_id", "scoring_model_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("releases.id"), index=True)
    scoring_model_version: Mapped[str] = mapped_column(String(16))
    earnings_quality: Mapped[float] = mapped_column(Float)
    market_confirmation: Mapped[float] = mapped_column(Float)
    entry_score: Mapped[float] = mapped_column(Float)
    final_trade_score: Mapped[float] = mapped_column(Float)
    component_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    vetoes_applied: Mapped[list] = mapped_column(JSON, default=list)
    analysis_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    needs_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    score_review: Mapped[bool] = mapped_column(Boolean, default=False)
    provisional: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("releases.id"), index=True)
    dedup_key: Mapped[str] = mapped_column(String(128), unique=True)
    channel: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(256), default="")
    body: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, default="")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("earnings_events.id"), index=True)
    release_id: Mapped[int | None] = mapped_column(ForeignKey("releases.id"), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(8), default="INFO")


class ProviderHealth(Base):
    __tablename__ = "provider_health"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(48), unique=True)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str] = mapped_column(Text, default="")
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Outcome(Base):
    """Post-scoring price outcomes for future empirical recalibration."""

    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("releases.id"), unique=True)
    price_at_score: Mapped[float | None] = mapped_column(Float)
    price_5m: Mapped[float | None] = mapped_column(Float)
    price_30m: Mapped[float | None] = mapped_column(Float)
    next_open: Mapped[float | None] = mapped_column(Float)
    next_close: Mapped[float | None] = mapped_column(Float)
    ret_1d: Mapped[float | None] = mapped_column(Float)
    ret_5d: Mapped[float | None] = mapped_column(Float)
    ret_30d: Mapped[float | None] = mapped_column(Float)
    captured_through: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
