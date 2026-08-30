# Changelog

All notable changes to Earnings Radar are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); this project
uses semantic versioning.

## [0.3.4] — 2026-08-30

### Fixed

- **Every score insert failed on an existing database.** The columns added in
  0.3.1–0.3.3 (`scoring_inputs`, `revision_reason`, `superseded`,
  `move_observable`, `data_delay_seconds`, `data_provider`) are NOT NULL with
  Python-side defaults. SQLAlchemy's `default=` is applied on insert and never
  reaches the DDL, so `add_missing_columns` refused them as non-nullable — and
  every later INSERT then named a column the table did not have:

  ```
  OperationalError: table catalyst_scores has no column named scoring_inputs
  ```

  A fresh database was fine, which is why the tests passed; only an upgraded
  one broke. `add_missing_columns` now derives a SQL literal from the model's
  default and adds NOT NULL columns with it, so existing rows get the same
  value a new row would. A NOT NULL column with no default is still refused —
  there is no honest value for the rows already there.
- Regression test replays the real 0.3.0 → 0.3.4 upgrade on a populated
  database and asserts the insert that used to fail now succeeds.

## [0.3.3] — 2026-08-30

### Added

- **`python -m app.preflight`** (and `GET /api/preflight`): one real call per
  capability, so a wrong key is caught on setup day rather than on an earnings
  evening. Every provider here fails quietly by design, which means a bad key
  looks exactly like a quiet market.
- Preflight measures the **observed** feed delay from a live timestamp and
  compares it to `MARKET_DATA_DELAY_SECONDS`. Configuring 0 on a delayed plan is
  reported as a failure — it is the direction that inverts the signal, scoring a
  move you cannot see yet as no move. The opposite mistake is a warning: merely
  wasteful. The check is skipped when the market is closed, where a stale print
  proves nothing.
- Preflight reports which `.env` was read and which keys came out of it,
  masked to four characters either end. This answers "is the key definitely in
  there" without opening the file, and names the two failures that are
  indistinguishable from a wrong key: Notepad saving `.env.txt`, and running
  from the wrong folder.
- `start.bat`: runs preflight, keeps Windows awake while open, starts the app,
  and restores the normal power settings on exit.
- `POLYGON_BASE_URL` — Polygon rebranded to Massive in July 2026 and
  `api.polygon.io` still serves the same API with the same keys, but a future
  endpoint move is now a settings change rather than a code change.

## [0.3.2] — 2026-08-30

Fixes a defect that would have made the **earnings** pipeline silent on a
delayed feed. 320 tests pass.

### Fixed

- **No earnings release could ever have alerted on Polygon Starter.**
  `capture_reaction` ran once, at `minutes_after=0`, which on a 15-minute feed
  is always inside the withhold window — so market confirmation was withheld,
  the "unavailable live price feeds" veto applied, and nothing ever came back
  to lift it. Every release would have been permanently capped at 8.9 against a
  9.0 push threshold. This matters more than the catalyst case: US releases land
  at 16:05 ET and the whole reaction happens after hours, so the delay always
  covers the moment of scoring.

### Added

- `EarningsRescoreService`: re-measures the after-hours reaction once the feed
  can show it, recomputes the score from the stored inputs (no second LLM call),
  and updates the stored context. Runs in the same scheduler job as the catalyst
  pass.
- `scoring_inputs`, `rescored_at` and `score_before_rescore` on `scores`;
  `ScoringInputs.to_dict`/`from_dict` for the earnings scorer.
- `NotificationService.band()` and a `revision` argument to `notify_score`, so a
  re-score that crosses a band can notify again while a drift inside one stays
  silent.

```
AMC release on a 15-minute feed:
  21:05 UK  scored blind        8.8   veto: unavailable live price feeds
  21:20 UK  re-scored, +9% AH   9.3   no vetoes
```

## [0.3.1] — 2026-08-30

Makes the system correct on a **delayed price feed**, so it can run on Polygon's
Stocks Starter plan ($29/mo, 15 minutes behind) and move to Advanced ($199/mo,
real-time) by changing one number. 315 tests pass.

### Fixed

Two defects that only appear on a delayed feed, both found by simulating one:

- **Every stock was flagged as a possible halt.** Quote staleness was measured
  as raw age, but on a 15-minute plan every healthy quote is 15 minutes old.
  Staleness is now silence *beyond* the feed's own delay, so a real halt is
  still caught (a stock silent for 25 minutes reads as 10 minutes stale) while
  a healthy one reads as zero.
- **A not-yet-visible move was scored as no move.** The measured move reads 0%
  before the feed catches up. Reaction Room scored that as "untouched — all the
  room is still there", producing a high score on a stock that had already run
  60%: the signal inverted at exactly the moment it matters. It is now
  explicitly unresolved, with the reason stated, and the score capped for it.

### Added

