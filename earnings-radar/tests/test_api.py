"""API and dashboard rendering against a populated database."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.models import Analysis, Company, EarningsEvent, MarketContext, Release, Score
from app.domain.enums import EventState
from app.domain.timeutil import utcnow
from app.main import create_app


@pytest.fixture
def client(db):
    app = create_app(start_scheduler=False)
    with TestClient(app) as c:
        yield c


def seed(db) -> int:
    with db.db_session() as session:
        company = Company(ticker="ESTC", name="Elastic N.V.", exchange="NYSE")
        session.add(company)
        session.flush()
        event = EarningsEvent(
            company_id=company.id, fiscal_year=2026, fiscal_quarter=2,
            expected_release_at=utcnow() + timedelta(hours=2),
            state=EventState.MONITORING.value, schedule_confidence="MEDIUM",
            confidence_reason="2 calendars agree")
        session.add(event)
        session.flush()
        release = Release(canonical_key="ESTC|FY2026|Q2", event_id=event.id,
                          published_at_utc=utcnow(), detected_at_utc=utcnow(),
                          detection_latency_ms=25_000, verified=True,
                          document_type="8-K", primary_url="https://sec.test/estc")
        session.add(release)
        session.flush()
        session.add(MarketContext(event_id=event.id, prev_close=100.0,
                                  pre_release_price=104.0, current_reaction_pct=16.4,
                                  reaction_pattern="POST_EARNINGS_MOMENTUM"))
        session.add(Score(release_id=release.id, scoring_model_version="1.0.0",
                          earnings_quality=9.2, market_confirmation=9.0, entry_score=6.8,
                          final_trade_score=8.9, analysis_confidence=94.0,
                          component_breakdown={"guidance": 9.0}, vetoes_applied=[]))
        session.add(Analysis(release_id=release.id, model="claude-opus-5",
                             bull_case="Beat and raise", bear_case="Extended valuation",
                             hidden_negatives=["SBC rising"], pre_announced=[],
                             one_off_items=[], reasoning_summary="Strong quarter",
                             guidance_status="RAISED", confidence=94))
        return release.id


def test_today_view_lists_the_watchlist_in_london_time(client, db):
    seed(db)
    data = client.get("/api/today").json()
    assert len(data["events"]) == 1
    event = data["events"][0]
    assert event["ticker"] == "ESTC"
    assert event["status"] == EventState.MONITORING.value
    assert ":" in event["expected_time_london"]
    assert event["confidence"] == "MEDIUM"


def test_results_view_returns_scores_and_reaction(client, db):
    seed(db)
    results = client.get("/api/results").json()["results"]
    assert results[0]["ticker"] == "ESTC"
    assert results[0]["final_trade_score"] == 8.9
    assert results[0]["reaction_pct"] == 16.4
    assert results[0]["detection_latency_ms"] == 25_000


def test_release_detail_exposes_full_analysis(client, db):
    release_id = seed(db)
    data = client.get(f"/api/releases/{release_id}").json()
    assert data["ticker"] == "ESTC"
    assert data["scores"]["earnings_quality"] == 9.2
    assert data["scores"]["scoring_model_version"] == "1.0.0"
    assert data["analysis"]["hidden_negatives"] == ["SBC rising"]
    assert data["release"]["detection_latency_ms"] == 25_000


def test_missing_release_returns_404(client, db):
    assert client.get("/api/releases/99999").status_code == 404


def test_health_reports_providers_and_latency(client, db):
    seed(db)
    health = client.get("/api/health").json()
    assert health["database"] == "ok"
    assert health["monitored_companies"] == 1
    assert health["scored_releases"] == 1
    assert health["average_detection_latency_ms"] == 25_000
    assert "sec_edgar" in health["providers"]


def test_dashboard_renders_watchlist_and_results(client, db):
    seed(db)
    html = client.get("/").text
    assert "Earnings Radar" in html
    assert "ESTC" in html
    assert "8.9" in html


def test_detail_page_renders(client, db):
    release_id = seed(db)
    html = client.get(f"/releases/{release_id}").text
    assert "Elastic N.V." in html
    assert "Beat and raise" in html
    assert "SBC rising" in html


def test_audit_endpoint_returns_entries(client, db):
    seed(db)
    client.post("/api/monitor/tick")
    entries = client.get("/api/audit").json()["entries"]
    assert isinstance(entries, list)
