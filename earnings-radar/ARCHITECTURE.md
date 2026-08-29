# Earnings Radar — Architecture

> DISCOVER → MONITOR → DETECT → VERIFY → ANALYSE → SCORE → NOTIFY
>
> Status: v1.0 (MVP architecture, implemented in Phase 1)

---

## 1. Specification review — weaknesses found & improvements made

The spec is strong. These are the points where I deviated from or hardened it:

### 1.1 Detection: poll the *cheapest, fastest-updating* index, not the documents
Polling IR pages or full press-release pages every 15s per company is slow (full HTML
fetches), fragile (IR pages are stale — your own war story) and rude to hosts. The
implemented design polls **small, machine-readable indexes**:

- **SEC EDGAR "recent filings" JSON** per CIK (`data.sec.gov/submissions/CIK##########.json`)
  — one small JSON GET tells us instantly whether an 8-K/6-K/10-Q just hit. EDGAR
  acceptance timestamps are also the best "official publication time" source.
- **Newswire RSS feeds** (Business Wire / PR Newswire / GlobeNewswire ticker & keyword
  feeds) — small XML, updated within seconds of the wire crossing.
- IR pages are a *verification/enrichment* source, not the primary detector.

This is the single biggest latency & reliability win over naive "check the IR page".

### 1.2 Two-phase scoring to protect notification latency
The LLM call is the slowest stage (10–40s). The pipeline computes a **deterministic
provisional package first** (extraction, surprise %, guidance classification, market
reaction) so that if the LLM stage fails or times out, we can still (configurably) send
a provisional notification rather than nothing. The push fires on the first score whose
`analysis_confidence` clears the threshold — normally the LLM-refined one.

### 1.3 Consensus quality is the weakest link — treat it as first-class uncertainty
Free-tier consensus data is mediocre. Rather than pretending otherwise, every estimate
row carries `(value, provider, retrieved_at, confidence)`; the expectations engine
computes a **consensus band** (min/max across providers), and the scoring engine scores
the beat against the band, never against the friendliest number (spec §consensus,
regression case 6). `estimate_confidence` flows into `analysis_confidence`.

### 1.4 Everything in UTC, converted at the edges
All timestamps stored as timezone-aware UTC. `Europe/London` (and `America/New_York`
for market sessions) are *display/derivation* zones only, via `zoneinfo` — BST/GMT and
EST/EDT handled automatically. Never a naive datetime in the DB.

### 1.5 Idempotency & concurrency
- Canonical release ID (`ticker|fy|fq`) with a DB unique constraint = dedup at the
  storage layer, not just app logic.
- A per-event `in_flight` lease prevents overlapping checks of the same company
  (spec §adaptive monitoring).
- Notification sends are recorded *before* dispatch with a unique key so a crash cannot
  double-notify.

### 1.6 Backtestability by construction
Every fact row carries `retrieved_at` and `source_url`. Every pipeline decision is an
audit event with a timestamp. A backtest replays only facts with
`retrieved_at <= simulated_now` — lookahead bias is prevented by the data model, not by
discipline.

### 1.7 What was intentionally deferred (Phase 2/3)
Options-implied move (needs a paid feed to be trustworthy), conference-call monitoring,
ML calibration, Celery (APScheduler is sufficient and far simpler for a single-node
MVP), React/Next.js dashboard (MVP ships a server-rendered dashboard from FastAPI —
same API endpoints a Next.js front-end would consume later).

---

## 2. Final architecture

