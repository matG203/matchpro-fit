"""Catalyst Sentinel tables (spec §82).

Extends the shared Base from app.db.models — Company, MarketSnapshot,
Notification, AuditLog and ProviderHealth are reused rather than duplicated.

Immutability rule (§83): snapshots record what was known AT DECISION TIME and
are never overwritten with later data. That is what makes backtesting honest.
"""
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base, TimestampMixin
from app.domain.timeutil import utcnow


class NewsItem(TimestampMixin, Base):
    """Raw inbound item from any source. Revisions stored separately (§7)."""

    __tablename__ = "news_items"
    __table_args__ = (UniqueConstraint("provider", "article_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(48), index=True)
    article_id: Mapped[str] = mapped_column(String(128))
    headline: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    tickers: Mapped[list] = mapped_column(JSON, default=list)
    author: Mapped[str] = mapped_column(String(128), default="")
    source_tier: Mapped[str] = mapped_column(String(24), default="REPUTABLE_NEWS")
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    original_source: Mapped[str] = mapped_column(String(256), default="")
    provider_tags: Mapped[list] = mapped_column(JSON, default=list)
    provider_channel: Mapped[str] = mapped_column(String(64), default="")

    published_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    updated_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    content_hash: Mapped[str] = mapped_column(String(64), index=True, default="")
    cluster_id: Mapped[int | None] = mapped_column(ForeignKey("event_clusters.id"), index=True)

    revisions: Mapped[list[NewsRevision]] = relationship(back_populates="item")


class NewsRevision(Base):
    """A materially updated version of a story — an update can itself be news."""

    __tablename__ = "news_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_item_id: Mapped[int] = mapped_column(ForeignKey("news_items.id"), index=True)
    headline: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    revised_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    materially_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    change_notes: Mapped[str] = mapped_column(Text, default="")

    item: Mapped[NewsItem] = relationship(back_populates="revisions")


class EventCluster(TimestampMixin, Base):
    """One underlying real-world event, however many sources report it (§12)."""

    __tablename__ = "event_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True, default="")
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    entity_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    entity_evidence: Mapped[str] = mapped_column(Text, default="")

    earliest_public_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    best_source_tier: Mapped[str] = mapped_column(String(24), default="SECONDARY")
    member_count: Mapped[int] = mapped_column(Integer, default=1)

    catalyst_event: Mapped[CatalystEvent | None] = relationship(
        back_populates="cluster", uselist=False)


class CatalystEvent(TimestampMixin, Base):
    """The analysed catalyst. One per cluster."""

    __tablename__ = "catalyst_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("event_clusters.id"), unique=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True, default="")

    event_type: Mapped[str] = mapped_column(String(48), default="unknown", index=True)
    event_category: Mapped[str] = mapped_column(String(32), default="UNKNOWN", index=True)
    certainty: Mapped[str] = mapped_column(String(16), default="SPECULATIVE")
    half_life: Mapped[str] = mapped_column(String(16), default="UNKNOWN")

    state: Mapped[str] = mapped_column(String(32), default="INGESTED", index=True)
    state_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reject_reason: Mapped[str] = mapped_column(String(48), default="")

    headline: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    primary_url: Mapped[str] = mapped_column(String(1024), default="")
    document_text: Mapped[str] = mapped_column(Text, default="")

    # Link back to Earnings Sentinel rather than double-counting (§1, §108)
    earnings_event_id: Mapped[int | None] = mapped_column(ForeignKey("earnings_events.id"))

    cluster: Mapped[EventCluster] = relationship(back_populates="catalyst_event")
    scores: Mapped[list[CatalystScore]] = relationship(back_populates="event")


class CatalystSource(Base):
    """Every source that carried this event, with its own timestamp."""

    __tablename__ = "catalyst_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), index=True)
    news_item_id: Mapped[int | None] = mapped_column(ForeignKey("news_items.id"))
    tier: Mapped[str] = mapped_column(String(24), default="SECONDARY")
    provider: Mapped[str] = mapped_column(String(48), default="")
    url: Mapped[str] = mapped_column(String(1024), default="")
    published_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_primary_document: Mapped[bool] = mapped_column(Boolean, default=False)


class EventFact(Base):
    """Structured facts with provenance — never Claude's unsupported assertions."""

    __tablename__ = "event_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    value_text: Mapped[str] = mapped_column(Text, default="")
    value_number: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(24), default="")
    quote: Mapped[str] = mapped_column(Text, default="")
    extracted_by: Mapped[str] = mapped_column(String(16), default="regex")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)


