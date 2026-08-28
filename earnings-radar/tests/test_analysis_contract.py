"""LLM contract: strict schema, retries on invalid output, anti-hallucination."""
from __future__ import annotations

import anthropic
import pytest
from pydantic import ValidationError

from app.domain.enums import GrowthDirection, GuidanceStatus
from app.domain.schemas import AnalysisOutput, FactCheck
from app.providers.base import EstimateDTO
from app.services.analysis import AnalysisFailed, EarningsAnalysisService
from app.services.expectations import build_expectations
from app.services.extraction import extract_financials
from app.services.marketdata import MarketContextData


def valid_payload(**overrides) -> dict:
    base = dict(
        ticker="ESTC", earnings_quality=9.0, guidance_score=8.5, business_kpi_score=8.0,
        true_surprise_score=7.5, guidance_status=GuidanceStatus.RAISED,
        growth_direction=GrowthDirection.ACCELERATING, bull_case="b", bear_case="c",
        reasoning_summary="d", facts=FactCheck(eps_actual=0.59, revenue_actual=1.16e9),
        confidence=90, verdict="STRONG")
    base.update(overrides)
    return base


class StubMessages:
    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls = 0

    def parse(self, **kwargs):
        self.calls += 1
        result = self._outputs.pop(0)
        if isinstance(result, Exception):
            raise result

        class Response:
            parsed_output = result

        return Response()


class StubClient:
    def __init__(self, outputs):
        self.messages = StubMessages(outputs)


def service_with(outputs) -> EarningsAnalysisService:
    return EarningsAnalysisService(client=StubClient(outputs))


# ── schema ───────────────────────────────────────────────────────────────────

def test_valid_output_parses():
    parsed = AnalysisOutput(**valid_payload())
    assert parsed.ticker == "ESTC"
    assert parsed.pre_announced_news == []


def test_scores_outside_zero_to_ten_are_rejected():
    with pytest.raises(ValidationError):
        AnalysisOutput(**valid_payload(earnings_quality=11.0))
    with pytest.raises(ValidationError):
        AnalysisOutput(**valid_payload(confidence=150))


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        AnalysisOutput(**valid_payload(made_up_field="x"))


def test_invalid_guidance_status_is_rejected():
    with pytest.raises(ValidationError):
        AnalysisOutput(**valid_payload(guidance_status="SLIGHTLY_BETTER"))


def test_unavailable_facts_are_null_not_guessed():
    parsed = AnalysisOutput(**valid_payload(facts=FactCheck()))
    assert parsed.facts.eps_actual is None
    assert parsed.facts.revenue_actual is None


# ── retries ──────────────────────────────────────────────────────────────────

def test_ticker_mismatch_is_retried_then_succeeds():
    wrong = AnalysisOutput(**valid_payload(ticker="AFRM"))
    right = AnalysisOutput(**valid_payload())
    service = service_with([wrong, right])
    evidence = _evidence(service)
    result = service.analyse(evidence)
    assert result.ticker == "ESTC"
    assert service._client.messages.calls == 2


def test_repeated_failures_raise_analysis_failed():
    service = service_with([
        anthropic.APIError("boom", request=None, body=None),
        anthropic.APIError("boom", request=None, body=None),
        anthropic.APIError("boom", request=None, body=None),
    ])
    with pytest.raises(AnalysisFailed):
        service.analyse(_evidence(service))


# ── anti-hallucination cross-check ───────────────────────────────────────────

RELEASE = ("Total revenue of $1.16 billion. Non-GAAP diluted earnings per share "
           "of $0.59. For the three months ended July 31, 2026.")


def test_matching_numbers_pass_the_cross_check():
    extraction = extract_financials(RELEASE)
    parsed = AnalysisOutput(**valid_payload())
    assert EarningsAnalysisService.fact_mismatch(parsed, extraction) is False


def test_invented_revenue_is_flagged():
    extraction = extract_financials(RELEASE)
    parsed = AnalysisOutput(**valid_payload(
        facts=FactCheck(eps_actual=0.59, revenue_actual=2.5e9)))
    assert EarningsAnalysisService.fact_mismatch(parsed, extraction) is True


def test_null_facts_are_not_treated_as_mismatch():
    extraction = extract_financials(RELEASE)
    parsed = AnalysisOutput(**valid_payload(facts=FactCheck()))
    assert EarningsAnalysisService.fact_mismatch(parsed, extraction) is False


def test_evidence_package_carries_only_deterministic_inputs():
    service = service_with([AnalysisOutput(**valid_payload())])
    evidence = _evidence(service)
    assert evidence.consensus["estimate_confidence"] in ("HIGH", "MEDIUM", "LOW")
    assert "bands" in evidence.consensus
    assert evidence.market_context["prev_close"] == 100.0
    assert evidence.extracted_facts["revenue"]["value"] == 1.16e9


def _evidence(service: EarningsAnalysisService):
    expectations = build_expectations([
        EstimateDTO("revenue", "current", 1.10e9, "finnhub"),
        EstimateDTO("eps", "current", 0.50, "finnhub"),
    ])
    market = MarketContextData(prev_close=100.0, pre_release_price=104.0,
                               current_reaction_pct=8.0)
    return service.build_evidence(
        ticker="ESTC", company_name="Elastic N.V.", fiscal_year=2026, fiscal_quarter=2,
        release_text=RELEASE, extraction=extract_financials(RELEASE),
        expectations=expectations, market=market)
