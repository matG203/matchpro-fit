# Changelog

All notable changes to Earnings Radar are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); this project
uses semantic versioning.

## [0.2.0] — 2026-08-29

Adds **Catalyst Sentinel**, a second pipeline for non-earnings catalysts, under
a shared Sentinel umbrella. Earnings Sentinel is unchanged and its 133 tests
still pass; 219 tests pass in total.

### Added

**Catalyst domain**
- Event taxonomy across contracts, M&A, biotech/FDA, guidance, capital
  allocation, financing, legal, regulatory, product, ownership and restructuring.
- Source tiers (primary / newswire / reputable news / secondary) with quality
  weights, and a certainty ladder from EXECUTED down to SPECULATIVE.
- 15 new tables, including immutable decision-time snapshots so backtesting
  cannot be contaminated by later data.

**Detection and resolution**
- SEC filing routing over 8-K item codes and 25+ form types; Item 2.02 hands off
  to Earnings Sentinel rather than double-counting.
- `NewsProvider` interface plus a mock implementation, so the subsystem runs and
  is testable with no credentials.
- Entity resolution with explicit confidence and an alert gate — a story that
  cannot be mapped confidently is never alerted.
- Aggressive deduplication into event clusters: syndicated copies of one story
  collapse to one event, scored once.

**Analysis engines (all deterministic)**
- Novelty engine distinguishing genuinely new information, recycled commentary,
  and incremental information where uncertainty has collapsed.
- Materiality engines for contracts (ceiling vs guaranteed vs funded, multi-award
  discounting), buybacks (authorisation vs execution, funding capacity), special
  dividends, M&A (target premium, acquirer dilution, clearance as uncertainty
  reduction) and legal awards.
- Negative-offset engine: textual, structural and dilution/cash-runway offsets,
  aggregated so one fatal flaw outweighs three mild caveats.
- Abnormal-move measurement, benchmark- and volatility-normalised, plus Reaction
  Room scored against historical analogue expectations.
- Move Amplification from float, short interest (freshness-weighted), relative
  volume and volatility — kept strictly separate from Execution Quality.

**Claude layer**
- Two-pass investigation: cheap triage, then adversarial deep review instructed
  to *disprove* the thesis. Facts are extracted before any interpretation, and a
  guardrail flags any contradiction of retrieved fundamentals.

**Scoring and alerting**
- Seven components → Upside Catalyst Score, with hard gates, event-type caps and
  a 9.5+ threshold requiring every condition simultaneously.
- Fundamental impact and immediate reaction potential reported separately.
- Idempotent alerts with band-based deduplication and pre-send revalidation.

**Interface**
- Live catalysts view, full auditable detail page with pipeline timeline, and
  calibration reporting honest about sample size.

### Tests

86 new tests, including the spec's false-positive scenarios: multi-award ceiling,
missed primary endpoint, buyback authorisation, already-priced catalyst, earnings
interaction, five-way syndication, unmappable story, halted stock, missing price
and unavailable LLM.

### Notes

- Still no automated trading.
- Historical analogues and ML calibration deliberately deferred until real
  outcome data exists; until then confidence is penalised for the absent sample.

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
