# Sentinel — Earnings Radar

Two autonomous pipelines that watch US equities for tradeable information and
push you a single-line rating.

| Pipeline | Watches | Answers |
|---|---|---|
| **Earnings Sentinel** | Scheduled earnings releases | Was it better than the market had truly priced in? |
| **Catalyst Sentinel** | Everything else — contracts, M&A, FDA, guidance, 13Ds, buybacks | Has genuinely new information just landed that is materially better than expected, and is the move still available? |

> **DISCOVER → MONITOR → DETECT → VERIFY → ANALYSE → SCORE → NOTIFY**

Every morning the system works out which companies report in the next 24 hours,
watches each one around its expected release time, detects the release the
moment it becomes public, verifies it is really this quarter's results,
analyses it, scores it against a conservative earnings-trading model, and pushes
you a one-line rating:

```
🔥 ESTC — 9.2/10
```

The detail lives in the dashboard. The notification stays deliberately minimal.

All times display in **Europe/London** and handle BST/GMT automatically.

**This system never trades. It detects, analyses, scores and notifies — you decide.**

### Catalyst Sentinel in one paragraph

It is *not* a sentiment reader. "Positive-sounding news" scores nothing. Each
event is quantified: is the information genuinely new, or yesterday's story
rewritten? Is the $5bn a guaranteed contract or a ceiling shared with 30
vendors? What is that worth against *this* company's revenue? What is the
offsetting negative — a missed primary endpoint, a concurrent equity offering,
an appeal? Can this stock even move violently (float, short interest, volume)?
And crucially — how much of the move has already happened? Only then does Claude
review it adversarially, explicitly trying to disprove the thesis, before a
deterministic engine produces the score.

```
🚨 CATALYST 9.2 — RKLB
Government Contract
Annualised value = 38% of revenue
Catalyst 9.7 · Surprise 9.3 · Amp 8.8 · Room 9.4
Since disclosure: +2.1%
```

---

## Quick start (5 minutes, no API keys required)

```bash
cd earnings-radar
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env          # then edit — see "Configuration" below
.venv/bin/uvicorn app.main:app --reload
```

Open <http://localhost:8000>. With no keys configured the app runs in a degraded
but honest mode: SEC EDGAR detection and the newswire feeds work, discovery is
empty (no calendar provider), and scoring is deterministic-only. `/api/health`
tells you exactly which providers are live.

Run the tests:

```bash
.venv/bin/python -m pytest -q          # 339 tests
.venv/bin/ruff check app tests
```

### With Docker (Postgres included)

```bash
cp .env.example .env
docker compose up --build
```

---

## Configuration

Everything is environment-driven; see `.env.example` for the full list.
Minimum useful setup:

| Variable | Why | Cost |
|---|---|---|
| `SEC_USER_AGENT` | **Required.** SEC demands a real contact string for automated access. | free |
| `NTFY_TOPIC` | Push to your iPhone. Install the *ntfy* app, subscribe to a long random topic, put the same string here. | free |
| `FINNHUB_API_KEY` | Earnings calendar, consensus, quotes. | free tier |
| `FMP_API_KEY` | Second calendar/consensus/price source — the cross-check that makes the consensus band meaningful. Also the only source of **free float**. | free tier |
| `POLYGON_API_KEY` | Prices, minute bars, reference data, short interest. Move Amplification, Reaction Room and outcome capture all run on this; without it they have no price inputs and cap themselves. | $29/mo (Starter) |
| `ANTHROPIC_API_KEY` | The qualitative analysis layer (`claude-opus-5`). Without it you get provisional deterministic scores only. | ~$0.25–0.40 per report |

Optional: `PUSHOVER_USER_KEY` + `PUSHOVER_APP_TOKEN` for a second push channel.

### Check it works before you need it

```bash
.venv/bin/python -m app.preflight
```

Every provider in this system fails *quietly* by design — a missing entitlement
lowers a score and writes an audit row rather than crashing a release evening.
That is right at 21:05 and useless on setup day, because a wrong key looks
exactly like a quiet market. Preflight makes one real call per capability and
says plainly what worked.

It also measures your **observed** feed delay from a live timestamp and compares
it to `MARKET_DATA_DELAY_SECONDS`. Getting that wrong is silent and serious in
one direction:

```
[ FAIL ] Feed delay
         prices are 15 min old but the system expects 0 min
         → Set MARKET_DATA_DELAY_SECONDS=900 — otherwise a move you cannot
           see yet is scored as no move
```

