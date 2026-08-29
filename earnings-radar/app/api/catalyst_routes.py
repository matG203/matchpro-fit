"""Catalyst Sentinel JSON API (spec §99-101)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc

from app.db.catalyst_models import (
    CatalystAlert,
    CatalystEvent,
    CatalystScore,
    CatalystSource,
    ClaudeInvestigation,
    EventCluster,
    EventFact,
    MarketStructureSnapshot,
    MaterialityAnalysis,
    NegativeOffsetRow,
    NewsItem,
    NoveltyAnalysis,
    PipelineTrace,
    ReactionAnalysis,
)
from app.db.session import db_session
from app.domain.timeutil import from_db, to_london, utcnow

router = APIRouter(prefix="/api/catalyst")


def _age_seconds(event: CatalystEvent, cluster: EventCluster | None) -> float | None:
    earliest = from_db(cluster.earliest_public_at_utc) if cluster else None
    if earliest is None:
        return None
    return (utcnow() - earliest).total_seconds()


@router.get("/live")
def live_catalysts(limit: int = 50, min_score: float = 0.0) -> dict:
    """LIVE CATALYSTS view — one row per scored event."""
    rows = []
    with db_session() as session:
        scores = (session.query(CatalystScore)
                  .order_by(desc(CatalystScore.created_at)).limit(limit * 3).all())
        seen: set[int] = set()
        for score in scores:
            if score.event_id in seen or score.upside_catalyst_score < min_score:
                continue
            seen.add(score.event_id)
            event = session.get(CatalystEvent, score.event_id)
            if event is None:
                continue
            cluster = session.get(EventCluster, event.cluster_id)
            reaction = session.query(ReactionAnalysis).filter_by(event_id=event.id).first()
            materiality = session.query(MaterialityAnalysis).filter_by(
                event_id=event.id).first()
            earliest = from_db(cluster.earliest_public_at_utc) if cluster else None
            rows.append({
                "event_id": event.id,
                "ticker": event.ticker,
                "event_type": event.event_type,
                "event_category": event.event_category,
                "headline": event.headline,
                "state": event.state,
                "certainty": event.certainty,
                "half_life": event.half_life,
                "first_public_london": (to_london(earliest).strftime("%d %b %H:%M")
                                        if earliest else None),
                "age_seconds": _age_seconds(event, cluster),
                "catalyst_strength": score.catalyst_strength,
                "surprise_novelty": score.surprise_novelty,
                "move_amplification": score.move_amplification,
                "reaction_room": score.reaction_room,
                "confidence": score.confidence,
                "execution_quality": score.execution_quality,
                "negative_offset_severity": score.negative_offset_severity,
                "upside_catalyst_score": score.upside_catalyst_score,
                "fundamental_impact": score.fundamental_impact,
                "immediate_reaction_potential": score.immediate_reaction_potential,
                "caps_applied": score.caps_applied,
                "move_since_disclosure_pct": (
                    reaction.move_since_disclosure_pct if reaction else None),
                "abnormal_move_pct": reaction.abnormal_move_pct if reaction else None,
                "value_to_revenue": materiality.value_to_revenue if materiality else None,
                "model_version": score.model_version,
            })
            if len(rows) >= limit:
                break
    return {"catalysts": rows}


@router.get("/events/{event_id}")
def event_detail(event_id: int) -> dict:
    """Full auditable detail for one catalyst (spec §100)."""
    with db_session() as session:
        event = session.get(CatalystEvent, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="catalyst event not found")

        cluster = session.get(EventCluster, event.cluster_id)
        score = (session.query(CatalystScore).filter_by(event_id=event_id)
                 .order_by(desc(CatalystScore.created_at)).first())
        novelty = session.query(NoveltyAnalysis).filter_by(event_id=event_id).first()
        materiality = session.query(MaterialityAnalysis).filter_by(event_id=event_id).first()
        reaction = session.query(ReactionAnalysis).filter_by(event_id=event_id).first()
        structure = session.query(MarketStructureSnapshot).filter_by(event_id=event_id).first()
        offsets = session.query(NegativeOffsetRow).filter_by(event_id=event_id).all()
        facts = session.query(EventFact).filter_by(event_id=event_id).all()
        sources = session.query(CatalystSource).filter_by(event_id=event_id).all()
        investigations = (session.query(ClaudeInvestigation)
                          .filter_by(event_id=event_id)
                          .order_by(ClaudeInvestigation.id).all())
        alerts = session.query(CatalystAlert).filter_by(event_id=event_id).all()
        traces = (session.query(PipelineTrace).filter_by(event_id=event_id)
                  .order_by(PipelineTrace.id).all())

        deep = next((i for i in investigations if i.pass_name == "deep" and i.raw_json), None)
        raw = deep.raw_json if deep else {}
        earliest = from_db(cluster.earliest_public_at_utc) if cluster else None

        return {
            "event": {
                "id": event.id, "ticker": event.ticker, "event_type": event.event_type,
                "event_category": event.event_category, "state": event.state,
                "certainty": event.certainty, "half_life": event.half_life,
                "headline": event.headline, "summary": event.summary,
                "primary_url": event.primary_url,
                "reject_reason": event.reject_reason,
                "earnings_event_id": event.earnings_event_id,
                "first_public_utc": earliest.isoformat() if earliest else None,
                "first_public_london": (to_london(earliest).isoformat() if earliest else None),
                "cluster_members": cluster.member_count if cluster else 0,
                "entity_confidence": cluster.entity_confidence if cluster else None,
                "entity_evidence": cluster.entity_evidence if cluster else "",
            },
            "scores": None if score is None else {
                "catalyst_strength": score.catalyst_strength,
                "surprise_novelty": score.surprise_novelty,
                "move_amplification": score.move_amplification,
                "reaction_room": score.reaction_room,
                "confidence": score.confidence,
                "execution_quality": score.execution_quality,
                "negative_offset_severity": score.negative_offset_severity,
                "upside_catalyst_score": score.upside_catalyst_score,
                "fundamental_impact": score.fundamental_impact,
                "immediate_reaction_potential": score.immediate_reaction_potential,
                "component_breakdown": score.component_breakdown,
                "caps_applied": score.caps_applied,
                "gates_failed": score.gates_failed,
                "model_version": score.model_version,
            },
            "what_is_new": None if novelty is None else {
                "novelty_score": novelty.novelty_score,
                "is_restatement": novelty.is_restatement,
                "information_delta": novelty.information_delta,
                "prior_mentions": novelty.prior_mentions,
                "certainty_before": novelty.certainty_before,
                "certainty_after": novelty.certainty_after,
                "notes": novelty.notes,
            },
            "economic_impact": None if materiality is None else {
                "headline_value": materiality.headline_value,
                "guaranteed_value": materiality.guaranteed_value,
                "expected_value": materiality.expected_value,
                "annualised_value": materiality.annualised_value,
                "value_to_market_cap": materiality.value_to_market_cap,
                "value_to_revenue": materiality.value_to_revenue,
                "annualised_to_revenue": materiality.annualised_to_revenue,
                "materiality_score": materiality.materiality_score,
                "basis": materiality.basis,
                "missing_inputs": materiality.missing_inputs,
                "notes": materiality.notes,
            },
            "market_structure": None if structure is None else {
                "market_cap": structure.market_cap,
                "free_float_shares": structure.free_float_shares,
                "avg_dollar_volume": structure.avg_dollar_volume,
                "relative_volume": structure.relative_volume,
                "spread_pct": structure.spread_pct,
                "short_percent_float": structure.short_percent_float,
                "days_to_cover": structure.days_to_cover,
                "short_interest_stale_days": structure.short_interest_stale_days,
                "session": structure.session,
                "halt_state": structure.halt_state,
                "missing_inputs": structure.missing_inputs,
            },
            "price_reaction": None if reaction is None else {
                "pre_event_runup_pct": reaction.pre_event_runup_pct,
                "move_since_disclosure_pct": reaction.move_since_disclosure_pct,
                "abnormal_move_pct": reaction.abnormal_move_pct,
                "benchmark_move_pct": reaction.benchmark_move_pct,
                "sector_move_pct": reaction.sector_move_pct,
                "move_multiple": reaction.move_multiple,
                "analogue_expected_move_pct": reaction.analogue_expected_move_pct,
                "reaction_room_score": reaction.reaction_room_score,
                "unresolved": reaction.unresolved,
                "notes": reaction.notes,
            },
            "positive_factors": raw.get("positive_factors", []),
            "negative_offsets": [
                {"description": o.description, "severity": o.severity,
                 "evidence": o.evidence_quote, "detected_by": o.detected_by}
                for o in sorted(offsets, key=lambda o: -o.severity)],
            "adversarial_review": {
                "findings": raw.get("adversarial_findings", []),
                "uncertainties": raw.get("uncertainties", []),
                "new_information": raw.get("new_information"),
                "previously_known_information": raw.get("previously_known_information"),
                "incremental_information": raw.get("incremental_information"),
                "invalidate": raw.get("invalidate"),
                "invalidation_reason": raw.get("invalidation_reason"),
            } if raw else None,
            "facts": [{"name": f.name, "value_text": f.value_text,
                       "value_number": f.value_number, "unit": f.unit,
                       "quote": f.quote, "extracted_by": f.extracted_by} for f in facts],
            "sources": [{"tier": s.tier, "provider": s.provider, "url": s.url,
                         "published_at": (from_db(s.published_at_utc).isoformat()
                                          if s.published_at_utc else None),
                         "is_primary_document": s.is_primary_document} for s in sources],
            "alerts": [{"band": a.band, "score": a.score_at_alert, "status": a.status,
                        "title": a.title, "sent_at": (from_db(a.sent_at).isoformat()
                                                      if a.sent_at else None)} for a in alerts],
            "timeline": [{"stage": t.stage,
                          "at": to_london(from_db(t.at_utc)).strftime("%H:%M:%S.%f")[:-3],
                          "duration_ms": t.duration_ms, "detail": t.detail} for t in traces],
        }


@router.get("/performance")
def performance() -> dict:
    """§85-88 — calibration reporting. Honest about sample size."""
    from app.db.catalyst_models import CatalystOutcome

    by_type: dict[str, dict] = {}
    by_band: dict[str, dict] = {}
    with db_session() as session:
        scores = session.query(CatalystScore).all()
        for score in scores:
            event = session.get(CatalystEvent, score.event_id)
            outcome = session.query(CatalystOutcome).filter_by(
                event_id=score.event_id).first()
            if event is None:
                continue
            band = _band_label(score.upside_catalyst_score)
            for bucket, key in ((by_type, event.event_type), (by_band, band)):
                entry = bucket.setdefault(key, {"n": 0, "scored": 0.0, "with_outcome": 0,
                                                "ret_60m": [], "ret_1d": []})
                entry["n"] += 1
                entry["scored"] += score.upside_catalyst_score
                if outcome:
                    entry["with_outcome"] += 1
                    if outcome.ret_60m is not None:
                        entry["ret_60m"].append(outcome.ret_60m)
                    if outcome.ret_1d is not None:
                        entry["ret_1d"].append(outcome.ret_1d)

    def summarise(bucket: dict) -> list[dict]:
        out = []
        for key, entry in sorted(bucket.items()):
            out.append({
                "key": key, "n": entry["n"],
                "avg_score": round(entry["scored"] / entry["n"], 2) if entry["n"] else None,
                "n_with_outcome": entry["with_outcome"],
                "median_ret_60m": _median(entry["ret_60m"]),
                "median_ret_1d": _median(entry["ret_1d"]),
                "sufficient_sample": entry["with_outcome"] >= 20,
            })
        return out

    return {
        "by_event_type": summarise(by_type),
        "by_score_band": summarise(by_band),
        "note": ("Outcome statistics are only meaningful once sufficient_sample is true. "
                 "Until then treat these as descriptive, not predictive."),
    }


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 3)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 3)


def _band_label(score: float) -> str:
    for threshold, label in ((9.5, "9.5+"), (9.25, "9.25-9.49"), (9.0, "9.0-9.24"),
                            (8.5, "8.5-8.99"), (8.0, "8.0-8.49"), (7.5, "7.5-7.99"),
                            (7.0, "7.0-7.49")):
        if score >= threshold:
            return label
    return "<7.0"


@router.get("/news")
def recent_news(limit: int = 50) -> dict:
    """Raw ingest view — including items that were screened out."""
    with db_session() as session:
        items = (session.query(NewsItem).order_by(desc(NewsItem.id)).limit(limit).all())
        return {"items": [{
            "id": i.id, "provider": i.provider, "headline": i.headline,
            "tickers": i.tickers, "source_tier": i.source_tier,
            "cluster_id": i.cluster_id,
            "published_at": (from_db(i.published_at_utc).isoformat()
                             if i.published_at_utc else None),
            "revisions": len(i.revisions),
        } for i in items]}
