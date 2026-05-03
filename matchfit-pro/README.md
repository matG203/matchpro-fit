# MatchFit Pro ⚽⚡

A football fitness gamification app. Track your match readiness, earn XP, upgrade your player card from Bronze to Elite, customise your avatar, and compete with friends on leaderboards.

---

## Features

- **Match Readiness %** — A transparent 0–100 score based on fitness consistency, cardio base, sleep, recovery, and test results
- **Player Card** — Football-style card starting at 45 Overall. Earn XP through workouts to reach Bronze → Silver → Gold → Rare Gold → Elite
- **XP System** — Earn XP from workouts, challenges, health logs, tests, and streaks
- **Avatar Customiser** — Build your footballer with XP-unlockable items (gold boots, chrome kit, elite poses, captain armband and more)
- **Smart Workout Planner** — Sessions generated based on your energy state, equipment, and goal
- **Daily & Weekly Challenges** — Auto-generated challenges with XP rewards
- **Leaderboards** — Friends and global leaderboards for XP, overall rating, steps, workouts
- **Wearables** — Fitbit OAuth, Apple Health ingestion endpoint, Google Health, Garmin structure, manual entry
- **Health Charts** — 30-day charts for steps, sleep, HR, weight, energy, active minutes
- **Daily Routine Checklist** — Customisable with XP reward for completion
- **Fitness Tests** — Log sprint times, push-ups, passing, shooting — tracks personal bests

---

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React + Vite + TypeScript + Tailwind CSS |
| Backend | Node.js + Express + TypeScript |
| Database | PostgreSQL |
| ORM | Prisma |
| Auth | JWT + bcrypt |
| Charts | Recharts |
| State | Zustand |
| Hosting | Railway |

---

## Local Development Setup

### Prerequisites
- Node.js 20+
- PostgreSQL running locally (or use a cloud DB)
- Git

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/matchfit-pro.git
cd matchfit-pro
```

### 2. Set up environment variables

```bash
cp .env.example backend/.env
```

Edit `backend/.env` and set at minimum:
```
DATABASE_URL=postgresql://postgres:password@localhost:5432/matchfitpro
JWT_SECRET=any-long-random-string-here
APP_URL=http://localhost:5173
```

### 3. Install dependencies

```bash
# Install backend deps
cd backend && npm install

# Install frontend deps
cd ../frontend && npm install

# Back to root
cd ..
```

### 4. Set up the database

```bash
cd backend

# Run migrations
npx prisma migrate dev --name init

# Generate Prisma client
npx prisma generate

# Seed with demo data
npx ts-node prisma/seed.ts
```

### 5. Run the app

Open two terminals:

**Terminal 1 — Backend:**
```bash
cd backend
npm run dev
# Runs on http://localhost:3001
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
# Runs on http://localhost:5173
```

Visit `http://localhost:5173`

**Demo login:** `demo@matchfitpro.com` / `matchfit123`

---

## Deploying to Railway

### Step 1: Create a Railway project