Also at `GET /api/preflight`. Exit code is 0 when nothing is blocking.

### Running on a delayed price feed

Polygon's **Starter** plan ($29/mo) is 15 minutes behind; **Advanced** ($199/mo)
is real-time. The system is built to run correctly on either, and the whole
difference is one setting:

```bash
MARKET_DATA_DELAY_SECONDS=900   # Starter (default)
MARKET_DATA_DELAY_SECONDS=0     # Advanced — no code changes
```

This is not cosmetic. On a delayed feed a catalyst is detected before its
reaction is visible, and the measured move reads **0%** — which is
indistinguishable from *"the stock hasn't moved"* unless the system knows about
the delay. Scoring that as "untouched, all the room is still there" would
produce a high score on a stock that has already run 60%: the signal inverted
at exactly the moment it matters. So:

- **A not-yet-visible move is never scored as no move.** Reaction Room goes
  unresolved with a stated reason, and the score is capped for it.
- **Every quote is 15 minutes old on Starter**, so staleness is measured as
  silence *beyond* the feed delay — otherwise every stock would be flagged as
  halted.
- **Both pipelines are re-scored when the data arrives**
  (`RESCORE_INTERVAL_SECONDS`). The original analysis is reused and only the
  price half recomputed, so a re-score costs no Claude usage.
- **Earnings depend on this absolutely.** US releases land at 16:05 ET —
  21:05 UK — and the whole reaction happens after hours, invisible on a delayed
  feed at the moment of scoring. The release takes the "unavailable live price
  feeds" veto, which caps it at 8.9. Without the re-score pass that cap is
  permanent and **no report could ever reach 9+**. With it:

  ```
  21:05 UK  scored blind        8.8   veto: unavailable live price feeds
  21:20 UK  re-scored, +9% AH   9.3   no vetoes
  ```

  Re-notification is band-based: crossing into a higher band is a new decision
  and alerts; drifting inside one is silent.

**`/api/catalyst/delay-impact`** answers the upgrade question with your own
data: not "did scores move" but *how often did waiting 15 minutes change what
you would have done*. It is blunt about small samples — with eleven events it
says so.

Scoring/notification behaviour:

```bash
MIN_NOTIFICATION_SCORE=0.0      # 0 = notify me about everything (validation mode)
HIGH_SCORE_ALERT=9.0            # 9+ gets 🔥 and urgent priority
MIN_CONFIDENCE_FOR_NOTIFICATION=75
```

---

## How it works

Full design rationale, provider costs, schema, state machine and scoring maths
are in **[ARCHITECTURE.md](ARCHITECTURE.md)**. The short version:

**Discovery** runs at 05:00 Europe/London plus reconciliation passes at 09:00,
13:00, 18:00 and 20:00. It merges multiple earnings calendars, never trusting
one, and tags each event `HIGH`/`MEDIUM`/`LOW` schedule confidence *with the
reason stored alongside it*.

**Detection** polls small machine-readable indexes — the SEC EDGAR submissions
JSON and newswire RSS feeds — rather than scraping IR pages, because a stale IR
homepage is exactly how a release gets missed. Polling is adaptive: nothing
until T−60, every 5 minutes to T−15, every minute to T−0, then every 20 seconds
through T+30.

**Catalyst detection** runs continuously rather than around known windows,
because catalysts are unscheduled by definition. Every 30 seconds it reads
EDGAR's latest-filings feed — one request that names every filer in the last
few minutes — then pulls item codes and documents only for companies it
watches. Polling the submissions JSON per company would be hundreds of requests
a sweep and would breach SEC's access guidance within seconds.

**Market context** is measured from the disclosure, not from "now" and not from
yesterday's close. Minute bars give the last print *before* the news broke —
the bar the news lands in already contains the reaction, so using it would
erase most of the move — and the same window on a benchmark and sector ETF
strips out what the whole market was doing anyway.

**Verification** is strict. A release counts only when a retrieved document
contains actual current-quarter financial results. Scheduling notices,
conference-call placeholders, analyst previews and previous-quarter reports are
rejected explicitly. One quarter collapses onto one canonical release
(`TICKER|FY|Q`) no matter how many sources carry it.

**Scoring** produces four numbers, all 0.0–10.0:

| Score | Question it answers |
|---|---|
| Earnings quality | How good was the report? |
| Market confirmation | Does the market agree it was a positive surprise? |
| Current entry | Is it still a good place to enter? |
| **Final trade score** | **The number you get pushed** |