```
                 ┌────────────────────────────────────────────────┐
                 │                 PROVIDER LAYER                 │
                 │  (interfaces + adapters, all replaceable)      │
                 │  CalendarProvider   Finnhub, FMP               │
                 │  FilingProvider     SEC EDGAR                  │
                 │  NewswireProvider   BW/PRN/GNW RSS             │
                 │  EstimatesProvider  Finnhub, FMP               │
                 │  PriceProvider      Finnhub, FMP (cross-check) │
                 │  NotifierProvider   ntfy, Pushover             │
                 └───────┬────────────────────────────────────────┘
                         │ rate-limited, cached, retried, fallback chains
┌───────────┐   ┌────────▼─────────┐   ┌──────────────────┐
│ Scheduler │──▶│ DiscoveryService │──▶│ Watchlist (DB)   │
│(APSched.) │   └──────────────────┘   └────────┬─────────┘
│ 05:00 full│                                   │ adaptive polling plan
│ 4x recon  │   ┌───────────────────────────────▼─────────┐
└─────┬─────┘   │ ReleaseMonitorService                   │
      │         │  EDGAR JSON + newswire RSS + IR page    │
      └────────▶│  → candidate document                   │
                └───────────────┬─────────────────────────┘
                ┌───────────────▼─────────┐
                │ VerificationService     │  ticker/quarter/doc-type checks
                │  + dedup (canonical id) │  release_verified = true
                └───────────────┬─────────┘
        ┌───────────────────────┼───────────────────────────┐
┌───────▼────────┐   ┌──────────▼─────────┐   ┌─────────────▼──────┐
│ Extraction     │   │ ExpectationsService│   │ MarketDataService  │
│ (deterministic │   │ consensus band,    │   │ pre-run, reaction, │
│  regex+tables) │   │ estimate_confidence│   │ spike/fade, x-check│
└───────┬────────┘   └──────────┬─────────┘   └─────────────┬──────┘
        └───────────────────────┼───────────────────────────┘
                ┌───────────────▼─────────────────┐
                │ AnalysisService (Claude,        │  structured JSON,
                │ structured outputs, evidence-   │  schema-validated,
                │ only facts, anti-hallucination) │  retry on invalid
                └───────────────┬─────────────────┘
                ┌───────────────▼────────┐
                │ ScoringService v1.0    │  4 scores, veto rules,
                │ (deterministic)        │  SCORE_REVIEW, confidence
                └───────────────┬────────┘
                ┌───────────────▼────────┐        ┌────────────────┐
                │ NotificationService    │───────▶│ 📱  ESTC 9.2 🔥 │
                └───────────────┬────────┘        └────────────────┘
                                ▼
                     AuditService (every step)
                     FastAPI dashboard + JSON API
```

Module = service. Each service takes its providers via constructor injection; tests
inject fakes. No service imports a concrete provider directly.

---

## 3. Provider recommendations & costs

### Detection & filings (the latency-critical path) — free
| Purpose | Provider | Cost | Notes |
|---|---|---|---|
| US filings, publication timestamps, CIK map | **SEC EDGAR** (`data.sec.gov`) | Free | 10 req/s hard cap; we self-throttle well below. Declared User-Agent required. Best-in-class acceptance timestamps. |
| Newswire detection | **Business Wire / PR Newswire / GlobeNewswire RSS** | Free | Per-company & keyword feeds; seconds-level freshness. |
| IR pages | Company sites | Free | Verification/enrichment only. |

### Calendars, estimates, prices
| Purpose | Free option | Paid upgrade | Est. monthly |
|---|---|---|---|
| Earnings calendar | **Finnhub** free (60 calls/min) + **FMP** free (250 calls/day) — cross-checked | FMP Starter/Premium $22–69, Finnhub $50+ | $0 → ~$25–70 |
| Consensus EPS/revenue | Finnhub free (basic), FMP | **Finnhub estimates** or **Zacks/Benzinga** ($100+) for quality | $0 → $100+ |
| Real-time + extended-hours prices | Finnhub free (delayed AH), FMP | **Polygon.io** $29 (stocks starter) – $199 (real-time + trades, incl. pre/post) | $0 → $29–199 |
| Options implied move (Phase 2) | — (do not fabricate) | Polygon options $29+, ORATS, Tradier | $29+ |
| Push notifications | **ntfy.sh** (default) | **Pushover** $5 one-time (recommended for reliability) | ~$0 |
| LLM analysis | — | **Anthropic API, `claude-opus-5`** ($5/$25 per MTok). ~30–60k in + ~3k out per report ≈ $0.25–0.40/report. 20 reports/night ≈ $6–8/day | ~$120–180 (heavy season), far less off-season |

**MVP total: ~$5 one-time (Pushover) + LLM usage.** First meaningful upgrade when the
system proves itself: Polygon ($29) for trustworthy after-hours prices, then a paid
estimates feed.

Free-tier caveats the code accounts for: FMP 250 calls/day budget is enforced by a
provider-level daily quota; Finnhub after-hours quotes can be stale — hence the
cross-check rule and `market_data_unresolved` flag.

