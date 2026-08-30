"""Preflight: does the system actually work, and is the delay setting right?

Every provider in this system fails quietly by design — a missing entitlement
lowers a score rather than crashing an earnings evening. That makes a wrong key
look exactly like a quiet market, which is why these checks exist.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.config import Settings
from app.preflight import FAIL, OK, SKIP, WARN, PreflightReport, run_preflight
from app.providers.base import ProviderError, ProviderUnavailable, ShortInterest, Snapshot

# A Thursday, 15:00 UTC = 11:00 New York — regular hours.
NOW = datetime(2026, 8, 27, 15, 0, tzinfo=UTC)


def settings(**overrides) -> Settings:
    base = dict(database_url="sqlite://", polygon_api_key="key",
                fmp_api_key="key", anthropic_api_key="key",
                ntfy_topic="topic", sec_user_agent="Radar (real@person.com)",
                market_data_delay_seconds=900.0)
    base.update(overrides)
    return Settings(**base)


class FakePolygon:
    def __init__(self, *, last_trade_age_minutes=15.0, short_error=None,
                 snapshot_error=None, bars=8, newest_bar_age_minutes=15.0):
        self.age = last_trade_age_minutes
        self.short_error = short_error
        self.snapshot_error = snapshot_error
        self.bar_count = bars
        self.newest_bar_age = newest_bar_age_minutes

    def snapshot(self, ticker):
        if self.snapshot_error:
            raise self.snapshot_error
        return Snapshot(ticker=ticker, price=210.5, bid=210.4, ask=210.6,
                        last_trade_at=NOW - timedelta(minutes=self.age))

    def bars(self, ticker, *, start, end, timespan="minute", multiplier=1, limit=5000):
        """Oldest first, as the real API returns them (sort=asc)."""
        from app.providers.base import Bar
        newest = NOW - timedelta(minutes=self.newest_bar_age)
        return [Bar(start_utc=newest - timedelta(minutes=self.bar_count - 1 - i),
                    open=210.0, high=211.0, low=209.0, close=210.5, volume=1000.0)
                for i in range(self.bar_count)]

    def details(self, ticker):
        from app.providers.base import TickerDetails
        return TickerDetails(ticker=ticker, market_cap=3.2e12,
                             shares_outstanding=15e9)

    def short_interest(self, ticker):
        if self.short_error:
            raise self.short_error
        return ShortInterest(ticker=ticker, settlement_date=NOW.date(),
                             short_interest_shares=100e6)


class FakeFmp:
    def __init__(self, value=8.9e9):
        self.value = value

    def free_float_shares(self, ticker):
        return self.value


class FakeSec:
    def __init__(self, error=None, count=10):
        self.error = error
        self.count = count

    def latest_filings(self, count=100):
        if self.error:
            raise self.error
        return [object()] * self.count


class FakeNotifier:
    def __init__(self, name="ntfy", on=True):
        self.name = name
        self._on = on

    def enabled(self):
        return self._on


class FakeWires:
    """Stands in for the newswire firehoses.

    Injected everywhere, including the default `run()` kwargs: without it
    `_check_wires` builds a real provider and the test suite starts making
    outbound requests to three press-release sites on every run.
    """

    def __init__(self, articles=None, error=None, health=None):
        from app.providers.wires import WireFeedHealth
        self.error = error
        self._articles = articles if articles is not None else [
            _wire_article("Kestrel Therapeutics Announces FDA Approval",
                          "Kestrel Therapeutics Inc. (NASDAQ: KTRX) announced."),
        ]
        self._health = health if health is not None else [
            WireFeedHealth(source="GlobeNewswire", url="https://gnw.test/f", ok=True,
                           items_seen=40, items_new=1,
                           newest_item_at=NOW - timedelta(minutes=6)),
        ]

    def fetch_since(self, since):
        if self.error:
            raise self.error
        return list(self._articles)

    def health(self):
        return list(self._health)


def _wire_article(headline, body):
    from app.providers.news import NewsArticle
    return NewsArticle(provider="wire_rss", article_id=headline, headline=headline,
                       body=body, published_at_utc=NOW - timedelta(minutes=6))


@pytest.fixture(scope="module")
def env_dir(tmp_path_factory):
    """A folder that looks correctly configured, so the provider checks can be
    tested without the .env check failing first."""
    path = tmp_path_factory.mktemp("configured")
    (path / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-abcd1234efgh5678\n")
    return path


def run(conf=None, *, cwd=None, **kwargs) -> PreflightReport:
    defaults = dict(polygon=FakePolygon(), fmp=FakeFmp(), sec=FakeSec(),
                    notifiers=[FakeNotifier()], wires=FakeWires(), now=NOW)
    defaults.update(kwargs)
    return run_preflight(conf or settings(), cwd=cwd or _ENV_DIR[0], **defaults)


# Set by the autouse fixture below so every `run()` sees a valid .env folder.
_ENV_DIR: list = [None]


@pytest.fixture(autouse=True)
def _use_env_dir(env_dir):
    _ENV_DIR[0] = env_dir
    yield


def status_of(report: PreflightReport, name: str) -> str:
    return next(c.status for c in report.checks if c.name == name)


def check(report: PreflightReport, name: str):
    return next(c for c in report.checks if c.name == name)


# ── the happy path ────────────────────────────────────────────────────────────


def test_a_correctly_configured_system_is_ready():
    report = run()
    assert report.ready is True
    assert status_of(report, "Polygon — snapshot") == OK
    assert status_of(report, "Polygon — minute bars") == OK
    assert status_of(report, "SEC — latest filings feed") == OK
    assert status_of(report, "Push notifications") == OK


# ── the delay setting, which nothing else would catch ─────────────────────────


def test_a_matching_delay_setting_passes():
    report = run(polygon=FakePolygon(last_trade_age_minutes=15.0))
    assert status_of(report, "Feed delay") == OK
    assert report.observed_delay_seconds == 900.0


def test_configuring_real_time_on_a_delayed_plan_is_a_failure():
    """The dangerous direction: the system would read 'has not moved' where it
    should read 'cannot see it yet' — a high score on a stock already gone."""
    report = run(settings(market_data_delay_seconds=0.0),
                 polygon=FakePolygon(last_trade_age_minutes=15.0))

    entry = check(report, "Feed delay")
    assert entry.status == FAIL
    assert "MARKET_DATA_DELAY_SECONDS=900" in entry.fix
    assert report.ready is False


def test_configuring_a_delay_on_a_real_time_plan_is_only_a_warning():
    """Wasteful rather than wrong: every score waits 15 minutes for nothing."""
    report = run(polygon=FakePolygon(last_trade_age_minutes=0.2))

    entry = check(report, "Feed delay")
    assert entry.status == WARN
    assert "MARKET_DATA_DELAY_SECONDS=0" in entry.fix
    assert report.ready is True


def test_the_delay_check_is_skipped_when_the_market_is_closed():
    """A stale print at 3am says nothing about the feed's lag."""
    closed = datetime(2026, 8, 29, 3, 0, tzinfo=UTC)      # Saturday
    report = run(polygon=FakePolygon(last_trade_age_minutes=600), now=closed)

    assert status_of(report, "Feed delay") == SKIP
    assert report.ready is True


