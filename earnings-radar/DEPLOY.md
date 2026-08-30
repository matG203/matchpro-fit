# Running Earnings Radar on Railway

Right now the system only detects things while your laptop is awake and
`start.bat` is running. Catalysts do not wait for that. This puts the same
system on a server that runs continuously, so you can close the laptop.

Railway is a hosting service: you point it at your GitHub repository, it builds
the app and keeps it running. Cost is usage-based; this app is small and idle
most of the time, so expect roughly **$5/month** on the Hobby plan.

Nothing here changes what the system does. It still **never places a trade** —
it detects, scores and sends you a notification, and you decide.

---

## Before you start

You need three things:

1. A **GitHub account** with this repository pushed to it.
2. Your **API keys**, the same ones in your local `.env` file:
   `ANTHROPIC_API_KEY`, `POLYGON_API_KEY`, `FMP_API_KEY`, `SEC_USER_AGENT`,
   and your `NTFY_TOPIC`.
3. A **card** for Railway's Hobby plan.

> **Your `.env` file never leaves your laptop.** Railway keeps secrets in its
> own settings screen. Do not commit `.env`, and do not paste keys into a
> `railway.json` or a Dockerfile — those are in the repository and anyone who
> can see it can read them.

---

## Step 0 — Get the new code onto your machine

New code lands on the `claude/stock-locator-repo-a7dg0y` branch of the
`matchpro-fit` repository, in an `earnings-radar` subfolder, and is copied
across from there.

> Paths below assume the project lives at `C:\Users\matra\earnings-radar`.
> Run `pwd` in your project folder if you are not sure.

**Back up your `.env` first.** It is not in the repository (that is the point of
it), so a mirroring copy would delete it:

```powershell
copy C:\Users\matra\earnings-radar\.env $env:USERPROFILE\env-backup.txt
dir $env:USERPROFILE\env-backup.txt
```

The second line must list a file before you go any further. Do not use Desktop
for this: OneDrive redirects it on many machines, so `$env:USERPROFILE\Desktop`
often does not exist. Your user folder always does.

Get a fresh copy of the update branch. This clones into a throwaway folder —
it is not your project, and you can delete it afterwards:

```powershell
cd $env:USERPROFILE
if (Test-Path .\radar-update) { Remove-Item .\radar-update -Recurse -Force }
git clone --branch claude/stock-locator-repo-a7dg0y --depth 1 https://github.com/matG203/matchpro-fit.git radar-update
```

Confirm the source really exists before copying anything — the destination is
mirrored, so pointing at a folder that is not there is worth ruling out:

```powershell
dir $env:USERPROFILE\radar-update\earnings-radar\DEPLOY.md
```

Now copy it across:

```powershell
robocopy $env:USERPROFILE\radar-update\earnings-radar C:\Users\matra\earnings-radar /MIR `
  /XD .venv .git __pycache__ .pytest_cache .ruff_cache `
  /XF .env *.db *.log
```

`/MIR` mirrors the folder so files I have deleted go away too. `/XD` keeps your
virtual environment and your local git history; **`/XF .env`** keeps your keys,
and `*.db` keeps your database. Excluded items are left alone entirely, so
mirroring does not remove them.

Check your keys survived and the new code arrived:

```powershell
dir C:\Users\matra\earnings-radar\.env
dir C:\Users\matra\earnings-radar\DEPLOY.md
```

If `.env` is missing for any reason, copy the backup back:

```powershell
copy $env:USERPROFILE\env-backup.txt C:\Users\matra\earnings-radar\.env
```

Then tidy up the throwaway clone:

```powershell
Remove-Item $env:USERPROFILE\radar-update -Recurse -Force
```

---

## Step 1 — Push the code to GitHub

In PowerShell, from your project folder:

```powershell
cd C:\Users\matra\earnings-radar
git add -A
git commit -m "Ready for deployment"
git push
```

If `git push` complains that there is no remote, create an empty **private**
repository on github.com first, then:

```powershell
git remote add origin https://github.com/YOUR-USERNAME/earnings-radar.git
git push -u origin main
```

Make the repository **private**. It contains your trading logic.

> **The Dockerfile must be at the top level of whatever repo you point Railway
> at.** In `C:\Users\matra\earnings-radar` it already is. If you ever point Railway at the
> `matchpro-fit` repo instead, the code sits in a subfolder, and you must set
> **Settings → Root Directory** to `earnings-radar` or the build will find
> nothing to build.

---

## Step 2 — Create the Railway project

1. Go to <https://railway.app> and sign in with GitHub.
2. Click **New Project** → **Deploy from GitHub repo**.
3. Choose `earnings-radar`. Railway will find the `Dockerfile` and start
   building. The first build takes 2-4 minutes.

It will probably show a failed or restarting deployment at this point. That is
expected — there is no database yet.

---

## Step 3 — Add the database

**This step is not optional.** Skipping it is the one mistake that produces a
system which looks like it is working and is not.

Railway wipes the container's disk on every deploy and restart. The database is
where the record of "we already alerted on this" lives. On a wiped database the
poller re-reads the last hour of news on every restart and pushes every one of
those alerts to your phone again.

