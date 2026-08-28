"""Scoring engine unit tests — calibration, weights, vetoes, confidence."""
from __future__ import annotations

from app.domain.enums import GuidanceStatus, ReactionPattern
from app.services.scoring import (
    SCORING_MODEL_VERSION,
    WEIGHTS,
    ScoringInputs,
    analysis_confidence,
    compute_scores,
    entry_score,
    market_confirmation_score,
    needs_score_review,
)


def strong_report(**overrides) -> ScoringInputs:
    base = dict(
        llm_earnings_quality=9.4, llm_guidance_score=9.2, llm_business_kpi_score=9.0,
        llm_true_surprise_score=8.8, llm_confidence=94,
        guidance_status=GuidanceStatus.RAISED, organic_guidance_change=True,
        eps_surprise_pct=18.0, revenue_surprise_pct=5.0,
        estimate_confidence="HIGH", reaction_pct=8.0,
        reaction_vs_prev_close_pct=8.0, pre_run_1m_pct=3.0,
        release_source_quality=1.0, kpi_completeness=1.0,
    )
    base.update(overrides)
    return ScoringInputs(**base)


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_strong_beat_and_raise_scores_high_but_below_ten():
    result = compute_scores(strong_report())
    assert 8.0 <= result.final_trade_score <= 9.6
    assert result.final_trade_score < 10.0
    assert result.vetoes_applied == []
    assert result.scoring_model_version == SCORING_MODEL_VERSION


def test_ten_is_unreachable_even_for_a_perfect_report():
    result = compute_scores(strong_report(
        llm_earnings_quality=10, llm_guidance_score=10, llm_business_kpi_score=10,
        llm_true_surprise_score=10, eps_surprise_pct=200, revenue_surprise_pct=50,
        reaction_pct=12.0, reaction_vs_prev_close_pct=12.0))
    assert result.final_trade_score <= 9.9


def test_guidance_cut_vetoes_nine_plus():
    result = compute_scores(strong_report(guidance_status=GuidanceStatus.LOWERED))
    assert result.final_trade_score < 9.0
    assert "guidance cut" in result.vetoes_applied


def test_acquisition_driven_raise_scores_below_organic_raise():
    organic = compute_scores(strong_report(organic_guidance_change=True))
    acquired = compute_scores(strong_report(organic_guidance_change=False))
    assert acquired.final_trade_score < organic.final_trade_score


def test_low_consensus_confidence_caps_and_lowers_confidence():
    result = compute_scores(strong_report(estimate_confidence="LOW",
                                          consensus_disagreement=True))
    assert result.final_trade_score < 9.0
    assert "low-confidence consensus" in result.vetoes_applied
    assert result.analysis_confidence < 90


def test_market_confirmation_penalises_spike_and_fade():
    faded = market_confirmation_score(strong_report(
        reaction_pct=1.0, reaction_pattern=ReactionPattern.POST_EARNINGS_REVERSAL))
    held = market_confirmation_score(strong_report(reaction_pct=8.0))
    assert faded < held


def test_market_confirmation_uses_implied_move_when_available():
    modest = market_confirmation_score(strong_report(reaction_pct=5.0,
                                                     implied_move_pct=12.0))
    dramatic = market_confirmation_score(strong_report(reaction_pct=20.0,
                                                       implied_move_pct=8.0))
    assert dramatic > modest


def test_entry_score_falls_as_the_move_extends():
    small = entry_score(strong_report(reaction_pct=4.0))
    huge = entry_score(strong_report(reaction_pct=27.0))
    assert huge < small
    assert huge < 6.0


def test_unresolved_market_data_is_vetoed_not_scored_bullishly():
    result = compute_scores(strong_report(market_data_unresolved=True, reaction_pct=None))
    assert "contradictory/unavailable live price feeds" in result.vetoes_applied
    assert result.final_trade_score < 9.0


def test_score_review_triggers_when_great_report_meets_falling_stock():
    inputs = strong_report(reaction_pct=-8.0, reaction_vs_prev_close_pct=-8.0)
    assert needs_score_review(9.4, inputs) is True
    result = compute_scores(inputs)
    assert result.score_review is True
    assert result.final_trade_score < 9.0


def test_provisional_score_when_llm_unavailable():
    result = compute_scores(ScoringInputs(
        eps_surprise_pct=10.0, revenue_surprise_pct=4.0, estimate_confidence="MEDIUM",
        reaction_pct=6.0, guidance_status=GuidanceStatus.NONE))
    assert result.provisional is True
    assert result.analysis_confidence < 80


def test_confidence_drops_on_llm_fact_mismatch():
    clean = analysis_confidence(strong_report())
    mismatched = analysis_confidence(strong_report(llm_fact_mismatch=True))
    assert mismatched < clean


def test_needs_verification_below_threshold():
    result = compute_scores(
        strong_report(llm_confidence=60, estimate_confidence="LOW"), min_confidence=75)
    assert result.needs_verification is True