def test_a_quiet_minute_is_not_reported_as_a_wrong_setting():
    report = run(polygon=FakePolygon(last_trade_age_minutes=17.0))
    assert status_of(report, "Feed delay") == OK


# ── failures that must block ──────────────────────────────────────────────────


def test_a_missing_polygon_key_blocks():
    report = run_preflight(settings(polygon_api_key=""), fmp=FakeFmp(),
                           sec=FakeSec(), notifiers=[FakeNotifier()],
                           wires=FakeWires(), now=NOW, cwd=_ENV_DIR[0])
    assert status_of(report, "Polygon — API key") == FAIL
    assert report.ready is False


def test_a_rejected_polygon_key_blocks_and_stops_further_calls():
    report = run(polygon=FakePolygon(
        snapshot_error=ProviderUnavailable("polygon: not entitled to /v2/snapshot")))

    assert status_of(report, "Polygon — snapshot") == FAIL
    assert report.ready is False
    # No point reporting on bars when the key itself was refused.
    assert not any(c.name == "Polygon — minute bars" for c in report.checks)


def test_the_placeholder_sec_user_agent_blocks():
    """SEC blocks anonymous automation, so the default would fail silently."""
    report = run(settings(sec_user_agent="Earnings Radar (contact@example.com)"))

    entry = check(report, "SEC — user agent")
    assert entry.status == FAIL
    assert report.ready is False


def test_an_unreachable_edgar_feed_blocks():
    report = run(sec=FakeSec(error=ProviderError("403 Forbidden")))
    assert status_of(report, "SEC — latest filings feed") == FAIL
    assert report.ready is False


def test_no_push_channel_blocks():
    """Scores would be computed perfectly and never reach a phone."""
    report = run(notifiers=[FakeNotifier(on=False)])
    assert status_of(report, "Push notifications") == FAIL
    assert report.ready is False


# ── degradations that should not block ────────────────────────────────────────


def test_missing_short_interest_is_a_warning_not_a_failure():
    report = run(polygon=FakePolygon(
        short_error=ProviderUnavailable("not entitled")))

    assert status_of(report, "Polygon — short interest") == WARN
    assert report.ready is True


