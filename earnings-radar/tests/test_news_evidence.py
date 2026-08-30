"""Evidence that news is digested, and that alerts land before the move.

These run against the real database and the real HTTP app. The arithmetic in
the lead-time report is the part worth distrusting — a number that flatters the
system is worse than no number — so the prices here are chosen so the right
answer is obvious by inspection.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.catalyst_models import (
    CatalystAlert,
    CatalystEvent,
    CatalystOutcome,
    CatalystScore,
    EventCluster,
    NewsItem,
)
from app.domain.timeutil import utcnow
from app.main import create_app
from app.services.news_evidence import ingestion_report, lead_time_report


@pytest.fixture
def client(db):
    app = create_app(start_scheduler=False)
    with TestClient(app) as c:
        yield c


NOW = utcnow()


def _news(session, *, headline, provider="wire_rss", source="GlobeNewswire",
          cluster_id=None, published_minutes_ago=10, detected_lag_s=40):
    published = NOW - timedelta(minutes=published_minutes_ago)
    item = NewsItem(provider=provider, article_id=headline, headline=headline,
                    body="", original_source=source, source_tier="PRIMARY",
                    source_url=f"https://wire.test/{abs(hash(headline))}",
                    published_at_utc=published,
                    received_at_utc=published + timedelta(seconds=detected_lag_s),
                    cluster_id=cluster_id)
    session.add(item)
    session.flush()
    return item


def _cluster(session, ticker="KTRX", minutes_ago=10):
    cluster = EventCluster(cluster_key=f"{ticker}|x", ticker=ticker,
                           entity_confidence=0.98, entity_evidence="exchange tag",
                           earliest_public_at_utc=NOW - timedelta(minutes=minutes_ago))
    session.add(cluster)
    session.flush()
    return cluster


def _event(session, cluster, *, state="SCORED", reject_reason="",
           event_type="FDA_APPROVAL"):
    event = CatalystEvent(cluster_id=cluster.id, ticker=cluster.ticker,
                          event_type=event_type, event_category="REGULATORY",
                          headline=f"{cluster.ticker} news", state=state,
                          reject_reason=reject_reason)
    session.add(event)
    session.flush()
    return event


# ── ingestion: is news being read? ───────────────────────────────────────────


class FakeWires:
    """Just the introspection surface the report reads."""

    name = "wire_rss"

    def __init__(self, health, sweep=None):
        self._health = health
        self.last_sweep = sweep

    def health(self):
        return self._health


def _health(source, *, ok=True, seen=40, new=2, error="", newest_minutes=6,
            polled=True):
    from app.providers.wires import WireFeedHealth
    return WireFeedHealth(source=source, url=f"https://{source}.test/f", ok=ok,
                          items_seen=seen, items_new=new, error=error,
                          last_success_at=NOW - timedelta(seconds=20),
                          last_attempt_at=(NOW - timedelta(seconds=20)
                                           if polled else None),
                          newest_item_at=NOW - timedelta(minutes=newest_minutes))


def test_a_dead_wire_is_visible_even_though_it_wrote_no_rows(db):
    """The failure the page exists for.

    A wire that stops answering produces no rows, no errors and no log lines.
    Its absence is only detectable by asking the live provider, which is why
    feed health is read from the object rather than reconstructed from data.
    """
    wires = FakeWires([_health("GlobeNewswire"),
                       _health("PR Newswire", ok=False, seen=0, new=0,
                               error="404 Not Found")])
    with db.db_session() as session:
        report = ingestion_report(session, providers=[wires], now=NOW)

    feeds = {f["source"]: f for f in report["feeds"]}
    assert feeds["GlobeNewswire"]["state"] == "ok"
    assert feeds["PR Newswire"]["state"] == "failing"
    assert "404" in feeds["PR Newswire"]["error"]


def test_a_feed_not_yet_polled_is_not_reported_as_broken(db):
    """The first thirty seconds after a restart.

    Nothing has been fetched, so every feed has ok=False. Rendering that as
    failure puts three red lights on a healthy system and trains the operator
    to ignore them.
    """
    wires = FakeWires([_health("GlobeNewswire", ok=False, seen=0, new=0,
                               polled=False)])
    with db.db_session() as session:
        report = ingestion_report(session, providers=[wires], now=NOW)

    assert report["feeds"][0]["state"] == "unpolled"
    assert report["feeds"][0]["error"] == ""


def test_every_inbound_item_gets_a_visible_fate(db):
    with db.db_session() as session:
        # 1. never matched to a company — the commonest outcome, and correct
        _news(session, headline="Some private company opens an office")
        # 2. matched, screened out
        screened = _cluster(session, "NVI")
        _event(session, screened, state="REJECTED", reject_reason="IMMATERIAL")
        _news(session, headline="NVI to present at a conference",
              cluster_id=screened.id)
        # 3. matched and scored, but below the alert threshold
        scored = _cluster(session, "HSY")
        scored_event = _event(session, scored)
        session.add(CatalystScore(event_id=scored_event.id, upside_catalyst_score=7.4,
                                  model_version="1.0.0"))
        _news(session, headline="HSY wins a small order", cluster_id=scored.id)
        # 4. alerted
        alerted = _cluster(session, "KTRX")
        alerted_event = _event(session, alerted)
        session.add(CatalystScore(event_id=alerted_event.id, upside_catalyst_score=9.3,
                                  model_version="1.0.0"))
        session.add(CatalystAlert(event_id=alerted_event.id, dedup_key="k1",
                                  band="9.0-9.24", score_at_alert=9.3, status="SENT",
                                  sent_at=NOW - timedelta(minutes=9)))
        _news(session, headline="KTRX announces FDA approval", cluster_id=alerted.id)
        session.flush()

        report = ingestion_report(session, now=NOW)

    outcomes = report["totals"]["by_outcome"]
    assert outcomes == {"no_entity": 1, "screened_out": 1, "scored": 1, "alerted": 1}
    assert report["totals"]["ingested"] == 4
    # Every row in the log carries a human-readable reason, not just a code.
    assert all(row["outcome_label"] for row in report["log"])
    screened_row = next(r for r in report["log"] if "conference" in r["headline"])
    assert screened_row["outcome_label"] == "immaterial"


def test_detection_lag_is_measured_not_assumed(db):
    with db.db_session() as session:
        _news(session, headline="One", detected_lag_s=30, published_minutes_ago=20)
        _news(session, headline="Two", detected_lag_s=50, published_minutes_ago=10)
        session.flush()
        report = ingestion_report(session, now=NOW)

    assert report["totals"]["median_detection_lag_seconds"] == 40.0
    assert [r["detected_lag_seconds"] for r in report["log"]] == [50.0, 30.0]


def test_the_log_is_ordered_by_publication_not_by_arrival(db):
    """A slow feed or a revision can arrive out of order; a log whose visible
    timestamp column jumps around is hard to scan."""
    with db.db_session() as session:
        _news(session, headline="Published first", published_minutes_ago=30)
        _news(session, headline="Published last", published_minutes_ago=5)
        _news(session, headline="Published second", published_minutes_ago=20)
        session.flush()
        report = ingestion_report(session, now=NOW)

    assert [r["headline"] for r in report["log"]] == [
        "Published last", "Published second", "Published first"]


def test_items_outside_the_window_are_not_counted(db):
    with db.db_session() as session:
        _news(session, headline="Recent", published_minutes_ago=30)
        _news(session, headline="Ancient", published_minutes_ago=60 * 40)
        session.flush()
        report = ingestion_report(session, now=NOW, hours=24)

    assert report["totals"]["ingested"] == 1


# ── lead time: did the alert beat the move? ──────────────────────────────────


def _alerted_event(session, *, base, on_tape, ret_60m, alert_lag_minutes=1):
    cluster = _cluster(session, "KTRX", minutes_ago=90)
    event = _event(session, cluster)
    disclosed = NOW - timedelta(minutes=90)
    session.add(CatalystAlert(
        event_id=event.id, dedup_key=f"k{event.id}", band="9.0-9.24",
        score_at_alert=9.3, status="SENT",
        price_at_alert=base,          # the delayed feed's stale view
        sent_at=disclosed + timedelta(minutes=alert_lag_minutes)))
    session.add(CatalystOutcome(
        event_id=event.id, price_earliest_public=base,
        price_at_alert=base, price_on_tape_at_alert=on_tape, ret_60m=ret_60m))
    _news(session, headline=f"KTRX approval {event.id}", cluster_id=cluster.id,
          published_minutes_ago=90, detected_lag_s=45)
    session.flush()
    return event


def test_an_alert_ahead_of_the_move_reads_as_ahead(db):
    """£10.00 at disclosure, £10.20 when the alert fired, £12.00 an hour later.

    The move was +20%; 2% of it had happened by the alert, so 90% was still
    ahead."""
    with db.db_session() as session:
        _alerted_event(session, base=10.0, on_tape=10.2, ret_60m=20.0)
        report = lead_time_report(session, now=NOW)

    row = report["alerts"][0]
    assert row["move_before_alert_pct"] == pytest.approx(2.0, abs=0.01)
    assert row["share_of_60m_move_still_ahead"] == pytest.approx(0.9, abs=0.01)
    assert row["move_after_alert_pct"]["60m"] == pytest.approx(17.65, abs=0.05)
    assert row["measurable"] is True


def test_an_alert_after_the_move_is_not_flattered(db):
    """The result the system must be willing to report about itself.

    The stock had already done the whole 20% by the time the alert went out.
    Nothing was left; 'still ahead' must read 0%, not 100%.
    """
    with db.db_session() as session:
        _alerted_event(session, base=10.0, on_tape=12.0, ret_60m=20.0,
                       alert_lag_minutes=25)
        report = lead_time_report(session, now=NOW)

    row = report["alerts"][0]
    assert row["move_before_alert_pct"] == pytest.approx(20.0, abs=0.01)
    assert row["share_of_60m_move_still_ahead"] == 0.0
    assert row["move_after_alert_pct"]["60m"] == pytest.approx(0.0, abs=0.01)


def test_the_delayed_feed_price_is_never_used_for_the_lead_calculation(db):
    """The trap this module was written around.

    `price_at_alert` is what the 15-minute delayed feed showed — the price from
    a quarter of an hour before. Using it would report that no move had begun
    for every single alert. Here the feed showed 10.00 while the tape was
    already 12.00, and the honest answer is 0% still ahead.
    """
    with db.db_session() as session:
        _alerted_event(session, base=10.0, on_tape=12.0, ret_60m=20.0)
        report = lead_time_report(session, now=NOW, delay_seconds=900.0)

    row = report["alerts"][0]
    assert row["price_feed_showed_at_alert"] == 10.0
    assert row["price_on_tape_at_alert"] == 12.0
    assert row["share_of_60m_move_still_ahead"] == 0.0
    assert "15 minutes delayed" in report["delay_note"]


def test_a_move_too_small_to_measure_reports_nothing_rather_than_a_guess(db):
    with db.db_session() as session:
        _alerted_event(session, base=10.0, on_tape=10.01, ret_60m=0.05)
        report = lead_time_report(session, now=NOW)

    row = report["alerts"][0]
    assert row["share_of_60m_move_still_ahead"] is None


def test_an_alert_awaiting_outcome_capture_says_so(db):
    with db.db_session() as session:
        cluster = _cluster(session, "KTRX", minutes_ago=3)
        event = _event(session, cluster)
        session.add(CatalystAlert(event_id=event.id, dedup_key="pending",
                                  band="9.0-9.24", score_at_alert=9.1, status="SENT",
                                  sent_at=NOW - timedelta(minutes=2)))
        _news(session, headline="KTRX approval, just in", cluster_id=cluster.id,
              published_minutes_ago=3, detected_lag_s=45)
        session.flush()
        report = lead_time_report(session, now=NOW)

    row = report["alerts"][0]
    assert row["measurable"] is False
    assert row["share_of_60m_move_still_ahead"] is None
    assert "has not yet reconstructed" in row["why_not_measurable"]
    # Timing is known immediately even when the price outcome is not.
    assert row["alert_lag_seconds"] == pytest.approx(60.0, abs=1)
    assert row["detection_lag_seconds"] is not None


def test_the_summary_only_averages_measurable_rows(db):
    with db.db_session() as session:
        _alerted_event(session, base=10.0, on_tape=10.2, ret_60m=20.0)
        cluster = _cluster(session, "NVI", minutes_ago=3)
        pending = _event(session, cluster)
        session.add(CatalystAlert(event_id=pending.id, dedup_key="p2", band="9.0-9.24",
                                  score_at_alert=9.1, status="SENT", sent_at=NOW))
        session.flush()
        report = lead_time_report(session, now=NOW)

    assert report["summary"]["n_alerts"] == 2
    assert report["summary"]["n_measurable"] == 1
    assert report["summary"]["median_share_of_move_still_ahead"] == pytest.approx(0.9, abs=0.01)


# ── the pages actually render ────────────────────────────────────────────────


def test_the_news_page_renders_with_no_data_at_all(client, db):
    response = client.get("/news")
    assert response.status_code == 200
    assert "News → alert evidence" in response.text
    # An empty system says why it is empty rather than showing a blank table.
    assert "nothing to measure" in response.text


def test_the_news_page_shows_the_funnel_and_the_lead_table(client, db):
    with db.db_session() as session:
        _alerted_event(session, base=10.0, on_tape=10.2, ret_60m=20.0)
        _news(session, headline="Unmatched release from a private company")
        session.flush()

    response = client.get("/news")
    assert response.status_code == 200
    body = response.text
    assert "Are the wires alive?" in body
    assert "Did the alert beat the market?" in body
    assert "KTRX" in body
    assert "90%" in body                      # share still ahead
    assert "Unmatched release" in body        # discards are shown, not hidden


def test_both_evidence_endpoints_serve_json(client, db):
    with db.db_session() as session:
        _alerted_event(session, base=10.0, on_tape=10.2, ret_60m=20.0)
        session.flush()

    digest = client.get("/api/catalyst/ingestion").json()
    lead = client.get("/api/catalyst/lead-time").json()

    assert digest["totals"]["ingested"] == 1
    assert lead["alerts"][0]["ticker"] == "KTRX"
    assert lead["summary"]["n_measurable"] == 1