1. In your project, click **New** → **Database** → **Add PostgreSQL**.
2. That is all. Railway sets `DATABASE_URL` on your app automatically.

Do not type a `DATABASE_URL` yourself. If you already added one, delete it so
Railway's own value is used.

The app checks this at startup. If you get it wrong, the logs open with:

```
EPHEMERAL DATABASE — DATABASE_URL is SQLite, but this looks like a hosted container...
```

---

## Step 4 — Add your keys

Click your app service → **Variables** → **Raw Editor**, and paste this,
filling in your own values:

```
ANTHROPIC_API_KEY=sk-ant-...
POLYGON_API_KEY=...
FMP_API_KEY=...
SEC_USER_AGENT=Earnings Radar (your-email@example.com)
NTFY_TOPIC=your-long-random-topic-name

MARKET_DATA_DELAY_SECONDS=900
WIRE_FEEDS_ENABLED=true
CATALYST_SENTINEL_ENABLED=true
LOCAL_TZ=Europe/London
```

Notes on those:

- **`SEC_USER_AGENT` must contain your real email.** SEC blocks anonymous
  automation, and detection stops dead without it.
- **`MARKET_DATA_DELAY_SECONDS=900`** is your Polygon Starter plan's 15-minute
  delay. If you ever upgrade to Advanced, change this one number to `0` — that
  is the whole upgrade.
- **`NTFY_TOPIC`** is the same topic your phone is subscribed to. Alerts will
  now come from the server instead of your laptop; the phone does not care.
- Everything else has a sensible default. `.env.example` documents all of it.

Railway redeploys automatically when you save.

---

## Step 5 — Check it is actually working

Click **Settings** → **Networking** → **Generate Domain**. You get a URL like
`earnings-radar-production.up.railway.app`.

Open these, in order:

| Open this | What it should say |
|---|---|
| `/api/health` | `"scheduler_running": true`, `"database": "ok"` |
| `/api/preflight` | every line `ok` — this makes one real call per provider |
| `/news` | the wires green, and a count of releases read |
| `/catalysts` | probably empty at first, and that is correct |

**`/api/preflight` is the one that matters.** It fetches a Polygon quote, the
SEC feed and all three newswires for real, and tells you which of them actually
answered. A wrong key looks exactly like a quiet market otherwise.

`/news` is where you watch the system read news. It shows every release that
came in, whether it matched a company, why it was discarded if it was, and for
anything that alerted, how long after the wire published it we sent it.

---

## Step 6 — Turn the laptop off

That is it. `start.bat` is no longer needed. You can keep using it locally for
testing, but do not run both at once against the same ntfy topic or you will
get every alert twice.

---

## Things worth knowing

**Only ever run one copy.** Railway's `numReplicas` is set to 1 in
`railway.json` for this reason: each copy runs its own scheduler, so two copies
means two of every alert. Do not raise it.

**Railway starts with an empty database.** Your laptop's SQLite file does not
come with it, and is not worth migrating: the company list rebuilds itself from
the next few discovery runs (05:00, 09:00, 13:00, 18:00, 20:00 London), and the
catalyst universe grows from there. What you lose is the outcome history behind
`/api/catalyst/performance` — which needs dozens of events before it says
anything anyway, so starting that clock now costs you very little. Keep the
laptop copy if you want it; just do not run both against the same ntfy topic.

**Deploys are safe.** Pushing to GitHub redeploys automatically. The in-memory
"already seen" state resets, so the poller re-reads the last hour — and the
database throws the repeats away. That is why Step 3 is not optional.

**Logs.** Click the deployment → **Logs**. Every sweep that finds something
writes a line. Silence in the logs during market hours, with green wires on
`/news`, means a quiet market. Silence with red wires means a broken feed.

**Cost.** The app is idle between sweeps. Polygon Starter is $29/month and
Anthropic usage depends on how many catalysts clear the screen for deep
analysis — typically a handful a day. Set a spend limit in the Anthropic
console if you want a hard ceiling.

**If a wire feed URL stops working**, `/news` shows it red and `/api/preflight`
names it. The other wires keep working. You can replace it without a code
change by setting `WIRE_FEED_URLS` to the new address.

---

## If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Deploy crashes immediately, logs mention `sqlalchemy.dialects:postgres` | An old-style `postgres://` URL | Already handled in code — make sure you are on the latest commit |
| `EPHEMERAL DATABASE` in the logs | No Postgres attached | Step 3 |
| App builds but the URL never loads | Something is binding a fixed port | Do not override the start command; `app.entrypoint` reads Railway's `$PORT` |
| `/api/preflight` says SEC user agent is a placeholder | `SEC_USER_AGENT` still says `example.com` | Put your real email in it |
| No alerts for days | Usually correct | Check `/news`: if the wires are green and releases are being read, the screen is simply not passing anything. 9+ is designed to be rare |
| Every alert arrives twice | Two copies running | Stop `start.bat`, or check `numReplicas` is 1 |
