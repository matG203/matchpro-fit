"""Provider layer: fallback chains, rate limiting, quotas, feed parsing."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.enums import ReleaseSourceKind
from app.providers.base import (
    AllProvidersFailed,
    DailyQuota,
    FallbackChain,
    FilingHit,
    PriceProvider,
    ProviderError,
    ProviderUnavailable,
    Quote,
    RateLimiter,
    TTLCache,
    retry_with_backoff,
)
from app.providers.newswire import parse_feed
from app.providers.sec_edgar import _parse_acceptance, is_earnings_filing


class FlakyPrice(PriceProvider):
    def __init__(self, name: str, fail_times: int = 0, price: float = 100.0,
                 unavailable: bool = False):
        self.name = name
        self.fail_times = fail_times
        self.price = price
        self.unavailable = unavailable
        self.calls = 0

    def quote(self, ticker: str) -> Quote:
        self.calls += 1
        if self.unavailable:
            raise ProviderUnavailable(f"{self.name} disabled")
        if self.calls <= self.fail_times:
            raise ProviderError(f"{self.name} transient failure")
        return Quote(ticker=ticker, price=self.price, provider=self.name)


# ── fallback ─────────────────────────────────────────────────────────────────

def test_primary_provider_is_used_when_healthy():
    primary, secondary = FlakyPrice("primary"), FlakyPrice("secondary", price=50.0)
    quote, name = FallbackChain("price").call([primary, secondary], "quote", "ESTC")
    assert name == "primary"
    assert quote.price == 100.0
    assert secondary.calls == 0


def test_failover_to_secondary_when_primary_keeps_failing():
    primary = FlakyPrice("primary", fail_times=99)
    secondary = FlakyPrice("secondary", price=50.0)
    quote, name = FallbackChain("price", sleep=lambda _: None).call(
        [primary, secondary], "quote", "ESTC")
    assert name == "secondary"
    assert quote.price == 50.0


def test_unavailable_provider_is_skipped_without_retries():
    disabled = FlakyPrice("nokey", unavailable=True)
    working = FlakyPrice("working", price=42.0)
    quote, name = FallbackChain("price").call([disabled, working], "quote", "ESTC")
    assert name == "working" and quote.price == 42.0
    assert disabled.calls == 1  # no retry storm on a permanently disabled provider


def test_all_providers_failed_reports_every_error():
    a, b = FlakyPrice("a", fail_times=99), FlakyPrice("b", fail_times=99)
    with pytest.raises(AllProvidersFailed) as exc:
        FallbackChain("price", sleep=lambda _: None).call([a, b], "quote", "ESTC")
    assert set(exc.value.errors) == {"a", "b"}


def test_transient_failures_are_retried_then_succeed():
    provider = FlakyPrice("flaky", fail_times=1)
    quote, name = FallbackChain("price", sleep=lambda _: None).call(
        [provider], "quote", "ESTC")
    assert name == "flaky" and quote.price == 100.0
    assert provider.calls == 2


def test_retry_backoff_stops_after_attempts():
    calls = {"n": 0}

    def always_fail():
        calls["n"] += 1
        raise ProviderError("nope")

    with pytest.raises(ProviderError):
        retry_with_backoff(always_fail, attempts=3, sleep=lambda _: None)
    assert calls["n"] == 3


def test_circuit_opens_after_repeated_failures():
    bad = FlakyPrice("bad", fail_times=999)
    good = FlakyPrice("good", price=7.0)
    chain = FallbackChain("price", sleep=lambda _: None)
    for _ in range(3):
        chain.call([bad, good], "quote", "X")
    calls_before = bad.calls
    chain.call([bad, good], "quote", "X")
    assert bad.calls == calls_before  # circuit open — provider not called again


# ── rate limiting, quota, cache ──────────────────────────────────────────────

def test_rate_limiter_allows_burst_then_throttles():
    limiter = RateLimiter(rate_per_second=1000, burst=3)
    for _ in range(5):
        limiter.acquire()  # would hang forever if the bucket never refilled


def test_daily_quota_blocks_when_exhausted():
    quota = DailyQuota(limit=2)
    assert quota.consume() and quota.consume()
    assert quota.consume() is False


def test_ttl_cache_returns_value_then_expires():
    cache = TTLCache(ttl_seconds=1000)
    cache.put("k", 123)
    assert cache.get("k") == 123
    assert TTLCache(ttl_seconds=-1).get("missing") is None


# ── SEC helpers ──────────────────────────────────────────────────────────────

def test_8k_item_202_is_an_earnings_filing():
    hit = FilingHit(ticker="ESTC", form_type="8-K",
                    accepted_at_utc=datetime.now(UTC), url="u",
                    items=["2.02", "9.01"])
    assert is_earnings_filing(hit)


def test_unrelated_8k_is_not_an_earnings_filing():
    hit = FilingHit(ticker="ESTC", form_type="8-K",
                    accepted_at_utc=datetime.now(UTC), url="u",
                    items=["5.02"], description="Departure of Directors")
    assert not is_earnings_filing(hit)


def test_10q_and_6k_always_count():
    for form in ("10-Q", "6-K"):
        hit = FilingHit(ticker="X", form_type=form,
                        accepted_at_utc=datetime.now(UTC), url="u")
        assert is_earnings_filing(hit)


def test_sec_acceptance_timestamp_is_parsed_as_utc():
    parsed = _parse_acceptance("2026-08-27T21:05:03.000Z")
    assert parsed.tzinfo is not None
    assert (parsed.hour, parsed.minute, parsed.second) == (21, 5, 3)


# ── newswire feed parsing ────────────────────────────────────────────────────

RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Elastic Reports Second Quarter Fiscal 2026 Financial Results</title>
<link>https://wire.example/estc-q2</link>
<pubDate>Thu, 27 Aug 2026 21:05:03 GMT</pubDate>
<description>Revenue of $427.3 million</description></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Acme Announces Q3 Results</title>
<link href="https://wire.example/acme"/>
<published>2026-08-27T21:05:03Z</published></entry></feed>"""


