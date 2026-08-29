"""Claude adversarial investigation (spec §59-63, §95).

Two passes:
  FAST — cheap triage on headline + opening body. Kills routine items.
  DEEP — adversarial review of the full document plus every deterministic
         figure the quant engines retrieved.

Claude's remit is strictly bounded (§59): messy text, contract wording,
regulatory nuance, hidden negatives, whether information is incremental. It
never supplies a price, a ratio, or a final score, and it never invents a
financial quantity — unknown means null (§63).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import anthropic

from app.catalyst.schemas import DeepInvestigation, FastTriage
from app.config import get_settings

logger = logging.getLogger("earnings_radar.catalyst.investigator")

PROMPT_VERSION = "1.0"

FAST_SYSTEM = """\
You are the triage stage of a catalyst-detection system for US equities. You
see a single news item. Decide cheaply whether it deserves expensive analysis.

Kill it unless it plausibly represents genuinely NEW, company-specific,
economically material information. In particular:
- Commentary ABOUT an earlier announcement is not new information.
- "Company to present at conference", awards lists, appointments: not material.
- Paid promotion, pump-style PR, vague AI/blockchain claims with no economics:
  mark promotional.
- Derivative coverage of an earnings release: mark restates_earnings_release
  so it routes to the earnings pipeline instead.

Be decisive. The majority of items should not warrant deep analysis.
"""

DEEP_SYSTEM = """\
You are the adversarial investigator of a catalyst-detection system for US
equities. Your instruction is explicit:

    TRY TO PROVE THIS IS NOT A MAJOR POSITIVE CATALYST.

Work in this order and do not skip ahead:

1. EXTRACT FACTS FIRST. Populate the structured fields from the document
   verbatim. Every fact carries the exact sentence supporting it. If something
   is not stated, leave it null. NEVER estimate, infer or invent a financial
   quantity — market cap, revenue, guaranteed value and share counts are
   supplied to you by retrieval, and missing values are handled downstream.

2. SEPARATE WHAT IS NEW. State precisely what was already public, what is new
   right now, and what changed. A contract that was announced as "preferred
   bidder" last month and is now signed contains new information: the
   uncertainty has collapsed. A rewritten version of last week's press release
   contains none.

3. READ THE COMMITMENT LANGUAGE. "Has been awarded" and "definitive agreement"
   are worlds apart from "memorandum of understanding", "preferred bidder",
   "up to", "potential value" and "intends to". Classify certainty on the
   evidence, and quote it.

4. HUNT FOR THE OFFSET. Every apparently positive event has a counterweight:
   a ceiling value with no guaranteed orders; a multi-award vehicle shared with
   competitors; an approval with a restrictive label; a trial that met a
   subgroup endpoint but missed the primary; a concurrent equity offering; an
   appeal; an unpaid pilot dressed as a partnership. Find it, or state
   explicitly that you looked and found none.

5. ARGUE AGAINST. In adversarial_findings, give the strongest case that this
   is NOT a major catalyst. If that case is compelling, set invalidate.

Ask yourself: Is this genuinely new? Is the headline exaggerated? Is the money
guaranteed? Does the company actually receive the full value? Is there dilution?
Is the ticker mapping correct? Is the source reliable? Is this merely
promotional? Has the market already reacted?

