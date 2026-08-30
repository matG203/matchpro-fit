"""Live market-data wiring: the Polygon adapter, the context builder, and the
engine changes that depend on them.

The adapter is tested against recorded response shapes through a fake HTTP
transport, so parsing is exercised for real without a network or an API key.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import httpx
import pytest

from app.catalyst import amplification as amp
from app.catalyst.enums import HaltState
from app.catalyst.reaction import AbnormalMove, assess_reaction_room
from app.config import Settings
from app.domain.timeutil import UTC
from app.providers.base import Bar, ProviderError, ProviderUnavailable, Snapshot
from app.providers.polygon import PolygonProvider
from app.services.catalyst_market import (
    CatalystMarketDataService,
    CompanyHints,
    atr_pct,
    price_at,
    realised_volatility_pct,
    runup_pct,
    sector_etf,
)

NOW = datetime(2026, 8, 27, 14, 30, tzinfo=UTC)


def settings(**overrides) -> Settings:
    base = dict(database_url="sqlite://", benchmark_ticker="SPY", market_data_delay_seconds=0.0,
                catalyst_atr_days=14, catalyst_runup_lookback_days=10)
    base.update(overrides)
    return Settings(**base)


def fake_polygon(routes: dict[str, dict]) -> PolygonProvider:
    """Polygon adapter backed by a canned route table."""

    def handler(request: httpx.Request) -> httpx.Response:
        for path, payload in routes.items():
            if request.url.path.startswith(path):
                return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"status": "NOT_FOUND"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return PolygonProvider(client=client, api_key="test-key")


# ── adapter parsing ───────────────────────────────────────────────────────────


SNAPSHOT_PAYLOAD = {
    "ticker": {
        "ticker": "ACME",
        "day": {"o": 10.0, "h": 10.4, "l": 9.9, "c": 10.2, "v": 1_500_000},
        "prevDay": {"c": 9.8},
        "min": {"c": 10.25, "av": 1_500_000},
        "lastTrade": {"p": 10.27, "t": 1787000000000000000},
        "lastQuote": {"p": 10.26, "P": 10.28, "t": 1787000000000000000},
    }
}


def test_snapshot_parses_prices_and_spread():
    provider = fake_polygon({"/v2/snapshot": SNAPSHOT_PAYLOAD})
    snap = provider.snapshot("acme")

    assert snap.ticker == "ACME"
    assert snap.price == 10.27          # last trade wins over the day close
    assert snap.prev_close == 9.8
    assert snap.day_volume == 1_500_000
    # (10.28 - 10.26) / 10.27 ≈ 0.195%
    assert snap.spread_pct() == pytest.approx(0.1947, abs=0.001)
    assert snap.last_trade_at is not None


def test_snapshot_falls_back_to_the_minute_bar_outside_regular_hours():
    """Before the open there is no `day` aggregate and often no last trade;
    the extended-hours minute bar is the only live price."""
    payload = {"ticker": {"ticker": "ACME", "day": {}, "prevDay": {"c": 9.8},
                          "min": {"c": 11.4}}}
    snap = fake_polygon({"/v2/snapshot": payload}).snapshot("ACME")
    assert snap.price == 11.4
    assert snap.prev_close == 9.8


def test_crossed_book_is_not_reported_as_a_spread():
    snap = Snapshot(ticker="ACME", bid=10.30, ask=10.20)
    assert snap.spread_pct() is None


def test_bars_are_parsed_oldest_first():
    payload = {"results": [
        {"t": 1787000000000, "o": 10.0, "h": 10.2, "l": 9.9, "c": 10.1, "v": 5000, "vw": 10.05},
        {"t": 1787000060000, "o": 10.1, "h": 10.5, "l": 10.0, "c": 10.4, "v": 8000},
    ]}
    bars = fake_polygon({"/v2/aggs": payload}).bars(
        "ACME", start=NOW - timedelta(hours=1), end=NOW)

    assert [b.close for b in bars] == [10.1, 10.4]
    assert bars[0].vwap == 10.05
    assert bars[1].vwap is None
    assert bars[0].start_utc < bars[1].start_utc


def test_details_never_reports_shares_outstanding_as_free_float():
    payload = {"results": {"name": "Acme Corp", "market_cap": 400_000_000,
                           "weighted_shares_outstanding": 40_000_000,
                           "share_class_shares_outstanding": 42_000_000,
                           "primary_exchange": "XNAS", "active": True}}
    details = fake_polygon({"/v3/reference": payload}).details("ACME")

    assert details.shares_outstanding == 40_000_000
    assert details.free_float_shares is None
    assert details.market_cap == 400_000_000


def test_short_interest_parses_the_settlement_date():
    payload = {"results": [{"ticker": "ACME", "settlement_date": "2026-08-14",
                            "short_interest": 6_000_000, "avg_daily_volume": 900_000,
                            "days_to_cover": 6.7}]}
    short = fake_polygon({"/stocks/v1/short-interest": payload}).short_interest("ACME")

    assert short.settlement_date == date(2026, 8, 14)
    assert short.short_interest_shares == 6_000_000
    assert short.days_to_cover == 6.7


def test_no_api_key_is_unavailable_not_an_error():
    """Unavailable providers are skipped by the fallback chain; errors are
    retried. Conflating them would burn retries on a missing key."""
    provider = PolygonProvider(client=httpx.Client(), api_key="")
    with pytest.raises(ProviderUnavailable):
        provider.snapshot("ACME")


def test_a_403_is_permanent_not_retryable():
    def handler(request):
        return httpx.Response(403, json={"error": "not entitled"})

    provider = PolygonProvider(client=httpx.Client(transport=httpx.MockTransport(handler)),
                               api_key="k")
    with pytest.raises(ProviderUnavailable):
        provider.short_interest("ACME")


def test_a_404_is_a_retryable_provider_error():
    provider = fake_polygon({})
    with pytest.raises(ProviderError):
        provider.snapshot("NOPE")


# ── pure maths ────────────────────────────────────────────────────────────────


def bars_from(closes: list[float], start: datetime, minutes: int = 1) -> list[Bar]:
    return [Bar(start_utc=start + timedelta(minutes=i * minutes), open=c, high=c * 1.01,
                low=c * 0.99, close=c, volume=1000.0)
            for i, c in enumerate(closes)]


def test_price_at_never_uses_a_bar_from_after_the_event():
    start = NOW - timedelta(minutes=5)
    bars = bars_from([10.0, 10.1, 12.0, 12.5], start)

    assert price_at(bars, start + timedelta(minutes=1)) == 10.1
    assert price_at(bars, start - timedelta(minutes=1)) is None


def test_the_baseline_excludes_the_bar_the_news_broke_in():
    """The minute the news lands already contains the reaction. Taking its
    close as the 'before' price erases most of the move — a 20% jump would be
    scored as 0%, and Reaction Room would call a repriced stock untouched."""
    start = NOW - timedelta(minutes=4)
    event_at = start + timedelta(minutes=2)
    bars = bars_from([10.0, 10.0, 12.0, 12.5], start)   # the spike opens at event_at

    assert price_at(bars, event_at, completed_only=True) == 10.0
    assert price_at(bars, event_at) == 12.0             # contains the reaction


def test_the_final_bar_is_treated_as_still_open():
    """Nothing in a bar series proves the last bar has closed, so it is never
    used as a completed baseline."""
    start = NOW - timedelta(minutes=2)
    bars = bars_from([10.0, 11.0], start)
    assert price_at(bars, start + timedelta(minutes=1), completed_only=True) == 10.0


def test_atr_uses_true_range_so_overnight_gaps_count():
    start = NOW - timedelta(days=20)
    bars = [Bar(start_utc=start + timedelta(days=i), open=100.0, high=101.0,
                low=99.0, close=100.0, volume=1e6) for i in range(20)]
    flat = atr_pct(bars, periods=14)

    # Same intraday ranges, but one session gaps 10 points away from the last
    # close: true range must pick that up, high−low would not.
    bars[-5] = Bar(start_utc=bars[-5].start_utc, open=110.0, high=111.0,
                   low=109.0, close=110.0, volume=1e6)
    gapped = atr_pct(bars, periods=14)

    assert flat is not None and gapped is not None
    assert gapped > flat


def test_atr_returns_none_without_enough_history():
    assert atr_pct(bars_from([10.0, 10.1, 10.2], NOW), periods=14) is None


def test_realised_volatility_needs_a_real_series():
    assert realised_volatility_pct(bars_from([10.0, 10.1], NOW)) is None
    value = realised_volatility_pct(bars_from([10, 11, 10, 12, 10, 13, 9], NOW))
    assert value is not None and value > 0


def test_runup_is_measured_to_the_pre_event_price():
    bars = bars_from([10.0, 10.5, 11.0], NOW - timedelta(days=3), minutes=1440)
    assert runup_pct(bars, 11.0) == pytest.approx(10.0)
    assert runup_pct(bars, None) is None


@pytest.mark.parametrize("sector,expected", [
    ("Technology", "XLK"),
    ("health care", "XLV"),
    ("Consumer Cyclical", "XLY"),
    ("Aerospace & Defense", None),
])
def test_sector_etf_mapping(sector, expected):
    assert sector_etf(sector) == expected


def test_sector_etf_falls_back_to_industry():
    assert sector_etf("", "Biotechnology") == "XBI"


# ── context builder ───────────────────────────────────────────────────────────


class FakeBars:
    """Deterministic bar/structure provider, so the builder is testable
    without network access or a clock dependency."""

    name = "fake"

    def __init__(self, series: dict[str, list[Bar]], *, snapshot=None, details=None,
                 short=None, fail: set[str] | None = None):
        self.series = series
        self._snapshot = snapshot
        self._details = details
        self._short = short
        self._fail = fail or set()
        self.calls: list[str] = []

    def bars(self, ticker, *, start, end, timespan="minute", multiplier=1, limit=5000):
        self.calls.append(f"bars:{ticker}")
        if "bars" in self._fail:
            raise ProviderError("bars down")
        return [b for b in self.series.get(ticker.upper(), []) if start <= b.start_utc <= end]

    def daily_bars(self, ticker, days):
        self.calls.append(f"daily:{ticker}")
        return self.series.get(f"{ticker.upper()}:daily", [])[-days:]

    def snapshot(self, ticker):
        if "snapshot" in self._fail:
            raise ProviderError("snapshot down")
        return self._snapshot

    def details(self, ticker):
        if "details" in self._fail:
            raise ProviderUnavailable("no reference entitlement")
        return self._details

    def short_interest(self, ticker):
        if "short" in self._fail or self._short is None:
            raise ProviderUnavailable("no short interest")
        return self._short


class FakeFloat:
    def __init__(self, value):
        self.value = value

    def free_float_shares(self, ticker):
        return self.value


def build_service(**kwargs) -> tuple[CatalystMarketDataService, FakeBars]:
    event_at = NOW - timedelta(minutes=10)
    stock = bars_from([10.0, 10.0, 10.0, 11.5, 12.0], event_at - timedelta(minutes=2))
    spy = bars_from([500.0, 500.0, 500.0, 501.0, 502.0], event_at - timedelta(minutes=2))
    daily = [Bar(start_utc=NOW - timedelta(days=30 - i), open=9.0 + i * 0.05,
                 high=9.3 + i * 0.05, low=8.8 + i * 0.05, close=9.0 + i * 0.05,
                 volume=1_000_000) for i in range(30)]

    provider = FakeBars(
        {"ACME": stock, "SPY": spy, "ACME:daily": daily},
        snapshot=kwargs.pop("snapshot", Snapshot(
            ticker="ACME", price=12.0, prev_close=10.0, day_volume=5_000_000,
            bid=11.99, ask=12.01, last_trade_at=NOW)),
        details=kwargs.pop("details", None),
        short=kwargs.pop("short", None),
        fail=kwargs.pop("fail", None))
    service = CatalystMarketDataService(
        bars=provider, structure=provider, settings=settings(),
        float_providers=kwargs.pop("float_providers", []))
    return service, provider


def test_context_prices_the_event_at_disclosure_not_now():
    service, _ = build_service()
    event_at = NOW - timedelta(minutes=10)

    context = service.context("ACME", NOW, event_at=event_at)

    assert context.price_before == 10.0     # the print before the news
    assert context.price_now == 12.0
    # The benchmark is measured over exactly the same window.
    assert context.benchmark_before == 500.0
    assert context.benchmark_now == 502.0


def test_context_without_a_disclosure_time_leaves_the_move_unmeasured():
    """No honest baseline exists, so none is invented — the scoring engine
    then treats reaction room as unresolved rather than scoring a guess."""
    service, _ = build_service()
    context = service.context("ACME", NOW)

    assert context.price_before is None
    assert context.benchmark_before is None
    assert context.price_now == 12.0


def test_sector_comparator_is_fetched_when_the_sector_is_known():
    service, provider = build_service()
    service.context("ACME", NOW, event_at=NOW - timedelta(minutes=10),
                    hints=CompanyHints(sector="Technology"))
    assert "bars:XLK" in provider.calls


def test_free_float_comes_from_a_float_provider_never_from_shares_outstanding():
    from app.providers.base import TickerDetails

    service, _ = build_service(
        details=TickerDetails(ticker="ACME", shares_outstanding=40e6, market_cap=480e6),
        float_providers=[FakeFloat(18e6)])
    context = service.context("ACME", NOW, event_at=NOW - timedelta(minutes=10))

    assert context.structure.free_float_shares == 18e6
    assert context.structure.shares_outstanding == 40e6


def test_no_float_provider_leaves_free_float_unknown():
    from app.providers.base import TickerDetails

    service, _ = build_service(
        details=TickerDetails(ticker="ACME", shares_outstanding=40e6, market_cap=480e6))
    context = service.context("ACME", NOW, event_at=NOW - timedelta(minutes=10))

    assert context.structure.free_float_shares is None
    assert "free_float_shares" in context.structure.missing()


def test_short_interest_percentages_use_the_right_denominators():
    from app.providers.base import ShortInterest, TickerDetails

    service, _ = build_service(
        details=TickerDetails(ticker="ACME", shares_outstanding=40e6),
        short=ShortInterest(ticker="ACME", settlement_date=date(2026, 8, 14),
                            short_interest_shares=4e6, days_to_cover=5.0),
        float_providers=[FakeFloat(20e6)])
    structure = service.context("ACME", NOW,
                                event_at=NOW - timedelta(minutes=10)).structure

    assert structure.short_percent_float == pytest.approx(20.0)
    assert structure.short_percent_shares_outstanding == pytest.approx(10.0)
    assert structure.short_interest_as_of is not None


def test_one_failing_provider_call_does_not_lose_the_rest_of_the_context():
    service, _ = build_service(fail={"details", "short"})
    context = service.context("ACME", NOW, event_at=NOW - timedelta(minutes=10))

    assert context.price_before == 10.0     # prices survived
    assert context.structure.market_cap is None
    assert context.structure.short_percent_float is None


def test_service_without_providers_is_honest_rather_than_neutral():
    service = CatalystMarketDataService(bars=None, structure=None, settings=settings())
    assert service.available is False

    context = service.context("ACME", NOW, event_at=NOW)
    assert context.price_now is None
    assert context.structure.missing()


# ── engine changes that depend on the new inputs ──────────────────────────────


def test_short_interest_on_shares_outstanding_is_discounted_and_labelled():
    on_float = amp.MarketStructure(
        short_percent_float=25.0, short_interest_as_of=NOW - timedelta(days=3),
        free_float_shares=20e6, share_price=10.0)
    on_shares = amp.MarketStructure(
        short_percent_shares_outstanding=25.0,
        short_interest_as_of=NOW - timedelta(days=3),
        free_float_shares=20e6, share_price=10.0)

    strong = amp.assess_amplification(on_float, NOW)
    weaker = amp.assess_amplification(on_shares, NOW)

    assert strong.components["short_interest"] > weaker.components["short_interest"]
    assert any("shares outstanding" in n for n in weaker.notes)


def test_a_stopped_tape_makes_the_quote_untradeable():
    """Five minutes without a print during regular hours is a halt in all but
    name — and we do not claim to know the reason."""
    structure = amp.MarketStructure(
        session="regular", quote_stale_seconds=900.0, spread_pct=0.2,
        avg_dollar_volume=50e6, halt_state=HaltState.UNKNOWN)

    quality = amp.assess_execution_quality(structure)

    assert quality.tradeable is False
    assert quality.score == 0.0
    assert "possible halt" in quality.notes[0]


def test_a_quiet_tape_after_hours_is_not_treated_as_a_halt():
    structure = amp.MarketStructure(
        session="post", quote_stale_seconds=900.0, spread_pct=0.2,
        avg_dollar_volume=50e6)
    assert amp.assess_execution_quality(structure).tradeable is True


def test_stale_prices_leave_reaction_room_unresolved():
    abnormal = AbnormalMove(raw_move_pct=8.0, abnormal_move_pct=7.5, move_multiple=1.5)
    room = assess_reaction_room(abnormal=abnormal, analogue_expected_move_pct=20.0,
                                prices_stale=True)

    assert room.unresolved is True
    assert "tape has stopped" in room.notes[0]


def test_market_status_endpoint_is_reachable():
    provider = fake_polygon({"/v1/marketstatus": {"market": "open"}})
    assert provider.market_status()["market"] == "open"


def test_daily_bars_trims_to_the_requested_count():
    rows = [{"t": 1787000000000 + i * 86400000, "o": 10, "h": 11, "l": 9, "c": 10 + i,
             "v": 1000} for i in range(40)]
    provider = fake_polygon({"/v2/aggs": {"results": rows}})
    bars = provider.daily_bars("ACME", 10)

    assert len(bars) == 10
    assert bars[-1].close == 49


def test_the_adapter_sends_the_api_key_and_never_logs_it():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=SNAPSHOT_PAYLOAD)

    provider = PolygonProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="secret-key")
    provider.snapshot("ACME")

    assert seen["params"]["apiKey"] == "secret-key"
    # And the DTO carries no credential anywhere.
    assert "secret" not in json.dumps(provider.snapshot("ACME").__dict__, default=str)