- `MARKET_DATA_DELAY_SECONDS` — the entire Starter → Advanced upgrade. The
  system uses it to tell "has not moved" apart from "cannot see it yet".
- **Re-score pass** (`app/services/rescore.py`): revisits catalysts scored
  before their move was visible, once the data arrives. The original
  `ScoringInputs` are stored verbatim on each score, so only the market-derived
  half is recomputed — **no second Claude call, no extra API spend**. The first
  score is kept and marked superseded; re-alerting reuses the existing
  band-based deduplication, so a revision inside the same band is silent.
- **`/api/catalyst/delay-impact`**: the evidence for the upgrade decision. Not
  "did scores move" but how often waiting changed what you would have done —
  alerts that would have fired sooner, and moves already gone by the time they
  were visible. Blunt about small samples.
- `POST /api/catalyst/rescore` to run the pass on demand; `scoring_inputs`,
  `revision_reason` and `superseded` on `catalyst_scores`; `move_observable`,
  `data_delay_seconds`, `observable_through_utc` and `rescored_at_utc` on
  `reaction_analysis`.

### Changed

- The **earnings** pipeline is delay-aware too: a reaction captured inside the
  delay window is withheld as unresolved rather than recorded as a 0% reaction,
  which would have read as the market declining to confirm a good report.
- Price reasoning runs against what the feed can actually show; no "current"
  price predating the disclosure is published.

## [0.3.0] — 2026-08-30

Catalyst Sentinel stops running on injected test data and starts running on live
prices. 294 tests pass; Earnings Sentinel is unchanged.

### Added

**Polygon.io adapter** (`app/providers/polygon.py`)
- Snapshots carrying last trade, previous close, day aggregate and bid/ask, with
  an extended-hours fallback to the last minute bar — before the open there is
  no day aggregate, and the regular-session close would be a stale answer.
- Minute and daily aggregate bars; reference data; short interest with its
  settlement date; market status.
- `403` is treated as permanent (wrong plan) and `429`/`5xx` as retryable, so a
  missing entitlement does not burn the retry budget.

**Live market context** (`app/services/catalyst_market.py`)
- Prices the event at the moment it became public, from the last minute bar that
  *closed* before the disclosure. The bar the news breaks in already contains the
  reaction; using its close would have erased most of every move.
- Benchmark and sector-ETF comparators measured over the identical window, so an
  abnormal move is genuinely company-specific.
- ATR from true range (so overnight gaps count), realised volatility, relative
  volume, spread, and free float.
- Every field independently guarded: a missing short-interest entitlement leaves
  the price analysis intact.

**Continuous detection** (`app/services/catalyst_poller.py`)
- EDGAR's latest-filings feed as a firehose: one request names every filer, and
  only watched companies get a second call for item codes and documents. A sweep
  over a 400-name universe is typically one request.
- 8-K Item 2.02 and the periodic reports are handed to Earnings Sentinel rather
  than double-scored.
- Form 3/4/5 and 13G are routed on metadata without downloading the document.
- A full response that parses to zero filings is raised as a format change, not
  reported as a quiet market.

**Outcome capture** (`app/services/outcomes.py`)
- Returns at +1m/+5m/+15m/+30m/+60m, close, next open and +1d, measured from the
  disclosure price and benchmark-adjusted, plus MFE/MAE.
- Backfilled from historical bars rather than sampled live, so nothing depends on
  the process being awake at a particular second; incremental and idempotent.
- Completed events populate `historical_analogues`, which is the only route by
  which Reaction Room ever stops guessing.

**Schema**
- `market_structure_snapshots` gains `short_percent_shares_outstanding`,
  `quote_stale_seconds` and `data_provider`.
- `init_db` now adds nullable columns that exist in the models but not in the
  database. `create_all` only creates missing *tables*, so without this an
  existing local database would break on the next insert.

### Changed

- Short interest may now be expressed against shares outstanding when free float
  is unavailable. It is stored in its own column, weighted at 60% confidence and
  labelled in the notes — it flatters the stock, so it is never relabelled as
  short interest of float.
- A stopped tape during regular hours now zeroes Execution Quality and marks
  Reaction Room unresolved. This is reported as staleness rather than as a halt:
  the consequence is identical, but we do not claim to know the reason.
- `market_context_fn` receives the disclosure time and the company's sector.
- Polygon leads the price fallback chain when configured.

### Fixed

- The EDGAR feed's title regex split on a bare hyphen, which would have dropped
  every form containing one — 8-K, 10-Q, S-1, SC 13D/A, very nearly everything.
- `realised_volatility_pct` used `zip(..., strict=True)` on deliberately offset
  sequences and so always raised.

### Notes

- Still no automated trading.
- The live EDGAR latest-filings feed could not be reached from the build
  environment (network policy blocks sec.gov), so its parsing is verified against
  a recorded fixture rather than a live response. Worth watching on the first
  real run — the format-change guard will say so loudly if the shape differs.

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