class NoveltyAnalysis(Base):
    """§13-15 — what is actually new, and how much uncertainty was removed."""

    __tablename__ = "novelty_analysis"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), unique=True)
    novelty_score: Mapped[float] = mapped_column(Float, default=0.0)
    earliest_known_public_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prior_mentions: Mapped[int] = mapped_column(Integer, default=0)
    prior_mention_refs: Mapped[list] = mapped_column(JSON, default=list)
    is_restatement: Mapped[bool] = mapped_column(Boolean, default=False)
    information_delta: Mapped[str] = mapped_column(Text, default="")
    certainty_before: Mapped[float | None] = mapped_column(Float)
    certainty_after: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str] = mapped_column(Text, default="")


class MaterialityAnalysis(Base):
    """§18-21 — economic significance relative to THIS company."""

    __tablename__ = "materiality_analysis"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), unique=True)

    headline_value: Mapped[float | None] = mapped_column(Float)
    guaranteed_value: Mapped[float | None] = mapped_column(Float)
    expected_value: Mapped[float | None] = mapped_column(Float)
    annualised_value: Mapped[float | None] = mapped_column(Float)

    value_to_market_cap: Mapped[float | None] = mapped_column(Float)
    value_to_revenue: Mapped[float | None] = mapped_column(Float)
    annualised_to_revenue: Mapped[float | None] = mapped_column(Float)
    value_to_ebitda: Mapped[float | None] = mapped_column(Float)
    estimated_eps_impact: Mapped[float | None] = mapped_column(Float)

    materiality_score: Mapped[float] = mapped_column(Float, default=0.0)
    basis: Mapped[str] = mapped_column(String(32), default="")
    missing_inputs: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")


class NegativeOffsetRow(Base):
    __tablename__ = "negative_offsets"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_quote: Mapped[str] = mapped_column(Text, default="")
    detected_by: Mapped[str] = mapped_column(String(16), default="engine")


class MarketStructureSnapshot(Base):
    """§42-47 — how capable this stock is of moving violently, as at decision time."""

    __tablename__ = "market_structure_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), unique=True)
    captured_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    market_cap: Mapped[float | None] = mapped_column(Float)
    free_float_shares: Mapped[float | None] = mapped_column(Float)
    shares_outstanding: Mapped[float | None] = mapped_column(Float)
    avg_dollar_volume: Mapped[float | None] = mapped_column(Float)
    relative_volume: Mapped[float | None] = mapped_column(Float)
    spread_pct: Mapped[float | None] = mapped_column(Float)

    short_percent_float: Mapped[float | None] = mapped_column(Float)
    days_to_cover: Mapped[float | None] = mapped_column(Float)
    short_interest_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    short_interest_stale_days: Mapped[float | None] = mapped_column(Float)

    realised_volatility: Mapped[float | None] = mapped_column(Float)
    atr_pct: Mapped[float | None] = mapped_column(Float)
    implied_move_pct: Mapped[float | None] = mapped_column(Float)

    session: Mapped[str] = mapped_column(String(16), default="unknown")
    halt_state: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    missing_inputs: Mapped[list] = mapped_column(JSON, default=list)


class CatalystPriceSnapshot(Base):
    """Pre-event run-up and post-event reaction points (§37-38)."""

    __tablename__ = "catalyst_price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), index=True)
    label: Mapped[str] = mapped_column(String(24))          # t-1d, t-1h, t0, t+5m ...
    offset_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    benchmark_price: Mapped[float | None] = mapped_column(Float)
    sector_price: Mapped[float | None] = mapped_column(Float)
    provider: Mapped[str] = mapped_column(String(32), default="")
    captured_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReactionAnalysis(Base):
    """§39 — how much of the plausible move may still remain."""

    __tablename__ = "reaction_analysis"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), unique=True)

    pre_event_runup_pct: Mapped[float | None] = mapped_column(Float)
    abnormal_pre_event_runup_pct: Mapped[float | None] = mapped_column(Float)
    move_since_disclosure_pct: Mapped[float | None] = mapped_column(Float)
    abnormal_move_pct: Mapped[float | None] = mapped_column(Float)
    benchmark_move_pct: Mapped[float | None] = mapped_column(Float)
    sector_move_pct: Mapped[float | None] = mapped_column(Float)
    move_multiple: Mapped[float | None] = mapped_column(Float)
    analogue_expected_move_pct: Mapped[float | None] = mapped_column(Float)
    reaction_room_score: Mapped[float] = mapped_column(Float, default=5.0)
    unresolved: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class ClaudeInvestigation(TimestampMixin, Base):
    """Immutable record of what the model was asked and what it returned."""

    __tablename__ = "claude_investigations"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), index=True)
    pass_name: Mapped[str] = mapped_column(String(16))     # fast | deep
    model: Mapped[str] = mapped_column(String(64), default="")
    prompt_version: Mapped[str] = mapped_column(String(16), default="1.0")
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    invalidated: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str] = mapped_column(Text, default="")