---

## 4. PostgreSQL schema (implemented in `app/db/models.py`)

```
companies
  id PK, ticker (uq), name, exchange, cik, market_cap, avg_volume,
  liquidity_tier, sector, industry, ir_url, kpi_profile (json), created/updated

earnings_events                      -- one expected report (the watchlist row)
  id PK, company_id FK, fiscal_year, fiscal_quarter,
  expected_date, session (BMO/AMC/INTRADAY/UNKNOWN),
  expected_release_at, window_start, window_end,        -- UTC
  call_time, schedule_confidence (HIGH/MED/LOW), confidence_reason,
  eps_estimate, revenue_estimate,                        -- convenience copy
  state (state machine below), state_changed_at,
  monitor_lease_until,                                   -- overlap prevention
  sources (json list), created/updated
  UNIQUE (company_id, fiscal_year, fiscal_quarter)

releases                             -- one confirmed publication (deduped)
  id PK, canonical_key (uq: TICKER|FY|FQ), event_id FK,
  published_at_utc, detected_at_utc, verified_at_utc,
  detection_latency_ms, document_type (8-K/6-K/10-Q/PRESS_RELEASE/...),
  primary_url, verified bool, verification_notes

release_sources                      -- every place we saw it
  id PK, release_id FK, source (SEC/BUSINESSWIRE/IR/...), url,
  first_seen_at, published_at_claimed

estimates                            -- every consensus datapoint, per provider
  id PK, event_id FK, metric (eps/revenue/next_q_revenue/...),
  period (current/next_q/fy), value, provider, retrieved_at, confidence

extracted_financials                 -- deterministic extraction w/ attribution
  id PK, release_id FK, metric, value, unit, period,
  source_url, retrieved_at, confidence, method (regex/table/llm)

kpi_values
  id PK, release_id FK, kpi_name, value, unit, yoy_growth, qoq_growth,
  prior_values (json: [q-2, q-1]), growth_direction (ACCEL/STABLE/DECEL)

market_snapshots                     -- price context & reaction timeline
  id PK, event_id FK, kind (prev_close/pre_release/post_1m/post_5m/.../
  post_high/post_low), price, volume, provider, captured_at
  + per-event derived row: pre_earnings_run_5d/1m/3m, reaction_pattern
    (NONE/POST_EARNINGS_REVERSAL/POST_EARNINGS_MOMENTUM), unresolved bool

analyses                             -- LLM output, verbatim + validated
  id PK, release_id FK, model, prompt_version, raw_json (json),
  earnings_quality, market_confirmation, entry_score, final_trade_score,
  guidance_status (RAISED/NARROWED/MAINTAINED/LOWERED/NONE),
  growth_direction, confidence, verdict, bull_case, bear_case,
  hidden_negatives (json), pre_announced (json), one_off_items (json),
  created_at

scores                               -- final deterministic scoring output
  id PK, release_id FK (uq per model version), scoring_model_version,
  earnings_quality, market_confirmation, entry_score, final_trade_score,
  component_breakdown (json), vetoes_applied (json),
  analysis_confidence, needs_verification bool, score_review bool,
  created_at

notifications
  id PK, release_id FK, dedup_key (uq), channel, title, body,
  status (PENDING/SENT/FAILED), created_at, sent_at, error

audit_log
  id PK, at_utc, event_id FK?, release_id FK?, actor (service name),
  action, detail, level

provider_health
  id PK, provider, last_ok_at, last_error_at, last_error,
  consecutive_failures, circuit_open_until

outcomes                             -- for future calibration (Phase 2/3)
  id PK, release_id FK, price_at_score, price_5m, price_30m,
  next_open, next_close, ret_1d, ret_5d, ret_30d, captured_through
```

SQLAlchemy 2.0, engine URL from `DATABASE_URL`; Postgres in production/docker,
SQLite for local dev and tests (schema is compatible).

---

## 5. Earnings-event state machine