Weights: 25% beat quality, 25% guidance, 15% business/KPI, 15% true surprise vs
what the market had *really* priced in, 10% market confirmation, 10% entry.
Then the veto pass caps the final score at 8.9 for any major unresolved issue —
guidance cut, one-off-driven EPS, spike-and-fade rejection, conflicting price
feeds, low-confidence consensus, extreme extension, and others.

A great report with a falling stock triggers `SCORE_REVIEW` and cannot reach 9+
until reviewed. **10.0 is unreachable in practice, and days with zero 9+ scores
are expected.**

The LLM supplies qualitative sub-scores through a strict JSON schema; every
weight, veto and calibration rule is plain deterministic code with unit tests.
Numbers the model echoes back are cross-checked against deterministic
extraction, and a mismatch lowers confidence.

---

## Dashboard & API

| Route | What |
|---|---|
| `/` | Today's watchlist + recent results |
| `/releases/{id}` | Full analysis: scores, vetoes, financials, bull/bear, hidden negatives, sources |
| `/api/today` | Watchlist JSON |
| `/api/results` | Scored releases JSON |
| `/api/releases/{id}` | Full detail JSON |
| `/catalysts` | Live catalysts — score, components, abnormal move |
| `/catalysts/{id}` | Full catalyst detail: what's new, economics, offsets, adversarial review, pipeline timeline |
| `/api/catalyst/live` | Live catalysts JSON |
| `/api/catalyst/events/{id}` | Full catalyst detail JSON |
| `/api/catalyst/performance` | Calibration by event type and score band |
| `/api/catalyst/news` | Raw ingest log, including screened-out items |
| `/api/audit` | Audit trail — every check, every decision, timestamped |
| `/api/health` | Scheduler, providers, DB, queue, average detection latency |
| `POST /api/discovery/run` | Run discovery now |
| `POST /api/monitor/tick` | Run one monitor sweep now |
| `POST /api/catalyst/poll` | Run one catalyst detection sweep now |
| `POST /api/catalyst/outcomes/capture` | Backfill outcomes for recent catalysts now |
| `POST /api/catalyst/rescore` | Re-score catalysts whose delayed data has arrived |
| `/api/catalyst/delay-impact` | Is the delayed feed costing you anything? |
| `/api/preflight` | Does every provider actually work? |

---

## Operational notes

- **Rate limits are respected**: SEC is self-throttled to 4 req/s (well under
  its 10 req/s ceiling) with a declared User-Agent and a cached ticker→CIK map;
  FMP's free tier gets a hard 240-calls/day budget; responses are cached and
  deduplicated.
- **Provider failure is expected**, not exceptional: every call retries with
  jittered backoff, then fails over to the next adapter, then opens a circuit
  breaker. If all sources for a fact fail, the system degrades *explicitly* —
  lower confidence, an audit row, a veto — never a silent guess.
- **Nothing is fabricated.** No options-implied move is invented when there is
  no options feed; unavailable values stay null.
- **Missing releases are never marked "not released"** — they go
  `NOT_YET_VERIFIED`, then `DELAYED_OR_UNVERIFIED` after the grace period.
- **Silence is never mistaken for calm.** If EDGAR's feed returns a full
  response that parses to zero filings, that is treated as a format change and
  raised — an empty list would look exactly like a quiet market.
- **Schema additions are applied automatically.** `create_all` only creates
  missing tables, so a nullable column added to the models is `ALTER TABLE`d
  into an existing database on startup. Anything beyond an additive change is
  refused and logged rather than guessed at.

## Project layout

```
app/
  config.py          settings (env-driven)
  container.py       composition root
  domain/            enums, state machine, timezones, canonical ids, LLM schema
  db/                SQLAlchemy models + session
  providers/         SEC EDGAR, Finnhub, FMP, Polygon, newswire RSS,
                     ntfy, Pushover
  services/          discovery, scheduler, monitor, verification, extraction,
                     expectations, marketdata, analysis, scoring, notification,
                     pipeline, audit, catalyst_market, catalyst_poller,
                     outcomes, rescore, delay_impact
  api/               JSON API + server-rendered dashboard
  catalyst/          Catalyst Sentinel: entities, dedup, novelty, classify,
                     materiality, negatives, amplification, reaction, scoring,
                     investigator, alerts, pipeline, SEC routing
tests/               339 tests incl. earnings regression cases, the catalyst
                     false-positive scenarios, the live market-data wiring and
                     the delayed-feed traps
```

See [TODO.md](TODO.md) for what is deferred to Phase 2/3 and
[CHANGELOG.md](CHANGELOG.md) for release history.