def test_missing_float_is_a_warning():
    report = run(fmp=FakeFmp(value=None))
    assert status_of(report, "FMP — free float") == WARN
    assert report.ready is True


# ── newswires ─────────────────────────────────────────────────────────────────


def test_live_wires_report_what_they_returned():
    report = run()
    entry = check(report, "Newswires — free feeds")

    assert entry.status == OK
    assert "40 releases" in entry.detail
    assert "GlobeNewswire" in entry.detail
    assert report.ready is True


def test_every_wire_being_unreachable_blocks():
    from app.providers.base import ProviderError

    report = run(wires=FakeWires(error=ProviderError("all three refused")))
    entry = check(report, "Newswires — free feeds")

    assert entry.status == FAIL
    assert "all three refused" in entry.detail
    assert report.ready is False


def test_a_reachable_but_empty_firehose_blocks():
    """The failure this check exists for.

    A feed whose URL still resolves but whose shape has changed returns zero
    items. Nothing errors, nothing logs, and the system quietly stops seeing
    news — indistinguishable from a slow day unless something asserts on it.
    """
    from app.providers.wires import WireFeedHealth

    report = run(wires=FakeWires(
        articles=[],
        health=[WireFeedHealth(source="GlobeNewswire", url="https://gnw.test/f",
                               ok=True, items_seen=0)]))
    entry = check(report, "Newswires — free feeds")

    assert entry.status == FAIL
    assert "empty over 24 hours" in entry.detail
    assert report.ready is False


def test_one_dead_wire_is_reported_without_blocking_the_run():
    from app.providers.wires import WireFeedHealth

    report = run(wires=FakeWires(health=[
        WireFeedHealth(source="GlobeNewswire", url="https://gnw.test/f", ok=True,
                       items_seen=40, newest_item_at=NOW - timedelta(minutes=6)),
        WireFeedHealth(source="PR Newswire", url="https://prn.test/f", ok=False,
                       error="404 Not Found"),
    ]))

    assert status_of(report, "Newswire — PR Newswire") == WARN
    assert status_of(report, "Newswires — free feeds") == OK
    # Visible, but not a block: SEC and the surviving wires still work, and
    # refusing to start over one rotted URL loses more coverage than it saves.
    assert report.ready is True


def test_releases_without_ticker_tags_warn_rather_than_pass_silently():
    report = run(wires=FakeWires(articles=[
        _wire_article("Something happened at a company", "No ticker anywhere."),
        _wire_article("Another vague headline", "Still no ticker."),
    ]))
    entry = check(report, "Newswires — ticker tags")

    assert entry.status == WARN
    assert "0/2" in entry.detail
    assert report.ready is True


def test_disabling_the_wires_is_a_skip_not_a_failure():
    report = run(settings(wire_feeds_enabled=False))
    entry = check(report, "Newswires — free feeds")

    assert entry.status == SKIP
    assert report.ready is True


def test_a_missing_anthropic_key_warns_about_the_9_plus_gate():
    report = run(settings(anthropic_api_key=""))
    entry = check(report, "Anthropic — API key")

    assert entry.status == WARN
    assert "9+" in entry.fix
    assert report.ready is True


def test_no_bars_over_a_long_weekend_is_a_warning():
    report = run(polygon=FakePolygon(bars=0))
    assert status_of(report, "Polygon — minute bars") == WARN
    assert report.ready is True


# ── output ────────────────────────────────────────────────────────────────────


def test_the_report_renders_every_check_and_a_verdict():
    text = run().render()
    assert "Earnings Radar — preflight" in text
    assert "READY" in text
    assert "Feed delay" in text


def test_a_failing_report_says_it_is_not_ready():
    text = run(notifiers=[FakeNotifier(on=False)]).render()
    assert "NOT READY" in text


def test_the_report_serialises_for_the_api():
    payload = run().as_dict()
    assert payload["ready"] is True
    assert payload["observed_delay_seconds"] == 900.0
    assert payload["configured_delay_seconds"] == 900.0
    assert all({"name", "status", "detail", "fix"} <= set(c) for c in payload["checks"])


def test_the_polygon_base_url_is_configurable_for_the_massive_rebrand():
    """Polygon became Massive; api.polygon.io still serves the same API, but a
    future endpoint move should be a settings change, not a code change."""
    import httpx

    from app.providers.polygon import PolygonProvider

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"ticker": {"ticker": "AAPL",
                                                    "lastTrade": {"p": 210.0}}})

    provider = PolygonProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_key="k", base_url="https://api.massive.com")
    provider.snapshot("AAPL")

    assert seen["url"].startswith("https://api.massive.com/v2/snapshot")


# ── configuration: the failures that look like missing keys ───────────────────