```
DISCOVERED ─▶ SCHEDULED ─▶ MONITORING ─▶ RELEASE_DETECTED ─▶ VERIFYING
                 ▲   │          │                                │
                 │   │          │ window passed, nothing found   ├─ ok ─▶ VERIFIED
    reconciliation   │          ▼                                │         │
    updates schedule │     NOT_YET_VERIFIED (keep polling)       │ bad doc │
                 │   │          │ > grace period                 ▼         ▼
                 └───┘          ▼                        back to      EXTRACTING
                        DELAYED_OR_UNVERIFIED            MONITORING        │
                                                                           ▼
      NOTIFIED ◀─ SCORED ◀─ (SCORE_REVIEW?) ◀─ SCORING ◀─ ANALYSING ◀─ CONTEXT
         │            ▲                                                (expectations
         ▼            └── FAILED (any stage; retries exhausted;         + market data)
       DONE               audit records why)
```

Transitions are the *only* way state changes; every transition writes an audit event.
`SCORE_REVIEW` is entered when `earnings_quality >= 9.0` and reaction ≤ −3%
(market-disagreement rule) — the 9+ cap applies until review resolves.

## 6. Adaptive polling plan (configurable, `app/services/scheduler.py`)

| Time vs expected release | Interval |
|---|---|
| > 60 min before | none (scheduler wakes it at T−60) |
| 60–15 min before | 5 min |
| 15–0 min before | 1 min |
| 0 → +30 min | 20 s (config `burst_interval`, ≥15 s floor for SEC etiquette) |
| +30 → +120 min | 1 min |
| > +120 min | 5 min until grace timeout → DELAYED_OR_UNVERIFIED |

One async monitor loop; each event holds a `monitor_lease_until` so a slow check can
never overlap the next one for the same company.

## 7. Provider fallback strategy

Each provider call goes through `FallbackChain`:
1. try primary (with per-provider rate limiter + response cache + jittered
   exponential backoff on transient errors),
2. on failure record `provider_health`, open circuit after N consecutive failures,
3. try next adapter in the chain,
4. if all fail: raise `AllProvidersFailed` → the calling service degrades explicitly
   (e.g. expectations engine lowers `estimate_confidence`; price engine sets
   `unresolved`; detection falls back from newswire → SEC + IR).

Extreme-value cross-check: if two price providers disagree by > `price_conflict_pct`
(default 5 points of % move), the reaction is `unresolved` and market-confirmation
scoring is withheld (regression case 5).

## 8. LLM analysis contract

- Model: `claude-opus-5` (config `ANALYSIS_MODEL`), Anthropic Python SDK,
  **structured outputs** via `client.messages.parse(..., output_format=AnalysisOutput)`
  where `AnalysisOutput` is a strict Pydantic schema (spec §LLM output format —
  extended with per-component sub-scores and rationale fields).
- The prompt contains **only deterministic evidence**: extracted financials with
  sources, the consensus band, guidance history, price context, KPI history, and the
  press-release text. System prompt forbids inventing numbers; unknowns must be null.
- Server-side validation: schema-invalid or range-invalid responses are retried
  (max 2), then the pipeline falls back to the deterministic provisional score with
  reduced confidence.
- Anti-hallucination cross-check: numeric fields the LLM echoes (eps_actual etc.) are
  compared against the deterministic extraction; disagreement lowers confidence and is
  audited.

## 9. Scoring algorithm (v1.0, deterministic, `app/services/scoring.py`)

Inputs: LLM sub-scores (quality/guidance/KPI judgment) + deterministic market data.

```
beat_quality        (25%)  surprise vs consensus band, scored against the
                           *least* favourable edge, scaled by estimate dispersion
guidance            (25%)  RAISED/NARROWED/MAINTAINED/LOWERED base points,
                           adjusted for organic vs acquisition/FX (LLM), magnitude
business_kpi        (15%)  LLM KPI/business-quality sub-score, growth direction
true_surprise       (15%)  beat re-based against pre-earnings run (a stock up 15%
                           into the print has a higher true hurdle) + whisper flags
market_confirmation (10%)  reaction vs implied move (when available), hold vs fade
                           pattern, volume; withheld while unresolved
entry               (10%)  magnitude of the move already taken, extension vs
                           pre-earnings run, risk/reward

final = Σ(weight × component)                     → 0.0–10.0
      → veto pass: any major unresolved issue caps final at 8.9
        (guidance cut, KPI deterioration, FCF deterioration, dilution, one-off-
         driven EPS, reversal pattern, unresolved market data, low-confidence
         consensus, extreme extension, market-disagreement SCORE_REVIEW pending)
      → calibration clamp (conservative bands; 10.0 unreachable in practice)
```