class CatalystScore(TimestampMixin, Base):
    """§64-72 — the seven components plus the final score, versioned."""

    __tablename__ = "catalyst_scores"
    __table_args__ = (UniqueConstraint("event_id", "model_version", "revision"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(16))
    revision: Mapped[int] = mapped_column(Integer, default=1)

    catalyst_strength: Mapped[float] = mapped_column(Float, default=0.0)
    surprise_novelty: Mapped[float] = mapped_column(Float, default=0.0)
    move_amplification: Mapped[float] = mapped_column(Float, default=0.0)
    reaction_room: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    execution_quality: Mapped[float] = mapped_column(Float, default=0.0)
    negative_offset_severity: Mapped[float] = mapped_column(Float, default=0.0)

    upside_catalyst_score: Mapped[float] = mapped_column(Float, default=0.0)
    component_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    caps_applied: Mapped[list] = mapped_column(JSON, default=list)
    gates_failed: Mapped[list] = mapped_column(JSON, default=list)
    fundamental_impact: Mapped[float | None] = mapped_column(Float)
    immediate_reaction_potential: Mapped[float | None] = mapped_column(Float)
    decision_inputs: Mapped[dict] = mapped_column(JSON, default=dict)

    event: Mapped[CatalystEvent] = relationship(back_populates="scores")


class CatalystAlert(Base):
    __tablename__ = "catalyst_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), index=True)
    score_id: Mapped[int | None] = mapped_column(ForeignKey("catalyst_scores.id"))
    dedup_key: Mapped[str] = mapped_column(String(160), unique=True)
    band: Mapped[str] = mapped_column(String(24), default="")
    score_at_alert: Mapped[float] = mapped_column(Float, default=0.0)
    price_at_alert: Mapped[float | None] = mapped_column(Float)
    move_at_alert_pct: Mapped[float | None] = mapped_column(Float)
    title: Mapped[str] = mapped_column(String(256), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, default="")


class CatalystOutcome(Base):
    """§84 — what actually happened afterwards. Raw values, so the definition
    of a 'major move' can change later without losing data."""

    __tablename__ = "catalyst_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("catalyst_events.id"), unique=True)
    price_at_detection: Mapped[float | None] = mapped_column(Float)
    price_at_alert: Mapped[float | None] = mapped_column(Float)
    price_earliest_public: Mapped[float | None] = mapped_column(Float)

    ret_1m: Mapped[float | None] = mapped_column(Float)
    ret_5m: Mapped[float | None] = mapped_column(Float)
    ret_15m: Mapped[float | None] = mapped_column(Float)
    ret_30m: Mapped[float | None] = mapped_column(Float)
    ret_60m: Mapped[float | None] = mapped_column(Float)
    ret_close: Mapped[float | None] = mapped_column(Float)
    ret_next_open: Mapped[float | None] = mapped_column(Float)
    ret_1d: Mapped[float | None] = mapped_column(Float)

    mfe_1h: Mapped[float | None] = mapped_column(Float)
    mfe_1d: Mapped[float | None] = mapped_column(Float)
    mae_1d: Mapped[float | None] = mapped_column(Float)

    abnormal_ret_60m: Mapped[float | None] = mapped_column(Float)
    abnormal_ret_1d: Mapped[float | None] = mapped_column(Float)
    move_multiple_1d: Mapped[float | None] = mapped_column(Float)

    session_at_event: Mapped[str] = mapped_column(String(16), default="")
    captured_through: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HistoricalAnalogue(Base):
    """§40 — feature vector for similarity search over past events."""

    __tablename__ = "historical_analogues"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("catalyst_events.id"), unique=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    observed_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    outcome_ret_60m: Mapped[float | None] = mapped_column(Float)
    outcome_ret_1d: Mapped[float | None] = mapped_column(Float)
    outcome_abnormal_1d: Mapped[float | None] = mapped_column(Float)


class PipelineTrace(Base):
    """§94, §112 — latency and traceability for every stage."""

    __tablename__ = "pipeline_traces"

    id: Mapped[int] = mapped_column(primary_key=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("catalyst_events.id"), index=True)
    stage: Mapped[str] = mapped_column(String(32))
    at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    detail: Mapped[str] = mapped_column(Text, default="")