1. Go to [railway.app](https://railway.app) and sign in
2. Click **New Project**
3. Select **Deploy from GitHub repo**
4. Connect your GitHub and select this repo

### Step 2: Add PostgreSQL

1. In your Railway project, click **+ New**
2. Select **Database → PostgreSQL**
3. Railway will auto-provision a Postgres instance
4. Click on the Postgres service → **Variables** tab
5. Copy the `DATABASE_URL` value

### Step 3: Set environment variables

In your Railway service (the Node.js app), go to **Variables** and add:

```
DATABASE_URL          = (paste from PostgreSQL service)
JWT_SECRET            = (generate: node -e "console.log(require('crypto').randomBytes(64).toString('hex'))")
NODE_ENV              = production
APP_URL               = https://your-frontend-domain.railway.app
PORT                  = 3001

# Optional - only if using Fitbit OAuth
FITBIT_CLIENT_ID      = 
FITBIT_CLIENT_SECRET  = 
FITBIT_REDIRECT_URI   = https://your-app.railway.app/api/wearables/fitbit/callback
```

### Step 4: Deploy

Railway will auto-deploy on push to your main branch. The `railway.json` config handles:
- Building backend TypeScript
- Running `prisma migrate deploy` on startup
- Starting the Express server

### Step 5: Seed the database (optional)

In Railway's shell tab for your service:
```bash
cd backend && npx ts-node prisma/seed.ts
```

### Step 6: Frontend (static hosting)

The frontend needs to be served separately. Options:

**Option A — Serve from Express (simplest):**
Add this to `backend/src/index.ts` after building the frontend:
```typescript
import path from 'path';
app.use(express.static(path.join(__dirname, '../../frontend/dist')));
app.get('*', (_req, res) => res.sendFile(path.join(__dirname, '../../frontend/dist/index.html')));
```

Build the frontend: `cd frontend && npm run build`

**Option B — Deploy frontend to Railway separately:**
1. Create a second Railway service from the same repo
2. Set build command: `cd frontend && npm install && npm run build`
3. Set start command: `npx serve frontend/dist`
4. Set `VITE_API_URL` env var to your backend Railway URL

**Option C — Vercel (recommended for frontend):**
1. Import repo into Vercel
2. Set root directory to `frontend`
3. Add env var: `VITE_API_URL=https://your-backend.railway.app/api`

---

## Project Structure

```
matchfit-pro/
├── backend/
│   ├── prisma/
│   │   ├── schema.prisma        # All database models
│   │   └── seed.ts              # Demo data seeder
│   ├── src/
│   │   ├── index.ts             # Express server entry
│   │   ├── middleware/
│   │   │   ├── auth.ts          # JWT authentication
│   │   │   └── errorHandler.ts
│   │   ├── routes/              # All API routes
│   │   │   ├── auth.ts
│   │   │   ├── onboarding.ts
│   │   │   ├── dashboard.ts
│   │   │   ├── workout.ts
│   │   │   ├── challenges.ts
│   │   │   ├── avatar.ts        # XP unlock system
│   │   │   ├── playerCard.ts
│   │   │   ├── wearables.ts
│   │   │   └── ...
│   │   ├── services/
│   │   │   ├── xpService.ts     # XP, levelling, card tiers
│   │   │   ├── readinessService.ts
│   │   │   ├── workoutService.ts
│   │   │   └── challengeService.ts
│   │   └── utils/
│   │       └── prisma.ts
│   ├── package.json
│   └── tsconfig.json
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Router
│   │   ├── components/
│   │   │   ├── card/
│   │   │   │   └── PlayerCard.tsx  # Flippable card with tiers + Elite animation
│   │   │   ├── dashboard/
│   │   │   │   ├── ReadinessRing.tsx
│   │   │   │   └── XPBar.tsx
│   │   │   └── layout/
│   │   │       └── Layout.tsx
│   │   ├── pages/               # All 15 pages
│   │   ├── store/
│   │   │   └── authStore.ts     # Zustand auth state
│   │   ├── lib/
│   │   │   └── api.ts           # Axios client
│   │   └── index.css            # Tailwind + custom animations
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── .env.example
├── .gitignore
├── nixpacks.toml               # Railway build config
├── railway.json                # Railway deploy config
└── README.md
```

---

## XP Unlock System

Avatar items are locked behind XP thresholds. Players earn XP through workouts, challenges, and health logging. Items unlock automatically when the threshold is reached:

| Item | XP Required |
|------|------------|
| Headband | 300 XP |
| Wrist Tape | 400 XP |
| Celebration Pose | 600 XP |
| Gold Boots | 750 XP |
| Elite Blue Kit | 800 XP |
| Captain Armband | 1,000 XP |
| Flame Kit Pattern | 1,000 XP |
| Lean Build | 1,000 XP |
| Blackout Kit | 1,200 XP |
| Gold Hair | 500 XP |
| Platinum Hair | 1,500 XP |
| Power Pose | 1,500 XP |
| Camo Kit Pattern | 2,000 XP |
| Platinum Boots | 2,000 XP |
| Muscular Build | 2,000 XP |
| Gold Kit | 2,500 XP |
| Elite Pose | 3,000 XP |
| Lightning Kit | 3,500 XP |
| Chrome Boots | 4,000 XP |
| Chrome Kit | 5,000 XP |

---

## Card Tiers

| Tier | Overall Range | Visual |
|------|--------------|--------|
| Bronze | 45–59 | Bronze gradient |
| Silver | 60–74 | Silver gradient |
| Gold | 75–84 | Gold gradient |
| Rare Gold | 85–89 | Multi-tone gold |
| Elite ⚡ | 90+ | Animated shine + glow + pulse |

---

## API Endpoints

All routes prefixed with `/api/`

| Method | Route | Description |
|--------|-------|-------------|
| POST | /auth/register | Create account |
| POST | /auth/login | Login |
| GET | /auth/me | Get current user |
| DELETE | /auth/account | Delete account |
| POST | /onboarding | Complete onboarding |
| GET | /dashboard | Full dashboard data |
| POST | /workouts/generate | Generate a workout |
| POST | /workouts/complete | Submit workout for XP |
| GET | /challenges/daily | Today's challenges |
| GET | /challenges/weekly | This week's challenges |
| POST | /challenges/:id/complete | Mark challenge done |
| GET | /avatar | Get avatar + XP unlocks |
| PUT | /avatar | Update avatar (validates XP) |
| GET | /player-card | Full card + profile + avatar |
| POST | /player-card/recalculate | Recalculate stats |
| GET | /leaderboards/friends | Friends leaderboard |
| POST | /friends/request | Send friend request |
| GET | /health | Health metrics + summaries |
| POST | /health/log-energy | Log energy + health data |
| GET | /wearables | Connected wearables |
| GET | /wearables/fitbit/connect | Start Fitbit OAuth |
| POST | /wearables/apple-health/ingest | Apple Health companion endpoint |
| POST | /wearables/manual | Manual health data entry |

---

## Wearable Integration Status

| Provider | Status | Notes |
|----------|--------|-------|
| Fitbit | ✅ OAuth ready | Add `FITBIT_CLIENT_ID` and `FITBIT_CLIENT_SECRET` |
| Manual Entry | ✅ Fully working | Always available |
| Apple Health | 🔧 Endpoint ready | Needs native iOS companion app using HealthKit |
| Garmin | 🔧 Structure ready | Requires Garmin partner API approval |
| Google Fit | 🔧 Endpoint ready | OAuth TODO |

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m 'Add feature'`
4. Push: `git push origin feature/my-feature`
5. Open a pull request

---

Built with ⚽ by MatchFit Pro
