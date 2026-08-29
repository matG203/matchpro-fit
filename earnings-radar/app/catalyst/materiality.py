"""Economic materiality (spec §18-21, §28-31).

The same headline means wildly different things depending on the company.
"$250m contract" is transformative for a $400m-cap firm with $120m revenue and
a rounding error for Microsoft. Everything here is arithmetic on retrieved
fundamentals — Claude supplies structure, never the numbers (§63).

Missing inputs are recorded, never guessed. A materiality score computed from
incomplete data is capped and flagged so scoring can penalise it honestly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.catalyst.enums import CERTAINTY_VALUE, Certainty, EventType

_MULTIPLIERS = {
    "trillion": 1e12, "tn": 1e12, "t": 1e12,
    "billion": 1e9, "bn": 1e9, "b": 1e9,
    "million": 1e6, "mn": 1e6, "mm": 1e6, "m": 1e6,
    "thousand": 1e3, "k": 1e3,
}

_MONEY = re.compile(
    r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s*"
    r"(trillion|billion|million|thousand|tn|bn|mn|mm|[tbmk])?\b",
    re.IGNORECASE)


def parse_money(text: str) -> float | None:
    """First dollar amount in a string, scaled. None when absent."""
    match = _MONEY.search(text or "")
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = (match.group(2) or "").lower()
    return value * _MULTIPLIERS.get(unit, 1.0)


def parse_all_money(text: str) -> list[float]:
    out: list[float] = []
    for match in _MONEY.finditer(text or ""):
        try:
            value = float(match.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = (match.group(2) or "").lower()
        out.append(value * _MULTIPLIERS.get(unit, 1.0))
    return out


@dataclass
class CompanyFinancials:
    """Fundamentals as at decision time. All optional — absence is signal."""

    market_cap: float | None = None
    enterprise_value: float | None = None
    annual_revenue: float | None = None
    ebitda: float | None = None
    net_income: float | None = None
    free_cash_flow: float | None = None
    cash: float | None = None
    debt: float | None = None
    shares_outstanding: float | None = None
    backlog: float | None = None
    share_price: float | None = None

    def missing(self, *names: str) -> list[str]:
        return [n for n in names if getattr(self, n, None) in (None, 0)]


@dataclass
class MaterialityResult:
    materiality_score: float                    # 0-10
    headline_value: float | None = None
    guaranteed_value: float | None = None
    expected_value: float | None = None
    annualised_value: float | None = None
    value_to_market_cap: float | None = None
    value_to_revenue: float | None = None
    annualised_to_revenue: float | None = None
    value_to_ebitda: float | None = None
    estimated_eps_impact: float | None = None
    basis: str = ""
    missing_inputs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def data_complete(self) -> bool:
        return not self.missing_inputs


def _score_from_ratio(ratio: float) -> float:
    """Map economic significance to 0-10 on a log-ish curve.

    Anchors chosen so that: 1% of revenue ≈ 2, 10% ≈ 5, 50% ≈ 8, 200%+ ≈ 10.
    """
    if ratio <= 0:
        return 0.0
    if ratio >= 2.0:
        return 10.0
    if ratio >= 0.5:
        return 8.0 + (ratio - 0.5) / 1.5 * 2.0
    if ratio >= 0.10:
        return 5.0 + (ratio - 0.10) / 0.40 * 3.0
    if ratio >= 0.01:
        return 2.0 + (ratio - 0.01) / 0.09 * 3.0
    return ratio / 0.01 * 2.0


# ── Contracts (§20-21) ───────────────────────────────────────────────────────


@dataclass
class ContractInputs:
    headline_value: float | None = None
    guaranteed_value: float | None = None
    funded_value: float | None = None
    ceiling_value: float | None = None
    term_years: float | None = None
    single_award: bool | None = None
    competitors_on_vehicle: int | None = None
    certainty: Certainty = Certainty.SPECULATIVE
    is_extension: bool | None = None


def contract_expected_value(inputs: ContractInputs) -> tuple[float | None, str, list[str]]:
    """Probability-weighted value the company can actually expect.

    The rule that matters (§20): a multi-award ceiling is NOT revenue. Where a
    vehicle has N eligible suppliers and nothing is guaranteed, the expected
    share is a fraction of the ceiling, heavily discounted for certainty.
    """
    notes: list[str] = []

    # Funded/guaranteed money is real money.
    committed = inputs.funded_value if inputs.funded_value is not None else inputs.guaranteed_value
    if committed is not None:
        basis = "funded" if inputs.funded_value is not None else "guaranteed"
        notes.append(f"using {basis} value — the only contractually committed amount")
        return committed, basis, notes

    ceiling = inputs.ceiling_value if inputs.ceiling_value is not None else inputs.headline_value
    if ceiling is None:
        return None, "unknown", ["no contract value could be established"]

    if inputs.single_award is False:
        n = inputs.competitors_on_vehicle
        share = 1.0 / n if n and n > 0 else 0.15
        notes.append(
            f"multi-award vehicle: headline ceiling is shared across "
            f"{n if n else 'an unknown number of'} suppliers — expected share {share:.0%}")
        value = ceiling * share * CERTAINTY_VALUE[inputs.certainty]
        notes.append(f"discounted for {inputs.certainty.value.lower()} certainty")
        return value, "ceiling_multi_award_discounted", notes

    if inputs.single_award is None:
        notes.append("award structure unknown — assuming shared ceiling, heavily discounted")
        value = ceiling * 0.25 * CERTAINTY_VALUE[inputs.certainty]
        return value, "ceiling_unknown_structure", notes

    notes.append("single-award vehicle: full ceiling is addressable")
    value = ceiling * CERTAINTY_VALUE[inputs.certainty]
    notes.append(f"discounted for {inputs.certainty.value.lower()} certainty")
    return value, "ceiling_single_award", notes


def assess_contract(inputs: ContractInputs,
                    financials: CompanyFinancials) -> MaterialityResult:
    expected, basis, notes = contract_expected_value(inputs)
    missing = financials.missing("market_cap", "annual_revenue")

    annualised = None
    if expected is not None and inputs.term_years and inputs.term_years > 0:
        annualised = expected / inputs.term_years
        notes.append(f"annualised over {inputs.term_years:g} years")

    result = MaterialityResult(
        materiality_score=0.0,
        headline_value=inputs.headline_value or inputs.ceiling_value,
        guaranteed_value=inputs.guaranteed_value if inputs.guaranteed_value is not None
        else inputs.funded_value,
        expected_value=expected,
        annualised_value=annualised,
        basis=basis,
        missing_inputs=missing,
        notes=notes,
    )

    if expected is None:
        result.notes.append("no expected value — materiality cannot be computed")
        return result

    if financials.market_cap:
        result.value_to_market_cap = expected / financials.market_cap
    if financials.annual_revenue:
        result.value_to_revenue = expected / financials.annual_revenue
        if annualised is not None:
            result.annualised_to_revenue = annualised / financials.annual_revenue
    if financials.ebitda and financials.ebitda > 0:
        result.value_to_ebitda = expected / financials.ebitda

    # Prefer the annualised revenue ratio: a 10-year contract worth 1x revenue
    # is far less significant per year than a 1-year one.
    ratio = None
    if result.annualised_to_revenue is not None:
        ratio = result.annualised_to_revenue
        result.basis += "|annualised_vs_revenue"
    elif result.value_to_revenue is not None:
        ratio = result.value_to_revenue
        result.basis += "|value_vs_revenue"
    elif result.value_to_market_cap is not None:
        ratio = result.value_to_market_cap
        result.basis += "|value_vs_market_cap"

    if ratio is None:
        result.notes.append("no fundamentals available to scale the contract against")
        return result

    score = _score_from_ratio(ratio)
    if inputs.is_extension:
        score *= 0.6
        result.notes.append("extension of existing work — incremental value discounted")
    if missing:
        score = min(score, 7.0)
        result.notes.append(f"capped: missing fundamentals {missing}")
    result.materiality_score = round(min(score, 10.0), 2)
    return result


# ── Buybacks (§28) ───────────────────────────────────────────────────────────


@dataclass
class BuybackInputs:
    authorised_amount: float | None = None
    executed_amount: float | None = None
    replaces_existing: bool | None = None
    previous_utilisation: float | None = None    # 0-1 of prior programme used
    expected_annual_execution: float | None = None


def assess_buyback(inputs: BuybackInputs,
                   financials: CompanyFinancials) -> MaterialityResult:
    """An authorisation is permission, not a purchase. Only executed money —
    or credibly fundable, historically-executed money — counts."""
    notes: list[str] = []
    missing = financials.missing("market_cap")

    if inputs.executed_amount is not None:
        effective = inputs.executed_amount
        basis = "executed"
        notes.append("executed repurchase — cash actually deployed")
    elif inputs.authorised_amount is not None:
        basis = "authorisation_discounted"
        utilisation = inputs.previous_utilisation
        if utilisation is None:
            factor = 0.4
            notes.append("no execution history — assuming 40% of authorisation is used")
        else:
            factor = max(0.05, min(1.0, utilisation))
            notes.append(f"prior programme utilisation {utilisation:.0%} applied")
        effective = inputs.authorised_amount * factor

        # Can they even fund it? (§28)
        fundable = None
        if financials.free_cash_flow is not None:
            fundable = max(financials.free_cash_flow, 0.0)
        elif financials.cash is not None:
            fundable = max(financials.cash * 0.5, 0.0)
        if fundable is not None and effective > fundable:
            notes.append(
                f"capped by funding capacity: effective {effective:,.0f} exceeds "
                f"available {fundable:,.0f}")
            effective = fundable
        if inputs.replaces_existing:
            notes.append("replaces an existing programme — incremental capacity is lower")
            effective *= 0.5
    else:
        return MaterialityResult(0.0, basis="unknown", missing_inputs=missing,
                                 notes=["no buyback amount stated"])

    result = MaterialityResult(
        materiality_score=0.0,
        headline_value=inputs.authorised_amount or inputs.executed_amount,
        expected_value=effective, basis=basis, missing_inputs=missing, notes=notes)

    if financials.market_cap:
        result.value_to_market_cap = effective / financials.market_cap
        score = _score_from_ratio(result.value_to_market_cap * 1.5)
        if missing:
            score = min(score, 7.0)
        result.materiality_score = round(min(score, 10.0), 2)
    else:
        result.notes.append("no market cap — buyback significance cannot be scaled")
    return result


# ── Special dividends (§29) ──────────────────────────────────────────────────


def assess_special_dividend(amount_per_share: float | None, total_payout: float | None,
                            financials: CompanyFinancials) -> MaterialityResult:
    """Price mechanically adjusts on the ex-date — a special dividend is not
    free upside, so it is scored conservatively."""
    notes = ["price adjusts mechanically on ex-date; yield is not abnormal upside"]
    missing = financials.missing("market_cap")

    if total_payout is None and amount_per_share and financials.shares_outstanding:
        total_payout = amount_per_share * financials.shares_outstanding

    result = MaterialityResult(0.0, headline_value=total_payout,
                               expected_value=total_payout, basis="special_dividend",
                               missing_inputs=missing, notes=notes)
    if total_payout and financials.market_cap:
        result.value_to_market_cap = total_payout / financials.market_cap
        # Deliberately damped relative to a contract of the same size.
        result.materiality_score = round(
            min(_score_from_ratio(result.value_to_market_cap) * 0.6, 10.0), 2)
    if financials.cash and total_payout:
        if total_payout > financials.cash:
            result.notes.append("payout exceeds cash on hand — likely debt-funded")
    return result


# ── M&A (§22-23) ─────────────────────────────────────────────────────────────


@dataclass
class DealInputs:
    is_target: bool | None = None
    offer_price_per_share: float | None = None
    current_price: float | None = None
    purchase_price_total: float | None = None
    consideration_type: str | None = None
    financing_secured: bool | None = None
    certainty: Certainty = Certainty.CONDITIONAL
    prior_close_probability: float | None = None   # for clearance events (§23)
    new_close_probability: float | None = None


def assess_deal(inputs: DealInputs, financials: CompanyFinancials) -> MaterialityResult:
    """Target: premium is the catalyst. Acquirer: an acquisition is NOT
    automatically bullish (§22)."""
    notes: list[str] = []
    missing: list[str] = []

    # Regulatory clearance of an existing deal: value is the reduction in
    # uncertainty, not the whole premium (§23).
    if inputs.prior_close_probability is not None and inputs.new_close_probability is not None:
        delta = inputs.new_close_probability - inputs.prior_close_probability
        premium = None
        if inputs.offer_price_per_share and inputs.current_price:
            premium = (inputs.offer_price_per_share - inputs.current_price) / inputs.current_price
        notes.append(
            f"clearance event: close probability {inputs.prior_close_probability:.0%} → "
            f"{inputs.new_close_probability:.0%}")
        if premium is None:
            notes.append("no deal spread available — cannot value the uncertainty reduction")
            return MaterialityResult(0.0, basis="deal_clearance",
                                     missing_inputs=["deal_spread"], notes=notes)
        captured = max(delta, 0.0) * premium
        notes.append(f"expected repricing ≈ {captured:.1%} (spread {premium:.1%} × Δp {delta:.0%})")
        return MaterialityResult(
            materiality_score=round(min(_score_from_ratio(captured * 4), 10.0), 2),
            expected_value=None, basis="deal_clearance", notes=notes)

    if inputs.is_target:
        if not (inputs.offer_price_per_share and inputs.current_price):
            missing.append("offer_or_current_price")
            return MaterialityResult(0.0, basis="takeover_target",
                                     missing_inputs=missing,
                                     notes=["cannot compute premium without both prices"])
        premium = (inputs.offer_price_per_share - inputs.current_price) / inputs.current_price
        notes.append(f"offer premium {premium:.1%}")
        if inputs.consideration_type == "stock":
            notes.append("stock consideration — realised value moves with the acquirer")
        if inputs.financing_secured is False:
            notes.append("financing not secured — completion risk elevated")
        score = _score_from_ratio(max(premium, 0.0) * 2.5)
        score *= CERTAINTY_VALUE[inputs.certainty] * 1.15
        return MaterialityResult(
            materiality_score=round(min(score, 10.0), 2),
            headline_value=inputs.purchase_price_total,
            basis="takeover_target", notes=notes)

    # Acquirer side.
    notes.append("acquirer side — an acquisition is not automatically positive")
    if inputs.purchase_price_total and financials.market_cap:
        ratio = inputs.purchase_price_total / financials.market_cap
        notes.append(f"purchase price is {ratio:.0%} of acquirer market cap")
        if ratio > 0.5:
            notes.append("large relative to acquirer — integration and funding risk material")
        # Deliberately muted: acquirers often fall on announcement.
        score = min(_score_from_ratio(ratio) * 0.35, 5.0)
        return MaterialityResult(materiality_score=round(score, 2),
                                 headline_value=inputs.purchase_price_total,
                                 value_to_market_cap=ratio,
                                 basis="acquirer", notes=notes)
    return MaterialityResult(0.0, basis="acquirer",
                             missing_inputs=["purchase_price_or_market_cap"], notes=notes)


# ── Legal awards (§31) ───────────────────────────────────────────────────────


def assess_legal_award(gross_amount: float | None, *, appeal_likely: bool | None,
                       insurance_covered: float | None,
                       financials: CompanyFinancials) -> MaterialityResult:
    """Headline damages are not cash received."""
    notes: list[str] = []
    missing = financials.missing("market_cap")
    if gross_amount is None:
        return MaterialityResult(0.0, basis="legal", missing_inputs=["gross_amount"],
                                 notes=["no monetary amount stated"])

    net = gross_amount
    if insurance_covered:
        net -= insurance_covered
        notes.append(f"insurance covers {insurance_covered:,.0f}")
    if appeal_likely is not False:
        net *= 0.5
        notes.append("appeal risk — collection probability discounted to 50%")
    notes.append("gross award is not cash received; tax and legal costs not modelled")

    result = MaterialityResult(0.0, headline_value=gross_amount, expected_value=net,
                               basis="legal_award", missing_inputs=missing, notes=notes)
    if financials.market_cap:
        result.value_to_market_cap = net / financials.market_cap
        score = _score_from_ratio(result.value_to_market_cap * 1.2)
        if missing:
            score = min(score, 7.0)
        result.materiality_score = round(min(score, 10.0), 2)
    return result


# ── Router ───────────────────────────────────────────────────────────────────

_MATERIALITY_ROUTER = {
    EventType.GOVERNMENT_CONTRACT, EventType.COMMERCIAL_CONTRACT, EventType.CUSTOMER_WIN,
    EventType.SUPPLY_AGREEMENT, EventType.DISTRIBUTION_AGREEMENT, EventType.LICENSING_DEAL,
}


def is_contract_event(event_type: EventType) -> bool:
    return event_type in _MATERIALITY_ROUTER
