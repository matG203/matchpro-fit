"""Canonical release identity used for deduplication.

One earnings release may surface via SEC, Business Wire and the company IR
page within seconds of each other. All of them collapse onto one canonical
key so the pipeline runs exactly once per fiscal quarter.
"""
from __future__ import annotations


def canonical_release_key(ticker: str, fiscal_year: int, fiscal_quarter: int) -> str:
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("ticker required")
    if not 1 <= fiscal_quarter <= 4:
        raise ValueError(f"fiscal_quarter must be 1-4, got {fiscal_quarter}")
    if fiscal_year < 1990 or fiscal_year > 2100:
        raise ValueError(f"implausible fiscal_year {fiscal_year}")
    return f"{ticker}|FY{fiscal_year}|Q{fiscal_quarter}"
