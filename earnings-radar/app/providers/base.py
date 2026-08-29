"""Provider abstractions: DTOs, rate limiting, caching, retries, fallback.

Every external dependency sits behind an interface here so any provider can be
replaced without touching the services (spec §SYSTEM ARCHITECTURE).
"""
from __future__ import annotations

import abc
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.domain.enums import MarketSession, ReleaseSourceKind

# ─── DTOs ─────────────────────────────────────────────────────────────────────


@dataclass
class CalendarEntry:
    ticker: str
    date: date
    session: MarketSession
    eps_estimate: float | None = None
    revenue_estimate: float | None = None
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    call_time_utc: datetime | None = None
    provider: str = ""
    source_url: str = ""


@dataclass
class EstimateDTO:
    metric: str                # eps | revenue | next_q_revenue | next_q_eps | fy_revenue | fy_eps
    period: str                # current | next_q | fy
    value: float
    provider: str
    confidence: float = 1.0


@dataclass
class Quote:
    ticker: str
    price: float
    prev_close: float | None = None
    volume: float | None = None
    session: str = "regular"   # regular | pre | post
    as_of: datetime | None = None
    provider: str = ""


@dataclass
class FilingHit:
    ticker: str
    form_type: str             # 8-K, 6-K, 10-Q, ...
    accepted_at_utc: datetime
    url: str
    description: str = ""
    items: list[str] = field(default_factory=list)   # e.g. 8-K item codes ("2.02")
    provider: str = "SEC"


@dataclass
class NewsItem:
    ticker: str | None
    title: str
    url: str
    published_at_utc: datetime | None
    source: ReleaseSourceKind
    summary: str = ""


@dataclass
class CompanyProfile:
    ticker: str
    name: str = ""
    exchange: str = ""
    market_cap: float | None = None
    avg_volume: float | None = None
    sector: str = ""
    industry: str = ""
    ir_url: str = ""
    cik: str | None = None


# ─── Errors ───────────────────────────────────────────────────────────────────


class ProviderError(Exception):
    """Transient or permanent failure of one provider call."""


class ProviderUnavailable(ProviderError):
    """Provider disabled (no API key) or circuit open — skip, don't retry."""


class AllProvidersFailed(Exception):
    def __init__(self, purpose: str, errors: dict[str, str]):
        self.purpose = purpose
        self.errors = errors
        super().__init__(f"all providers failed for {purpose}: {errors}")


# ─── Interfaces ───────────────────────────────────────────────────────────────


class EarningsCalendarProvider(abc.ABC):
    name: str = "calendar"

    @abc.abstractmethod
    def fetch_window(self, start: date, end: date) -> list[CalendarEntry]: ...


class EstimatesProvider(abc.ABC):
    name: str = "estimates"

    @abc.abstractmethod
    def fetch_estimates(self, ticker: str) -> list[EstimateDTO]: ...


class PriceProvider(abc.ABC):
    name: str = "price"

    @abc.abstractmethod
    def quote(self, ticker: str) -> Quote: ...

    def daily_closes(self, ticker: str, days: int) -> list[float]:
        """Oldest→newest closes; optional (used for pre-earnings run)."""
        raise ProviderUnavailable(f"{self.name} has no historical closes")


class FilingProvider(abc.ABC):
    name: str = "filings"

    @abc.abstractmethod
    def recent_filings(self, ticker: str, cik: str | None) -> list[FilingHit]: ...

    @abc.abstractmethod
    def fetch_document_text(self, url: str) -> str: ...


class NewswireProvider(abc.ABC):
    name: str = "newswire"

    @abc.abstractmethod
    def recent_items(self, ticker: str, company_name: str) -> list[NewsItem]: ...


class ProfileProvider(abc.ABC):
    name: str = "profile"

    @abc.abstractmethod
    def profile(self, ticker: str) -> CompanyProfile: ...


