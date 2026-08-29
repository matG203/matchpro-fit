"""Catalyst Sentinel unit tests: entities, dedup, novelty, classification,
materiality, negatives, amplification, reaction, scoring."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.catalyst.amplification import (
    MarketStructure,
    assess_amplification,
    assess_execution_quality,
    market_session,
    relative_volume,
    short_interest_freshness,
)
from app.catalyst.classify import classify_event, screen
from app.catalyst.dedup import ClusterCandidate, extract_numbers, is_same_event, tokenise
from app.catalyst.entities import resolve_entity
from app.catalyst.enums import (
    CatalystHalfLife,
    Certainty,
    EventType,
    HaltState,
    RejectReason,
    SourceTier,
)
from app.catalyst.materiality import (
    BuybackInputs,
    CompanyFinancials,
    ContractInputs,
    DealInputs,
    assess_buyback,
    assess_contract,
    assess_deal,
    assess_special_dividend,
    contract_expected_value,
    parse_money,
)
from app.catalyst.negatives import (
    aggregate_severity,
    assess_dilution,
    detect_textual_offsets,
    structural_offsets,
)
from app.catalyst.novelty import PriorMention, assess_novelty, detect_certainty
from app.catalyst.reaction import (
    assess_reaction_room,
    compute_abnormal_move,
    normal_expected_move_pct,
)
from app.catalyst.scoring import ScoringInputs, alert_band, compute_catalyst_score
from app.catalyst.sec_routing import route_filing
from app.domain.timeutil import UTC

NOW = datetime(2026, 8, 27, 14, 30, tzinfo=UTC)


# ── entity resolution (§9) ───────────────────────────────────────────────────

def test_exchange_qualified_ticker_is_near_certain():
    result = resolve_entity(headline="Rocket Lab USA, Inc. (NASDAQ: RKLB) wins contract")
    assert result.ticker == "RKLB"
    assert result.confidence >= 0.95


def test_bare_company_word_does_not_resolve_to_a_ticker():
    """'Apple' in an unrelated context must not become AAPL."""
    result = resolve_entity(headline="Apple harvest hits record in Washington state")
    assert not result.resolved or result.confidence < 0.7


def test_ambiguous_multi_company_story_is_capped():
    result = resolve_entity(
        headline="Sector moves", body="(NASDAQ: AAA) and (NASDAQ: BBB) both rallied",
        provider_tickers=["AAA", "BBB"])
    assert result.ambiguous
    assert result.confidence <= 0.5


def test_ticker_stopwords_are_never_resolved():
    result = resolve_entity(headline="$AI $CEO commentary", provider_tickers=[])
    assert result.ticker not in {"AI", "CEO"}


# ── dedup / clustering (§12) ─────────────────────────────────────────────────

def test_same_event_from_two_wires_clusters_together():
    candidate = ClusterCandidate(
        cluster_key="RKLB|20260827|contract", ticker="RKLB",
        headline="Rocket Lab awarded $1.1 billion Space Force contract",
        tokens=tokenise("Rocket Lab awarded $1.1 billion Space Force contract"),
        numbers=extract_numbers("$1.1 billion"),
        earliest_public_at=NOW)
    match = is_same_event(
        candidate, ticker="RKLB",
        headline="Space Force awards Rocket Lab $1.1 billion contract",
        published_at=NOW + timedelta(minutes=3))
    assert match.matched


def test_different_companies_never_cluster():
    candidate = ClusterCandidate(cluster_key="A", ticker="AAA", headline="x",
                                 tokens={"x"}, earliest_public_at=NOW)
    assert not is_same_event(candidate, ticker="BBB", headline="x").matched


def test_identical_sec_accession_forces_a_match():
    candidate = ClusterCandidate(cluster_key="A", ticker="AAA", headline="unrelated",
                                 tokens={"unrelated"}, earliest_public_at=NOW,
                                 accession_numbers={"000123"})
    assert is_same_event(candidate, ticker="AAA", headline="totally different words",
                         accession="000123").matched


def test_events_far_apart_in_time_do_not_cluster():
    candidate = ClusterCandidate(
        cluster_key="A", ticker="AAA", headline="contract awarded",
        tokens=tokenise("contract awarded"), earliest_public_at=NOW)
    match = is_same_event(candidate, ticker="AAA", headline="contract awarded",
                          published_at=NOW + timedelta(days=10))
    assert not match.matched


# ── certainty language (§17) ─────────────────────────────────────────────────

def test_definitive_agreement_reads_as_executed():
    certainty, _ = detect_certainty("The company has entered into a definitive agreement")
    assert certainty == Certainty.EXECUTED


def test_preferred_bidder_reads_as_intent_only():
    certainty, _ = detect_certainty("The company was selected as preferred bidder")
    assert certainty == Certainty.INTENT


def test_mou_reads_as_intent():
    certainty, _ = detect_certainty("signed a memorandum of understanding")
    assert certainty == Certainty.INTENT


# ── novelty (§13-15) ─────────────────────────────────────────────────────────

def test_first_disclosure_scores_maximum_novelty():
    result = assess_novelty(headline="Acme awarded $250 million Navy contract",
                            published_at=NOW)
    assert result.novelty_score == 10.0
    assert not result.is_restatement


def test_recycled_commentary_is_rejected_as_restatement():
    """§14 — Monday's contract, Tuesday's think-piece."""
    prior = [PriorMention(published_at=NOW - timedelta(days=1),
                          headline="Acme awarded $250 million Navy contract",
                          certainty=Certainty.EXECUTED)]
    result = assess_novelty(
        headline="Acme's $250 million Navy contract could transform growth",
        published_at=NOW, prior_mentions=prior)
    assert result.is_restatement
    assert result.novelty_score < 1.0


def test_preferred_bidder_to_signed_is_incremental_not_restatement():
    """§15 — uncertainty collapsed, so this is genuinely new information."""
    prior = [PriorMention(published_at=NOW - timedelta(days=2),
                          headline="Acme named preferred bidder for Navy programme",
                          certainty=Certainty.INTENT)]
    result = assess_novelty(
        headline="Acme signs definitive agreement for Navy programme",
        body="The company has entered into a definitive agreement.",
        published_at=NOW, prior_mentions=prior)
    assert not result.is_restatement
    assert result.novelty_score > 5.0
    assert result.certainty_after > result.certainty_before


# ── classification and screening (§10-11, §57) ───────────────────────────────

def test_fda_approval_and_acceptance_are_different_events():
    assert classify_event("FDA approves Acme's drug").event_type == EventType.FDA_APPROVAL
    accepted = classify_event("FDA accepts Acme's NDA for review")
    assert accepted.event_type == EventType.FDA_ACCEPTANCE


def test_buyback_authorisation_and_execution_are_distinguished():
    assert classify_event(
        "Board authorizes $1 billion share repurchase program"
    ).event_type == EventType.BUYBACK_AUTHORISATION
    assert classify_event(
        "Company completed $1 billion accelerated share repurchase"
    ).event_type == EventType.BUYBACK_EXECUTED


def test_promotional_content_is_flagged_and_rejected():
    classification = classify_event(
        "This tiny stock could soar 500% — sponsored content")
    assert classification.is_promotional
    result = screen(classification=classification, entity_confidence=0.95,
                    source_tier=SourceTier.NEWSWIRE, is_restatement=False)
    assert not result.passed
    assert result.reject_reason == RejectReason.PROMOTIONAL


def test_social_only_source_cannot_pass_the_screen():
    classification = classify_event("Acme awarded $250 million contract")
    result = screen(classification=classification, entity_confidence=0.95,
                    source_tier=SourceTier.SECONDARY, is_restatement=False)
    assert not result.passed
    assert result.reject_reason == RejectReason.SOCIAL_RUMOUR_ONLY


def test_low_entity_confidence_blocks_the_screen():
    classification = classify_event("Acme awarded $250 million contract")
    result = screen(classification=classification, entity_confidence=0.4,
                    source_tier=SourceTier.NEWSWIRE, is_restatement=False)
    assert not result.passed
    assert result.reject_reason == RejectReason.LOW_ENTITY_CONFIDENCE


def test_earnings_content_routes_away_from_catalyst():
    classification = classify_event("Acme reports second quarter results")
    result = screen(classification=classification, entity_confidence=0.95,
                    source_tier=SourceTier.NEWSWIRE, is_restatement=False)
    assert result.reject_reason == RejectReason.EARNINGS_EVENT


# ── SEC routing (§6) ─────────────────────────────────────────────────────────

def test_8k_item_202_routes_to_earnings():
    route = route_filing("8-K", ["2.02", "9.01"])
    assert route.route_to_earnings
    assert not route.deep_analysis


def test_8k_item_101_is_a_material_agreement_for_catalyst():
    route = route_filing("8-K", ["1.01"])
    assert route.deep_analysis
    assert route.event_type == EventType.COMMERCIAL_CONTRACT


def test_13d_and_13g_route_differently():
    assert route_filing("SC 13D").deep_analysis
    assert not route_filing("SC 13G").deep_analysis


def test_unmonitored_form_is_ignored():
    assert not route_filing("S-8").monitored


# ── contract materiality (§20-21) ────────────────────────────────────────────

def test_guaranteed_value_beats_headline_ceiling():
    value, basis, _ = contract_expected_value(ContractInputs(
        headline_value=1_200_000_000, guaranteed_value=45_000_000,
        certainty=Certainty.EXECUTED))
    assert value == 45_000_000
    assert basis == "guaranteed"


def test_multi_award_ceiling_is_heavily_discounted():
    """§104 — a $5bn vehicle shared with 30 vendors is not $5bn of revenue."""
    value, basis, notes = contract_expected_value(ContractInputs(
        headline_value=5_000_000_000, ceiling_value=5_000_000_000,
        single_award=False, competitors_on_vehicle=30,
        certainty=Certainty.CONDITIONAL))
    assert value is not None
    assert value < 5_000_000_000 * 0.05
    assert "multi-award" in notes[0]


def test_single_award_executed_contract_keeps_most_of_its_value():
    value, _, _ = contract_expected_value(ContractInputs(
        ceiling_value=250_000_000, single_award=True, certainty=Certainty.EXECUTED))
    assert value == 250_000_000


def test_contract_materiality_scales_to_company_size():
    """Same contract, two companies, very different significance."""
    inputs = ContractInputs(headline_value=250_000_000, guaranteed_value=100_000_000,
                            term_years=1, single_award=True, certainty=Certainty.EXECUTED)
    small = assess_contract(inputs, CompanyFinancials(
        market_cap=400e6, annual_revenue=120e6))
    mega = assess_contract(inputs, CompanyFinancials(
        market_cap=3e12, annual_revenue=240e9))
    assert small.materiality_score > 8.0
    assert mega.materiality_score < 2.0


def test_missing_fundamentals_cap_materiality_and_are_recorded():
    result = assess_contract(
        ContractInputs(guaranteed_value=100e6, single_award=True,
                       certainty=Certainty.EXECUTED),
        CompanyFinancials())
    assert result.missing_inputs
    assert not result.data_complete


def test_money_parser_handles_scale_words():
    assert parse_money("valued at $1.1 billion") == 1_100_000_000
    assert parse_money("$45 million contract") == 45_000_000
    assert parse_money("no money here") is None


# ── buyback (§28, §106) ──────────────────────────────────────────────────────

def test_buyback_authorisation_is_not_treated_as_executed():
    """§106 — $1bn authorisation on a $5bn cap is not a 20% repurchase."""
    authorised = assess_buyback(
        BuybackInputs(authorised_amount=1e9, previous_utilisation=0.1,
                      replaces_existing=True),
        CompanyFinancials(market_cap=5e9, free_cash_flow=50e6))
    executed = assess_buyback(
        BuybackInputs(executed_amount=1e9),
        CompanyFinancials(market_cap=5e9, free_cash_flow=2e9))
    assert authorised.expected_value < 1e9 * 0.2
    assert authorised.materiality_score < executed.materiality_score


def test_buyback_capped_by_funding_capacity():
    result = assess_buyback(
        BuybackInputs(authorised_amount=1e9),
        CompanyFinancials(market_cap=5e9, free_cash_flow=20e6))
    assert result.expected_value <= 20e6


# ── special dividend (§29) ───────────────────────────────────────────────────

def test_special_dividend_is_damped_versus_a_contract():
    dividend = assess_special_dividend(
        2.0, None, CompanyFinancials(market_cap=1e9, shares_outstanding=100e6))
    assert dividend.materiality_score < 8.0
    assert "adjusts mechanically" in dividend.notes[0]


# ── M&A (§22-23) ─────────────────────────────────────────────────────────────

def test_takeover_premium_drives_target_score():
    result = assess_deal(
        DealInputs(is_target=True, offer_price_per_share=50.0, current_price=40.0,
                   certainty=Certainty.BINDING), CompanyFinancials())
    assert result.materiality_score > 5.0


def test_acquirer_side_is_not_automatically_bullish():
    target = assess_deal(
        DealInputs(is_target=True, offer_price_per_share=50.0, current_price=40.0,
                   certainty=Certainty.BINDING), CompanyFinancials())
    acquirer = assess_deal(
        DealInputs(is_target=False, purchase_price_total=2e9),
        CompanyFinancials(market_cap=4e9))
    assert acquirer.materiality_score < target.materiality_score


def test_clearance_values_only_the_uncertainty_removed():
    """§23 — clearance is worth the spread × probability change, not the deal."""
    result = assess_deal(
        DealInputs(offer_price_per_share=50.0, current_price=48.0,
                   prior_close_probability=0.6, new_close_probability=0.95),
        CompanyFinancials())
    assert result.basis == "deal_clearance"
    assert result.materiality_score < 8.0


# ── negative offsets (§58) ───────────────────────────────────────────────────

def test_ceiling_language_is_detected_as_an_offset():
    offsets = detect_textual_offsets("The contract has a ceiling of up to $5 billion "
                                     "with no guaranteed order volume")
    descriptions = " ".join(o.description for o in offsets)
    assert "guaranteed order volume" in descriptions


def test_missed_primary_endpoint_is_a_severe_offset():
    offsets = detect_textual_offsets(
        "The study did not meet its primary endpoint but a subgroup showed benefit")
    assert max(o.severity for o in offsets) >= 9.0


def test_concurrent_offering_is_a_severe_offset():
    offsets = detect_textual_offsets(
        "Alongside the approval the company announced a concurrent public offering")
    assert max(o.severity for o in offsets) >= 7.0


def test_worst_offset_dominates_aggregation():
    from app.catalyst.negatives import Offset
    single_severe = aggregate_severity([Offset("fatal", 9.0)])
    three_mild = aggregate_severity([Offset("a", 3.0), Offset("b", 3.0), Offset("c", 3.0)])
    assert single_severe > three_mild


def test_intent_certainty_creates_a_structural_offset():
    offsets = structural_offsets(event_type=EventType.COMMERCIAL_CONTRACT,
                                 certainty=Certainty.INTENT, materiality_missing=[])
    assert any("intent" in o.description for o in offsets)


def test_short_cash_runway_is_a_dilution_offset():
    assessment = assess_dilution(CompanyFinancials(cash=20e6), quarterly_burn=15e6)
    assert assessment.needs_capital
    assert assessment.cash_runway_quarters < 2


# ── market structure (§42-47) ────────────────────────────────────────────────

def test_small_float_amplifies_more_than_mega_cap():
    small = assess_amplification(MarketStructure(
        market_cap=300e6, free_float_shares=12e6, share_price=8.0,
        avg_dollar_volume=8e6, relative_volume=6.0, short_percent_float=22.0,
        short_interest_as_of=NOW - timedelta(days=3), atr_pct=7.0), NOW)
    mega = assess_amplification(MarketStructure(
        market_cap=2e12, free_float_shares=7e9, share_price=200.0,
        avg_dollar_volume=8e9, relative_volume=1.2, short_percent_float=0.8,
        short_interest_as_of=NOW - timedelta(days=3), atr_pct=1.2), NOW)
    assert small.score > mega.score


def test_stale_short_interest_is_discounted_not_trusted():
    """§44 — published short interest lags; never treat it as live."""
    fresh_conf, _ = short_interest_freshness(NOW - timedelta(days=2), NOW)
    stale_conf, stale_days = short_interest_freshness(NOW - timedelta(days=60), NOW)
    assert fresh_conf == 1.0
    assert stale_conf < 0.3
    assert stale_days > 50

    fresh = assess_amplification(MarketStructure(
        market_cap=500e6, free_float_shares=20e6, share_price=10.0,
        short_percent_float=30.0, short_interest_as_of=NOW - timedelta(days=2)), NOW)
    stale = assess_amplification(MarketStructure(
        market_cap=500e6, free_float_shares=20e6, share_price=10.0,
        short_percent_float=30.0, short_interest_as_of=NOW - timedelta(days=60)), NOW)
    assert fresh.score > stale.score


def test_missing_float_is_recorded_not_substituted():
    result = assess_amplification(MarketStructure(
        market_cap=500e6, shares_outstanding=100e6, share_price=5.0), NOW)
    assert "free_float_shares" in result.missing_inputs
    assert result.score <= 7.5


def test_illiquid_stock_is_amplified_but_untradeable():
    """§46 — thin liquidity must not be rewarded in a single blended score."""
    structure = MarketStructure(
        market_cap=80e6, free_float_shares=6e6, share_price=3.0,
        avg_dollar_volume=200_000, spread_pct=8.0, relative_volume=4.0,
        short_percent_float=15.0, short_interest_as_of=NOW - timedelta(days=3),
        atr_pct=9.0)
    amplification = assess_amplification(structure, NOW)
    execution = assess_execution_quality(structure)
    assert amplification.score >= 6.0
    assert not execution.tradeable
    assert execution.score < 4.0


def test_halted_stock_has_zero_execution_quality():
    execution = assess_execution_quality(
        MarketStructure(halt_state=HaltState.NEWS_PENDING))
    assert execution.score == 0.0
    assert not execution.tradeable


def test_market_session_boundaries():
    assert market_session(datetime(2026, 8, 27, 14, 0, tzinfo=UTC)) == "regular"   # 10:00 ET
    assert market_session(datetime(2026, 8, 27, 12, 0, tzinfo=UTC)) == "pre"       # 08:00 ET
    assert market_session(datetime(2026, 8, 27, 21, 0, tzinfo=UTC)) == "post"      # 17:00 ET
    assert market_session(datetime(2026, 8, 29, 14, 0, tzinfo=UTC)) == "closed"    # Saturday


def test_relative_volume_accounts_for_time_of_day():
    at = datetime(2026, 8, 27, 14, 0, tzinfo=UTC)   # 30 min into the session
    rvol = relative_volume(current_volume=500_000, avg_daily_volume=1_000_000, at=at)
    assert rvol is not None and rvol > 3.0


# ── abnormal move and reaction room (§3, §39) ────────────────────────────────

def test_abnormal_move_strips_out_the_market():
    result = compute_abnormal_move(
        price_before=100, price_now=108,
        benchmark_before=100, benchmark_now=103)
    assert result.raw_move_pct == 8.0
    assert result.abnormal_move_pct == 5.0


def test_same_percentage_move_is_not_equally_abnormal():
    """§3 — +6% in a placid mega cap vs a volatile microcap."""
    normal_mega, _ = normal_expected_move_pct(atr_pct=1.0)
    normal_micro, _ = normal_expected_move_pct(atr_pct=9.0)
    mega = compute_abnormal_move(price_before=100, price_now=106,
                                 normal_move_pct=normal_mega)
    micro = compute_abnormal_move(price_before=100, price_now=106,
                                  normal_move_pct=normal_micro)
    assert mega.move_multiple > micro.move_multiple
    assert mega.move_multiple >= 5.0
    assert micro.move_multiple < 1.0


def test_reaction_room_low_when_move_already_exceeds_analogue():
    """§107 — brilliant catalyst, but the move has already happened."""
    abnormal = compute_abnormal_move(price_before=100, price_now=170,
                                     normal_move_pct=8.0)
    room = assess_reaction_room(abnormal=abnormal, analogue_expected_move_pct=25.0)
    assert room.score < 2.0


def test_reaction_room_high_when_barely_moved():
    abnormal = compute_abnormal_move(price_before=100, price_now=101,
                                     normal_move_pct=5.0)
    room = assess_reaction_room(abnormal=abnormal, analogue_expected_move_pct=25.0)
    assert room.score > 8.0


def test_pre_event_runup_reduces_reaction_room():
    abnormal = compute_abnormal_move(price_before=100, price_now=103,
                                     normal_move_pct=5.0)
    clean = assess_reaction_room(abnormal=abnormal, analogue_expected_move_pct=25.0)
    ran_up = assess_reaction_room(abnormal=abnormal, analogue_expected_move_pct=25.0,
                                  pre_event_runup_pct=30.0)
    assert ran_up.score < clean.score


def test_halted_stock_marks_reaction_room_unresolved():
    abnormal = compute_abnormal_move(price_before=100, price_now=100)
    room = assess_reaction_room(abnormal=abnormal, analogue_expected_move_pct=20.0,
                                halt_state=HaltState.NEWS_PENDING)
    assert room.unresolved


def test_missing_price_marks_unresolved():
    abnormal = compute_abnormal_move(price_before=None, price_now=None)
    room = assess_reaction_room(abnormal=abnormal, analogue_expected_move_pct=20.0)
    assert room.unresolved


# ── scoring (§64-76) ─────────────────────────────────────────────────────────

def strong_catalyst(**overrides) -> ScoringInputs:
    base = dict(
        event_type=EventType.GOVERNMENT_CONTRACT, certainty=Certainty.EXECUTED,
        source_tier=SourceTier.PRIMARY, half_life=CatalystHalfLife.STRUCTURAL,
        materiality_score=9.0, materiality_complete=True, novelty_score=10.0,
        information_delta_score=9.0, pre_event_runup_pct=0.5,
        move_amplification=8.5, reaction_room=9.0, execution_quality=8.0,
        negative_offset_severity=0.0, entity_confidence=0.98,
        llm_event_quality=9.0, llm_strategic_significance=9.0,
        event_age_seconds=120, corroborating_primary_sources=1,
        claude_available=True, analogue_sample_size=25)
    base.update(overrides)
    return ScoringInputs(**base)


def test_ideal_catalyst_scores_very_high():
    result = compute_catalyst_score(strong_catalyst())
    assert result.upside_catalyst_score >= 9.0
    assert result.band in ("PUSH", "EXCEPTIONAL")


def test_restatement_is_rejected_outright():
    result = compute_catalyst_score(strong_catalyst(is_restatement=True))
    assert result.rejected
    assert result.upside_catalyst_score == 0.0


def test_claude_invalidation_rejects():
    result = compute_catalyst_score(strong_catalyst(llm_invalidated=True))
    assert result.rejected


def test_secondary_source_cannot_reach_nine():
    result = compute_catalyst_score(strong_catalyst(source_tier=SourceTier.REPUTABLE_NEWS))
    assert result.upside_catalyst_score < 9.0
    assert "source_quality" in result.gates_failed


def test_intent_certainty_caps_at_eight():
    result = compute_catalyst_score(strong_catalyst(certainty=Certainty.INTENT))
    assert result.upside_catalyst_score <= 8.0


def test_severe_negative_offset_collapses_the_score():
    result = compute_catalyst_score(strong_catalyst(negative_offset_severity=9.0))
    assert result.upside_catalyst_score <= 6.0
    assert "negative_offsets" in result.gates_failed


def test_low_reaction_room_prevents_a_fresh_push():
    result = compute_catalyst_score(strong_catalyst(reaction_room=1.0))
    assert result.upside_catalyst_score <= 8.4
    assert "reaction_room" in result.gates_failed


def test_incomplete_materiality_is_capped():
    result = compute_catalyst_score(strong_catalyst(
        materiality_complete=False, materiality_missing=["annual_revenue"]))
    assert result.upside_catalyst_score <= 8.4
    assert "data_completeness" in result.gates_failed


def test_analyst_action_is_structurally_capped():
    result = compute_catalyst_score(strong_catalyst(event_type=EventType.ANALYST_ACTION))
    assert result.upside_catalyst_score <= 7.5


def test_fda_acceptance_capped_below_approval():
    approval = compute_catalyst_score(strong_catalyst(event_type=EventType.FDA_APPROVAL))
    acceptance = compute_catalyst_score(strong_catalyst(event_type=EventType.FDA_ACCEPTANCE))
    assert acceptance.upside_catalyst_score < approval.upside_catalyst_score
    assert acceptance.upside_catalyst_score <= 8.0


def test_unavailable_claude_prevents_nine():
    result = compute_catalyst_score(strong_catalyst(claude_available=False))
    assert result.upside_catalyst_score < 9.0
    assert "claude_review" in result.gates_failed


def test_low_entity_confidence_prevents_nine():
    result = compute_catalyst_score(strong_catalyst(entity_confidence=0.72))
    assert result.upside_catalyst_score < 9.0


def test_halted_stock_caps_the_score():
    result = compute_catalyst_score(strong_catalyst(is_halted=True))
    assert result.upside_catalyst_score <= 8.4


def test_fundamental_impact_and_immediate_reaction_are_separate():
    """§54 — a structural contract with little room left should show high
    fundamental impact but modest immediate potential."""
    result = compute_catalyst_score(strong_catalyst(
        reaction_room=1.0, move_amplification=3.0))
    assert result.fundamental_impact > result.immediate_reaction_potential


def test_alert_bands_match_the_spec():
    assert alert_band(9.6) == "EXCEPTIONAL"
    assert alert_band(9.1) == "PUSH"
    assert alert_band(8.7) == "VERY_STRONG"
    assert alert_band(8.2) == "INTERESTING"
    assert alert_band(7.3) == "STORE"
    assert alert_band(6.5) == "IGNORE"


def test_nine_five_requires_everything_simultaneously():
    almost = compute_catalyst_score(strong_catalyst(negative_offset_severity=3.5))
    assert almost.upside_catalyst_score < 9.5
