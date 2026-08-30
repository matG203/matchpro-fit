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

# Release pages fetched to measure the real entity-resolution rate. Enough to
# be indicative, few enough to stay polite to a free feed.
_BODY_SAMPLE = 8

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
                  polygon=None, fmp=None, sec=None, notifiers=None, wires=None,
                  now: datetime | None = None, cwd=None) -> PreflightReport:
    """One real call per capability. Providers are injectable for testing."""
    settings = settings or get_settings()
    now = now or datetime.now(UTC)
    report = PreflightReport(configured_delay_seconds=settings.market_data_delay_seconds)

    _check_config(report, settings, cwd=cwd)
    _check_polygon(report, settings, polygon, now)
    _check_float(report, settings, fmp)
    _check_sec(report, settings, sec)
    _check_wires(report, settings, wires, now)
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

    detail = "; ".join(f"{name} {_mask(value)}" for name, value in keys.items())

    if not env_file.exists():
        if loaded:
            # A hosted deployment has no .env at all — Railway, Render and the
            # rest inject variables directly. Calling that a failure would send
            # someone hunting a file that is not supposed to exist, and would
            # make a correctly configured server report NOT READY.
            report.add("Configuration — environment", OK,
                       f"no .env file; {len(loaded)} keys read from the "
                       f"environment (normal for a hosted deployment)")
            report.add("Configuration — keys", OK, detail)
            return
        decoys = sorted(p.name for p in root.glob(".env.*")
                        if p.name in {".env.txt", ".env.text"})
        hint = (f"found {decoys[0]} instead — Notepad appended .txt; "
                f'rename it to .env (in Explorer: View → File name extensions)'
                if decoys else
                f"no .env in {root}, and no keys in the environment either — "
                f"are you running from the project folder?")
        report.add("Configuration — .env", FAIL,
                   "no configuration was found from any source", hint)
        return

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

    # 2. Minute bars — the disclosure-anchored measurement needs these, and
    #    they also date the last print when the snapshot does not.
    bars = []
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

    # 3. Observed delay — the setting the delayed-feed design depends on.
    _check_delay(report, settings, snap, now, bars)

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
                 now: datetime, bars: list | None = None) -> None:
    """Compare the feed's actual lag against what we told the system to expect."""
    from app.catalyst.amplification import market_session
    from app.domain.timeutil import ensure_utc

    # Some plans omit lastTrade from the snapshot; the newest minute bar dates
    # the last print just as well, and is what the pipeline falls back to.
    last_print = snap.last_trade_at
    source = "last trade"
    if last_print is None and bars:
        last_print = bars[-1].start_utc
        source = "newest minute bar"
    if last_print is None:
        report.add("Feed delay", SKIP,
                   "no trade timestamp and no minute bars to date the feed")
        return

    observed = (now - ensure_utc(last_print)).total_seconds()
    report.observed_delay_seconds = round(observed, 1)
    configured = settings.market_data_delay_seconds
    session = market_session(now)

    if session == "closed":
        report.add("Feed delay", SKIP,
                   f"market closed — last print {observed / 60:.0f} min ago ({source}) "
                   "tells us nothing about the feed's lag",
                   "Re-run during market hours to confirm the setting")
        return

    # Allow generous slack: a quiet minute in a thin name is not a delay.
    if abs(observed - configured) <= 300:
        plan = "real-time" if configured == 0 else f"{configured / 60:.0f}-minute delayed"
        report.add("Feed delay", OK,
                   f"observed {observed / 60:.1f} min ({source}), configured "
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


def _check_wires(report: PreflightReport, settings: Settings, wires,
                 now: datetime) -> None:
    """Fetch every newswire firehose for real, and read what came back.

    This check exists because the build environment cannot reach the wires:
    parsing is proven against recorded samples of each feed's format, but
    nothing offline can prove the URLs still serve those formats today. This
    is the only place that question gets an honest answer, so it asks it
    properly — not "did the request succeed" but "did we get releases, are
    they recent, and do they carry the ticker tags entity resolution needs".

    A dead wire is the quietest failure in the system. It produces no error,
    no alert and no log line: just a market that seems to have gone silent.
    """
    from app.providers.base import ProviderError

    if not settings.wire_feeds_enabled:
        report.add("Newswires — free feeds", SKIP,
                   "WIRE_FEEDS_ENABLED is false; SEC filings only",
                   "Set WIRE_FEEDS_ENABLED=true to see catalysts before they are 8-K'd")
        return

    if wires is None:
        from app.catalyst.enums import SourceTier
        from app.providers.wires import (
            DEFAULT_WIRE_FEEDS,
            WireFeed,
            WireFirehoseProvider,
        )

        feeds = list(DEFAULT_WIRE_FEEDS) if settings.wire_use_default_feeds else []
        feeds += [WireFeed(url=url, source=label, tier=SourceTier.NEWSWIRE)
                  for url, label in settings.wire_feed_list()]
        if not feeds:
            report.add("Newswires — free feeds", FAIL,
                       "wire feeds are enabled but none are configured",
                       "Set WIRE_USE_DEFAULT_FEEDS=true, or list feeds in WIRE_FEED_URLS")
            return
        # No body fetches: this is a connectivity check, not a sweep.
        wires = WireFirehoseProvider(feeds=feeds, max_body_fetches=0)

    try:
        # A wide window so the check works at 3am on a Sunday, when the wires
        # are genuinely quiet and a narrow one would look like a failure.
        articles = wires.fetch_since(now - timedelta(hours=24))
    except ProviderError as exc:
        report.add("Newswires — free feeds", FAIL, str(exc),
                   "Every wire is unreachable. Check outbound HTTPS, or set "
                   "WIRE_FEEDS_ENABLED=false to run on SEC filings alone")
        return

    live = [h for h in wires.health() if h.ok]
    dead = [h for h in wires.health() if not h.ok]
    total = sum(h.items_seen for h in live)

    for health in dead:
        # A warning, not a block: the remaining wires and SEC still work, and
        # refusing to start over one rotted URL would cost more coverage than
        # it protects. Losing every wire is the FAIL, and it is handled above.
        report.add(f"Newswire — {health.source}", WARN,
                   health.error or "no response",
                   "This wire's feed URL may have changed. Coverage continues "
                   "on the other wires; fix or replace it via WIRE_FEED_URLS")

    # A feed that answers, parses, and yields nothing. This is the worst of the
    # three outcomes because it is the only one that looks like success: no
    # error, no exception, just a wire that has quietly stopped contributing.
    # It has to be judged per feed — summing across wires lets a live one hide
    # a dead one, which is exactly what a total-only check did.
    for health in [h for h in live if h.items_seen == 0]:
        report.add(f"Newswire — {health.source}", WARN,
                   "reachable and parsed, but returned no releases at all over "
                   "24 hours — this wire publishes hundreds a day, so it is "
                   "contributing nothing",
                   "The feed URL is almost certainly wrong or retired. Find a "
                   "working one with: python -m app.probe_feed <url> — then set "
                   "it in WIRE_FEED_URLS")

    if not live:
        return

    detail = ", ".join(f"{h.source}: {h.items_seen} releases" for h in live)
    if total == 0:
        report.add("Newswires — free feeds", FAIL,
                   f"reachable but empty over 24 hours ({detail})",
                   "An empty firehose means the feed shape changed. Nothing "
                   "will be detected from news until this is fixed")
        return

    newest = max((h.newest_item_at for h in live if h.newest_item_at), default=None)
    age = f", newest {(now - newest).total_seconds() / 60:.0f} min old" if newest else ""
    report.add("Newswires — free feeds", OK, f"{total} releases in 24h ({detail}){age}")

    # Parsing a feed is not the same as being able to use it. Entity resolution
    # needs an exchange-qualified ticker, and if the wires stopped including
    # them the whole news stream would resolve to nothing while every other
    # check stayed green.
    #
    # The RSS summary alone resolves only a minority of releases, because the
    # "(NASDAQ: ABC)" tag sits in the release body. A live sweep fetches those
    # bodies; so does this check, for a sample. Reporting the summary-only rate
    # and *asserting* the body fetch fixes it would be a guess about the single
    # number that decides whether this system ever sees a catalyst.
    from app.catalyst.entities import resolve_entity

    checked = articles[:40]
    if not checked:
        return

    def resolves(headline: str, body: str) -> bool:
        return (resolve_entity(headline=headline, body=body, known_companies={})
                .confidence >= settings.min_entity_confidence)

    from_summary = [a for a in checked if resolves(a.headline, a.body)]
    unresolved = [a for a in checked if a not in from_summary]

    # Fetch a bounded sample of the ones the summary could not place, and see
    # how many the full text rescues.
    sample = unresolved[:_BODY_SAMPLE]
    rescued = 0
    fetch_failures = 0
    fetch_body = getattr(wires, "_fetch_body", None)
    for article in sample:
        body = fetch_body(article.source_url) if fetch_body else None
        if body is None:
            fetch_failures += 1
            continue
        if resolves(article.headline, body):
            rescued += 1

    summary_pct = 100.0 * len(from_summary) / len(checked)
    if not sample:
        report.add("Newswires — ticker tags", OK,
                   f"{len(from_summary)}/{len(checked)} releases ({summary_pct:.0f}%) "
                   f"resolve to a ticker from the RSS summary alone")
        return

    fetched = len(sample) - fetch_failures
    if fetched == 0:
        report.add("Newswires — ticker tags", WARN,
                   f"{len(from_summary)}/{len(checked)} ({summary_pct:.0f}%) resolve "
                   f"from the summary; could not fetch any release page to test the rest",
                   "The wires serve their feeds but not their article pages to this "
                   "machine. Detection will run on headlines only, which resolves far "
                   "fewer companies")
        return

    rescue_pct = 100.0 * rescued / fetched
    # Projected end-to-end rate: summary hits, plus the same rescue rate applied
    # to everything the summary missed.
    projected = (len(from_summary) + (len(unresolved) * rescued / fetched)) / len(checked)
    status = OK if projected >= 0.35 else WARN
    report.add("Newswires — ticker tags", status,
               f"{len(from_summary)}/{len(checked)} ({summary_pct:.0f}%) resolve from "
               f"the summary; fetching the release page rescued {rescued}/{fetched} "
               f"more ({rescue_pct:.0f}%) → about {projected:.0%} of releases end up "
               f"attributable to a company",
               "" if status == OK else
               "Most releases cannot be tied to a ticker even with the full text. "
               "Detection will still work, on fewer stories than it should")


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
