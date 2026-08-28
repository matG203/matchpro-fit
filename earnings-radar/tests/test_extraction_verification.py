"""Financial extraction, release verification and deduplication."""
from __future__ import annotations

from app.domain.canonical import canonical_release_key
from app.services.extraction import extract_financials
from app.services.verification import infer_fiscal_period, verify_release_document

RESULTS_RELEASE = """
Elastic N.V. (NYSE: ESTC) Reports Second Quarter Fiscal 2026 Financial Results

SAN FRANCISCO — Elastic today announced financial results for its second
quarter ended July 31, 2026. Total revenue of $427.3 million, up 18% year over
year. GAAP diluted earnings per share of $0.21. Non-GAAP diluted earnings per
share of $0.59. Gross margin of 76.4%. Net cash provided by operating
activities of $88.2 million. Free cash flow of $81.5 million.
For the three months ended July 31, 2026, the Company reported...
"""

SCHEDULING_NOTICE = """
Elastic N.V. (NYSE: ESTC) Announces Date of Second Quarter Fiscal 2026
Financial Results

Elastic today announced that it will report financial results for its second
quarter fiscal 2026 after market close on August 27, 2026. Elastic invites you
to join the conference call and webcast at 4:30 p.m. Eastern Time.
"""

PREVIOUS_QUARTER = """
Elastic N.V. (NYSE: ESTC) Reports First Quarter Fiscal 2026 Financial Results
Total revenue of $393.1 million. GAAP diluted earnings per share of $0.11.
For the three months ended April 30, 2026, the Company reported...
"""


# ── extraction ───────────────────────────────────────────────────────────────

def test_revenue_is_extracted_with_millions_multiplier():
    result = extract_financials(RESULTS_RELEASE)
    assert result.value("revenue") == 427_300_000


def test_gaap_and_adjusted_eps_are_extracted_separately():
    result = extract_financials(RESULTS_RELEASE)
    assert result.value("eps_diluted") == 0.21
    assert result.value("eps_adjusted") == 0.59


def test_cash_flow_and_margins_are_extracted():
    result = extract_financials(RESULTS_RELEASE)
    assert result.value("operating_cash_flow") == 88_200_000
    assert result.value("free_cash_flow") == 81_500_000
    assert result.value("gross_margin_pct") == 76.4


def test_missing_metrics_are_absent_not_guessed():
    result = extract_financials("A short note with no financial detail.")
    assert result.value("revenue") is None
    assert result.facts == {}


def test_billions_multiplier_is_handled():
    result = extract_financials("Total revenue of $1.16 billion for the quarter.")
    assert result.value("revenue") == 1_160_000_000


def test_loss_per_share_is_negative():
    result = extract_financials(
        "GAAP diluted net loss per share of $(0.34) for the three months ended.")
    assert result.value("eps_diluted") == -0.34


def test_every_fact_carries_confidence_and_snippet():
    fact = extract_financials(RESULTS_RELEASE).facts["revenue"]
    assert 0 < fact.confidence <= 1.0
    assert "427.3" in fact.snippet


# ── verification ─────────────────────────────────────────────────────────────

def test_real_results_release_verifies():
    result = verify_release_document(
        text=RESULTS_RELEASE, ticker="ESTC", company_name="Elastic N.V.",
        expected_fy=2026, expected_fq=2, document_type="8-K")
    assert result.verified is True
    assert (result.fiscal_year, result.fiscal_quarter) == (2026, 2)


def test_scheduling_notice_is_rejected():
    result = verify_release_document(
        text=SCHEDULING_NOTICE, ticker="ESTC", company_name="Elastic N.V.",
        expected_fy=2026, expected_fq=2)
    assert result.verified is False
    assert "placeholder" in result.reasons[0]


def test_previous_quarter_report_is_rejected():
    result = verify_release_document(
        text=PREVIOUS_QUARTER, ticker="ESTC", company_name="Elastic N.V.",
        expected_fy=2026, expected_fq=2)
    assert result.verified is False
    assert "mismatch" in result.reasons[-1]


def test_wrong_company_document_is_rejected():
    result = verify_release_document(
        text=RESULTS_RELEASE, ticker="AFRM", company_name="Affirm Holdings",
        expected_fy=2026, expected_fq=2)
    assert result.verified is False


def test_fiscal_period_inference_handles_multiple_phrasings():
    assert infer_fiscal_period("Second Quarter Fiscal 2026 results") == (2026, 2)
    assert infer_fiscal_period("Q3 FY2026 highlights") == (2026, 3)
    assert infer_fiscal_period("no period mentioned") == (None, None)


# ── deduplication ────────────────────────────────────────────────────────────

def test_same_release_from_three_sources_shares_one_canonical_key():
    keys = {canonical_release_key("ESTC", 2026, 2) for _ in range(3)}
    assert len(keys) == 1


def test_different_quarters_are_distinct_releases():
    assert canonical_release_key("ESTC", 2026, 2) != canonical_release_key("ESTC", 2026, 3)
