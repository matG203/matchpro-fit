"""Preflight — prove the system can actually do its job, before it needs to.

Every provider here fails *quietly* by design: a missing entitlement lowers a
score and writes an audit row rather than crashing a release evening. That is
right at 21:05, and useless the day you set the thing up, because a wrong key
looks exactly like a quiet market.

This makes one real call per capability and says plainly what worked. It also
measures the **observed** feed delay from a live timestamp and compares it to
`MARKET_DATA_DELAY_SECONDS` — the setting the whole delayed-feed design hangs
on. Configure 0 on a 15-minute plan and the system will read "the stock has not
moved" where it should read "we cannot see it yet"; configure 900 on a
real-time plan and every score waits a quarter of an hour for nothing. Neither
mistake announces itself in normal operation.

Run it:

    python -m app.preflight

or GET /api/preflight.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.config import Settings, get_settings

logger = logging.getLogger("earnings_radar.preflight")

# A large, always-liquid name: if this returns nothing, the problem is the
# account, not the ticker.
PROBE_TICKER = "AAPL"

OK, FAIL, WARN, SKIP = "ok", "fail", "warn", "skip"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    fix: str = ""

    @property
    def blocking(self) -> bool:
        return self.status == FAIL


@dataclass
class PreflightReport:
    checks: list[Check] = field(default_factory=list)
    observed_delay_seconds: float | None = None
    configured_delay_seconds: float = 0.0

    def add(self, name: str, status: str, detail: str = "", fix: str = "") -> None:
        self.checks.append(Check(name, status, detail, fix))

    @property
    def ready(self) -> bool:
        return not any(c.blocking for c in self.checks)

    def as_dict(self) -> dict:
        return {
            "ready": self.ready,
            "observed_delay_seconds": self.observed_delay_seconds,
            "configured_delay_seconds": self.configured_delay_seconds,
            "checks": [{"name": c.name, "status": c.status,
                        "detail": c.detail, "fix": c.fix} for c in self.checks],
        }

    def render(self) -> str:
        symbols = {OK: "  OK  ", FAIL: " FAIL ", WARN: " WARN ", SKIP: " SKIP "}
        lines = ["", "Earnings Radar — preflight", "=" * 66]
        for check in self.checks:
            lines.append(f"[{symbols[check.status]}] {check.name}")
            if check.detail:
                lines.append(f"           {check.detail}")
            if check.fix:
                lines.append(f"           → {check.fix}")
        lines.append("=" * 66)
        lines.append("READY — nothing is blocking a live run." if self.ready
                     else "NOT READY — fix the FAIL lines above before relying on this.")
        lines.append("")
        return "\n".join(lines)


def run_preflight(settings: Settings | None = None, *,
                  polygon=None, fmp=None, sec=None, notifiers=None,
                  now: datetime | None = None, cwd=None) -> PreflightReport:
    """One real call per capability. Providers are injectable for testing."""
    settings = settings or get_settings()
    now = now or datetime.now(UTC)
    report = PreflightReport(configured_delay_seconds=settings.market_data_delay_seconds)

    _check_config(report, settings, cwd=cwd)
    _check_polygon(report, settings, polygon, now)
    _check_float(report, settings, fmp)
    _check_sec(report, settings, sec)
    _check_llm(report, settings)
    _check_push(report, settings, notifiers)
    return report


# ── individual checks ─────────────────────────────────────────────────────────


def _mask(value: str) -> str:
    """Enough to recognise a key, never enough to leak one."""
    if not value:
        return "not set"
    if len(value) <= 8:
        return "set (short)"
    return f"set — {value[:4]}…{value[-4:]} ({len(value)} chars)"


def _check_config(report: PreflightReport, settings: Settings,
                  cwd: object | None = None) -> None:
    """Which .env was actually read, and what did it contain?

    Worth its own check because the common failures are invisible: Notepad
    saves `.env.txt` unless you force it, and running from the wrong folder
    means no `.env` is found at all. Both look like "every key is missing",
    which is easy to misread as the keys being wrong.
    """
    from pathlib import Path

    root = Path(cwd) if cwd is not None else Path.cwd()
    env_file = root / ".env"
    keys = {
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
        "POLYGON_API_KEY": settings.polygon_api_key,
        "FMP_API_KEY": settings.fmp_api_key,
        "NTFY_TOPIC": settings.ntfy_topic,
    }
    loaded = [name for name, value in keys.items() if value]

    if not env_file.exists():
        decoys = sorted(p.name for p in root.glob(".env.*")
                        if p.name in {".env.txt", ".env.text"})
        hint = (f"found {decoys[0]} instead — Notepad appended .txt; "
                f'rename it to .env (in Explorer: View → File name extensions)'
                if decoys else
                f"no .env in {root} — are you running from the project folder?")
        report.add("Configuration — .env", FAIL,
                   f"no .env file was read; {len(loaded)} keys are set from the "
                   "environment", hint)
        return

    detail = "; ".join(f"{name} {_mask(value)}" for name, value in keys.items())
    if not loaded:
        report.add("Configuration — .env", FAIL,
                   f"{env_file} exists but no keys were read from it",
                   "Check for stray quotes or spaces: KEY=value, not KEY = \"value\"")
        return

    report.add("Configuration — .env", OK, f"read {env_file}")
    report.add("Configuration — keys", OK, detail)


def _check_polygon(report: PreflightReport, settings: Settings, polygon,
                   now: datetime) -> None:
    from app.providers.base import ProviderError, ProviderUnavailable

    if polygon is None:
        if not settings.polygon_api_key:
            report.add("Polygon — API key", FAIL, "POLYGON_API_KEY is not set",
                       "Add it to .env; without prices nothing can reach 9+")
            return
        from app.providers.polygon import PolygonProvider
        polygon = PolygonProvider()

    # 1. Snapshot — proves the key, and carries the timestamp we need.
    try:
        snap = polygon.snapshot(PROBE_TICKER)
        report.add("Polygon — snapshot", OK,
                   f"{PROBE_TICKER} at {snap.price} "
                   f"(bid/ask {snap.bid}/{snap.ask})")
    except ProviderUnavailable as exc:
        report.add("Polygon — snapshot", FAIL, str(exc),
                   "Check the key is correct and the plan includes US stocks")
        return
    except ProviderError as exc:
        report.add("Polygon — snapshot", FAIL, str(exc),
                   "Check POLYGON_BASE_URL and network access")
        return

    # 2. Observed delay — the setting the delayed-feed design depends on.
    _check_delay(report, settings, snap, now)

    # 3. Minute bars — the disclosure-anchored measurement needs these.
    try:
        bars = polygon.bars(PROBE_TICKER, start=now - timedelta(days=5), end=now,
                            timespan="minute")
        if bars:
            report.add("Polygon — minute bars", OK,
                       f"{len(bars)} bars, newest {bars[-1].start_utc:%Y-%m-%d %H:%M} UTC")
        else:
            report.add("Polygon — minute bars", WARN,
                       "no bars returned for the last 5 days",
                       "Normal over a long weekend; re-run on a trading day")
    except (ProviderError, ProviderUnavailable) as exc:
        report.add("Polygon — minute bars", FAIL, str(exc),
                   "Without minute bars the move cannot be priced at disclosure")

    # 4. Reference data — market cap and shares outstanding.
    try:
        details = polygon.details(PROBE_TICKER)
        report.add("Polygon — reference data", OK,
                   f"market cap {details.market_cap}, "
                   f"shares out {details.shares_outstanding}")
    except (ProviderError, ProviderUnavailable) as exc:
        report.add("Polygon — reference data", WARN, str(exc),
                   "Materiality falls back to the stored company record")

    # 5. Short interest — often a higher tier; not fatal.
    try:
        short = polygon.short_interest(PROBE_TICKER)
        report.add("Polygon — short interest", OK,
                   f"{short.short_interest_shares} shares, "
                   f"settled {short.settlement_date}")
    except (ProviderError, ProviderUnavailable) as exc:
        report.add("Polygon — short interest", WARN, str(exc),
                   "Move Amplification runs without it and records it as missing")


def _check_delay(report: PreflightReport, settings: Settings, snap,
                 now: datetime) -> None:
    """Compare the feed's actual lag against what we told the system to expect."""
    from app.catalyst.amplification import market_session
    from app.domain.timeutil import ensure_utc

    if snap.last_trade_at is None:
        report.add("Feed delay", SKIP, "snapshot carried no trade timestamp")
        return

    observed = (now - ensure_utc(snap.last_trade_at)).total_seconds()
    report.observed_delay_seconds = round(observed, 1)
    configured = settings.market_data_delay_seconds
    session = market_session(now)

    if session == "closed":
        report.add("Feed delay", SKIP,
                   f"market closed — last print {observed / 60:.0f} min ago tells "
                   "us nothing about the feed's lag",
                   "Re-run during market hours to confirm the setting")
        return

    # Allow generous slack: a quiet minute in a thin name is not a delay.
    if abs(observed - configured) <= 300:
        plan = "real-time" if configured == 0 else f"{configured / 60:.0f}-minute delayed"
        report.add("Feed delay", OK,
                   f"observed {observed / 60:.1f} min, configured "
                   f"{configured / 60:.0f} min — consistent with a {plan} plan")
        return

    if observed > configured + 300:
        report.add(
            "Feed delay", FAIL,
            f"prices are {observed / 60:.0f} min old but the system expects "
            f"{configured / 60:.0f} min",
            f"Set MARKET_DATA_DELAY_SECONDS={int(round(observed / 60) * 60)} — "
            "otherwise a move you cannot see yet is scored as no move")
    else:
        report.add(
            "Feed delay", WARN,
            f"prices are only {observed / 60:.1f} min old but the system waits "
            f"{configured / 60:.0f} min",
            "Set MARKET_DATA_DELAY_SECONDS=0 if you are on a real-time plan — "
            "every score is currently held back for nothing")