class NotifierProvider(abc.ABC):
    name: str = "notifier"

    @abc.abstractmethod
    def send(self, title: str, body: str, high_priority: bool = False) -> None: ...

    @abc.abstractmethod
    def enabled(self) -> bool: ...


# ─── Resilience primitives ────────────────────────────────────────────────────


class RateLimiter:
    """Token-bucket limiter; blocks the calling thread until a slot frees."""

    def __init__(self, rate_per_second: float, burst: int = 1):
        self.rate = rate_per_second
        self.capacity = max(burst, 1)
        self.tokens = float(self.capacity)
        self.last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) / self.rate
            time.sleep(wait)


class DailyQuota:
    """Hard daily call budget (e.g. FMP free tier)."""

    def __init__(self, limit: int):
        self.limit = limit
        self._day: date | None = None
        self._used = 0
        self._lock = threading.Lock()

    def consume(self) -> bool:
        with self._lock:
            today = datetime.now(UTC).date()
            if self._day != today:
                self._day = today
                self._used = 0
            if self._used >= self.limit:
                return False
            self._used += 1
            return True


class TTLCache:
    def __init__(self, ttl_seconds: float, max_items: int = 2048):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._data: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            hit = self._data.get(key)
            if hit and time.monotonic() - hit[0] < self.ttl:
                return hit[1]
            return None

    def put(self, key: str, value: object) -> None:
        with self._lock:
            if len(self._data) >= self.max_items:
                self._data.pop(next(iter(self._data)))
            self._data[key] = (time.monotonic(), value)


def retry_with_backoff(fn, attempts: int = 3, base_delay: float = 0.5, max_delay: float = 8.0,
                       sleep=time.sleep):
    """Jittered exponential backoff over transient ProviderErrors."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except ProviderUnavailable:
            raise
        except ProviderError as exc:
            last = exc
            if attempt < attempts - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                sleep(delay + random.uniform(0, delay / 2))
    assert last is not None
    raise last


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 120.0):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown_seconds
        self.failures = 0
        self.open_until = 0.0
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            return time.monotonic() >= self.open_until

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.open_until = time.monotonic() + self.cooldown
                self.failures = 0


class FallbackChain:
    """Try providers in order; report which failed and why.

    health_cb(provider_name, ok, error_text) lets the caller persist
    provider-health rows without this module knowing about the DB.
    """

    def __init__(self, purpose: str, health_cb=None, *, attempts: int = 2,
                 failure_threshold: int = 3, sleep=time.sleep):
        self.purpose = purpose
        self.health_cb = health_cb
        # Few in-provider retries: with a second provider available, failing
        # over beats waiting out a long backoff on the latency-critical path.
        self.attempts = attempts
        self.failure_threshold = failure_threshold
        self.sleep = sleep
        self._breakers: dict[str, CircuitBreaker] = {}

    def _breaker(self, name: str) -> CircuitBreaker:
        return self._breakers.setdefault(
            name, CircuitBreaker(failure_threshold=self.failure_threshold))

    def call(self, providers: list, fn_name: str, *args, **kwargs):
        errors: dict[str, str] = {}
        for provider in providers:
            name = getattr(provider, "name", provider.__class__.__name__)
            breaker = self._breaker(name)
            if not breaker.allow():
                errors[name] = "circuit open"
                continue
            try:
                result = retry_with_backoff(
                    lambda p=provider: getattr(p, fn_name)(*args, **kwargs),
                    attempts=self.attempts, sleep=self.sleep)
                breaker.record_success()
                if self.health_cb:
                    self.health_cb(name, True, "")
                return result, name
            except ProviderUnavailable as exc:
                errors[name] = f"unavailable: {exc}"
            except ProviderError as exc:
                breaker.record_failure()
                errors[name] = str(exc)
                if self.health_cb:
                    self.health_cb(name, False, str(exc))
        raise AllProvidersFailed(self.purpose, errors)