def test_a_present_env_file_reports_which_keys_were_read(tmp_path):
    from app.preflight import _check_config

    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-abcd1234efgh5678\n")
    report = PreflightReport()
    _check_config(report, settings(anthropic_api_key="sk-ant-abcd1234efgh5678"),
                  cwd=tmp_path)

    assert status_of(report, "Configuration — .env") == OK
    entry = check(report, "Configuration — keys")
    assert "ANTHROPIC_API_KEY set — sk-a…5678" in entry.detail


def test_the_key_is_never_printed_in_full(tmp_path):
    """A preflight report is the sort of thing that gets pasted into chat."""
    from app.preflight import _check_config

    secret = "sk-ant-SUPERSECRETVALUE123456"
    (tmp_path / ".env").write_text(f"ANTHROPIC_API_KEY={secret}\n")
    report = PreflightReport()
    _check_config(report, settings(anthropic_api_key=secret), cwd=tmp_path)

    assert secret not in report.render()
    assert "SUPERSECRET" not in report.render()


def test_the_notepad_dot_txt_trap_is_named_explicitly(tmp_path):
    """Notepad silently saves .env.txt, which loads nothing and looks exactly
    like every key being wrong."""
    from app.preflight import _check_config

    (tmp_path / ".env.txt").write_text("ANTHROPIC_API_KEY=x\n")
    report = PreflightReport()
    _check_config(report, settings(anthropic_api_key="", polygon_api_key="",
                                   fmp_api_key="", ntfy_topic=""), cwd=tmp_path)

    entry = check(report, "Configuration — .env")
    assert entry.status == FAIL
    assert ".env.txt" in entry.fix
    assert "File name extensions" in entry.fix


def test_running_from_the_wrong_folder_is_named(tmp_path):
    from app.preflight import _check_config

    report = PreflightReport()
    _check_config(report, settings(anthropic_api_key="", polygon_api_key="",
                                   fmp_api_key="", ntfy_topic=""), cwd=tmp_path)

    entry = check(report, "Configuration — .env")
    assert entry.status == FAIL
    assert "project folder" in entry.fix


def test_a_hosted_deployment_with_no_env_file_is_correctly_configured(tmp_path):
    """Railway and the rest inject variables directly; there is no `.env` and
    there is not supposed to be one. Calling that a failure would send someone
    hunting a file that should not exist, and would make a correctly set-up
    server report NOT READY on the page the deploy guide tells them to check.
    """
    from app.preflight import _check_config

    report = PreflightReport()
    _check_config(report, settings(anthropic_api_key="sk-ant-abcd1234efgh5678",
                                   polygon_api_key="poly-abcd1234"), cwd=tmp_path)

    assert status_of(report, "Configuration — environment") == OK
    assert "hosted deployment" in check(report, "Configuration — environment").detail
    assert report.ready is True
    # And still never prints a key in full.
    assert "sk-ant-abcd1234efgh5678" not in report.render()


def test_an_env_file_that_parsed_to_nothing_is_a_failure(tmp_path):
    """A file full of KEY = "value" reads as empty and needs its own message."""
    from app.preflight import _check_config

    (tmp_path / ".env").write_text('ANTHROPIC_API_KEY = "x"\n')
    report = PreflightReport()
    _check_config(report, settings(anthropic_api_key="", polygon_api_key="",
                                   fmp_api_key="", ntfy_topic=""), cwd=tmp_path)

    entry = check(report, "Configuration — .env")
    assert entry.status == FAIL
    assert "stray quotes" in entry.fix


# ── plans that omit lastTrade from the snapshot ───────────────────────────────


class NoTradeStampPolygon(FakePolygon):
    """Some plans return a price but no lastTrade block at all."""

    def snapshot(self, ticker):
        snap = super().snapshot(ticker)
        snap.last_trade_at = None
        snap.bid = snap.ask = None
        return snap


def test_the_delay_is_measured_from_minute_bars_when_the_snapshot_has_no_stamp():
    """Without this the check just skips, and the setting the whole
    delayed-feed design depends on is never verified."""
    report = run(polygon=NoTradeStampPolygon(bars=8))

    entry = check(report, "Feed delay")
    assert entry.status == OK
    assert "newest minute bar" in entry.detail
    assert report.observed_delay_seconds is not None


def test_a_wrong_setting_is_still_caught_without_a_trade_stamp():
    report = run(settings(market_data_delay_seconds=900.0),
                 polygon=NoTradeStampPolygon(bars=4, newest_bar_age_minutes=0.2))

    entry = check(report, "Feed delay")
    assert entry.status == WARN
    assert "MARKET_DATA_DELAY_SECONDS=0" in entry.fix


def test_the_check_skips_only_when_there_is_nothing_at_all_to_date_it():
    report = run(polygon=NoTradeStampPolygon(bars=0))
    assert status_of(report, "Feed delay") == SKIP