def _check_float(report: PreflightReport, settings: Settings, fmp) -> None:
    if fmp is None:
        if not settings.fmp_api_key:
            report.add("FMP — free float", WARN, "FMP_API_KEY is not set",
                       "Move Amplification caps at 7.5 without free float")
            return
        from app.providers.fmp import FmpProvider
        fmp = FmpProvider()

    value = fmp.free_float_shares(PROBE_TICKER)
    if value:
        report.add("FMP — free float", OK, f"{PROBE_TICKER} float {value:,.0f} shares")
    else:
        report.add("FMP — free float", WARN,
                   "the plan did not return a float figure",
                   "Short interest falls back to shares outstanding at reduced "
                   "confidence, and amplification records the gap")


def _check_sec(report: PreflightReport, settings: Settings, sec) -> None:
    from app.providers.base import ProviderError, ProviderUnavailable

    if sec is None:
        from app.providers.sec_edgar import SecEdgarProvider
        sec = SecEdgarProvider()

    if "example.com" in settings.sec_user_agent:
        report.add("SEC — user agent", FAIL,
                   "SEC_USER_AGENT is still the placeholder",
                   "Put your real email in it; SEC blocks anonymous automation")
        return

    try:
        entries = sec.latest_filings(count=10)
        report.add("SEC — latest filings feed", OK,
                   f"{len(entries)} filings in the current window")
    except (ProviderError, ProviderUnavailable) as exc:
        report.add("SEC — latest filings feed", FAIL, str(exc),
                   "This is the only detection source; nothing is found without it")


def _check_llm(report: PreflightReport, settings: Settings) -> None:
    if settings.anthropic_api_key:
        report.add("Anthropic — API key", OK,
                   f"set; analysis model {settings.analysis_model}")
    else:
        report.add("Anthropic — API key", WARN, "ANTHROPIC_API_KEY is not set",
                   "Both pipelines fall back to deterministic scores, and no "
                   "catalyst can pass the adversarial-review gate to reach 9+")


def _check_push(report: PreflightReport, settings: Settings, notifiers) -> None:
    if notifiers is None:
        from app.providers.notifiers import NtfyNotifier, PushoverNotifier
        notifiers = [NtfyNotifier(), PushoverNotifier()]

    live = [n.name for n in notifiers if n.enabled()]
    if live:
        report.add("Push notifications", OK, f"channels: {', '.join(live)}")
    else:
        report.add("Push notifications", FAIL, "no push channel configured",
                   "Set NTFY_TOPIC — scores would be stored but never reach you")


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    report = run_preflight()
    print(report.render())
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
