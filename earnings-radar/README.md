# Earnings Radar

Autonomous earnings-release detection, analysis, scoring and push notification.

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
.venv/bin/python -m pytest -q          # 133 tests
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
| `FMP_API_KEY` | Second calendar/consensus/price source — the cross-check that makes the consensus band meaningful. | free tier |
| `ANTHROPIC_API_KEY` | The qualitative analysis layer (`claude-opus-5`). Without it you get provisional deterministic scores only. | ~$0.25–0.40 per report |

Optional: `PUSHOVER_USER_KEY` + `PUSHOVER_APP_TOKEN` for a second push channel.

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
| `/api/audit` | Audit trail — every check, every decision, timestamped |
| `/api/health` | Scheduler, providers, DB, queue, average detection latency |
| `POST /api/discovery/run` | Run discovery now |
| `POST /api/monitor/tick` | Run one monitor sweep now |

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

## Project layout

```
app/
  config.py          settings (env-driven)
  container.py       composition root
  domain/            enums, state machine, timezones, canonical ids, LLM schema
  db/                SQLAlchemy models + session
  providers/         SEC EDGAR, Finnhub, FMP, newswire RSS, ntfy, Pushover
  services/          discovery, scheduler, monitor, verification, extraction,
                     expectations, marketdata, analysis, scoring, notification,
                     pipeline, audit
  api/               JSON API + server-rendered dashboard
tests/               133 tests incl. the 6 spec regression cases
```

See [TODO.md](TODO.md) for what is deferred to Phase 2/3 and
[CHANGELOG.md](CHANGELOG.md) for release history.