`analysis_confidence` (0–100) = weighted product of release-source quality, estimate
confidence, guidance availability, market-data quality, KPI completeness, LLM/
deterministic agreement. Below `min_confidence_for_notification` (default 75) →
`NEEDS_VERIFICATION`, no definitive push.

Every score row stores `scoring_model_version` (= "1.0.0") and the full component
breakdown for future recalibration.

## 10. Notification design

- `NotifierProvider` interface; MVP ships **ntfy** (default — free, install ntfy iOS
  app, subscribe to your private topic) and **Pushover** adapters. Multiple channels
  may be active; each gets the same minimal payload.
- Format: `{emoji} {TICKER} — {score}/10` (emoji: 🔥 ≥9.0, 🟢 8.0–8.9, 🟡 7.0–7.9,
  🔴 <7). Nothing else. Details live in the dashboard.
- `minimum_notification_score` (default 0.0 — you want everything for validation) and
  `high_score_alert` (9.0 → priority/emphasis flag on supported channels).
- Idempotent: unique `dedup_key = canonical_key|model_version` recorded before send.

## 11. Project structure

```
earnings-radar/
├── app/
│   ├── config.py               # pydantic-settings, all env-driven
│   ├── db/                     # engine, session, models
│   ├── domain/                 # enums, state machine, canonical ids, timezones,
│   │   └── schemas.py          # AnalysisOutput etc. (strict Pydantic)
│   ├── providers/
│   │   ├── base.py             # interfaces, FallbackChain, RateLimiter, cache
│   │   ├── sec_edgar.py        # filings + CIK map + fulltext
│   │   ├── finnhub.py fmp.py   # calendar / estimates / quotes
│   │   ├── newswire.py         # RSS adapters
│   │   └── notifiers.py        # ntfy, Pushover
│   ├── services/               # one file per service (§2 diagram)
│   ├── api/                    # FastAPI routers + server-rendered dashboard
│   └── main.py                 # app factory; scheduler lifecycle
├── tests/                      # unit + regression (cases 1–6)
├── Dockerfile  docker-compose.yml
├── pyproject.toml  .env.example
└── README.md  TODO.md  CHANGELOG.md  ARCHITECTURE.md
```

## 12. MVP roadmap (Phase 1 = this repo)

1. ✅ Scaffold + config + DB models + domain core (state machine, tz, canonical ids)
2. ✅ Provider layer: SEC EDGAR, Finnhub, FMP, newswire RSS, ntfy/Pushover
3. ✅ Discovery + reconciliation + adaptive monitoring scheduler
4. ✅ Detection → verification → dedup → extraction pipeline
5. ✅ Expectations + market-data engines (consensus band, spike/fade, cross-check)
6. ✅ LLM analysis (structured outputs) + scoring v1.0 + notifications + audit
7. ✅ Dashboard + API + health
8. ✅ Tests incl. the 6 regression cases
9. Phase 2: options implied move (Polygon), call monitoring, Next.js front-end,
   Celery if multi-node, outcome capture job, backtest runner
10. Phase 3: empirical recalibration, ML weights, brokerage-ready interfaces (no
    auto-trading)
