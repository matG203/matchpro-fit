"""Consensus bands, market reaction analytics and notification formatting."""
from __future__ import annotations

from app.domain.enums import ReactionPattern
from app.providers.base import EstimateDTO
from app.services.expectations import build_expectations, surprise_pct_vs_band
from app.services.marketdata import (
    ReactionPoint,
    classify_reaction,
    compute_runs,
    pct_change,
    quotes_conflict,
)
from app.services.notification import format_notification, score_emoji

# ── consensus bands ──────────────────────────────────────────────────────────

def test_agreeing_providers_give_high_confidence():
    exp = build_expectations([
        EstimateDTO("eps", "current", 0.50, "finnhub"),
        EstimateDTO("eps", "current", 0.51, "fmp"),
        EstimateDTO("revenue", "current", 1.10e9, "finnhub"),
        EstimateDTO("revenue", "current", 1.105e9, "fmp"),
    ])
    assert exp.estimate_confidence == "HIGH"
    assert not exp.bands["revenue"].disagreement


def test_wide_revenue_band_is_flagged_as_disagreement():
    exp = build_expectations([
        EstimateDTO("revenue", "current", 1.10e9, "finnhub"),
        EstimateDTO("revenue", "current", 1.14e9, "fmp"),
    ])
    assert exp.bands["revenue"].disagreement is True
    assert exp.estimate_confidence == "LOW"
    assert "disagreement" in exp.notes[0]


def test_single_provider_is_medium_at_best():
    exp = build_expectations([
        EstimateDTO("eps", "current", 0.50, "finnhub"),
        EstimateDTO("revenue", "current", 1.10e9, "finnhub"),
    ])
    assert exp.estimate_confidence == "MEDIUM"


def test_no_estimates_means_low_confidence():
    exp = build_expectations([])
    assert exp.estimate_confidence == "LOW"
    assert exp.band("eps") is None


def test_beat_is_measured_against_the_least_favourable_edge():
    # Spec example: providers say $1.10bn and $1.14bn, actual $1.16bn
    exp = build_expectations([
        EstimateDTO("revenue", "current", 1.10e9, "finnhub"),
        EstimateDTO("revenue", "current", 1.14e9, "fmp"),
    ])
    conservative, favourable = surprise_pct_vs_band(1.16e9, exp.bands["revenue"])
    assert round(conservative, 1) == 1.8      # vs the highest estimate
    assert round(favourable, 1) == 5.5        # vs the lowest estimate
    assert conservative < favourable


def test_zero_base_does_not_explode_percentages():
    exp = build_expectations([EstimateDTO("eps", "current", 0.0, "finnhub")])
    conservative, favourable = surprise_pct_vs_band(0.10, exp.bands["eps"])
    assert conservative == favourable == 0.0


# ── market analytics ─────────────────────────────────────────────────────────

def test_pct_change_and_runs():
    assert round(pct_change(100.0, 110.0), 2) == 10.0
    closes = [100.0] * 60 + [96.0, 98.0, 100.0, 104.0, 107.0, 107.0]
    run_5d, run_1m, run_3m = compute_runs(closes)
    assert run_5d is not None and run_5d > 0
    assert run_3m is None or isinstance(run_3m, float)


def test_spike_and_fade_is_tagged_as_reversal():
    points = [ReactionPoint(0, 25.0), ReactionPoint(5, 14.0),
              ReactionPoint(10, 4.0), ReactionPoint(15, 0.0)]
    assert classify_reaction(points) == ReactionPattern.POST_EARNINGS_REVERSAL


def test_building_move_is_tagged_as_momentum():
    points = [ReactionPoint(0, 5.0), ReactionPoint(5, 8.0), ReactionPoint(15, 12.0)]
    assert classify_reaction(points) == ReactionPattern.POST_EARNINGS_MOMENTUM


def test_steady_move_has_no_pattern():
    points = [ReactionPoint(0, 6.0), ReactionPoint(15, 6.5)]
    assert classify_reaction(points) == ReactionPattern.NONE


def test_single_point_cannot_be_classified():
    assert classify_reaction([ReactionPoint(0, 10.0)]) == ReactionPattern.NONE


def test_provider_price_conflict_detection():
    assert quotes_conflict(25.0, 0.0, threshold_pct=5.0) is True
    assert quotes_conflict(8.0, 8.4, threshold_pct=5.0) is False


# ── notification format ──────────────────────────────────────────────────────

def test_notification_is_minimal_ticker_and_score():
    title, body = format_notification("ESTC", 9.2)
    assert title == "🔥 ESTC — 9.2/10"
    assert body == "ESTC — 9.2/10"
    assert len(body) < 40


def test_emoji_bands_match_the_spec():
    assert score_emoji(9.3) == "🔥"
    assert score_emoji(8.1) == "🟢"
    assert score_emoji(7.5) == "🟡"
    assert score_emoji(6.3) == "🔴"


def test_unverified_scores_are_marked_in_the_body():
    _, body = format_notification("RBRK", 8.1, needs_verification=True)
    assert "unverified" in body