Missing a questionable candidate is far cheaper than emitting a false 9.
"""


class InvestigationFailed(Exception):
    pass


@dataclass
class InvestigationEvidence:
    """Everything the model is allowed to reason over. Deterministic inputs
    only — no derived opinions, no scores."""

    ticker: str
    company_name: str
    headline: str
    document_text: str
    source_tier: str
    source_urls: list[str] = field(default_factory=list)
    published_at_utc: str | None = None
    classified_event_type: str = "unknown"
    entity_confidence: float = 0.0
    entity_evidence: list[str] = field(default_factory=list)
    prior_public_items: list[dict[str, Any]] = field(default_factory=list)
    detected_certainty: str = "SPECULATIVE"
    novelty: dict[str, Any] = field(default_factory=dict)
    retrieved_financials: dict[str, Any] = field(default_factory=dict)
    market_structure: dict[str, Any] = field(default_factory=dict)
    price_context: dict[str, Any] = field(default_factory=dict)
    engine_detected_offsets: list[dict[str, Any]] = field(default_factory=list)


class CatalystInvestigator:
    def __init__(self, client: anthropic.Anthropic | None = None,
                 fast_model: str | None = None, deep_model: str | None = None):
        settings = get_settings()
        self._settings = settings
        self._client = client or anthropic.Anthropic(
            api_key=settings.anthropic_api_key or None,
            timeout=settings.analysis_timeout_seconds)
        self.fast_model = fast_model or settings.catalyst_fast_model
        self.deep_model = deep_model or settings.analysis_model

    # ── Fast pass ─────────────────────────────────────────────────────────────

    def triage(self, *, ticker: str, headline: str, body: str) -> tuple[FastTriage, int]:
        payload = json.dumps({
            "ticker": ticker,
            "headline": headline,
            "body_excerpt": body[:4000],
        })
        started = time.monotonic()
        last_error: Exception | None = None
        for attempt in range(self._settings.analysis_max_retries + 1):
            try:
                response = self._client.messages.parse(
                    model=self.fast_model,
                    max_tokens=2000,
                    system=FAST_SYSTEM,
                    messages=[{"role": "user", "content": payload}],
                    output_format=FastTriage,
                )
                parsed = response.parsed_output
                if parsed is None:
                    raise InvestigationFailed("no parsed output from triage")
                return parsed, int((time.monotonic() - started) * 1000)
            except (anthropic.APIError, InvestigationFailed, ValueError) as exc:
                last_error = exc
                logger.warning("catalyst triage attempt %d failed: %s", attempt + 1, exc)
        raise InvestigationFailed(f"triage failed after retries: {last_error}")

    # ── Deep pass ─────────────────────────────────────────────────────────────

    def investigate(self, evidence: InvestigationEvidence) -> tuple[DeepInvestigation, int]:
        payload = (
            "Investigate this candidate catalyst adversarially. The evidence "
            "package below is deterministic retrieval — treat every figure in "
            "retrieved_financials, market_structure and price_context as ground "
            "truth, and never restate them as your own estimates.\n\n"
            + json.dumps(asdict(evidence), default=str)
        )
        started = time.monotonic()
        last_error: Exception | None = None
        for attempt in range(self._settings.analysis_max_retries + 1):
            try:
                response = self._client.messages.parse(
                    model=self.deep_model,
                    max_tokens=16000,
                    system=DEEP_SYSTEM,
                    messages=[{"role": "user", "content": payload}],
                    output_format=DeepInvestigation,
                )
                parsed = response.parsed_output
                if parsed is None:
                    raise InvestigationFailed("no parsed output from investigation")
                return parsed, int((time.monotonic() - started) * 1000)
            except (anthropic.APIError, InvestigationFailed, ValueError) as exc:
                last_error = exc
                logger.warning("catalyst investigation attempt %d failed: %s", attempt + 1, exc)
        raise InvestigationFailed(f"investigation failed after retries: {last_error}")

    # ── Guardrail ─────────────────────────────────────────────────────────────

    @staticmethod
    def invented_financials(parsed: DeepInvestigation,
                            retrieved: dict[str, Any],
                            tolerance_pct: float = 2.0) -> list[str]:
        """Catch the model contradicting retrieved fundamentals (§63).

        Only compares fields we actually retrieved; silence about an unknown
        is correct behaviour, not a violation.
        """
        problems: list[str] = []
        checks = {
            "market_cap": retrieved.get("market_cap"),
            "annual_revenue": retrieved.get("annual_revenue"),
        }
        for fact in parsed.facts:
            target = checks.get(fact.name)
            if target is None or fact.value_number is None:
                continue
            base = max(abs(target), 1e-9)
            if abs(fact.value_number - target) / base * 100 > tolerance_pct:
                problems.append(
                    f"{fact.name}: model stated {fact.value_number:,.0f} but retrieval "
                    f"has {target:,.0f}")
        return problems