```

---

# Part II — Catalyst Sentinel

> Added as a sibling pipeline under the shared **Sentinel** umbrella.
> Earnings Sentinel keeps scheduled earnings; Catalyst Sentinel handles
> everything else. Scoring methodologies stay separate; infrastructure is shared.

## 13. Why a separate scoring model

Earnings releases are *scheduled*: the market knows they are coming, consensus
exists, and the question is "was it better than expected?". Non-earnings
catalysts are *unscheduled*: there is often no consensus at all, and four
genuinely different questions have to be answered before a number means
anything (spec §2):

| Score | Question |
|---|---|
| **Catalyst Strength** | How important is the news? |
| **Surprise & Novelty** | How genuinely new is it? |
| **Move Amplification** | Can this stock react violently? |
| **Reaction Room** | How much of the move is left? |

Plus **Confidence**, **Execution Quality** and **Negative Offset Severity**,
combining into the **Upside Catalyst Score** (0–10).

Collapsing these prematurely is the central error the design avoids. A
brilliant catalyst on a stock already up 40% has low Reaction Room. A moderate
catalyst on a 15m-share float with 30% short interest has high Amplification.
They must be reported separately or the number lies.

## 14. "Skyrocket" is defined quantitatively

Never raw percentage (§3). Every move is measured as:

```
abnormal_return = stock_return − benchmark_return      (sector preferred over market)
move_multiple   = |abnormal_return| ÷ normal_expected_move
```

where `normal_expected_move` comes from options-implied move → ATR → realised
volatility, in that order, and is **never fabricated** — absent, it is recorded
as absent and confidence falls. +6% in a mega cap is a 5× event; the same +6%
in a volatile microcap is under 1×.

## 15. Pipeline

```
NewsProvider / SEC EDGAR
   ↓ ingest (revisions stored, never overwritten)
   ↓ ENTITY RESOLUTION      confidence-gated; "Apple" ≠ AAPL without evidence
   ↓ DEDUP → EVENT CLUSTER  5 syndicated copies = 1 event, scored once
   ↓ NOVELTY                what is new? what changed? information delta
   ↓ CLASSIFY + SCREEN      cheap kill of routine items BEFORE any LLM call
   ↓ MATERIALITY            ceiling vs guaranteed, scaled to THIS company
   ↓ NEGATIVE OFFSETS       the counterweight, textual + structural + dilution
   ↓ MARKET STRUCTURE       float, short interest (freshness-weighted), RVOL
   ↓ ABNORMAL MOVE + REACTION ROOM
   ↓ CLAUDE ADVERSARIAL     "try to prove this is NOT a major catalyst"
   ↓ SCORE                  7 components, gates, caps, versioned
   ↓ REVALIDATE PRICE
   ↓ ALERT                  only then
```

Every stage writes a `pipeline_traces` row under one correlation id, so any
alert reconstructs end to end with per-stage latency (§94, §112).

## 16. The traps this is built to avoid

| Trap | Defence |
|---|---|
| Yesterday's news rewritten | Novelty engine; restatement → rejected outright |
| "$5bn contract" that is a shared ceiling | Multi-award discount; guaranteed/funded value preferred |
| MOU treated like a signed deal | Certainty ladder caps INTENT/SPECULATIVE at 8.0 |
| FDA *acceptance* read as approval | Distinct event types; acceptance capped at 8.0 |
| Trial "success" that missed its primary endpoint | Offset severity 9.0 → score collapses |
| Buyback authorisation read as execution | Utilisation history + funding capacity discount |
| Catalyst landing before a dilutive raise | Cash-runway and shelf-capacity offsets |
| Chasing a move that already happened | Reaction Room; gate recorded even when the cap doesn't bind |
| Illiquid microcap flattered by big % moves | Amplification and Execution Quality kept separate |
| Stale short interest treated as live | Freshness confidence blends toward neutral |
| Social rumour | Secondary tier can never trigger; capped below 9 |
| Pump-style PR | Promotional markers → rejected |
| Derivative earnings coverage | Routed to Earnings Sentinel and linked, never re-scored |

## 17. Scoring weights (v1.0.0 — provisional)

Final: 35% Catalyst Strength · 20% Surprise & Novelty · 15% Move Amplification
· 15% Reaction Room · 10% Confidence · 5% Execution Quality, then negative-offset
penalty, then gates and caps.

These are the spec's starting heuristic (§72) and are **explicitly provisional**.
`catalyst_scores.model_version` records which model produced every score so
weights can be recalibrated empirically once outcome data exists — at which
point `/api/catalyst/performance` shows whether 9.5s actually outperform 8.5s.

## 18. What is deliberately NOT built yet

- **No automated trading.** No order functions exist (§110).
- **Historical analogue engine** (§40) — schema and interface exist; until real
  events accumulate, `analogue_sample_size` is 0 and confidence is penalised
  accordingly. The fallback expectation is a volatility multiple, clearly
  labelled as such.
- **ML reaction models** (§89-91) — deferred until the event database is
  trustworthy, exactly as the spec instructs.
- **Licensed newswire adapter** — the `NewsProvider` interface and mock are
  complete; a Benzinga adapter drops in without touching the pipeline.
- **Options-implied move** — used when supplied, never fabricated.
