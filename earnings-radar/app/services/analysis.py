"""EarningsAnalysisService — the LLM layer.

Uses Anthropic structured outputs (`messages.parse`) with the strict
AnalysisOutput schema, so responses are schema-constrained at generation time
and re-validated server-side. The prompt carries ONLY deterministically
retrieved evidence; the model must return null for anything unavailable.
Numeric echoes are cross-checked against the deterministic extraction.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass

import anthropic

from app.config import get_settings
from app.domain.schemas import AnalysisOutput
from app.services.expectations import Expectations
from app.services.extraction import ExtractionResult
from app.services.marketdata import MarketContextData

logger = logging.getLogger("earnings_radar.analysis")

PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = """\
You are the analysis engine of an earnings-trading system. You receive an
earnings press release plus deterministically retrieved evidence (consensus
bands, price context, prior guidance, KPI history). Your job is adversarial
earnings analysis, answering: did this company release material NEW
information better than what the market had TRULY priced in?

Hard rules:
- NEVER invent numbers. Every figure you cite must come from the supplied
  evidence or the release text. If something is unavailable, use null.
- Bullish items already public before this release (pre-announced contracts,
  customers, guidance updates, financings) get little or no incremental
  surprise credit — list them in pre_announced_news.
- One-off items (tax valuation allowance releases, impairments, gains on
  sale, crypto fair-value moves, settlements) must not inflate
  earnings_quality; set eps_dominated_by_one_offs when applicable.
- A guidance "raise" that only lifts the bottom of the range is modest, not
  major. Separate organic changes from acquisition/FX contributions.
- Judge sequential (Q-2, Q-1, current) trends, not just YoY.
- Actively hunt for hidden negatives: decelerating ARR/RPO, margin or FCF
  deterioration, NRR below 100%, dilution/ATM, rising SBC, customer
  concentration, credit deterioration, inventory problems.
- Scores are conservative: 9+ sub-scores are rare; a mixed report is 5-7.
- The consensus band shows provider disagreement; when wide, judge the beat
  against its least favourable edge and lower your confidence.
"""


@dataclass
class AnalysisEvidence:
    ticker: str
    company_name: str
    fiscal_year: int
    fiscal_quarter: int
    release_text: str
    extracted_facts: dict
    consensus: dict
    market_context: dict
    prior_guidance: dict | None = None
    kpi_history: dict | None = None
    kpi_profile: dict | None = None


class AnalysisFailed(Exception):
    pass


class EarningsAnalysisService:
    def __init__(self, client: anthropic.Anthropic | None = None):
        settings = get_settings()
        self._settings = settings
        self._client = client or anthropic.Anthropic(
            api_key=settings.anthropic_api_key or None,
            timeout=settings.analysis_timeout_seconds,
        )

    def build_evidence(self, *, ticker: str, company_name: str, fiscal_year: int,
                       fiscal_quarter: int, release_text: str,
                       extraction: ExtractionResult, expectations: Expectations,
                       market: MarketContextData, prior_guidance: dict | None = None,
                       kpi_history: dict | None = None,
                       kpi_profile: dict | None = None) -> AnalysisEvidence:
        return AnalysisEvidence(
            ticker=ticker,
            company_name=company_name,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            release_text=release_text[:60000],
            extracted_facts={k: asdict(v) for k, v in extraction.facts.items()},
            consensus={
                "estimate_confidence": expectations.estimate_confidence,
                "notes": expectations.notes,
                "bands": {m: {"low": b.low, "high": b.high, "mid": b.mid,
                              "providers": b.providers, "disagreement": b.disagreement}
                          for m, b in expectations.bands.items()},
            },
            market_context={
                "prev_close": market.prev_close,
                "pre_release_price": market.pre_release_price,
                "run_5d_pct": market.run_5d_pct,
                "run_1m_pct": market.run_1m_pct,
                "run_3m_pct": market.run_3m_pct,
                "implied_move_pct": market.implied_move_pct,
                "initial_reaction_pct": market.initial_reaction_pct,
                "current_reaction_pct": market.current_reaction_pct,
                "reaction_vs_prev_close_pct": market.reaction_vs_prev_close_pct,
                "reaction_pattern": market.reaction_pattern.value,
                "market_data_unresolved": market.unresolved,
            },
            prior_guidance=prior_guidance,
            kpi_history=kpi_history,
            kpi_profile=kpi_profile,
        )

    def analyse(self, evidence: AnalysisEvidence) -> AnalysisOutput:
        user_content = (
            "Analyse this earnings release. Evidence package (deterministic "
            "retrieval; treat as ground truth; nulls mean unavailable):\n\n"
            + json.dumps(asdict(evidence), default=str)
        )
        last_error: Exception | None = None
        for attempt in range(self._settings.analysis_max_retries + 1):
            try:
                response = self._client.messages.parse(
                    model=self._settings.analysis_model,
                    max_tokens=16000,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_content}],
                    output_format=AnalysisOutput,
                )
                parsed = response.parsed_output
                if parsed is None:
                    raise AnalysisFailed("no parsed output in response")
                if parsed.ticker.upper() != evidence.ticker.upper():
                    raise AnalysisFailed(
                        f"analysis ticker mismatch: {parsed.ticker} != {evidence.ticker}")
                return parsed
            except (anthropic.APIError, AnalysisFailed, ValueError) as exc:
                last_error = exc
                logger.warning("analysis attempt %d failed: %s", attempt + 1, exc)
        raise AnalysisFailed(f"analysis failed after retries: {last_error}")

    @staticmethod
    def fact_mismatch(parsed: AnalysisOutput, extraction: ExtractionResult,
                      tolerance_pct: float = 2.0) -> bool:
        """True when the LLM's echoed numbers disagree with deterministic
        extraction — a hallucination tripwire that lowers confidence."""
        checks = [
            (parsed.facts.eps_actual,
             extraction.value("eps_adjusted") or extraction.value("eps_diluted")),
            (parsed.facts.revenue_actual, extraction.value("revenue")),
        ]
        for llm_value, det_value in checks:
            if llm_value is None or det_value is None:
                continue
            base = max(abs(det_value), 1e-9)
            if abs(llm_value - det_value) / base * 100 > tolerance_pct:
                return True
        return False