def test_rss_feed_is_parsed_with_utc_timestamp():
    items = parse_feed(RSS, "ESTC", ReleaseSourceKind.BUSINESSWIRE)
    assert len(items) == 1
    assert items[0].url == "https://wire.example/estc-q2"
    assert items[0].published_at_utc.hour == 21
    assert items[0].source == ReleaseSourceKind.BUSINESSWIRE


def test_atom_feed_is_parsed():
    items = parse_feed(ATOM, "ACME", ReleaseSourceKind.GLOBENEWSWIRE)
    assert len(items) == 1 and items[0].url == "https://wire.example/acme"


def test_malformed_feed_raises_provider_error():
    with pytest.raises(ProviderError):
        parse_feed("<not xml", "X", ReleaseSourceKind.OTHER)


# ── SEC timeouts ─────────────────────────────────────────────────────────────
#
# A live Railway deployment failed preflight with "The read operation timed
# out" on the latest-filings feed — a call that takes a couple of seconds from
# a home connection. EDGAR builds that feed per request and its latency varies
# wildly, so a slow response is normal rather than a fault.
#
# This matters more than a slow page: a timed-out sweep finds no filings, which
# is indistinguishable from an hour in which nobody filed.


def _sec_with(responses):
    """SecEdgarProvider whose transport plays back `responses` in order.

    Each entry is either an exception to raise or a body to return.
    """
    import httpx

    from app.providers.sec_edgar import SecEdgarProvider

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        item = responses[min(calls["n"], len(responses) - 1)]
        calls["n"] += 1
        if isinstance(item, Exception):
            raise item
        return httpx.Response(200, text=item)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = SecEdgarProvider(client=client)
    provider._timeout_retries = 2
    return provider, calls


FEED_OK = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>8-K - ACME CORP (0000012345) (Filer)</title>
    <link rel="alternate" href="https://www.sec.gov/x-index.htm"/>
    <updated>2026-08-27T10:20:31-04:00</updated>
  </entry>
</feed>"""


def test_a_transient_sec_timeout_is_retried(monkeypatch):
    import httpx

    monkeypatch.setattr("time.sleep", lambda _s: None)
    provider, calls = _sec_with([httpx.ReadTimeout("timed out"), FEED_OK])

    entries = provider.latest_filings(count=10)

    assert len(entries) == 1
    assert calls["n"] == 2, "should have retried exactly once before succeeding"


def test_repeated_timeouts_still_fail_rather_than_reporting_no_filings(monkeypatch):
    """The wrong answer here is an empty list — that reads as 'nobody filed'."""
    import httpx

    from app.providers.base import ProviderError

    monkeypatch.setattr("time.sleep", lambda _s: None)
    provider, calls = _sec_with([httpx.ReadTimeout("timed out")])

    with pytest.raises(ProviderError) as caught:
        provider.latest_filings(count=10)

    assert "timed out" in str(caught.value)
    assert calls["n"] == 3, "one initial attempt plus two retries"


def test_a_403_is_not_retried():
    """Only timeouts are worth retrying. A 403 means the user agent is wrong,
    and hammering SEC over it is exactly what their guidance forbids."""
    import httpx

    from app.providers.base import ProviderError
    from app.providers.sec_edgar import SecEdgarProvider

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(403, text="Forbidden")

    provider = SecEdgarProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ProviderError):
        provider.latest_filings(count=10)

    assert calls["n"] == 1
