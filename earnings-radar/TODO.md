# TODO

## Phase 1 (MVP) — done

- [x] Architecture review, provider/cost analysis, schema, state machine (ARCHITECTURE.md)
- [x] Config, packaging, Docker, Postgres compose
- [x] DB models, state machine, timezone discipline, canonical release IDs
- [x] Provider layer: SEC EDGAR, Finnhub, FMP, newswire RSS, ntfy, Pushover
- [x] Rate limiting, daily quotas, caching, retry/backoff, circuit breaker, fallback chains
- [x] Daily discovery + 4 reconciliation passes, schedule confidence with stored reason
- [x] Adaptive polling with per-event lease (no overlapping checks)
- [x] Multi-source detection; strict verification; deduplication; publication timestamps
- [x] Deterministic financial extraction with source attribution
- [x] Consensus bands + estimate confidence; conservative-edge surprise
- [x] Market context, reaction capture, spike/fade, cross-provider validation
- [x] LLM analysis via strict structured output + anti-hallucination cross-check
- [x] Scoring v1.0: 4 scores, vetoes, SCORE_REVIEW, confidence, model versioning
- [x] Idempotent push notifications
- [x] Dashboard + JSON API + audit log + health
- [x] 133 tests including the 6 spec regression cases

## Phase 1 follow-ups (small, worth doing next)

- [ ] **Learn per-company release times** from historical publication timestamps
      (`estimate_release_window` currently uses session defaults; the DB already
      stores every `published_at_utc` needed to do this).
- [ ] **Reaction timeline job**: capture +1/+3/+5/+10/+15/+30m points after
      scoring so `classify_reaction` sees a full curve rather than one point,
      and update the internal score as it develops.
- [ ] **Guidance extraction**: `classify_guidance()` is implemented and tested
      but not yet wired to an automatic prior-guidance store — guidance status
      currently comes from the LLM. Persist company guidance ranges per quarter
      and feed both into the comparison.
- [ ] **KPI registry**: `kpi_values` table and `Company.kpi_profile` exist; add
      per-industry KPI definitions (SaaS/semis/retail/fintech/banks/miners) and
      sequential Q-2/Q-1/current trend calculation.
- [ ] Per-company IR/newswire feed URLs on the company record.
- [ ] `outcomes` capture job (price at +5m/+30m/next open/close, 1d/5d/30d).

## Catalyst Sentinel — done (v0.2.0)

- [x] Domain models, taxonomy, 15 tables, immutable decision-time snapshots
- [x] SEC filing routing (8-K items + form types), NewsProvider interface + mock
- [x] Entity resolution with confidence gate; dedup into event clusters
- [x] Novelty engine incl. information delta on known topics
- [x] Classification + cheap pre-LLM screen
- [x] Materiality: contracts, buybacks, dividends, M&A, legal
- [x] Negative offsets: textual, structural, dilution/cash runway
- [x] Abnormal move, Reaction Room, Move Amplification, Execution Quality
- [x] Claude two-pass adversarial investigation with anti-invention guardrail
- [x] 7-component scoring with gates and caps; alerts with dedup
- [x] Live catalysts view, detail page, pipeline timeline, calibration endpoint
- [x] 86 tests incl. all spec false-positive scenarios

## Catalyst Sentinel — next

- [ ] **Licensed newswire adapter** (Benzinga or similar). Interface and mock are
      done; this is the single biggest capability gap — without it, detection
      relies on SEC filings alone.
- [ ] **Market-data wiring**: `market_context_fn` is injected but the production
      implementation (pre-event price points, benchmark/sector series, float,
      short interest, halt state, RVOL) still needs real providers. Polygon is
      the obvious candidate for extended-hours prices and float.
- [ ] **Outcome capture job**: `catalyst_outcomes` schema exists; the scheduler
      job to populate +1m/+5m/.../+1d returns does not.
- [ ] **Historical analogue engine**: currently returns a volatility-scaled
      placeholder with sample size 0. Needs real events before it means anything.
- [ ] Specialist providers: ClinicalTrials.gov verification, openFDA, USAspending
      contract verification.
- [ ] Scheduler integration for continuous news polling (the pipeline is ready;
      only the polling loop is missing).
- [ ] Conference-call monitoring and sector read-through (both explicitly V2).

## Phase 2

- [ ] Options-implied move (Polygon or similar) — deliberately absent until
      there is a real feed; never fabricated.
- [ ] Whisper/high-side expectations and analyst revision tracking.
- [ ] Conference-call monitoring for scores ≥ 8.5, with `RBRK UPDATED — 8.1 → 7.6`
      style follow-ups.
- [ ] Backtest runner using `retrieved_at` filters to prevent lookahead bias
      (the data model already supports this).
- [ ] Next.js front-end consuming the existing JSON API.
- [ ] Celery + Redis if the workload outgrows a single node.

## Phase 3

- [ ] Empirical recalibration from `outcomes` (which score bands actually predict returns).
- [ ] ML-optimised scoring weights, versioned alongside `scoring_model_version`.
- [ ] Brokerage integration interfaces — **no automated trading unless explicitly requested.**

## Known limitations (honest list)

- Financial extraction is regex-based and tuned for US press-release phrasing.
  It handles the common shapes well and returns `None` rather than guessing when
  it cannot parse — but XBRL parsing would be more robust for 10-Q data.
- Free-tier consensus data is mediocre; the consensus band and
  `estimate_confidence` make that visible rather than hiding it, but a paid
  estimates feed is the single biggest accuracy upgrade available.
- Non-US companies rely on newswire RSS only (no EDGAR equivalent wired up).
- The dashboard is server-rendered and functional rather than beautiful.
