"""Entity resolution (spec §9).

Maps an inbound item to exactly one company, with an explicit confidence.
A false mapping is worse than no mapping: "Apple" in a story about fruit
imports must never become AAPL. Below the configured threshold we refuse to
alert at all.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Words that look like tickers but almost never are, in prose.
_TICKER_STOPWORDS = {
    "A", "I", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "IF", "IN", "IS", "IT",
    "NO", "OF", "ON", "OR", "SO", "TO", "UP", "US", "WE", "AI", "CEO", "CFO",
    "FDA", "SEC", "USA", "GDP", "CPI", "ETF", "IPO", "EPS", "NYSE", "PDF",
    "NEW", "ALL", "AND", "FOR", "THE", "OUT", "NOW", "ONE", "TWO", "MAY", "CAN",
}

# "(NASDAQ: RKLB)" / "(NYSE: ESTC)" / "(Nasdaq:RKLB)" — the strongest signal
_EXCHANGE_TICKER = re.compile(
    r"\((?:NASDAQ|NYSE|NYSE\s+AMERICAN|AMEX|OTC|OTCQB|OTCQX|CBOE)\s*:\s*([A-Z][A-Z.\-]{0,6})\)",
    re.IGNORECASE)
# "$RKLB" cashtag
_CASHTAG = re.compile(r"\$([A-Z][A-Z.\-]{0,5})\b")


@dataclass
class EntityResolution:
    ticker: str | None = None
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    ambiguous: bool = False

    @property
    def resolved(self) -> bool:
        return bool(self.ticker) and self.confidence > 0.0


def _normalise_name(name: str) -> str:
    name = name.lower()
    for suffix in (" incorporated", " inc.", " inc", " corporation", " corp.", " corp",
                   " company", " co.", " plc", " ltd.", " ltd", " limited", " n.v.",
                   " nv", " s.a.", " sa", " holdings", " group", " technologies",
                   " therapeutics", " pharmaceuticals", ","):
        name = name.replace(suffix, " ")
    return re.sub(r"[^a-z0-9 ]+", " ", name).strip()


def resolve_entity(*, headline: str, body: str = "",
                   provider_tickers: list[str] | None = None,
                   known_companies: dict[str, str] | None = None,
                   aliases: dict[str, str] | None = None) -> EntityResolution:
    """Resolve one item to a ticker.

    known_companies: {TICKER: company name}
    aliases:         {alias text: TICKER} for subsidiaries/brands
    Confidence is capped below the alert threshold when several distinct
    companies are plausible (§9).
    """
    text = f"{headline}\n{body}"
    scores: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}

    def add(ticker: str, weight: float, why: str) -> None:
        ticker = ticker.upper().strip()
        if not ticker or ticker in _TICKER_STOPWORDS:
            return
        scores[ticker] = max(scores.get(ticker, 0.0), weight)
        evidence.setdefault(ticker, []).append(why)

    # 1. Explicit exchange-qualified ticker — near certainty.
    for match in _EXCHANGE_TICKER.finditer(text):
        add(match.group(1), 0.98, f"exchange-qualified ticker '{match.group(0).strip()}'")

    # 2. Provider-supplied tickers — reliable but occasionally over-broad
    #    (wires tag peers on sector stories).
    for ticker in provider_tickers or []:
        add(ticker, 0.85, f"provider tagged {ticker.upper()}")

    # 3. Company-name match against the known universe.
    if known_companies:
        haystack = _normalise_name(text)
        for ticker, name in known_companies.items():
            norm = _normalise_name(name)
            if len(norm) < 4:
                continue
            if re.search(rf"\b{re.escape(norm)}\b", haystack):
                add(ticker, 0.8, f"company name '{name}' matched")

    # 4. Aliases / subsidiaries / brands.
    if aliases:
        lowered = text.lower()
        for alias, ticker in aliases.items():
            if len(alias) >= 4 and alias.lower() in lowered:
                add(ticker, 0.72, f"alias '{alias}' matched")

    # 5. Cashtags — weak on their own; typical of social sources.
    for match in _CASHTAG.finditer(text):
        add(match.group(1), 0.45, f"cashtag ${match.group(1)}")

    if not scores:
        return EntityResolution(evidence=["no ticker or company name identified"])

    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top_ticker, top_score = ranked[0]
    candidates = [t for t, _ in ranked]

    # Several distinct companies at comparable strength → ambiguous.
    ambiguous = len(ranked) > 1 and (ranked[0][1] - ranked[1][1]) < 0.15
    confidence = top_score
    if ambiguous:
        confidence = min(confidence, 0.5)

    # Corroboration from a second independent signal raises confidence.
    if len(evidence.get(top_ticker, [])) > 1 and not ambiguous:
        confidence = min(0.99, confidence + 0.05)

    return EntityResolution(
        ticker=top_ticker,
        confidence=round(confidence, 3),
        evidence=evidence.get(top_ticker, []),
        candidates=candidates,
        ambiguous=ambiguous,
    )
