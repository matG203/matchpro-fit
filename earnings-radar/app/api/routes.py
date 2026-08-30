"""JSON API — the same endpoints a Next.js front-end would consume later."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc

from app.db.models import (
    Analysis,
    AuditLog,
    Company,
    EarningsEvent,
    ExtractedFinancial,
    MarketContext,
    Notification,
    Release,
    Score,
)
from app.db.session import db_session
from app.domain.enums import EventState
from app.domain.timeutil import from_db, london_display, to_london, utcnow

router = APIRouter(prefix="/api")


def get_container(request: Request):
    return request.app.state.container


@router.get("/today")
def today_view() -> dict:
    """Upcoming/monitored earnings for the next 24h, in Europe/London time."""
    now = utcnow()
    horizon = now + timedelta(hours=26)
    rows = []
    with db_session() as session:
        events = (session.query(EarningsEvent)
                  .join(Company)
                  .filter(EarningsEvent.expected_release_at.isnot(None))
                  .order_by(EarningsEvent.expected_release_at)
                  .all())
        for event in events:
            expected = from_db(event.expected_release_at)
            if expected is None or expected > horizon or expected < now - timedelta(hours=24):
                continue
            rows.append({
                "ticker": event.company.ticker,
                "company": event.company.name,
                "expected_time_london": london_display(expected),
                "expected_at_utc": expected.isoformat(),
                "session": event.session,
                "confidence": event.schedule_confidence,
                "confidence_reason": event.confidence_reason,
                "status": event.state,
                "fiscal": f"FY{event.fiscal_year}Q{event.fiscal_quarter}",
            })
    return {"as_of_london": to_london(now).isoformat(), "events": rows}


@router.get("/results")
def results_view(limit: int = 50) -> dict:
    rows = []
    with db_session() as session:
        scores = (session.query(Score)
                  .order_by(desc(Score.created_at))
                  .limit(limit).all())
        for score in scores:
            release = session.get(Release, score.release_id)
            if release is None:
                continue
            event = session.get(EarningsEvent, release.event_id)
            company = session.get(Company, event.company_id) if event else None
            ctx = (session.query(MarketContext).filter_by(event_id=event.id).first()
                   if event else None)
            published = from_db(release.published_at_utc)
            rows.append({
                "ticker": company.ticker if company else "?",
                "release_time_london": london_display(published) if published else None,
                "final_trade_score": score.final_trade_score,
                "earnings_quality": score.earnings_quality,
                "market_confirmation": score.market_confirmation,
                "entry_score": score.entry_score,
                "reaction_pct": ctx.current_reaction_pct if ctx else None,
                "confidence": score.analysis_confidence,
                "needs_verification": score.needs_verification,
                "score_review": score.score_review,
                "provisional": score.provisional,
                "detection_latency_ms": release.detection_latency_ms,
                "release_id": release.id,
            })
    return {"results": rows}


@router.get("/releases/{release_id}")
def release_detail(release_id: int) -> dict:
    with db_session() as session:
        release = session.get(Release, release_id)
        if release is None:
            raise HTTPException(status_code=404, detail="release not found")
        event = session.get(EarningsEvent, release.event_id)
        company = session.get(Company, event.company_id)
        score = (session.query(Score).filter_by(release_id=release_id)
                 .order_by(desc(Score.created_at)).first())
        analysis = (session.query(Analysis).filter_by(release_id=release_id)
                    .order_by(desc(Analysis.created_at)).first())
        ctx = session.query(MarketContext).filter_by(event_id=event.id).first()
        financials = session.query(ExtractedFinancial).filter_by(release_id=release_id).all()
        published = from_db(release.published_at_utc)

        return {
            "ticker": company.ticker,
            "company": company.name,
            "fiscal": f"FY{event.fiscal_year}Q{event.fiscal_quarter}",
            "release": {
                "published_at_utc": published.isoformat() if published else None,
                "published_at_london": to_london(published).isoformat() if published else None,
                "detected_at_utc": (from_db(release.detected_at_utc).isoformat()
                                    if release.detected_at_utc else None),
                "detection_latency_ms": release.detection_latency_ms,
                "document_type": release.document_type,
                "primary_url": release.primary_url,
                "verified": release.verified,
                "verification_notes": release.verification_notes,
                "sources": [{"source": s.source, "url": s.url} for s in release.source_rows],
            },
            "scores": None if score is None else {
                "earnings_quality": score.earnings_quality,
                "market_confirmation": score.market_confirmation,
                "entry_score": score.entry_score,
                "final_trade_score": score.final_trade_score,
                "components": score.component_breakdown,
                "vetoes": score.vetoes_applied,
                "analysis_confidence": score.analysis_confidence,
                "needs_verification": score.needs_verification,
                "score_review": score.score_review,
                "provisional": score.provisional,
                "scoring_model_version": score.scoring_model_version,
            },
            "financials": [{"metric": f.metric, "value": f.value, "unit": f.unit,
                            "confidence": f.confidence, "source_url": f.source_url}
                           for f in financials],
            "market": None if ctx is None else {
                "prev_close": ctx.prev_close,
                "pre_release_price": ctx.pre_release_price,
                "run_5d_pct": ctx.run_5d_pct,
                "run_1m_pct": ctx.run_1m_pct,
                "run_3m_pct": ctx.run_3m_pct,
                "implied_move_pct": ctx.implied_move_pct,
                "initial_reaction_pct": ctx.initial_reaction_pct,
                "current_reaction_pct": ctx.current_reaction_pct,
                "reaction_vs_prev_close_pct": ctx.reaction_vs_prev_close_pct,
                "reaction_pattern": ctx.reaction_pattern,
                "unresolved": ctx.unresolved,
                "notes": ctx.notes,
            },
            "analysis": None if analysis is None else {
                "model": analysis.model,
                "guidance_status": analysis.guidance_status,
                "growth_direction": analysis.growth_direction,
                "verdict": analysis.verdict,
                "bull_case": analysis.bull_case,
                "bear_case": analysis.bear_case,
                "hidden_negatives": analysis.hidden_negatives,
                "pre_announced": analysis.pre_announced,
                "one_off_items": analysis.one_off_items,
                "reasoning_summary": analysis.reasoning_summary,
                "confidence": analysis.confidence,
            },
        }


@router.get("/audit")
def audit_log(limit: int = 200, event_id: int | None = None,
              release_id: int | None = None) -> dict:
    with db_session() as session:
        query = session.query(AuditLog)
        if event_id is not None:
            query = query.filter(AuditLog.event_id == event_id)
        if release_id is not None:
            query = query.filter(AuditLog.release_id == release_id)
        rows = query.order_by(desc(AuditLog.at_utc)).limit(limit).all()
        return {"entries": [{
            "at_london": to_london(from_db(row.at_utc)).strftime("%Y-%m-%d %H:%M:%S"),
            "actor": row.actor, "action": row.action, "detail": row.detail,
            "level": row.level, "event_id": row.event_id, "release_id": row.release_id,
        } for row in rows]}


@router.get("/health")
def health(container=Depends(get_container)) -> dict:
    with db_session() as session:
        monitored = (session.query(EarningsEvent)
                     .filter(EarningsEvent.state.in_([EventState.SCHEDULED.value,
                                                      EventState.MONITORING.value,
                                                      EventState.NOT_YET_VERIFIED.value]))
                     .count())
        scored = session.query(Score).count()
        failed_notifications = (session.query(Notification)
                                .filter(Notification.status == "FAILED").count())
        latencies = [r.detection_latency_ms for r in
                     session.query(Release).filter(Release.detection_latency_ms.isnot(None)).all()]
        db_ok = True
    scheduler = container.scheduler
    return {
        "database": "ok" if db_ok else "error",
        "scheduler_running": scheduler.running,
        "last_discovery_at": (scheduler.last_discovery_at.isoformat()
                              if scheduler.last_discovery_at else None),
        "last_monitor_tick_at": (scheduler.last_monitor_tick_at.isoformat()
                                 if scheduler.last_monitor_tick_at else None),
        "last_catalyst_poll_at": (scheduler.last_catalyst_poll_at.isoformat()
                                  if scheduler.last_catalyst_poll_at else None),
        "last_outcome_capture_at": (scheduler.last_outcome_capture_at.isoformat()
                                    if scheduler.last_outcome_capture_at else None),
        "monitored_companies": monitored,
        "scored_releases": scored,
        "failed_notifications": failed_notifications,
        "average_detection_latency_ms": (round(sum(latencies) / len(latencies))
                                         if latencies else None),
        "providers": container.provider_status(),
        "scoring_model_version": container.settings.scoring_model_version,
    }


@router.post("/discovery/run")
def run_discovery_now(container=Depends(get_container)) -> dict:
    count = container.scheduler.run_discovery()
    return {"discovered": count}


@router.post("/monitor/tick")
def run_monitor_tick(container=Depends(get_container)) -> dict:
    checked = container.scheduler.monitor_tick()
    return {"checked": checked}


@router.post("/catalyst/poll")
def run_catalyst_poll(container=Depends(get_container)) -> dict:
    """Run one catalyst sweep now, rather than waiting for the interval."""
    result = container.scheduler.catalyst_poll()
    if result is None:
        return {"ran": False, "reason": "catalyst polling not configured"}
    return {
        "ran": True,
        "filings_seen": result.filings_seen,
        "filings_processed": result.filings_processed,
        "articles_seen": result.articles_seen,
        "articles_processed": result.articles_processed,
        "scored": result.scored,
        "alerted": result.alerted,
        "errors": result.errors,
    }


@router.post("/catalyst/outcomes/capture")
def run_outcome_capture(container=Depends(get_container)) -> dict:
    result = container.scheduler.capture_outcomes()
    if result is None:
        return {"ran": False, "reason": "outcome capture not configured"}
    return {
        "ran": True,
        "events_considered": result.events_considered,
        "events_updated": result.events_updated,
        "events_completed": result.events_completed,
        "errors": result.errors,
    }
