# Changelog

All notable changes to Earnings Radar are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); this project
uses semantic versioning.

## [0.1.0] — 2026-08-28

First working MVP: the full DISCOVER → MONITOR → DETECT → VERIFY → ANALYSE →
SCORE → NOTIFY pipeline, with 133 passing tests.

### Added

**Architecture**
- `ARCHITECTURE.md`: specification review, identified weaknesses and fixes,
  final architecture, provider recommendations with free/paid cost estimates,
  PostgreSQL schema, folder structure, event state machine, LLM JSON contract,
  scoring algorithm, polling logic, fallback strategy, notification design and
  MVP roadmap.

**Domain core**
- Event state machine with enforced legal transitions — verification and
  scoring cannot be skipped.
- UTC-everywhere timezone discipline; Europe/London and America/New_York
  conversion via `zoneinfo` (BST/GMT and EST/EDT automatic); naive datetimes
  rejected at the boundary.
- Canonical release identity (`TICKER|FY|Q`) with a DB unique constraint.

**Providers** (all behind replaceable interfaces)
- SEC EDGAR: submissions-JSON polling, ticker→CIK map, acceptance timestamps,
  document retrieval, 8-K Item 2.02 detection.
- Finnhub and FMP: earnings calendar, consensus estimates, quotes, profiles.
- Newswire RSS (Business Wire / PR Newswire / GlobeNewswire), RSS + Atom.
- ntfy and Pushover push channels.
- Resilience: token-bucket rate limiting, daily quotas, TTL caching, jittered
  exponential backoff, circuit breakers, ordered fallback chains.

**Services**
- Discovery with multi-calendar merge, schedule confidence (`HIGH`/`MEDIUM`/
  `LOW`) plus the stored reason, release-window estimation from Eastern wall
  clock, liquidity tiering from megacap to microcap.
- APScheduler-driven daily discovery (05:00 London) with four reconciliation
  passes, and an adaptive monitoring loop with per-event leases.
- Multi-source release detection; strict verification that rejects scheduling
  notices, placeholders, previews and previous-quarter reports; deduplication.
- Deterministic financial extraction with per-fact confidence and source
  attribution.
- Expectations engine: consensus bands across providers, disagreement
  detection, conservative-edge surprise calculation.
- Market data: pre-earnings runs, dual-baseline reaction measurement,
  spike-and-fade / momentum classification, cross-provider conflict detection.
- Analysis engine using Claude structured outputs with a strict schema,
  evidence-only prompting, retries, and a numeric cross-check against
  deterministic extraction.
- Scoring v1.0: earnings quality, market confirmation, current entry and final
  trade score; weighted components; veto rules capping 9+; `SCORE_REVIEW` for
  market disagreement; analysis confidence; `scoring_model_version` stored on
  every score.
- Idempotent minimal push notifications with emoji bands and score/confidence
  thresholds.
- Audit service recording every check and decision.

**Interface**
- JSON API: today, results, release detail, audit, health, manual discovery and
  monitor triggers.
- Server-rendered dashboard with watchlist, results and full detail pages;
  light/dark aware.

**Tests** — 133 passing
- Unit: scoring calibration and vetoes, timezone/DST, state machine, canonical
  IDs, polling cadence, guidance classification, provider fallback and circuit
  breaking, extraction, verification, consensus bands, reaction analytics,
  notification formatting, LLM schema and anti-hallucination.
- Integration: discovery, reconciliation, monitoring loop, API and dashboard.
- The six specification regression cases: stale IR page vs newswire, pre-run
  then selloff, one-off tax benefit, previously-known news, conflicting price
  feeds, disagreeing consensus providers.

### Notes

- No automated trading, by design.
- Options-implied move is deferred to Phase 2 rather than fabricated.
