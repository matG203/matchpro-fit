"""Evidence that news is being read, and that it is reaching us first.

Three questions, kept separate because they have different answers and the
honest ones are not always flattering:

  1. **Are articles arriving at all?** Feed health and ingest counts. A dead
     wire produces silence, and silence looks exactly like a quiet market, so
     this is stated in counts rather than left to inference.

  2. **What happened to each one?** Every inbound item gets a fate: no ticker
     resolved, screened out (and why), scored, alerted. Most items are correctly
     discarded — a system that acted on wire traffic indiscriminately would be
     worthless — so the discard reasons are shown, not hidden.

  3. **Did we get there before the market did?** This is the claim worth being
     sceptical about, and the one this module is most careful with. Two
     timestamps and two prices:

         disclosed → detected → alerted        (how fast we were)
         price at disclosure → price at alert → price later   (was it worth it)

     The trap is `price_at_alert`, which records what the *price feed* showed
     when the alert fired. On the 15-minute delayed plan that number is a
     quarter of an hour stale, so it will always suggest the move had not
     started yet — flattering and meaningless. `price_on_tape_at_alert` is what
     the market was actually doing at that instant, reconstructed from
     historical bars afterwards. Every lead-time figure here uses the tape
     price, and says so when it is not yet available.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.catalyst.reaction import pct_change
from app.db.catalyst_models import (
    CatalystAlert,
    CatalystEvent,
    CatalystOutcome,
    CatalystScore,
    EventCluster,
    NewsItem,
)
from app.domain.timeutil import from_db, to_london, utcnow

# Horizons offered as "the move after the alert". 60 minutes is the headline:
# short enough that the catalyst is still what is driving the price, long
# enough to have moved.
LEAD_HORIZONS = (("5m", "ret_5m"), ("15m", "ret_15m"), ("60m", "ret_60m"),
                 ("1d", "ret_1d"))

# Below this 60-minute move, "how much of it did we beat" has no answer worth
# printing — the denominator is noise.
MIN_MOVE_PCT = 0.5


@dataclass
class ItemFate:
    """What became of one inbound article."""

    outcome: str          # machine-readable
    label: str            # for a human reading the log
    event_id: int | None = None
    ticker: str = ""
    score: float | None = None


def _fate(session: Session, item: NewsItem) -> ItemFate:
    """Trace one news item to its end state.

    `cluster_id` is the pivot. The pipeline only clusters an item once entity
    resolution has succeeded, so a null cluster means we could not tell which
    company the story was about — much the commonest outcome on a firehose, and
    the right one.
    """
    if item.cluster_id is None:
        return ItemFate("no_entity", "no company identified")

    cluster = session.get(EventCluster, item.cluster_id)
    if cluster is None:
        return ItemFate("no_entity", "no company identified")

    event = (session.query(CatalystEvent)
             .filter_by(cluster_id=cluster.id)
             .order_by(CatalystEvent.id).first())
    if event is None:
        return ItemFate("clustered", f"matched {cluster.ticker}, no event created",
                        ticker=cluster.ticker)

    score = (session.query(CatalystScore).filter_by(event_id=event.id)
             .order_by(desc(CatalystScore.created_at)).first())
    alert = session.query(CatalystAlert).filter_by(event_id=event.id).first()

    if alert is not None:
        return ItemFate("alerted", f"alerted at {alert.score_at_alert:.1f}",
                        event_id=event.id, ticker=event.ticker,
                        score=alert.score_at_alert)
    if score is not None:
        return ItemFate("scored", f"scored {score.upside_catalyst_score:.1f}, below "
                                  f"the alert threshold",
                        event_id=event.id, ticker=event.ticker,
                        score=score.upside_catalyst_score)
    reason = (event.reject_reason or "screened out").replace("_", " ").lower()
    return ItemFate("screened_out", reason, event_id=event.id, ticker=event.ticker)


def ingestion_report(session: Session, *, providers=None, now: datetime | None = None,
                     hours: int = 24, limit: int = 80) -> dict:
    """Question 1 and 2: what came in, and what became of it."""
    now = now or utcnow()
    since = now - timedelta(hours=hours)

    feeds: list[dict] = []
    sweep: dict | None = None
    for provider in providers or []:
        health_fn = getattr(provider, "health", None)
        if health_fn is None:
            continue
        for health in health_fn():
            newest = from_db(health.newest_item_at)
            feeds.append({
                "source": health.source,
                "state": health.state,
                "ok": health.ok,
                "error": health.error,
                "items_last_sweep": health.items_seen,
                "new_last_sweep": health.items_new,
                "newest_item_age_minutes": (
                    round((now - newest).total_seconds() / 60, 1) if newest else None),
                "last_success_london": _london(from_db(health.last_success_at)),
            })
        last = getattr(provider, "last_sweep", None)
        if last is not None:
            sweep = {
                "at_london": _london(from_db(last.at)),
                "items_seen": last.items_seen,
                "items_new": last.items_new,
                "bodies_fetched": last.bodies_fetched,
                "body_fetch_failures": last.body_fetch_failures,
                "budget_exhausted": last.budget_exhausted,
            }

    # Newest release first. Ordering by insertion would be close but not the
    # same — a slow feed or a revision can arrive out of order — and a log
    # whose visible timestamp column jumps around is hard to scan.
    items = (session.query(NewsItem)
             .filter(NewsItem.received_at_utc >= since)
             .order_by(desc(NewsItem.published_at_utc), desc(NewsItem.id)).all())

    by_provider: dict[str, dict] = {}
    fates: dict[str, int] = {}
    lags: list[float] = []
    log: list[dict] = []

    for item in items:
        bucket = by_provider.setdefault(
            item.provider, {"provider": item.provider, "ingested": 0, "resolved": 0,
                            "scored": 0, "alerted": 0})
        bucket["ingested"] += 1

        fate = _fate(session, item)
        fates[fate.outcome] = fates.get(fate.outcome, 0) + 1
        if fate.outcome != "no_entity":
            bucket["resolved"] += 1
        if fate.outcome in ("scored", "alerted"):
            bucket["scored"] += 1
        if fate.outcome == "alerted":
            bucket["alerted"] += 1

        published = from_db(item.published_at_utc)
        received = from_db(item.received_at_utc)
        lag = ((received - published).total_seconds()
               if published and received and received >= published else None)
        if lag is not None:
            lags.append(lag)

        if len(log) < limit:
            log.append({
                "id": item.id,
                "provider": item.provider,
                "source": item.original_source or item.provider,
                "headline": item.headline[:200],
                "source_tier": item.source_tier,
                "url": item.source_url,
                "published_london": _london(published),
                "detected_lag_seconds": round(lag, 1) if lag is not None else None,
                "outcome": fate.outcome,
                "outcome_label": fate.label,
                "ticker": fate.ticker,
                "event_id": fate.event_id,
                "score": fate.score,
            })

    return {
        "window_hours": hours,
        "generated_london": _london(now),
        "feeds": feeds,
        "last_sweep": sweep,
        "totals": {
            "ingested": len(items),
            "by_outcome": fates,
            "median_detection_lag_seconds": _median(lags),
        },
        "by_provider": sorted(by_provider.values(), key=lambda b: -b["ingested"]),
        "log": log,
        "note": ("Most inbound releases are correctly discarded — the wires carry "
                 "conference invitations and award announcements alongside the "
                 "material ones. A high 'no company identified' count is normal: "
                 "it is the screen doing its job, not a fault."),
    }


def lead_time_report(session: Session, *, now: datetime | None = None,
                     limit: int = 40, delay_seconds: float = 0.0) -> dict:
    """Question 3: did the alert land before the market reacted?

    One row per alert. Everything is derived from stored raw values so the
    arithmetic can be checked against the detail page.
    """
    now = now or utcnow()
    alerts = (session.query(CatalystAlert)
              .order_by(desc(CatalystAlert.id)).limit(limit).all())

    rows: list[dict] = []
    for alert in alerts:
        event = session.get(CatalystEvent, alert.event_id)
        if event is None:
            continue
        cluster = session.get(EventCluster, event.cluster_id)
        outcome = session.query(CatalystOutcome).filter_by(event_id=event.id).first()

        disclosed = from_db(cluster.earliest_public_at_utc) if cluster else None
        detected = _first_detection(session, event)
        alerted = from_db(alert.sent_at) or from_db(alert.created_at)

        base = outcome.price_earliest_public if outcome else None
        on_tape = outcome.price_on_tape_at_alert if outcome else None

        # Of the whole move the catalyst produced, how much was still ahead of
        # us when the alert fired? Anything at or below zero means the market
        # had already finished moving — the honest failure this view exists to
        # expose.
        after: dict[str, float | None] = {}
        for label, column in LEAD_HORIZONS:
            later = _price_at_horizon(outcome, base, column)
            after[label] = (round(pct_change(on_tape, later), 3)
                            if on_tape and later else None)

        move_before = (round(pct_change(base, on_tape), 3)
                       if base and on_tape else None)
        total_60m = getattr(outcome, "ret_60m", None) if outcome else None
        captured = None
        # A stock that barely moved has no move to have been ahead of, and
        # dividing by a near-zero denominator would manufacture a confident
        # number out of noise. Below this the question is simply not asked.
        if move_before is not None and total_60m is not None and abs(total_60m) >= MIN_MOVE_PCT:
            # Share of the 60-minute move that had NOT yet happened. Works in
            # both directions: a half-completed fall reads the same as a
            # half-completed rise.
            captured = round(max(0.0, min(1.0, 1 - (move_before / total_60m))), 3)

        rows.append({
            "event_id": event.id,
            "ticker": event.ticker,
            "event_type": event.event_type,
            "headline": event.headline[:200],
            "score_at_alert": alert.score_at_alert,
            "band": alert.band,
            "alert_status": alert.status,
            "disclosed_london": _london(disclosed),
            "detected_london": _london(detected),
            "alerted_london": _london(alerted),
            "detection_lag_seconds": _gap(disclosed, detected),
            "alert_lag_seconds": _gap(disclosed, alerted),
            "price_at_disclosure": base,
            "price_feed_showed_at_alert": alert.price_at_alert,
            "price_on_tape_at_alert": on_tape,
            "move_before_alert_pct": move_before,
            "move_after_alert_pct": after,
            "share_of_60m_move_still_ahead": captured,
            "measurable": on_tape is not None,
            "why_not_measurable": (
                "" if on_tape is not None else
                "the outcome pass has not yet reconstructed the tape price at "
                "the alert — it fills in as historical bars mature"),
        })

    measured = [r for r in rows if r["share_of_60m_move_still_ahead"] is not None]
    lags = [r["alert_lag_seconds"] for r in rows if r["alert_lag_seconds"] is not None]

    return {
        "generated_london": _london(now),
        "feed_delay_seconds": delay_seconds,
        "alerts": rows,
        "summary": {
            "n_alerts": len(rows),
            "n_measurable": len(measured),
            "median_alert_lag_seconds": _median(lags),
            "median_share_of_move_still_ahead": _median(
                [r["share_of_60m_move_still_ahead"] for r in measured]),
        },
        "how_to_read": (
            "'Still ahead' is the share of the stock's 60-minute move that had "
            "not yet happened when the alert fired, measured against the tape "
            "rather than against the delayed feed. 1.0 means the alert beat the "
            "market entirely; 0.0 means it arrived after the move was over. "
            "A sample of a handful of alerts proves nothing either way — read "
            "the median only once n is in the dozens."),
        "delay_note": (
            "" if delay_seconds <= 0 else
            f"The price feed is {delay_seconds / 60:.0f} minutes delayed, so "
            f"'what the feed showed' and 'what the tape was' differ by that much "
            f"at alert time. Detection and alert timing are unaffected: the wire "
            f"and SEC feeds are not delayed, only prices are."),
    }


# ── helpers ──────────────────────────────────────────────────────────────────


def _price_at_horizon(outcome: CatalystOutcome | None, base: float | None,
                      column: str) -> float | None:
    """Reconstruct an absolute price from a stored percentage return."""
    if outcome is None or not base:
        return None
    ret = getattr(outcome, column, None)
    if ret is None:
        return None
    return base * (1 + ret / 100.0)


def _first_detection(session: Session, event: CatalystEvent) -> datetime | None:
    """When we first held the story, across every source in its cluster."""
    items = (session.query(NewsItem)
             .filter(NewsItem.cluster_id == event.cluster_id).all())
    stamps = [from_db(i.received_at_utc) for i in items]
    stamps = [s for s in stamps if s is not None]
    return min(stamps) if stamps else None


def _gap(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None or end < start:
        return None
    return round((end - start).total_seconds(), 1)


def _london(value: datetime | None) -> str | None:
    return to_london(value).strftime("%d %b %H:%M:%S") if value else None


def _median(values: list) -> float | None:
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return round(clean[mid], 3)
    return round((clean[mid - 1] + clean[mid]) / 2, 3)
