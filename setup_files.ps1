$base = "$env:USERPROFILE\Documents\matchpro-fit"
function Write-File($path, $content) {
    $full = "$base\$path"
    $dir = Split-Path $full -Parent
    if (!(Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    [System.IO.File]::WriteAllText($full, $content, [System.Text.Encoding]::UTF8)
    Write-Host "Created: $path" -ForegroundColor Green
}

Write-File '.env.example' @'
# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://user:password@localhost:5432/matchfitpro

# ── App ───────────────────────────────────────────────────────────────────────
PORT=3001
NODE_ENV=development
APP_URL=http://localhost:5173
API_URL=http://localhost:3001

# ── Auth ──────────────────────────────────────────────────────────────────────
# Generate with: node -e "console.log(require(''crypto'').randomBytes(64).toString(''hex''))"
JWT_SECRET=your-super-secret-jwt-key-change-this-in-production
ENCRYPTION_KEY=your-32-char-encryption-key-here

# ── Fitbit OAuth ──────────────────────────────────────────────────────────────
# Register at: https://dev.fitbit.com/apps/new
FITBIT_CLIENT_ID=
FITBIT_CLIENT_SECRET=
FITBIT_REDIRECT_URI=http://localhost:3001/api/wearables/fitbit/callback

# ── Garmin (requires partner approval) ───────────────────────────────────────
# Apply at: https://developer.garmin.com/gc-developer-program/overview/
GARMIN_CLIENT_ID=
GARMIN_CLIENT_SECRET=
GARMIN_REDIRECT_URI=http://localhost:3001/api/wearables/garmin/callback

# ── Google Fit / Health Connect ───────────────────────────────────────────────
# Console: https://console.cloud.google.com
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:3001/api/wearables/google-health/callback

# ── Apple Health ──────────────────────────────────────────────────────────────
# Apple Health requires a native iOS app using HealthKit
# This backend exposes endpoints for the companion app to POST to
# No env vars needed for the ingestion endpoint itself

'@

Write-File '.gitignore' @'
node_modules/
dist/
.env
.env.local
*.log
.DS_Store
Thumbs.db
backend/dist/
frontend/dist/

'@

Write-File 'README.md' @'
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
JWT_SECRET            = (generate: node -e "console.log(require(''crypto'').randomBytes(64).toString(''hex''))")
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

In Railway''s shell tab for your service:
```bash
cd backend && npx ts-node prisma/seed.ts
```

### Step 6: Frontend (static hosting)

The frontend needs to be served separately. Options:

**Option A — Serve from Express (simplest):**
Add this to `backend/src/index.ts` after building the frontend:
```typescript
import path from ''path'';
app.use(express.static(path.join(__dirname, ''../../frontend/dist'')));
app.get(''*'', (_req, res) => res.sendFile(path.join(__dirname, ''../../frontend/dist/index.html'')));
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
| GET | /challenges/daily | Today''s challenges |
| GET | /challenges/weekly | This week''s challenges |
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
3. Commit changes: `git commit -m ''Add feature''`
4. Push: `git push origin feature/my-feature`
5. Open a pull request

---

Built with ⚽ by MatchFit Pro

'@

Write-File 'backend\package.json' @'
{
  "name": "matchfit-pro-backend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "ts-node-dev --respawn --transpile-only src/index.ts",
    "build": "tsc",
    "start": "node dist/index.js",
    "db:migrate": "prisma migrate deploy",
    "db:migrate:dev": "prisma migrate dev",
    "db:seed": "ts-node prisma/seed.ts",
    "db:generate": "prisma generate"
  },
  "dependencies": {
    "@prisma/client": "^5.10.0",
    "bcryptjs": "^2.4.3",
    "compression": "^1.7.4",
    "cors": "^2.8.5",
    "date-fns": "^3.3.1",
    "express": "^4.18.2",
    "express-rate-limit": "^7.2.0",
    "helmet": "^7.1.0",
    "jsonwebtoken": "^9.0.2",
    "node-cron": "^3.0.3",
    "uuid": "^9.0.0",
    "zod": "^3.22.4"
  },
  "devDependencies": {
    "@types/bcryptjs": "^2.4.6",
    "@types/compression": "^1.7.5",
    "@types/cors": "^2.8.17",
    "@types/express": "^4.17.21",
    "@types/jsonwebtoken": "^9.0.5",
    "@types/node": "^20.11.5",
    "@types/node-cron": "^3.0.11",
    "@types/uuid": "^9.0.7",
    "prisma": "^5.10.0",
    "ts-node": "^10.9.2",
    "ts-node-dev": "^2.0.0",
    "typescript": "^5.3.3"
  }
}

'@

Write-File 'backend\prisma\schema.prisma' @'
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id           String   @id @default(cuid())
  email        String   @unique
  username     String   @unique
  passwordHash String
  friendCode   String   @unique @default(cuid())
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt

  profile              Profile?
  avatar               Avatar?
  wearableConnections  WearableConnection[]
  healthMetrics        HealthMetric[]
  dailySummaries       DailySummary[]
  workouts             Workout[]
  generatedWorkouts    GeneratedWorkout[]
  userChallenges       UserChallenge[]
  xpEvents             XPEvent[]
  playerCard           PlayerCard?
  playerStatHistory    PlayerStatHistory[]
  readinessScores      ReadinessScore[]
  sentFriendRequests   FriendRequest[]      @relation("SentRequests")
  receivedFriendRequests FriendRequest[]    @relation("ReceivedRequests")
  friendshipsA         Friendship[]         @relation("FriendA")
  friendshipsB         Friendship[]         @relation("FriendB")
  leaderboardSnapshots LeaderboardSnapshot[]
  routineChecklists    RoutineChecklist[]
  routineCompletions   RoutineCompletion[]
  notifications        Notification[]
  manualTestResults    ManualTestResult[]
  supplementReminders  SupplementReminder[]
  userSettings         UserSettings?
  goals                Goal[]
  dietaryPreferences   DietaryPreference[]
  equipment            UserEquipment[]
}

model Profile {
  id               String    @id @default(cuid())
  userId           String    @unique
  displayName      String
  dateOfBirth      DateTime?
  gender           String?
  heightCm         Float?
  weightKg         Float?
  country          String?
  timezone         String    @default("UTC")
  units            String    @default("metric")
  currentLevel     Int       @default(3)
  footballLevel    String    @default("casual")
  position         String    @default("Any")
  fatigueSensitive Boolean   @default(false)
  sleepDifficulty  Boolean   @default(false)
  injuryConcerns   String?
  recoveryPref     String?
  energyBaseline   Int       @default(3)
  stressBaseline   Int       @default(3)
  onboardingDone   Boolean   @default(false)
  createdAt        DateTime  @default(now())
  updatedAt        DateTime  @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model Avatar {
  id             String   @id @default(cuid())
  userId         String   @unique
  skinTone       String   @default("medium")
  hairStyle      String   @default("short")
  hairColour     String   @default("brown")
  facialHair     String   @default("none")
  kitColour      String   @default("red")
  kitPattern     String   @default("plain")
  bootColour     String   @default("black")
  bodyType       String   @default("athletic")
  pose           String   @default("ready")
  headband       Boolean  @default(false)
  wristTape      Boolean  @default(false)
  gloves         Boolean  @default(false)
  captainArmband Boolean  @default(false)
  glasses        Boolean  @default(false)
  unlockedItems  Json     @default("[]")
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model Goal {
  id           String    @id @default(cuid())
  userId       String
  mainGoal     String    @default("get_match_fit")
  targetDate   DateTime?
  matchDate    DateTime?
  fitnessLevel Int       @default(3)
  isActive     Boolean   @default(true)
  createdAt    DateTime  @default(now())
  updatedAt    DateTime  @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model DietaryPreference {
  id         String   @id @default(cuid())
  userId     String
  preference String
  createdAt  DateTime @default(now())

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model UserEquipment {
  id        String   @id @default(cuid())
  userId    String
  equipment String
  createdAt DateTime @default(now())

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model SupplementReminder {
  id        String   @id @default(cuid())
  userId    String
  name      String
  timing    String
  isActive  Boolean  @default(true)
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model UserSettings {
  id                   String   @id @default(cuid())
  userId               String   @unique
  notificationsEnabled Boolean  @default(true)
  emailNotifications   Boolean  @default(false)
  privacyPublic        Boolean  @default(false)
  workStartTime        String?
  workEndTime          String?
  preferredWorkoutDays Json     @default("[]")
  preferredWorkoutTime String?
  maxWorkoutDuration   Int      @default(60)
  minWorkoutDuration   Int      @default(15)
  preferredRestDays    Json     @default("[]")
  napRecoveryBlocks    Boolean  @default(false)
  createdAt            DateTime @default(now())
  updatedAt            DateTime @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model WearableConnection {
  id           String    @id @default(cuid())
  userId       String
  provider     String
  accessToken  String?
  refreshToken String?
  tokenExpiry  DateTime?
  isActive     Boolean   @default(true)
  lastSync     DateTime?
  metadata     Json?
  createdAt    DateTime  @default(now())
  updatedAt    DateTime  @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([userId, provider])
}

model HealthMetric {
  id         String   @id @default(cuid())
  userId     String
  date       DateTime
  metricType String
  value      Float
  unit       String?
  source     String   @default("manual")
  notes      String?
  createdAt  DateTime @default(now())

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId, date])
  @@index([userId, metricType])
}

model DailySummary {
  id             String   @id @default(cuid())
  userId         String
  date           DateTime
  steps          Int?
  sleepHours     Float?
  sleepScore     Int?
  restingHr      Int?
  hrv            Float?
  vo2Max         Float?
  activeMinutes  Int?
  caloriesBurned Int?
  weightKg       Float?
  energyLevel    Int?
  stressLevel    Int?
  fatigueLevel   Int?
  mood           String?
  notes          String?
  isCrashDay     Boolean  @default(false)
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([userId, date])
}

model WorkoutTemplate {
  id              String   @id @default(cuid())
  name            String
  description     String?
  category        String
  difficulty      String
  durationMins    Int
  xpReward        Int
  exercises       Json
  equipmentNeeded Json     @default("[]")
  isActive        Boolean  @default(true)
  createdAt       DateTime @default(now())
}

model GeneratedWorkout {
  id               String    @id @default(cuid())
  userId           String
  title            String
  description      String?
  category         String
  difficulty       String
  durationMins     Int
  energyState      String
  xpReward         Int
  estimatedFatigue Int       @default(3)
  warmup           Json
  mainSection      Json
  cooldown         Json
  statsImproved    Json      @default("[]")
  isCompleted      Boolean   @default(false)
  completedAt      DateTime?
  createdAt        DateTime  @default(now())

  user    User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  workout Workout?
}

model Workout {
  id                String    @id @default(cuid())
  userId            String
  generatedWorkoutId String?  @unique
  title             String
  category          String
  difficulty        String
  durationMins      Int
  rpe               Int?
  notes             String?
  equipmentUsed     Json      @default("[]")
  xpAwarded         Int       @default(0)
  statsImproved     Json      @default("[]")
  completedAt       DateTime  @default(now())
  createdAt         DateTime  @default(now())

  user             User              @relation(fields: [userId], references: [id], onDelete: Cascade)
  generatedWorkout GeneratedWorkout? @relation(fields: [generatedWorkoutId], references: [id])

  @@index([userId, completedAt])
}

model Challenge {
  id          String   @id @default(cuid())
  type        String
  title       String
  description String
  xpReward    Int
  statReward  Json?
  difficulty  String   @default("medium")
  category    String
  target      Float    @default(1)
  unit        String?
  isActive    Boolean  @default(true)
  createdAt   DateTime @default(now())

  userChallenges UserChallenge[]
}

model UserChallenge {
  id          String    @id @default(cuid())
  userId      String
  challengeId String
  progress    Float     @default(0)
  isCompleted Boolean   @default(false)
  completedAt DateTime?
  expiresAt   DateTime
  xpAwarded   Int       @default(0)
  createdAt   DateTime  @default(now())
  updatedAt   DateTime  @updatedAt

  user      User      @relation(fields: [userId], references: [id], onDelete: Cascade)
  challenge Challenge @relation(fields: [challengeId], references: [id])

  @@unique([userId, challengeId, expiresAt])
  @@index([userId, expiresAt])
}

model XPEvent {
  id          String   @id @default(cuid())
  userId      String
  amount      Int
  source      String
  description String?
  metadata    Json?
  createdAt   DateTime @default(now())

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId, createdAt])
}

model PlayerCard {
  id         String   @id @default(cuid())
  userId     String   @unique
  overall    Int      @default(45)
  tier       String   @default("bronze")
  pace       Int      @default(45)
  shooting   Int      @default(45)
  passing    Int      @default(45)
  dribbling  Int      @default(45)
  defending  Int      @default(45)
  physical   Int      @default(45)
  stamina    Int      @default(45)
  recovery   Int      @default(45)
  composure  Int      @default(45)
  totalXp    Int      @default(0)
  xpLevel    Int      @default(1)
  createdAt  DateTime @default(now())
  updatedAt  DateTime @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model PlayerStatHistory {
  id        String   @id @default(cuid())
  userId    String
  stat      String
  oldValue  Int
  newValue  Int
  source    String
  createdAt DateTime @default(now())

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId, createdAt])
}

model ReadinessScore {
  id                    String   @id @default(cuid())
  userId                String
  score                 Float
  fitnessConsistency    Float    @default(0)
  cardiovascularBase    Float    @default(0)
  footballConditioning  Float    @default(0)
  strengthPhysical      Float    @default(0)
  recoverySleep         Float    @default(0)
  bodyWeightTrend       Float    @default(0)
  skillsAgilityTests    Float    @default(0)
  calculatedAt          DateTime @default(now())

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId, calculatedAt])
}

model FriendRequest {
  id         String   @id @default(cuid())
  senderId   String
  receiverId String
  status     String   @default("pending")
  createdAt  DateTime @default(now())
  updatedAt  DateTime @updatedAt

  sender   User @relation("SentRequests", fields: [senderId], references: [id], onDelete: Cascade)
  receiver User @relation("ReceivedRequests", fields: [receiverId], references: [id], onDelete: Cascade)

  @@unique([senderId, receiverId])
}

model Friendship {
  id        String   @id @default(cuid())
  userAId   String
  userBId   String
  createdAt DateTime @default(now())

  userA User @relation("FriendA", fields: [userAId], references: [id], onDelete: Cascade)
  userB User @relation("FriendB", fields: [userBId], references: [id], onDelete: Cascade)

  @@unique([userAId, userBId])
}

model LeaderboardSnapshot {
  id             String   @id @default(cuid())
  userId         String
  weekStart      DateTime
  weeklyXp       Int      @default(0)
  totalXp        Int      @default(0)
  readiness      Float    @default(0)
  overall        Int      @default(45)
  weeklySteps    Int      @default(0)
  weeklyWorkouts Int      @default(0)
  currentStreak  Int      @default(0)
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([userId, weekStart])
}

model RoutineChecklist {
  id        String   @id @default(cuid())
  userId    String
  items     Json
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  user               User               @relation(fields: [userId], references: [id], onDelete: Cascade)
  routineCompletions RoutineCompletion[]

  @@unique([userId])
}

model RoutineCompletion {
  id                 String   @id @default(cuid())
  userId             String
  routineChecklistId String
  date               DateTime
  completedItems     Json     @default("[]")
  xpAwarded          Int      @default(0)
  createdAt          DateTime @default(now())

  user             User             @relation(fields: [userId], references: [id], onDelete: Cascade)
  routineChecklist RoutineChecklist @relation(fields: [routineChecklistId], references: [id])

  @@unique([userId, date])
}

model Notification {
  id        String   @id @default(cuid())
  userId    String
  type      String
  title     String
  body      String
  isRead    Boolean  @default(false)
  metadata  Json?
  createdAt DateTime @default(now())

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId, isRead])
}

model ManualTestResult {
  id        String   @id @default(cuid())
  userId    String
  testType  String
  value     Float
  unit      String?
  notes     String?
  testedAt  DateTime @default(now())
  createdAt DateTime @default(now())

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId, testType])
}

'@

Write-File 'backend\prisma\seed.ts' @'
import { PrismaClient } from ''@prisma/client'';
import bcrypt from ''bcryptjs'';

const prisma = new PrismaClient();

async function main() {
  console.log(''Seeding database...'');

  // Demo user
  const passwordHash = await bcrypt.hash(''matchfit123'', 12);
  const user = await prisma.user.upsert({
    where: { email: ''demo@matchfitpro.com'' },
    update: {},
    create: {
      email: ''demo@matchfitpro.com'',
      username: ''matchfit_demo'',
      passwordHash,
      profile: {
        create: {
          displayName: ''Demo Player'',
          footballLevel: ''5-a-side'',
          position: ''CM'',
          currentLevel: 3,
          energyBaseline: 3,
          stressBaseline: 2,
          onboardingDone: true,
          heightCm: 178,
          weightKg: 75,
          country: ''GB'',
          timezone: ''Europe/London'',
        },
      },
      avatar: { create: { kitColour: ''red'', bootColour: ''black'' } },
      playerCard: {
        create: {
          overall: 52,
          tier: ''bronze'',
          pace: 54,
          shooting: 50,
          passing: 53,
          dribbling: 51,
          defending: 49,
          physical: 52,
          stamina: 53,
          recovery: 50,
          composure: 51,
          totalXp: 350,
          xpLevel: 1,
        },
      },
      userSettings: {
        create: {
          preferredWorkoutDays: [''Monday'', ''Wednesday'', ''Friday'', ''Saturday''],
          maxWorkoutDuration: 60,
          minWorkoutDuration: 20,
        },
      },
    },
  });

  // Default goals
  await prisma.goal.upsert({
    where: { id: ''demo-goal'' },
    update: {},
    create: {
      id: ''demo-goal'',
      userId: user.id,
      mainGoal: ''get_match_fit'',
      fitnessLevel: 3,
      targetDate: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000),
    },
  });

  // Routine checklist
  await prisma.routineChecklist.upsert({
    where: { userId: user.id },
    update: {},
    create: {
      userId: user.id,
      items: [
        { id: ''wake'', label: ''Wake up'', time: ''morning'', enabled: true },
        { id: ''water'', label: ''Drink water'', time: ''morning'', enabled: true },
        { id: ''breakfast'', label: ''Breakfast'', time: ''morning'', enabled: true },
        { id: ''movement'', label: ''Movement'', time: ''afternoon'', enabled: true },
        { id: ''recovery'', label: ''Recovery block'', time: ''evening'', enabled: true },
        { id: ''sleep'', label: ''Sleep'', time: ''night'', enabled: true },
      ],
    },
  });

  // Sample supplement reminders
  await prisma.supplementReminder.createMany({
    data: [
      { userId: user.id, name: ''Vitamin D'', timing: ''morning'' },
      { userId: user.id, name: ''Creatine'', timing: ''morning'' },
      { userId: user.id, name: ''Magnesium Glycinate'', timing: ''bedtime'' },
    ],
    skipDuplicates: true,
  });

  // Sample equipment
  await prisma.userEquipment.createMany({
    data: [
      { userId: user.id, equipment: ''dumbbells'' },
      { userId: user.id, equipment: ''football'' },
      { userId: user.id, equipment: ''resistance_bands'' },
      { userId: user.id, equipment: ''foam_roller'' },
    ],
    skipDuplicates: true,
  });

  console.log(`✅ Seeded demo user: demo@matchfitpro.com / matchfit123`);
  console.log(''✅ Database seeded successfully'');
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());

'@

Write-File 'backend\src\index.ts' @'
import express from ''express'';
import cors from ''cors'';
import helmet from ''helmet'';
import compression from ''compression'';
import rateLimit from ''express-rate-limit'';
import { authRouter } from ''./routes/auth'';
import { profileRouter } from ''./routes/profile'';
import { avatarRouter } from ''./routes/avatar'';
import { onboardingRouter } from ''./routes/onboarding'';
import { dashboardRouter } from ''./routes/dashboard'';
import { workoutRouter } from ''./routes/workout'';
import { challengesRouter } from ''./routes/challenges'';
import { xpRouter } from ''./routes/xp'';
import { leaderboardRouter } from ''./routes/leaderboard'';
import { friendsRouter } from ''./routes/friends'';
import { wearablesRouter } from ''./routes/wearables'';
import { healthRouter } from ''./routes/health'';
import { routineRouter } from ''./routes/routine'';
import { testsRouter } from ''./routes/tests'';
import { notificationsRouter } from ''./routes/notifications'';
import { readinessRouter } from ''./routes/readiness'';
import { playerCardRouter } from ''./routes/playerCard'';
import { settingsRouter } from ''./routes/settings'';
import { errorHandler } from ''./middleware/errorHandler'';

const app = express();
const PORT = process.env.PORT || 3001;

app.use(helmet());
app.use(compression());
app.use(cors({
  origin: process.env.APP_URL || ''http://localhost:5173'',
  credentials: true,
}));
app.use(express.json({ limit: ''10mb'' }));

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 200,
  standardHeaders: true,
  legacyHeaders: false,
});
app.use(''/api'', limiter);

app.get(''/health'', (_req, res) => res.json({ status: ''ok'', app: ''MatchFit Pro'' }));

app.use(''/api/auth'', authRouter);
app.use(''/api/profile'', profileRouter);
app.use(''/api/avatar'', avatarRouter);
app.use(''/api/onboarding'', onboardingRouter);
app.use(''/api/dashboard'', dashboardRouter);
app.use(''/api/workouts'', workoutRouter);
app.use(''/api/challenges'', challengesRouter);
app.use(''/api/xp'', xpRouter);
app.use(''/api/leaderboards'', leaderboardRouter);
app.use(''/api/friends'', friendsRouter);
app.use(''/api/wearables'', wearablesRouter);
app.use(''/api/health'', healthRouter);
app.use(''/api/routine'', routineRouter);
app.use(''/api/tests'', testsRouter);
app.use(''/api/notifications'', notificationsRouter);
app.use(''/api/readiness'', readinessRouter);
app.use(''/api/player-card'', playerCardRouter);
app.use(''/api/settings'', settingsRouter);

app.use(errorHandler);

app.listen(PORT, () => {
  console.log(`MatchFit Pro API running on port ${PORT}`);
});

export default app;

'@

Write-File 'backend\src\middleware\auth.ts' @'
import { Request, Response, NextFunction } from ''express'';
import jwt from ''jsonwebtoken'';

export interface AuthRequest extends Request {
  userId?: string;
}

export const authenticate = (req: AuthRequest, res: Response, next: NextFunction) => {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith(''Bearer '')) {
    return res.status(401).json({ error: ''Unauthorized'' });
  }
  const token = authHeader.slice(7);
  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET || ''dev-secret'') as { userId: string };
    req.userId = payload.userId;
    next();
  } catch {
    return res.status(401).json({ error: ''Invalid token'' });
  }
};

'@

Write-File 'backend\src\middleware\errorHandler.ts' @'
import { Request, Response, NextFunction } from ''express'';

export const errorHandler = (err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error(err.stack);
  res.status(500).json({ error: ''Internal server error'', message: err.message });
};

'@

Write-File 'backend\src\routes\auth.ts' @'
import { Router, Request, Response } from ''express'';
import bcrypt from ''bcryptjs'';
import jwt from ''jsonwebtoken'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';

export const authRouter = Router();

const registerSchema = z.object({
  email: z.string().email(),
  username: z.string().min(3).max(30).regex(/^[a-zA-Z0-9_]+$/),
  password: z.string().min(8),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string(),
});

authRouter.post(''/register'', async (req: Request, res: Response) => {
  try {
    const body = registerSchema.parse(req.body);
    const existing = await prisma.user.findFirst({
      where: { OR: [{ email: body.email }, { username: body.username }] },
    });
    if (existing) {
      return res.status(409).json({ error: ''Email or username already taken'' });
    }
    const passwordHash = await bcrypt.hash(body.password, 12);
    const user = await prisma.user.create({
      data: {
        email: body.email,
        username: body.username,
        passwordHash,
        playerCard: {
          create: {
            overall: 45,
            tier: ''bronze'',
            pace: Math.floor(Math.random() * 5) + 43,
            shooting: Math.floor(Math.random() * 5) + 43,
            passing: Math.floor(Math.random() * 5) + 43,
            dribbling: Math.floor(Math.random() * 5) + 43,
            defending: Math.floor(Math.random() * 5) + 43,
            physical: Math.floor(Math.random() * 5) + 43,
            stamina: Math.floor(Math.random() * 5) + 43,
            recovery: Math.floor(Math.random() * 5) + 43,
            composure: Math.floor(Math.random() * 5) + 43,
          },
        },
        avatar: { create: {} },
      },
    });
    const token = jwt.sign({ userId: user.id }, process.env.JWT_SECRET || ''dev-secret'', { expiresIn: ''30d'' });
    return res.status(201).json({ token, userId: user.id, username: user.username });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

authRouter.post(''/login'', async (req: Request, res: Response) => {
  try {
    const body = loginSchema.parse(req.body);
    const user = await prisma.user.findUnique({ where: { email: body.email } });
    if (!user) return res.status(401).json({ error: ''Invalid credentials'' });
    const valid = await bcrypt.compare(body.password, user.passwordHash);
    if (!valid) return res.status(401).json({ error: ''Invalid credentials'' });
    const token = jwt.sign({ userId: user.id }, process.env.JWT_SECRET || ''dev-secret'', { expiresIn: ''30d'' });
    return res.json({ token, userId: user.id, username: user.username });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

authRouter.get(''/me'', authenticate, async (req: AuthRequest, res: Response) => {
  const user = await prisma.user.findUnique({
    where: { id: req.userId },
    include: { profile: true, playerCard: true },
  });
  if (!user) return res.status(404).json({ error: ''User not found'' });
  const { passwordHash: _pw, ...safeUser } = user;
  return res.json(safeUser);
});

authRouter.delete(''/account'', authenticate, async (req: AuthRequest, res: Response) => {
  await prisma.user.delete({ where: { id: req.userId } });
  return res.json({ message: ''Account deleted'' });
});

'@

Write-File 'backend\src\routes\avatar.ts' @'
import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';

export const avatarRouter = Router();

// XP unlock thresholds for avatar items
export const AVATAR_UNLOCKS = [
  { key: ''hair_gold'', label: ''Gold Hair'', type: ''hairColour'', value: ''gold'', xpRequired: 500 },
  { key: ''hair_platinum'', label: ''Platinum Hair'', type: ''hairColour'', value: ''platinum'', xpRequired: 1500 },
  { key: ''kit_elite_blue'', label: ''Elite Blue Kit'', type: ''kitColour'', value: ''elite_blue'', xpRequired: 800 },
  { key: ''kit_elite_black'', label: ''Blackout Kit'', type: ''kitColour'', value: ''elite_black'', xpRequired: 1200 },
  { key: ''kit_gold'', label: ''Gold Kit'', type: ''kitColour'', value: ''gold'', xpRequired: 2500 },
  { key: ''kit_chrome'', label: ''Chrome Kit'', type: ''kitColour'', value: ''chrome'', xpRequired: 5000 },
  { key: ''kit_flame'', label: ''Flame Kit'', type: ''kitPattern'', value: ''flame'', xpRequired: 1000 },
  { key: ''kit_camo'', label: ''Camo Kit'', type: ''kitPattern'', value: ''camo'', xpRequired: 2000 },
  { key: ''kit_lightning'', label: ''Lightning Kit'', type: ''kitPattern'', value: ''lightning'', xpRequired: 3500 },
  { key: ''boots_gold'', label: ''Gold Boots'', type: ''bootColour'', value: ''gold'', xpRequired: 750 },
  { key: ''boots_platinum'', label: ''Platinum Boots'', type: ''bootColour'', value: ''platinum'', xpRequired: 2000 },
  { key: ''boots_chrome'', label: ''Chrome Boots'', type: ''bootColour'', value: ''chrome'', xpRequired: 4000 },
  { key: ''pose_celebration'', label: ''Celebration Pose'', type: ''pose'', value: ''celebration'', xpRequired: 600 },
  { key: ''pose_power'', label: ''Power Pose'', type: ''pose'', value: ''power'', xpRequired: 1500 },
  { key: ''pose_elite'', label: ''Elite Pose'', type: ''pose'', value: ''elite'', xpRequired: 3000 },
  { key: ''accessory_headband'', label: ''Headband'', type: ''headband'', value: true, xpRequired: 300 },
  { key: ''accessory_wrist_tape'', label: ''Wrist Tape'', type: ''wristTape'', value: true, xpRequired: 400 },
  { key: ''accessory_gloves'', label: ''GK Gloves'', type: ''gloves'', value: true, xpRequired: 700 },
  { key: ''accessory_captain'', label: ''Captain Armband'', type: ''captainArmband'', value: true, xpRequired: 1000 },
  { key: ''accessory_glasses'', label: ''Shades'', type: ''glasses'', value: true, xpRequired: 500 },
  { key: ''body_muscular'', label: ''Muscular Build'', type: ''bodyType'', value: ''muscular'', xpRequired: 2000 },
  { key: ''body_lean'', label: ''Lean Build'', type: ''bodyType'', value: ''lean'', xpRequired: 1000 },
];

avatarRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const avatar = await prisma.avatar.findUnique({ where: { userId: req.userId } });
  const card = await prisma.playerCard.findUnique({ where: { userId: req.userId } });
  const totalXp = card?.totalXp || 0;
  const unlocked = AVATAR_UNLOCKS.filter((u) => totalXp >= u.xpRequired);
  return res.json({ avatar, unlocks: AVATAR_UNLOCKS, unlockedKeys: unlocked.map((u) => u.key), totalXp });
});

const avatarUpdateSchema = z.object({
  skinTone: z.string().optional(),
  hairStyle: z.string().optional(),
  hairColour: z.string().optional(),
  facialHair: z.string().optional(),
  kitColour: z.string().optional(),
  kitPattern: z.string().optional(),
  bootColour: z.string().optional(),
  bodyType: z.string().optional(),
  pose: z.string().optional(),
  headband: z.boolean().optional(),
  wristTape: z.boolean().optional(),
  gloves: z.boolean().optional(),
  captainArmband: z.boolean().optional(),
  glasses: z.boolean().optional(),
});

avatarRouter.put(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const data = avatarUpdateSchema.parse(req.body);
    const card = await prisma.playerCard.findUnique({ where: { userId: req.userId } });
    const totalXp = card?.totalXp || 0;

    // Validate XP-locked items
    for (const unlock of AVATAR_UNLOCKS) {
      const fieldVal = data[unlock.type as keyof typeof data];
      if (fieldVal === unlock.value && totalXp < unlock.xpRequired) {
        return res.status(403).json({ error: `${unlock.label} requires ${unlock.xpRequired} XP to unlock` });
      }
    }

    const avatar = await prisma.avatar.update({ where: { userId: req.userId }, data });
    return res.json(avatar);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

'@

Write-File 'backend\src\routes\challenges.ts' @'
import { Router, Response } from ''express'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { ensureDailyChallenges, ensureWeeklyChallenges, completeChallenge } from ''../services/challengeService'';

export const challengesRouter = Router();

challengesRouter.get(''/daily'', authenticate, async (req: AuthRequest, res: Response) => {
  const challenges = await ensureDailyChallenges(req.userId!);
  return res.json(challenges);
});

challengesRouter.get(''/weekly'', authenticate, async (req: AuthRequest, res: Response) => {
  const challenges = await ensureWeeklyChallenges(req.userId!);
  return res.json(challenges);
});

challengesRouter.post(''/:id/complete'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const result = await completeChallenge(req.userId!, req.params.id);
    return res.json(result);
  } catch (err) {
    return res.status(400).json({ error: (err as Error).message });
  }
});

'@

Write-File 'backend\src\routes\dashboard.ts' @'
import { Router, Response } from ''express'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { xpToLevel, xpProgressInLevel } from ''../services/xpService'';
import { calculateReadiness } from ''../services/readinessService'';
import { ensureDailyChallenges } from ''../services/challengeService'';
import { startOfDay } from ''date-fns'';

export const dashboardRouter = Router();

dashboardRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const userId = req.userId!;
  const today = startOfDay(new Date());

  const [profile, card, todaySummary, wearables, notifications, dailyChallenges] = await Promise.all([
    prisma.profile.findUnique({ where: { userId } }),
    prisma.playerCard.findUnique({ where: { userId } }),
    prisma.dailySummary.findFirst({ where: { userId, date: { gte: today } } }),
    prisma.wearableConnection.findMany({ where: { userId, isActive: true } }),
    prisma.notification.findMany({ where: { userId, isRead: false }, orderBy: { createdAt: ''desc'' }, take: 5 }),
    ensureDailyChallenges(userId),
  ]);

  const latestReadiness = await prisma.readinessScore.findFirst({
    where: { userId },
    orderBy: { calculatedAt: ''desc'' },
  });

  const totalXp = card?.totalXp || 0;
  const level = xpToLevel(totalXp);
  const xpProgress = xpProgressInLevel(totalXp);

  const energyLevel = todaySummary?.energyLevel || null;
  const energyState = energyLevel ? (energyLevel >= 4 ? ''green'' : energyLevel >= 2 ? ''yellow'' : ''red'') : null;

  return res.json({
    profile,
    playerCard: card,
    readiness: latestReadiness?.score || 0,
    level,
    xpProgress,
    totalXp,
    todaySummary,
    energyState,
    wearables: wearables.map((w) => ({ provider: w.provider, lastSync: w.lastSync })),
    notifications,
    dailyChallenges,
  });
});

'@

Write-File 'backend\src\routes\friends.ts' @'
import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';

export const friendsRouter = Router();

friendsRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const userId = req.userId!;
  const friendships = await prisma.friendship.findMany({
    where: { OR: [{ userAId: userId }, { userBId: userId }] },
    include: {
      userA: { include: { profile: true, playerCard: true, avatar: true } },
      userB: { include: { profile: true, playerCard: true, avatar: true } },
    },
  });
  const friends = friendships.map((f) => {
    const friend = f.userAId === userId ? f.userB : f.userA;
    return {
      id: f.id,
      userId: friend.id,
      username: friend.username,
      friendCode: friend.friendCode,
      displayName: friend.profile?.displayName || friend.username,
      overall: friend.playerCard?.overall || 45,
      tier: friend.playerCard?.tier || ''bronze'',
      avatar: friend.avatar,
    };
  });
  return res.json(friends);
});

friendsRouter.get(''/requests'', authenticate, async (req: AuthRequest, res: Response) => {
  const requests = await prisma.friendRequest.findMany({
    where: { receiverId: req.userId, status: ''pending'' },
    include: { sender: { include: { profile: true } } },
  });
  return res.json(requests);
});

friendsRouter.post(''/request'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({ usernameOrCode: z.string() });
    const { usernameOrCode } = schema.parse(req.body);
    const target = await prisma.user.findFirst({
      where: { OR: [{ username: usernameOrCode }, { friendCode: usernameOrCode }] },
    });
    if (!target) return res.status(404).json({ error: ''User not found'' });
    if (target.id === req.userId) return res.status(400).json({ error: ''Cannot add yourself'' });

    const existing = await prisma.friendship.findFirst({
      where: { OR: [{ userAId: req.userId, userBId: target.id }, { userAId: target.id, userBId: req.userId }] },
    });
    if (existing) return res.status(400).json({ error: ''Already friends'' });

    const request = await prisma.friendRequest.upsert({
      where: { senderId_receiverId: { senderId: req.userId!, receiverId: target.id } },
      update: { status: ''pending'' },
      create: { senderId: req.userId!, receiverId: target.id },
    });
    return res.status(201).json(request);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

friendsRouter.post(''/accept'', authenticate, async (req: AuthRequest, res: Response) => {
  const schema = z.object({ requestId: z.string() });
  const { requestId } = schema.parse(req.body);
  const request = await prisma.friendRequest.findUnique({ where: { id: requestId } });
  if (!request || request.receiverId !== req.userId) return res.status(404).json({ error: ''Request not found'' });

  await prisma.$transaction([
    prisma.friendRequest.update({ where: { id: requestId }, data: { status: ''accepted'' } }),
    prisma.friendship.create({ data: { userAId: request.senderId, userBId: request.receiverId } }),
  ]);
  return res.json({ success: true });
});

friendsRouter.post(''/decline'', authenticate, async (req: AuthRequest, res: Response) => {
  const schema = z.object({ requestId: z.string() });
  const { requestId } = schema.parse(req.body);
  await prisma.friendRequest.update({ where: { id: requestId }, data: { status: ''declined'' } });
  return res.json({ success: true });
});

friendsRouter.delete(''/:id'', authenticate, async (req: AuthRequest, res: Response) => {
  await prisma.friendship.deleteMany({
    where: {
      OR: [
        { userAId: req.userId, userBId: req.params.id },
        { userAId: req.params.id, userBId: req.userId },
      ],
    },
  });
  return res.json({ success: true });
});

'@

Write-File 'backend\src\routes\health.ts' @'
import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { awardXp, XP_REWARDS } from ''../services/xpService'';
import { startOfDay } from ''date-fns'';

export const healthRouter = Router();

healthRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const { days = ''30'', type } = req.query;
  const since = new Date(Date.now() - Number(days) * 24 * 60 * 60 * 1000);
  const where: Record<string, unknown> = { userId: req.userId, date: { gte: since } };
  if (type) where.metricType = type as string;
  const metrics = await prisma.healthMetric.findMany({ where, orderBy: { date: ''asc'' } });
  const summaries = await prisma.dailySummary.findMany({
    where: { userId: req.userId, date: { gte: since } },
    orderBy: { date: ''asc'' },
  });
  return res.json({ metrics, summaries });
});

healthRouter.post(''/log-energy'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({
      energyLevel: z.number().min(1).max(5),
      stressLevel: z.number().min(1).max(5).optional(),
      fatigueLevel: z.number().min(1).max(5).optional(),
      mood: z.string().optional(),
      notes: z.string().optional(),
      sleepHours: z.number().optional(),
      steps: z.number().optional(),
    });
    const data = schema.parse(req.body);
    const today = startOfDay(new Date());

    const summary = await prisma.dailySummary.upsert({
      where: { userId_date: { userId: req.userId!, date: today } },
      update: data,
      create: { userId: req.userId!, date: today, ...data },
    });

    await awardXp(req.userId!, XP_REWARDS.energy_log, ''energy_log'', ''Logged energy'');
    return res.json(summary);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

healthRouter.post(''/metric'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({
      date: z.string(),
      metricType: z.string(),
      value: z.number(),
      unit: z.string().optional(),
      source: z.string().default(''manual''),
      notes: z.string().optional(),
    });
    const data = schema.parse(req.body);
    const metric = await prisma.healthMetric.create({
      data: { userId: req.userId!, ...data, date: new Date(data.date) },
    });
    await awardXp(req.userId!, XP_REWARDS.manual_health_log, ''health_log'', `Logged ${data.metricType}`);
    return res.status(201).json(metric);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

'@

Write-File 'backend\src\routes\leaderboard.ts' @'
import { Router, Response } from ''express'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { startOfWeek } from ''date-fns'';

export const leaderboardRouter = Router();

leaderboardRouter.get(''/friends'', authenticate, async (req: AuthRequest, res: Response) => {
  const userId = req.userId!;
  const weekStart = startOfWeek(new Date(), { weekStartsOn: 1 });

  // Get all friend IDs
  const friendships = await prisma.friendship.findMany({
    where: { OR: [{ userAId: userId }, { userBId: userId }] },
  });
  const friendIds = friendships.map((f) => (f.userAId === userId ? f.userBId : f.userAId));
  const allIds = [userId, ...friendIds];

  const snapshots = await prisma.leaderboardSnapshot.findMany({
    where: { userId: { in: allIds }, weekStart: { gte: weekStart } },
    include: { user: { include: { profile: true, playerCard: true } } },
    orderBy: { weeklyXp: ''desc'' },
  });

  // Users without snapshots yet - create placeholder data
  const snapshotUserIds = snapshots.map((s) => s.userId);
  const missing = allIds.filter((id) => !snapshotUserIds.includes(id));
  const missingUsers = await prisma.user.findMany({
    where: { id: { in: missing } },
    include: { profile: true, playerCard: true },
  });

  const combined = [
    ...snapshots.map((s) => ({
      userId: s.userId,
      displayName: s.user.profile?.displayName || s.user.username,
      username: s.user.username,
      weeklyXp: s.weeklyXp,
      totalXp: s.totalXp,
      overall: s.overall,
      readiness: s.readiness,
      weeklySteps: s.weeklySteps,
      weeklyWorkouts: s.weeklyWorkouts,
      currentStreak: s.currentStreak,
      isCurrentUser: s.userId === userId,
    })),
    ...missingUsers.map((u) => ({
      userId: u.id,
      displayName: u.profile?.displayName || u.username,
      username: u.username,
      weeklyXp: 0,
      totalXp: u.playerCard?.totalXp || 0,
      overall: u.playerCard?.overall || 45,
      readiness: 0,
      weeklySteps: 0,
      weeklyWorkouts: 0,
      currentStreak: 0,
      isCurrentUser: u.id === userId,
    })),
  ].sort((a, b) => b.weeklyXp - a.weeklyXp);

  return res.json(combined);
});

leaderboardRouter.get(''/global'', authenticate, async (_req: AuthRequest, res: Response) => {
  const weekStart = startOfWeek(new Date(), { weekStartsOn: 1 });
  const snapshots = await prisma.leaderboardSnapshot.findMany({
    where: { weekStart: { gte: weekStart } },
    include: { user: { include: { profile: true, playerCard: true } } },
    orderBy: { weeklyXp: ''desc'' },
    take: 100,
  });
  return res.json(snapshots.map((s) => ({
    userId: s.userId,
    displayName: s.user.profile?.displayName || s.user.username,
    username: s.user.username,
    weeklyXp: s.weeklyXp,
    totalXp: s.totalXp,
    overall: s.overall,
    weeklyWorkouts: s.weeklyWorkouts,
  })));
});

'@

Write-File 'backend\src\routes\notifications.ts' @'
import { Router, Response } from ''express'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';

export const notificationsRouter = Router();

notificationsRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const notifications = await prisma.notification.findMany({
    where: { userId: req.userId },
    orderBy: { createdAt: ''desc'' },
    take: 50,
  });
  return res.json(notifications);
});

notificationsRouter.post(''/read'', authenticate, async (req: AuthRequest, res: Response) => {
  const { ids } = req.body as { ids?: string[] };
  if (ids?.length) {
    await prisma.notification.updateMany({ where: { id: { in: ids }, userId: req.userId }, data: { isRead: true } });
  } else {
    await prisma.notification.updateMany({ where: { userId: req.userId }, data: { isRead: true } });
  }
  return res.json({ success: true });
});

'@

Write-File 'backend\src\routes\onboarding.ts' @'
import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';

export const onboardingRouter = Router();

const onboardingSchema = z.object({
  displayName: z.string().min(1).max(50),
  dateOfBirth: z.string().optional(),
  gender: z.string().optional(),
  heightCm: z.number().optional(),
  weightKg: z.number().optional(),
  country: z.string().optional(),
  timezone: z.string().optional(),
  units: z.enum([''metric'', ''imperial'']).default(''metric''),
  mainGoal: z.string(),
  targetDate: z.string().optional(),
  matchDate: z.string().optional(),
  fitnessLevel: z.number().min(1).max(5),
  footballLevel: z.string(),
  position: z.string(),
  fatigueSensitive: z.boolean().default(false),
  sleepDifficulty: z.boolean().default(false),
  injuryConcerns: z.string().optional(),
  recoveryPref: z.string().optional(),
  energyBaseline: z.number().min(1).max(5),
  stressBaseline: z.number().min(1).max(5),
  workStartTime: z.string().optional(),
  workEndTime: z.string().optional(),
  preferredWorkoutDays: z.array(z.string()).default([]),
  preferredWorkoutTime: z.string().optional(),
  maxWorkoutDuration: z.number().default(60),
  minWorkoutDuration: z.number().default(15),
  preferredRestDays: z.array(z.string()).default([]),
  napRecoveryBlocks: z.boolean().default(false),
  equipment: z.array(z.string()).default([]),
  dietaryPreferences: z.array(z.string()).default([]),
  supplements: z.array(z.object({ name: z.string(), timing: z.string() })).default([]),
});

onboardingRouter.post(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const data = onboardingSchema.parse(req.body);
    const userId = req.userId!;

    await prisma.$transaction(async (tx) => {
      await tx.profile.upsert({
        where: { userId },
        update: {
          displayName: data.displayName,
          dateOfBirth: data.dateOfBirth ? new Date(data.dateOfBirth) : null,
          gender: data.gender,
          heightCm: data.heightCm,
          weightKg: data.weightKg,
          country: data.country,
          timezone: data.timezone || ''UTC'',
          units: data.units,
          currentLevel: data.fitnessLevel,
          footballLevel: data.footballLevel,
          position: data.position,
          fatigueSensitive: data.fatigueSensitive,
          sleepDifficulty: data.sleepDifficulty,
          injuryConcerns: data.injuryConcerns,
          recoveryPref: data.recoveryPref,
          energyBaseline: data.energyBaseline,
          stressBaseline: data.stressBaseline,
          onboardingDone: true,
        },
        create: {
          userId,
          displayName: data.displayName,
          dateOfBirth: data.dateOfBirth ? new Date(data.dateOfBirth) : null,
          gender: data.gender,
          heightCm: data.heightCm,
          weightKg: data.weightKg,
          country: data.country,
          timezone: data.timezone || ''UTC'',
          units: data.units,
          currentLevel: data.fitnessLevel,
          footballLevel: data.footballLevel,
          position: data.position,
          fatigueSensitive: data.fatigueSensitive,
          sleepDifficulty: data.sleepDifficulty,
          injuryConcerns: data.injuryConcerns,
          recoveryPref: data.recoveryPref,
          energyBaseline: data.energyBaseline,
          stressBaseline: data.stressBaseline,
          onboardingDone: true,
        },
      });

      await tx.goal.create({
        data: {
          userId,
          mainGoal: data.mainGoal,
          targetDate: data.targetDate ? new Date(data.targetDate) : null,
          matchDate: data.matchDate ? new Date(data.matchDate) : null,
          fitnessLevel: data.fitnessLevel,
        },
      });

      await tx.userSettings.upsert({
        where: { userId },
        update: {
          workStartTime: data.workStartTime,
          workEndTime: data.workEndTime,
          preferredWorkoutDays: data.preferredWorkoutDays,
          preferredWorkoutTime: data.preferredWorkoutTime,
          maxWorkoutDuration: data.maxWorkoutDuration,
          minWorkoutDuration: data.minWorkoutDuration,
          preferredRestDays: data.preferredRestDays,
          napRecoveryBlocks: data.napRecoveryBlocks,
        },
        create: {
          userId,
          workStartTime: data.workStartTime,
          workEndTime: data.workEndTime,
          preferredWorkoutDays: data.preferredWorkoutDays,
          preferredWorkoutTime: data.preferredWorkoutTime,
          maxWorkoutDuration: data.maxWorkoutDuration,
          minWorkoutDuration: data.minWorkoutDuration,
          preferredRestDays: data.preferredRestDays,
          napRecoveryBlocks: data.napRecoveryBlocks,
        },
      });

      await tx.userEquipment.deleteMany({ where: { userId } });
      if (data.equipment.length > 0) {
        await tx.userEquipment.createMany({
          data: data.equipment.map((e) => ({ userId, equipment: e })),
        });
      }

      await tx.dietaryPreference.deleteMany({ where: { userId } });
      if (data.dietaryPreferences.length > 0) {
        await tx.dietaryPreference.createMany({
          data: data.dietaryPreferences.map((p) => ({ userId, preference: p })),
        });
      }

      await tx.supplementReminder.deleteMany({ where: { userId } });
      if (data.supplements.length > 0) {
        await tx.supplementReminder.createMany({
          data: data.supplements.map((s) => ({ userId, name: s.name, timing: s.timing })),
        });
      }

      // Award onboarding XP
      await tx.xPEvent.create({
        data: { userId, amount: 100, source: ''onboarding'', description: ''Completed onboarding'' },
      });
      await tx.playerCard.update({
        where: { userId },
        data: { totalXp: { increment: 100 } },
      });

      // Create default routine checklist
      await tx.routineChecklist.upsert({
        where: { userId },
        update: {},
        create: {
          userId,
          items: [
            { id: ''wake'', label: ''Wake up'', time: ''morning'', enabled: true },
            { id: ''water'', label: ''Drink water'', time: ''morning'', enabled: true },
            { id: ''hygiene'', label: ''Hygiene'', time: ''morning'', enabled: true },
            { id: ''breakfast'', label: ''Breakfast'', time: ''morning'', enabled: true },
            { id: ''supplements_am'', label: ''Morning supplements'', time: ''morning'', enabled: true },
            { id: ''movement'', label: ''Movement / workout'', time: ''afternoon'', enabled: true },
            { id: ''lunch'', label: ''Lunch'', time: ''afternoon'', enabled: true },
            { id: ''snack'', label: ''Snack'', time: ''afternoon'', enabled: true },
            { id: ''training'', label: ''Training session'', time: ''afternoon'', enabled: false },
            { id: ''recovery'', label: ''Recovery block'', time: ''evening'', enabled: true },
            { id: ''dinner'', label: ''Dinner'', time: ''evening'', enabled: true },
            { id: ''wind_down'', label: ''Wind down'', time: ''evening'', enabled: true },
            { id: ''bedtime_routine'', label: ''Bedtime routine'', time: ''night'', enabled: true },
            { id: ''supplements_pm'', label: ''Bedtime supplements'', time: ''night'', enabled: true },
            { id: ''sleep'', label: ''Sleep'', time: ''night'', enabled: true },
          ],
        },
      });
    });

    return res.json({ success: true, message: ''Onboarding complete'' });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

'@

Write-File 'backend\src\routes\playerCard.ts' @'
import { Router, Response } from ''express'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { recalculatePlayerCard } from ''../services/xpService'';

export const playerCardRouter = Router();

playerCardRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const card = await prisma.playerCard.findUnique({ where: { userId: req.userId } });
  const profile = await prisma.profile.findUnique({ where: { userId: req.userId } });
  const avatar = await prisma.avatar.findUnique({ where: { userId: req.userId } });
  return res.json({ card, profile, avatar });
});

playerCardRouter.post(''/recalculate'', authenticate, async (req: AuthRequest, res: Response) => {
  const result = await recalculatePlayerCard(req.userId!);
  return res.json(result);
});

playerCardRouter.get(''/history'', authenticate, async (req: AuthRequest, res: Response) => {
  const history = await prisma.playerStatHistory.findMany({
    where: { userId: req.userId },
    orderBy: { createdAt: ''desc'' },
    take: 50,
  });
  return res.json(history);
});

'@

Write-File 'backend\src\routes\profile.ts' @'
import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';

export const profileRouter = Router();

profileRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const profile = await prisma.profile.findUnique({ where: { userId: req.userId } });
  return res.json(profile);
});

profileRouter.put(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const schema = z.object({
    displayName: z.string().min(1).max(50).optional(),
    heightCm: z.number().optional(),
    weightKg: z.number().optional(),
    country: z.string().optional(),
    timezone: z.string().optional(),
    units: z.enum([''metric'', ''imperial'']).optional(),
    position: z.string().optional(),
    footballLevel: z.string().optional(),
  });
  try {
    const data = schema.parse(req.body);
    const profile = await prisma.profile.update({ where: { userId: req.userId }, data });
    return res.json(profile);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

'@

Write-File 'backend\src\routes\readiness.ts' @'
import { Router, Response } from ''express'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { calculateReadiness } from ''../services/readinessService'';

export const readinessRouter = Router();

readinessRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const latest = await prisma.readinessScore.findFirst({
    where: { userId: req.userId },
    orderBy: { calculatedAt: ''desc'' },
  });
  return res.json(latest || { score: 0 });
});

readinessRouter.post(''/recalculate'', authenticate, async (req: AuthRequest, res: Response) => {
  const score = await calculateReadiness(req.userId!);
  return res.json({ score });
});

'@

Write-File 'backend\src\routes\routine.ts' @'
import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { awardXp } from ''../services/xpService'';
import { startOfDay } from ''date-fns'';

export const routineRouter = Router();

routineRouter.get(''/today'', authenticate, async (req: AuthRequest, res: Response) => {
  const userId = req.userId!;
  const today = startOfDay(new Date());
  const checklist = await prisma.routineChecklist.findUnique({ where: { userId } });
  const completion = await prisma.routineCompletion.findUnique({
    where: { userId_date: { userId, date: today } },
  });
  return res.json({ checklist, completion });
});

routineRouter.post(''/complete'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({ itemId: z.string() });
    const { itemId } = schema.parse(req.body);
    const userId = req.userId!;
    const today = startOfDay(new Date());
    const checklist = await prisma.routineChecklist.findUnique({ where: { userId } });
    if (!checklist) return res.status(404).json({ error: ''No routine found'' });

    const existing = await prisma.routineCompletion.findUnique({
      where: { userId_date: { userId, date: today } },
    });

    let completedItems: string[] = existing ? (existing.completedItems as string[]) : [];
    if (!completedItems.includes(itemId)) completedItems.push(itemId);

    const items = checklist.items as Array<{ id: string; enabled: boolean }>;
    const enabledItems = items.filter((i) => i.enabled);
    const isFullyComplete = enabledItems.every((i) => completedItems.includes(i.id));
    const xpAwarded = isFullyComplete && !existing?.xpAwarded ? 25 : 0;

    const completion = await prisma.routineCompletion.upsert({
      where: { userId_date: { userId, date: today } },
      update: { completedItems, xpAwarded: existing?.xpAwarded || xpAwarded },
      create: {
        userId,
        routineChecklistId: checklist.id,
        date: today,
        completedItems,
        xpAwarded,
      },
    });

    if (xpAwarded > 0) {
      await awardXp(userId, xpAwarded, ''routine_complete'', ''Completed daily routine'');
    }

    return res.json({ completion, isFullyComplete });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

routineRouter.put(''/settings'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({ items: z.array(z.object({ id: z.string(), label: z.string(), time: z.string(), enabled: z.boolean() })) });
    const { items } = schema.parse(req.body);
    const checklist = await prisma.routineChecklist.update({
      where: { userId: req.userId },
      data: { items },
    });
    return res.json(checklist);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

'@

Write-File 'backend\src\routes\settings.ts' @'
import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';

export const settingsRouter = Router();

settingsRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const settings = await prisma.userSettings.findUnique({ where: { userId: req.userId } });
  const supplements = await prisma.supplementReminder.findMany({ where: { userId: req.userId } });
  const equipment = await prisma.userEquipment.findMany({ where: { userId: req.userId } });
  const dietary = await prisma.dietaryPreference.findMany({ where: { userId: req.userId } });
  return res.json({ settings, supplements, equipment: equipment.map((e) => e.equipment), dietary: dietary.map((d) => d.preference) });
});

settingsRouter.put(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({
      notificationsEnabled: z.boolean().optional(),
      emailNotifications: z.boolean().optional(),
      privacyPublic: z.boolean().optional(),
      maxWorkoutDuration: z.number().optional(),
      minWorkoutDuration: z.number().optional(),
      preferredWorkoutTime: z.string().optional(),
    });
    const data = schema.parse(req.body);
    const settings = await prisma.userSettings.upsert({
      where: { userId: req.userId },
      update: data,
      create: { userId: req.userId!, ...data },
    });
    return res.json(settings);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

settingsRouter.put(''/equipment'', authenticate, async (req: AuthRequest, res: Response) => {
  const { equipment } = req.body as { equipment: string[] };
  await prisma.userEquipment.deleteMany({ where: { userId: req.userId } });
  if (equipment?.length) {
    await prisma.userEquipment.createMany({ data: equipment.map((e) => ({ userId: req.userId!, equipment: e })) });
  }
  return res.json({ success: true });
});

settingsRouter.put(''/supplements'', authenticate, async (req: AuthRequest, res: Response) => {
  const { supplements } = req.body as { supplements: Array<{ name: string; timing: string }> };
  await prisma.supplementReminder.deleteMany({ where: { userId: req.userId } });
  if (supplements?.length) {
    await prisma.supplementReminder.createMany({ data: supplements.map((s) => ({ userId: req.userId!, ...s })) });
  }
  return res.json({ success: true });
});

'@

Write-File 'backend\src\routes\tests.ts' @'
import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { awardXp, XP_REWARDS } from ''../services/xpService'';

export const testsRouter = Router();

testsRouter.post(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({
      testType: z.string(),
      value: z.number(),
      unit: z.string().optional(),
      notes: z.string().optional(),
    });
    const data = schema.parse(req.body);
    const userId = req.userId!;

    // Check if this is an improvement
    const previous = await prisma.manualTestResult.findFirst({
      where: { userId, testType: data.testType },
      orderBy: { testedAt: ''desc'' },
    });

    const result = await prisma.manualTestResult.create({
      data: { userId, ...data },
    });

    let xpAwarded = 50;
    let isImprovement = false;

    if (previous) {
      // For time-based tests, lower is better; for reps, higher is better
      const timeBasedTests = [''20m_sprint'', ''5_10_5_shuttle'', ''cone_drill'', ''beep_test''];
      const improved = timeBasedTests.includes(data.testType)
        ? data.value < previous.value
        : data.value > previous.value;

      if (improved) {
        xpAwarded = XP_REWARDS.test_improvement;
        isImprovement = true;
        await prisma.notification.create({
          data: {
            userId,
            type: ''test_improvement'',
            title: ''New Personal Best! 🏆'',
            body: `You improved your ${data.testType.replace(/_/g, '' '')} result!`,
          },
        });
      }
    }

    await awardXp(userId, xpAwarded, ''test'', `Test: ${data.testType}`);
    return res.status(201).json({ result, xpAwarded, isImprovement });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

testsRouter.get(''/history'', authenticate, async (req: AuthRequest, res: Response) => {
  const results = await prisma.manualTestResult.findMany({
    where: { userId: req.userId },
    orderBy: { testedAt: ''desc'' },
  });
  return res.json(results);
});

'@

Write-File 'backend\src\routes\wearables.ts' @'
import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { awardXp, XP_REWARDS } from ''../services/xpService'';

export const wearablesRouter = Router();

wearablesRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const connections = await prisma.wearableConnection.findMany({ where: { userId: req.userId } });
  return res.json(connections);
});

// ── Fitbit OAuth ─────────────────────────────────────────────────────────────
wearablesRouter.get(''/fitbit/connect'', authenticate, async (req: AuthRequest, res: Response) => {
  const clientId = process.env.FITBIT_CLIENT_ID;
  if (!clientId) return res.status(500).json({ error: ''Fitbit not configured'' });
  const redirect = process.env.FITBIT_REDIRECT_URI;
  const scope = ''activity heartrate sleep weight profile'';
  const url = `https://www.fitbit.com/oauth2/authorize?response_type=code&client_id=${clientId}&redirect_uri=${redirect}&scope=${encodeURIComponent(scope)}`;
  return res.json({ url });
});

wearablesRouter.get(''/fitbit/callback'', authenticate, async (req: AuthRequest, res: Response) => {
  // TODO: Exchange code for token using Fitbit API
  // For now, store placeholder connection
  const { code } = req.query;
  if (!code) return res.status(400).json({ error: ''No code provided'' });
  await prisma.wearableConnection.upsert({
    where: { userId_provider: { userId: req.userId!, provider: ''fitbit'' } },
    update: { isActive: true, metadata: { note: ''Token exchange required'' } },
    create: { userId: req.userId!, provider: ''fitbit'', isActive: true, metadata: { code } },
  });
  return res.json({ success: true, message: ''Fitbit connected (TODO: token exchange)'' });
});

wearablesRouter.post(''/fitbit/sync'', authenticate, async (req: AuthRequest, res: Response) => {
  // TODO: Call Fitbit Web API with stored access token to pull real data
  await awardXp(req.userId!, XP_REWARDS.wearable_sync, ''wearable_sync'', ''Synced Fitbit'');
  await prisma.wearableConnection.update({
    where: { userId_provider: { userId: req.userId!, provider: ''fitbit'' } },
    data: { lastSync: new Date() },
  });
  return res.json({ success: true, message: ''Fitbit sync triggered (TODO: real API call)'' });
});

// ── Garmin ───────────────────────────────────────────────────────────────────
wearablesRouter.get(''/garmin/connect'', authenticate, (_req: AuthRequest, res: Response) => {
  // TODO: Garmin requires approved API partner access
  // Implement OAuth once approved: https://developer.garmin.com/gc-developer-program/overview/
  return res.json({ message: ''Garmin integration requires partner API approval. Connect manually below.'' });
});

// ── Apple Health ──────────────────────────────────────────────────────────────
wearablesRouter.post(''/apple-health/ingest'', authenticate, async (req: AuthRequest, res: Response) => {
  // This endpoint is designed to receive data pushed from a companion iOS app using HealthKit
  // TODO: Build companion iOS app that reads HealthKit and POSTs to this endpoint
  try {
    const schema = z.object({
      metrics: z.array(z.object({
        type: z.string(),
        value: z.number(),
        date: z.string(),
        unit: z.string().optional(),
      })),
    });
    const { metrics } = schema.parse(req.body);
    await prisma.healthMetric.createMany({
      data: metrics.map((m) => ({
        userId: req.userId!,
        metricType: m.type,
        value: m.value,
        date: new Date(m.date),
        unit: m.unit,
        source: ''apple'',
      })),
      skipDuplicates: true,
    });
    await awardXp(req.userId!, XP_REWARDS.wearable_sync, ''wearable_sync'', ''Apple Health sync'');
    return res.json({ success: true, count: metrics.length });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

// ── Google Fit ────────────────────────────────────────────────────────────────
wearablesRouter.post(''/google-health/ingest'', authenticate, async (req: AuthRequest, res: Response) => {
  // TODO: Implement Google Health Connect OAuth and data pull
  return res.json({ message: ''Google Health Connect ingestion endpoint ready (TODO: OAuth implementation)'' });
});

// ── Manual entry ──────────────────────────────────────────────────────────────
wearablesRouter.post(''/manual'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({
      steps: z.number().optional(),
      sleepHours: z.number().optional(),
      sleepScore: z.number().optional(),
      restingHr: z.number().optional(),
      weightKg: z.number().optional(),
      activeMinutes: z.number().optional(),
      date: z.string().optional(),
    });
    const data = schema.parse(req.body);
    const date = data.date ? new Date(data.date) : new Date();

    const metrics = Object.entries(data)
      .filter(([k, v]) => k !== ''date'' && v !== undefined)
      .map(([type, value]) => ({ userId: req.userId!, metricType: type, value: value as number, date, source: ''manual'' }));

    if (metrics.length > 0) {
      await prisma.healthMetric.createMany({ data: metrics });
    }

    await awardXp(req.userId!, XP_REWARDS.manual_health_log, ''manual_entry'', ''Manual health data entry'');
    return res.json({ success: true, count: metrics.length });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

// ── CSV Import ────────────────────────────────────────────────────────────────
wearablesRouter.post(''/csv-import'', authenticate, async (_req: AuthRequest, res: Response) => {
  // TODO: Parse uploaded CSV and bulk-insert health metrics
  return res.json({ message: ''CSV import endpoint ready (TODO: multipart upload + CSV parser)'' });
});

wearablesRouter.delete(''/:provider'', authenticate, async (req: AuthRequest, res: Response) => {
  await prisma.wearableConnection.update({
    where: { userId_provider: { userId: req.userId!, provider: req.params.provider } },
    data: { isActive: false, accessToken: null, refreshToken: null },
  });
  return res.json({ success: true });
});

'@

Write-File 'backend\src\routes\workout.ts' @'
import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { generateWorkout, completeWorkout } from ''../services/workoutService'';
import { awardXp, XP_REWARDS } from ''../services/xpService'';
import { recalculatePlayerCard } from ''../services/xpService'';

export const workoutRouter = Router();

const generateSchema = z.object({
  durationMins: z.number().min(5).max(120),
  intensity: z.enum([''recovery'', ''easy'', ''moderate'', ''hard'']),
  goal: z.string(),
  equipment: z.array(z.string()).default([]),
  energyState: z.enum([''green'', ''yellow'', ''red'']).default(''green''),
});

workoutRouter.post(''/generate'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const params = generateSchema.parse(req.body);
    const userId = req.userId!;

    // Get user''s equipment if not provided
    if (!params.equipment.length) {
      const userEquipment = await prisma.userEquipment.findMany({ where: { userId } });
      params.equipment = userEquipment.map((e) => e.equipment);
    }

    const profile = await prisma.profile.findUnique({ where: { userId } });
    const workout = await generateWorkout(userId, { ...params, position: profile?.position });
    return res.status(201).json(workout);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

workoutRouter.post(''/minimum-viable'', authenticate, async (req: AuthRequest, res: Response) => {
  const userId = req.userId!;
  const workout = await generateWorkout(userId, {
    durationMins: 10,
    intensity: ''easy'',
    goal: ''mobility'',
    equipment: [],
    energyState: ''yellow'',
  });
  await awardXp(userId, XP_REWARDS.minimum_viable_session, ''minimum_viable_session'', ''Minimum viable session'');
  return res.status(201).json(workout);
});

workoutRouter.post(''/complete'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({ generatedWorkoutId: z.string(), rpe: z.number().min(1).max(10), notes: z.string().optional() });
    const { generatedWorkoutId, rpe, notes } = schema.parse(req.body);
    const workout = await completeWorkout(req.userId!, generatedWorkoutId, rpe, notes);
    await recalculatePlayerCard(req.userId!);
    return res.json(workout);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

workoutRouter.post(''/manual'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({
      title: z.string(),
      category: z.string(),
      difficulty: z.enum([''recovery'', ''easy'', ''moderate'', ''hard'']),
      durationMins: z.number(),
      rpe: z.number().min(1).max(10).optional(),
      notes: z.string().optional(),
      equipmentUsed: z.array(z.string()).default([]),
    });
    const data = schema.parse(req.body);
    const xpMap: Record<string, number> = { recovery: 30, easy: 50, moderate: 80, hard: 120 };
    const xpAwarded = xpMap[data.difficulty] || 50;
    const workout = await prisma.workout.create({
      data: { userId: req.userId!, ...data, xpAwarded },
    });
    await awardXp(req.userId!, xpAwarded, ''manual_workout'', `Manual workout: ${data.title}`);
    await recalculatePlayerCard(req.userId!);
    return res.status(201).json(workout);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

workoutRouter.get(''/history'', authenticate, async (req: AuthRequest, res: Response) => {
  const workouts = await prisma.workout.findMany({
    where: { userId: req.userId },
    orderBy: { completedAt: ''desc'' },
    take: 50,
  });
  return res.json(workouts);
});

'@

Write-File 'backend\src\routes\xp.ts' @'
import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { awardXp, xpToLevel, xpProgressInLevel } from ''../services/xpService'';

export const xpRouter = Router();

xpRouter.get(''/history'', authenticate, async (req: AuthRequest, res: Response) => {
  const events = await prisma.xPEvent.findMany({
    where: { userId: req.userId },
    orderBy: { createdAt: ''desc'' },
    take: 100,
  });
  const card = await prisma.playerCard.findUnique({ where: { userId: req.userId } });
  const totalXp = card?.totalXp || 0;
  return res.json({ events, totalXp, level: xpToLevel(totalXp), progress: xpProgressInLevel(totalXp) });
});

xpRouter.post(''/award'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({ amount: z.number().min(1).max(1000), source: z.string(), description: z.string().optional() });
    const { amount, source, description } = schema.parse(req.body);
    await awardXp(req.userId!, amount, source, description);
    return res.json({ success: true });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

'@

Write-File 'backend\src\services\challengeService.ts' @'
import { prisma } from ''../utils/prisma'';
import { awardXp } from ''./xpService'';
import { startOfDay, endOfDay, startOfWeek, endOfWeek } from ''date-fns'';

const DAILY_CHALLENGES = [
  { title: ''Log your energy'', description: ''Log your energy level for today'', xpReward: 10, category: ''daily'', target: 1, unit: ''logs'' },
  { title: ''Hit 8,000 steps'', description: ''Reach 8,000 steps today'', xpReward: 30, category: ''steps'', target: 8000, unit: ''steps'' },
  { title: ''Complete a workout'', description: ''Complete any workout session today'', xpReward: 50, category: ''workout'', target: 1, unit: ''workouts'' },
  { title: ''Drink 2L of water'', description: ''Stay hydrated with 2 litres of water'', xpReward: 15, category: ''hydration'', target: 2, unit: ''litres'' },
  { title: ''Morning routine'', description: ''Complete your morning routine checklist'', xpReward: 20, category: ''routine'', target: 1, unit: ''routines'' },
  { title: ''Recovery block'', description: ''Complete a recovery or mobility session'', xpReward: 25, category: ''recovery'', target: 1, unit: ''sessions'' },
  { title: ''10 mins of movement'', description: ''Get moving for at least 10 minutes'', xpReward: 20, category: ''activity'', target: 10, unit: ''minutes'' },
  { title: ''Submit workout for XP'', description: ''Submit your completed workout for XP rewards'', xpReward: 15, category: ''workout'', target: 1, unit: ''submissions'' },
  { title: ''Log your food'', description: ''Log at least one meal today'', xpReward: 10, category: ''nutrition'', target: 1, unit: ''meals'' },
  { title: ''Protein breakfast'', description: ''Eat a protein-rich breakfast today'', xpReward: 15, category: ''nutrition'', target: 1, unit: ''meals'' },
  { title: ''Bedtime routine'', description: ''Complete your bedtime wind-down routine'', xpReward: 20, category: ''routine'', target: 1, unit: ''routines'' },
];

const WEEKLY_CHALLENGES = [
  { title: ''Complete 3 workouts'', description: ''Complete 3 workout sessions this week'', xpReward: 200, category: ''workout'', target: 3, unit: ''workouts'' },
  { title: ''Hit weekly step target'', description: ''Reach 56,000 steps this week (8,000/day)'', xpReward: 200, category: ''steps'', target: 56000, unit: ''steps'' },
  { title: ''Agility session'', description: ''Complete 1 agility or speed session'', xpReward: 150, category: ''agility'', target: 1, unit: ''sessions'' },
  { title: ''Strength session'', description: ''Complete 1 strength training session'', xpReward: 150, category: ''strength'', target: 1, unit: ''sessions'' },
  { title: ''Stamina session'', description: ''Complete 1 cardio or stamina session'', xpReward: 150, category: ''stamina'', target: 1, unit: ''sessions'' },
  { title: ''Football skill session'', description: ''Complete 1 football skills session'', xpReward: 175, category: ''football'', target: 1, unit: ''sessions'' },
  { title: ''Sleep 7+ hours x4'', description: ''Get at least 7 hours sleep on 4 nights'', xpReward: 200, category: ''sleep'', target: 4, unit: ''nights'' },
  { title: ''Log energy 5 days'', description: ''Log your energy level 5 days this week'', xpReward: 100, category: ''energy'', target: 5, unit: ''days'' },
  { title: ''Maintain streak'', description: ''Keep your daily activity streak going all week'', xpReward: 300, category: ''streak'', target: 7, unit: ''days'' },
  { title: ''Complete 2 recovery blocks'', description: ''Complete 2 recovery or mobility sessions'', xpReward: 150, category: ''recovery'', target: 2, unit: ''sessions'' },
];

export async function ensureDailyChallenges(userId: string) {
  const today = new Date();
  const dayStart = startOfDay(today);
  const dayEnd = endOfDay(today);

  const existing = await prisma.userChallenge.findMany({
    where: { userId, expiresAt: { gte: dayStart, lte: dayEnd }, challenge: { type: ''daily'' } },
    include: { challenge: true },
  });

  if (existing.length >= 3) return existing;

  // Pick 3 random daily challenges
  const shuffled = [...DAILY_CHALLENGES].sort(() => Math.random() - 0.5).slice(0, 3);

  for (const c of shuffled) {
    const challenge = await prisma.challenge.create({
      data: { ...c, type: ''daily'', difficulty: ''medium'', isActive: true },
    });
    await prisma.userChallenge.create({
      data: { userId, challengeId: challenge.id, expiresAt: dayEnd },
    });
  }

  return prisma.userChallenge.findMany({
    where: { userId, expiresAt: { gte: dayStart, lte: dayEnd } },
    include: { challenge: true },
  });
}

export async function ensureWeeklyChallenges(userId: string) {
  const weekStart = startOfWeek(new Date(), { weekStartsOn: 1 });
  const weekEnd = endOfWeek(new Date(), { weekStartsOn: 1 });

  const existing = await prisma.userChallenge.findMany({
    where: { userId, expiresAt: { gte: weekStart, lte: weekEnd }, challenge: { type: ''weekly'' } },
    include: { challenge: true },
  });

  if (existing.length >= 3) return existing;

  const shuffled = [...WEEKLY_CHALLENGES].sort(() => Math.random() - 0.5).slice(0, 3);

  for (const c of shuffled) {
    const challenge = await prisma.challenge.create({
      data: { ...c, type: ''weekly'', difficulty: ''hard'', isActive: true },
    });
    await prisma.userChallenge.create({
      data: { userId, challengeId: challenge.id, expiresAt: weekEnd },
    });
  }

  return prisma.userChallenge.findMany({
    where: { userId, expiresAt: { gte: weekStart, lte: weekEnd } },
    include: { challenge: true },
  });
}

export async function completeChallenge(userId: string, userChallengeId: string) {
  const uc = await prisma.userChallenge.findUnique({
    where: { id: userChallengeId },
    include: { challenge: true },
  });
  if (!uc || uc.userId !== userId) throw new Error(''Challenge not found'');
  if (uc.isCompleted) throw new Error(''Already completed'');

  await prisma.userChallenge.update({
    where: { id: userChallengeId },
    data: { isCompleted: true, completedAt: new Date(), xpAwarded: uc.challenge.xpReward, progress: uc.challenge.target },
  });

  await awardXp(userId, uc.challenge.xpReward, ''challenge'', `Challenge: ${uc.challenge.title}`);
  return { xpAwarded: uc.challenge.xpReward };
}

'@

Write-File 'backend\src\services\readinessService.ts' @'
import { prisma } from ''../utils/prisma'';

export async function calculateReadiness(userId: string): Promise<number> {
  const fourteenDaysAgo = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000);
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);

  const [workouts, summaries, tests, goal] = await Promise.all([
    prisma.workout.findMany({ where: { userId, completedAt: { gte: thirtyDaysAgo } } }),
    prisma.dailySummary.findMany({ where: { userId, date: { gte: fourteenDaysAgo } }, orderBy: { date: ''desc'' } }),
    prisma.manualTestResult.findMany({ where: { userId }, orderBy: { testedAt: ''desc'' } }),
    prisma.goal.findFirst({ where: { userId, isActive: true }, orderBy: { createdAt: ''desc'' } }),
  ]);

  // 1. Fitness Consistency (20 pts) - workouts per week
  const workoutsPerWeek = workouts.length / 4.3;
  const fitnessConsistency = Math.min(20, workoutsPerWeek * 5);

  // 2. Cardiovascular Base (20 pts) - steps + active minutes + resting HR
  const avgSteps = summaries.length ? summaries.reduce((a, b) => a + (b.steps || 0), 0) / summaries.length : 0;
  const avgRestingHr = summaries.filter((s) => s.restingHr).length
    ? summaries.filter((s) => s.restingHr).reduce((a, b) => a + (b.restingHr || 70), 0) / summaries.filter((s) => s.restingHr).length
    : 70;
  const stepsScore = Math.min(10, (avgSteps / 10000) * 10);
  const hrScore = Math.min(10, ((80 - avgRestingHr) / 20) * 10);
  const cardiovascularBase = Math.max(0, stepsScore + hrScore);

  // 3. Football Conditioning (15 pts)
  const footballWorkouts = workouts.filter((w) => [''football_skill'', ''match_simulation'', ''agility'', ''speed''].includes(w.category));
  const footballConditioning = Math.min(15, footballWorkouts.length * 2.5);

  // 4. Strength / Physical (15 pts)
  const strengthWorkouts = workouts.filter((w) => w.category === ''strength'');
  const strengthPhysical = Math.min(15, strengthWorkouts.length * 3);

  // 5. Recovery / Sleep (15 pts)
  const avgSleep = summaries.filter((s) => s.sleepHours).length
    ? summaries.filter((s) => s.sleepHours).reduce((a, b) => a + (b.sleepHours || 7), 0) / summaries.filter((s) => s.sleepHours).length
    : 7;
  const avgEnergy = summaries.filter((s) => s.energyLevel).length
    ? summaries.filter((s) => s.energyLevel).reduce((a, b) => a + (b.energyLevel || 3), 0) / summaries.filter((s) => s.energyLevel).length
    : 3;
  const sleepScore = Math.min(10, (avgSleep / 8) * 10);
  const energyScore = Math.min(5, (avgEnergy / 5) * 5);
  const recoverySleep = sleepScore + energyScore;

  // 6. Body / Weight Trend (5 pts)
  const bodyWeightTrend = goal?.mainGoal ? 3 : 2.5;

  // 7. Skills / Agility Tests (10 pts)
  const recentTests = tests.filter((t) => new Date(t.testedAt) >= thirtyDaysAgo);
  const skillsAgilityTests = Math.min(10, recentTests.length * 2);

  const total = fitnessConsistency + cardiovascularBase + footballConditioning + strengthPhysical + recoverySleep + bodyWeightTrend + skillsAgilityTests;
  const score = Math.min(100, Math.max(0, Math.round(total)));

  await prisma.readinessScore.create({
    data: {
      userId,
      score,
      fitnessConsistency,
      cardiovascularBase,
      footballConditioning,
      strengthPhysical,
      recoverySleep,
      bodyWeightTrend,
      skillsAgilityTests,
    },
  });

  return score;
}

'@

Write-File 'backend\src\services\workoutService.ts' @'
import { prisma } from ''../utils/prisma'';
import { awardXp, XP_REWARDS } from ''./xpService'';

export interface WorkoutParams {
  durationMins: number;
  intensity: ''recovery'' | ''easy'' | ''moderate'' | ''hard'';
  goal: string;
  equipment: string[];
  energyState: ''green'' | ''yellow'' | ''red'';
  position?: string;
}

function getXpForWorkout(intensity: string): number {
  const map: Record<string, number> = {
    recovery: 30,
    easy: XP_REWARDS.workout_easy,
    moderate: XP_REWARDS.workout_moderate,
    hard: XP_REWARDS.workout_hard,
  };
  return map[intensity] || 50;
}

function generateExercises(params: WorkoutParams) {
  const { intensity, goal, equipment, energyState, durationMins } = params;
  const hasFootball = equipment.some((e) => [''football'', ''cones'', ''agility_ladder''].includes(e));
  const hasGym = equipment.some((e) => [''dumbbells'', ''barbell'', ''full_gym_access'', ''squat_rack''].includes(e));
  const hasTreadmill = equipment.some((e) => [''treadmill'', ''walking_pad''].includes(e));
  const hasBike = equipment.includes(''exercise_bike'');
  const hasRower = equipment.includes(''rowing_machine'');
  const hasKettlebell = equipment.includes(''kettlebells'');

  // Red day override - recovery only
  if (energyState === ''red'') {
    return {
      title: ''Recovery & Mobility Session'',
      warmup: [
        { name: ''Gentle walking'', duration: ''5 mins'', notes: ''Very easy pace'' },
        { name: ''Deep breathing'', duration: ''2 mins'', sets: '''', reps: '''' },
      ],
      main: [
        { name: ''Lying knee hugs'', sets: ''2'', reps: ''10 each'', rest: ''30s'' },
        { name: ''Cat-cow stretch'', sets: ''2'', duration: ''60s'', rest: ''20s'' },
        { name: ''Hip circles'', sets: ''2'', reps: ''10 each side'', rest: ''20s'' },
        { name: ''Seated forward fold'', sets: ''2'', duration: ''60s'', rest: ''30s'' },
        { name: ''Box breathing'', sets: ''3'', duration: ''60s'', rest: ''10s'' },
        { name: ''Gentle walking'', duration: ''5 mins'', notes: ''Cool down'' },
      ],
      cooldown: [{ name: ''Full body stretch'', duration: ''5 mins'' }],
      statsImproved: [''recovery''],
      xpReward: 30,
      estimatedFatigue: 1,
    };
  }

  const warmup = [
    { name: ''Light jog / march on spot'', duration: ''3 mins'' },
    { name: ''Leg swings'', sets: ''2'', reps: ''10 each side'' },
    { name: ''Arm circles'', sets: ''2'', reps: ''10 each direction'' },
    { name: ''Hip openers'', sets: ''2'', reps: ''8 each side'' },
  ];

  const cooldown = [
    { name: ''Walking cool-down'', duration: ''3 mins'' },
    { name: ''Hamstring stretch'', duration: ''60s each leg'' },
    { name: ''Quad stretch'', duration: ''45s each leg'' },
    { name: ''Hip flexor stretch'', duration: ''60s each side'' },
  ];

  let main: object[] = [];
  let statsImproved: string[] = [];

  if (goal === ''stamina'') {
    statsImproved = [''stamina'', ''recovery''];
    if (hasRower) {
      main = [
        { name: ''Rowing machine'', sets: ''1'', duration: `${Math.floor(durationMins * 0.7)} mins`, intensity: intensity === ''hard'' ? ''80-90% effort'' : ''65-75% effort'', rest: ''2 mins'' },
        { name: ''Step-ups'', sets: ''3'', reps: ''15 each leg'', rest: ''45s'' },
      ];
    } else if (hasTreadmill) {
      main = [
        { name: ''Treadmill intervals'', sets: ''6'', duration: ''2 mins on / 1 min walk'', notes: intensity === ''hard'' ? ''8-9 RPE'' : ''6-7 RPE'' },
        { name: ''Bodyweight squats'', sets: ''3'', reps: ''20'', rest: ''30s'' },
      ];
    } else {
      main = [
        { name: ''Burpees'', sets: ''4'', reps: intensity === ''hard'' ? ''15'' : ''10'', rest: ''60s'' },
        { name: ''Mountain climbers'', sets: ''3'', duration: ''45s'', rest: ''30s'' },
        { name: ''Jump squats'', sets: ''3'', reps: ''12'', rest: ''45s'' },
        { name: ''High knees'', sets: ''3'', duration: ''30s'', rest: ''30s'' },
      ];
    }
  } else if (goal === ''strength'') {
    statsImproved = [''physical'', ''defending''];
    if (hasGym) {
      main = [
        { name: ''Barbell squat'', sets: ''4'', reps: intensity === ''hard'' ? ''6'' : ''10'', rest: ''90s'' },
        { name: ''Romanian deadlift'', sets: ''3'', reps: ''8'', rest: ''90s'' },
        { name: ''Bench press'', sets: ''4'', reps: ''8'', rest: ''90s'' },
        { name: ''Dumbbell rows'', sets: ''3'', reps: ''10 each'', rest: ''60s'' },
        { name: ''Plank'', sets: ''3'', duration: ''60s'', rest: ''45s'' },
      ];
    } else if (hasKettlebell) {
      main = [
        { name: ''Kettlebell swings'', sets: ''4'', reps: ''15'', rest: ''60s'' },
        { name: ''Goblet squat'', sets: ''3'', reps: ''12'', rest: ''60s'' },
        { name: ''Single-arm KB row'', sets: ''3'', reps: ''10 each'', rest: ''45s'' },
        { name: ''KB Romanian deadlift'', sets: ''3'', reps: ''10'', rest: ''60s'' },
      ];
    } else {
      main = [
        { name: ''Push-ups'', sets: ''4'', reps: intensity === ''hard'' ? ''20'' : ''12'', rest: ''60s'' },
        { name: ''Bulgarian split squats'', sets: ''3'', reps: ''10 each'', rest: ''60s'' },
        { name: ''Pike push-ups'', sets: ''3'', reps: ''10'', rest: ''45s'' },
        { name: ''Glute bridges'', sets: ''3'', reps: ''15'', rest: ''30s'' },
        { name: ''Plank'', sets: ''3'', duration: ''60s'', rest: ''30s'' },
      ];
    }
  } else if (goal === ''speed'' || goal === ''agility'') {
    statsImproved = [''pace'', ''dribbling''];
    if (hasFootball) {
      main = [
        { name: ''5-10-5 shuttle drill'', sets: ''6'', rest: ''90s'', notes: ''Max effort'' },
        { name: ''Cone dribbling slalom'', sets: ''5'', rest: ''60s'', notes: ''Quick feet'' },
        { name: ''Agility ladder - two feet each box'', sets: ''4'', duration: ''30s'', rest: ''60s'' },
        { name: ''Acceleration runs 20m'', sets: ''6'', rest: ''90s'' },
      ];
    } else {
      main = [
        { name: ''10m acceleration sprints'', sets: ''8'', rest: ''90s'' },
        { name: ''Lateral shuffles'', sets: ''4'', duration: ''20s'', rest: ''40s'' },
        { name: ''T-drill (cones or markers)'', sets: ''5'', rest: ''90s'' },
        { name: ''Broad jumps'', sets: ''3'', reps: ''6'', rest: ''60s'' },
      ];
    }
  } else if (goal === ''football_skill'') {
    statsImproved = [''passing'', ''shooting'', ''dribbling''];
    main = [
      { name: ''Ball mastery - sole rolls'', sets: ''3'', duration: ''60s'' },
      { name: ''Wall passing (if available)'', sets: ''5'', duration: ''2 mins'', notes: ''Focus on first touch'' },
      { name: ''Shooting practice'', sets: ''3'', reps: ''10 shots'', notes: ''Vary placement'' },
      { name: ''Dribbling course (cones)'', sets: ''5'', rest: ''45s'' },
      { name: ''Keep-ups'', sets: ''3'', duration: ''2 mins'' },
    ];
  } else if (goal === ''mobility'' || goal === ''recovery'') {
    statsImproved = [''recovery'', ''composure''];
    main = [
      { name: ''World greatest stretch'', sets: ''2'', reps: ''8 each side'', rest: ''20s'' },
      { name: ''Pigeon pose'', sets: ''2'', duration: ''90s each side'', rest: ''20s'' },
      { name: ''Thoracic rotation'', sets: ''2'', reps: ''10 each side'' },
      { name: ''Hip 90/90 stretch'', sets: ''2'', duration: ''60s each'', rest: ''20s'' },
      { name: ''Shoulder cross-body stretch'', sets: ''2'', duration: ''45s each'' },
      { name: ''Box breathing'', sets: ''3'', duration: ''2 mins'', rest: ''30s'' },
    ];
  } else if (goal === ''match_simulation'') {
    statsImproved = [''stamina'', ''pace'', ''composure''];
    main = [
      { name: ''Warm-up rondos'', sets: ''2'', duration: ''5 mins'' },
      { name: ''High intensity intervals (match simulation)'', sets: ''6'', duration: ''4 mins on / 2 min walk'', notes: ''90% effort during work'' },
      { name: ''Sprint + recover shuttles'', sets: ''4'', rest: ''60s'' },
      { name: ''Core stability'', sets: ''3'', duration: ''45s'', rest: ''30s'' },
    ];
  } else {
    statsImproved = [''stamina'', ''physical''];
    main = [
      { name: ''Bodyweight squats'', sets: ''3'', reps: ''15'', rest: ''45s'' },
      { name: ''Push-ups'', sets: ''3'', reps: ''12'', rest: ''45s'' },
      { name: ''Lunges'', sets: ''3'', reps: ''10 each'', rest: ''45s'' },
      { name: ''Plank'', sets: ''3'', duration: ''45s'', rest: ''30s'' },
      { name: ''Jumping jacks'', sets: ''3'', duration: ''30s'', rest: ''30s'' },
    ];
  }

  return {
    title: `${intensity.charAt(0).toUpperCase() + intensity.slice(1)} ${goal.replace(/_/g, '' '')} Session`,
    warmup,
    main,
    cooldown,
    statsImproved,
    xpReward: getXpForWorkout(intensity),
    estimatedFatigue: intensity === ''hard'' ? 4 : intensity === ''moderate'' ? 3 : intensity === ''easy'' ? 2 : 1,
  };
}

export async function generateWorkout(userId: string, params: WorkoutParams) {
  const generated = generateExercises(params);
  const workout = await prisma.generatedWorkout.create({
    data: {
      userId,
      title: generated.title,
      category: params.goal,
      difficulty: params.intensity,
      durationMins: params.durationMins,
      energyState: params.energyState,
      xpReward: generated.xpReward,
      estimatedFatigue: generated.estimatedFatigue,
      warmup: generated.warmup,
      mainSection: generated.main,
      cooldown: generated.cooldown,
      statsImproved: generated.statsImproved,
    },
  });
  return workout;
}

export async function completeWorkout(userId: string, generatedWorkoutId: string, rpe: number, notes?: string) {
  const gw = await prisma.generatedWorkout.findUnique({ where: { id: generatedWorkoutId } });
  if (!gw || gw.userId !== userId) throw new Error(''Workout not found'');

  const workout = await prisma.$transaction(async (tx) => {
    const w = await tx.workout.create({
      data: {
        userId,
        generatedWorkoutId,
        title: gw.title,
        category: gw.category,
        difficulty: gw.difficulty,
        durationMins: gw.durationMins,
        rpe,
        notes,
        xpAwarded: gw.xpReward,
        statsImproved: gw.statsImproved,
        equipmentUsed: [],
      },
    });
    await tx.generatedWorkout.update({ where: { id: generatedWorkoutId }, data: { isCompleted: true, completedAt: new Date() } });
    return w;
  });

  await awardXp(userId, gw.xpReward, ''workout'', `Completed: ${gw.title}`);
  return workout;
}

'@

Write-File 'backend\src\services\xpService.ts' @'
import { prisma } from ''../utils/prisma'';

export const XP_REWARDS = {
  energy_log: 10,
  daily_challenge: 30,
  weekly_challenge: 200,
  minimum_viable_session: 20,
  workout_easy: 50,
  workout_moderate: 80,
  workout_hard: 120,
  test_improvement: 200,
  streak_7_days: 300,
  wearable_sync: 15,
  routine_complete: 25,
  manual_health_log: 10,
  step_goal: 30,
  onboarding: 100,
};

export function xpToLevel(totalXp: number): number {
  // Each level requires progressively more XP
  // Level 1: 0, Level 2: 500, Level 3: 1200, Level 4: 2200...
  let level = 1;
  let threshold = 0;
  const base = 500;
  while (totalXp >= threshold + base * level) {
    threshold += base * level;
    level++;
  }
  return level;
}

export function xpForNextLevel(level: number): number {
  return 500 * level;
}

export function xpProgressInLevel(totalXp: number): { current: number; needed: number; percent: number } {
  let level = 1;
  let threshold = 0;
  const base = 500;
  while (totalXp >= threshold + base * level) {
    threshold += base * level;
    level++;
  }
  const current = totalXp - threshold;
  const needed = base * level;
  return { current, needed, percent: Math.round((current / needed) * 100) };
}

export async function awardXp(userId: string, amount: number, source: string, description?: string) {
  await prisma.$transaction(async (tx) => {
    await tx.xPEvent.create({ data: { userId, amount, source, description } });
    const card = await tx.playerCard.update({
      where: { userId },
      data: { totalXp: { increment: amount } },
    });
    const newLevel = xpToLevel(card.totalXp);
    if (newLevel !== card.xpLevel) {
      await tx.playerCard.update({ where: { userId }, data: { xpLevel: newLevel } });
      await tx.notification.create({
        data: {
          userId,
          type: ''level_up'',
          title: `Level Up! 🎉`,
          body: `You reached Level ${newLevel}! Keep grinding!`,
        },
      });
    }
  });
}

export function getCardTier(overall: number): string {
  if (overall >= 90) return ''elite'';
  if (overall >= 85) return ''rare_gold'';
  if (overall >= 75) return ''common_gold'';
  if (overall >= 60) return ''silver'';
  return ''bronze'';
}

export async function recalculatePlayerCard(userId: string) {
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);

  const [workouts, tests, card, summaries] = await Promise.all([
    prisma.workout.findMany({
      where: { userId, completedAt: { gte: thirtyDaysAgo } },
    }),
    prisma.manualTestResult.findMany({ where: { userId } }),
    prisma.playerCard.findUnique({ where: { userId } }),
    prisma.dailySummary.findMany({
      where: { userId, date: { gte: thirtyDaysAgo } },
      orderBy: { date: ''desc'' },
      take: 30,
    }),
  ]);

  if (!card) return;

  const speedWorkouts = workouts.filter((w) => w.category === ''speed'' || w.category === ''agility'');
  const staminaWorkouts = workouts.filter((w) => w.category === ''stamina'');
  const strengthWorkouts = workouts.filter((w) => w.category === ''strength'');
  const footballWorkouts = workouts.filter((w) => w.category === ''football_skill'' || w.category === ''match_simulation'');
  const recoveryWorkouts = workouts.filter((w) => w.category === ''recovery'');

  const sprintTests = tests.filter((t) => t.testType === ''20m_sprint'');
  const avgSleep = summaries.length > 0 ? summaries.reduce((a, b) => a + (b.sleepHours || 7), 0) / summaries.length : 7;
  const avgSteps = summaries.length > 0 ? summaries.reduce((a, b) => a + (b.steps || 0), 0) / summaries.length : 0;

  const paceDelta = speedWorkouts.length * 0.3 + (sprintTests.length > 1 ? 1 : 0);
  const staminaDelta = staminaWorkouts.length * 0.4 + (avgSteps > 8000 ? 1 : 0);
  const physicalDelta = strengthWorkouts.length * 0.5;
  const shootingDelta = footballWorkouts.filter((w) => w.title.toLowerCase().includes(''shoot'')).length * 0.5;
  const passingDelta = footballWorkouts.filter((w) => w.title.toLowerCase().includes(''pass'')).length * 0.5;
  const dribblingDelta = speedWorkouts.length * 0.2 + footballWorkouts.length * 0.3;
  const defendingDelta = speedWorkouts.length * 0.2 + strengthWorkouts.length * 0.2;
  const recoveryDelta = recoveryWorkouts.length * 0.4 + (avgSleep >= 7 ? 1 : 0);
  const composureDelta = summaries.filter((s) => !s.isCrashDay).length * 0.1;

  const cap = (base: number, delta: number, max = 99) => Math.min(max, Math.round(base + delta));

  const newStats = {
    pace: cap(card.pace, paceDelta),
    stamina: cap(card.stamina, staminaDelta),
    physical: cap(card.physical, physicalDelta),
    shooting: cap(card.shooting, shootingDelta),
    passing: cap(card.passing, passingDelta),
    dribbling: cap(card.dribbling, dribblingDelta),
    defending: cap(card.defending, defendingDelta),
    recovery: cap(card.recovery, recoveryDelta),
    composure: cap(card.composure, composureDelta),
  };

  const statValues = Object.values(newStats);
  const overall = Math.round(statValues.reduce((a, b) => a + b, 0) / statValues.length);
  const tier = getCardTier(overall);

  await prisma.playerCard.update({
    where: { userId },
    data: { ...newStats, overall, tier },
  });

  return { ...newStats, overall, tier };
}

'@

Write-File 'backend\src\utils\prisma.ts' @'
import { PrismaClient } from ''@prisma/client'';

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };
export const prisma = globalForPrisma.prisma || new PrismaClient();
if (process.env.NODE_ENV !== ''production'') globalForPrisma.prisma = prisma;

'@

Write-File 'backend\tsconfig.json' @'
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "lib": ["ES2020"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "sourceMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}

'@

Write-File 'frontend\index.html' @'
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MatchFit Pro</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>

'@

Write-File 'frontend\package.json' @'
{
  "name": "matchfit-pro-frontend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "axios": "^1.6.7",
    "date-fns": "^3.3.1",
    "lucide-react": "^0.323.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "recharts": "^2.12.0",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.55",
    "@types/react-dom": "^18.2.19",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.35",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.3.3",
    "vite": "^5.1.0"
  }
}

'@

Write-File 'frontend\postcss.config.js' @'
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };

'@

Write-File 'frontend\src\App.tsx' @'
import { useEffect } from ''react'';
import { BrowserRouter, Routes, Route, Navigate } from ''react-router-dom'';
import { useAuthStore } from ''./store/authStore'';
import Layout from ''./components/layout/Layout'';
import LandingPage from ''./pages/LandingPage'';
import LoginPage from ''./pages/LoginPage'';
import RegisterPage from ''./pages/RegisterPage'';
import OnboardingPage from ''./pages/OnboardingPage'';
import DashboardPage from ''./pages/DashboardPage'';
import PlayerCardPage from ''./pages/PlayerCardPage'';
import AvatarPage from ''./pages/AvatarPage'';
import WorkoutPlannerPage from ''./pages/WorkoutPlannerPage'';
import WorkoutsPage from ''./pages/WorkoutsPage'';
import ChallengesPage from ''./pages/ChallengesPage'';
import LeaderboardPage from ''./pages/LeaderboardPage'';
import FriendsPage from ''./pages/FriendsPage'';
import WearablesPage from ''./pages/WearablesPage'';
import HealthPage from ''./pages/HealthPage'';
import RoutinePage from ''./pages/RoutinePage'';
import TestsPage from ''./pages/TestsPage'';
import SettingsPage from ''./pages/SettingsPage'';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, user } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;
  if (user && !user.profile?.onboardingDone) return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}

function OnboardingRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { token, fetchMe, loading } = useAuthStore();

  useEffect(() => {
    if (token) fetchMe();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-pitch-900 flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl font-display font-black text-electric-400 mb-2 animate-pulse">MATCHFIT PRO</div>
          <div className="text-gray-400 text-sm">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={token ? <Navigate to="/dashboard" /> : <LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/onboarding" element={<OnboardingRoute><OnboardingPage /></OnboardingRoute>} />
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/player-card" element={<ProtectedRoute><PlayerCardPage /></ProtectedRoute>} />
          <Route path="/avatar" element={<ProtectedRoute><AvatarPage /></ProtectedRoute>} />
          <Route path="/workout-planner" element={<ProtectedRoute><WorkoutPlannerPage /></ProtectedRoute>} />
          <Route path="/workouts" element={<ProtectedRoute><WorkoutsPage /></ProtectedRoute>} />
          <Route path="/challenges" element={<ProtectedRoute><ChallengesPage /></ProtectedRoute>} />
          <Route path="/leaderboards" element={<ProtectedRoute><LeaderboardPage /></ProtectedRoute>} />
          <Route path="/friends" element={<ProtectedRoute><FriendsPage /></ProtectedRoute>} />
          <Route path="/wearables" element={<ProtectedRoute><WearablesPage /></ProtectedRoute>} />
          <Route path="/health" element={<ProtectedRoute><HealthPage /></ProtectedRoute>} />
          <Route path="/routine" element={<ProtectedRoute><RoutinePage /></ProtectedRoute>} />
          <Route path="/tests" element={<ProtectedRoute><TestsPage /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

'@

Write-File 'frontend\src\components\card\PlayerCard.tsx' @'
import { useState } from ''react'';

interface CardData {
  overall: number;
  tier: string;
  pace: number;
  shooting: number;
  passing: number;
  dribbling: number;
  defending: number;
  physical: number;
  stamina: number;
  recovery: number;
  composure: number;
}

interface ProfileData {
  displayName: string;
  position: string;
}

interface AvatarData {
  skinTone: string;
  kitColour: string;
  kitPattern: string;
  hairStyle: string;
  hairColour: string;
  facialHair: string;
  bootColour: string;
  bodyType: string;
  pose: string;
  headband: boolean;
  wristTape: boolean;
  gloves: boolean;
  captainArmband: boolean;
  glasses: boolean;
}

interface PlayerCardProps {
  card: CardData;
  profile: ProfileData;
  avatar: AvatarData;
  animated?: boolean;
  compact?: boolean;
}

const TIER_CONFIG = {
  bronze: {
    bgClass: ''bronze-card'',
    borderColor: ''#cd7f32'',
    textColor: ''#ffd9a0'',
    accentColor: ''#cd7f32'',
    label: ''BRONZE'',
  },
  silver: {
    bgClass: ''silver-card'',
    borderColor: ''#a8b2c0'',
    textColor: ''#e2e8f0'',
    accentColor: ''#94a3b8'',
    label: ''SILVER'',
  },
  common_gold: {
    bgClass: ''gold-card'',
    borderColor: ''#f59e0b'',
    textColor: ''#fde68a'',
    accentColor: ''#f59e0b'',
    label: ''GOLD'',
  },
  rare_gold: {
    bgClass: ''rare-gold-card'',
    borderColor: ''#f59e0b'',
    textColor: ''#fde68a'',
    accentColor: ''#fbbf24'',
    label: ''RARE GOLD'',
  },
  elite: {
    bgClass: ''elite-card'',
    borderColor: ''#a78bfa'',
    textColor: ''#e9d5ff'',
    accentColor: ''#a78bfa'',
    label: ''ELITE'',
  },
};

const SKIN_COLORS: Record<string, string> = {
  light: ''#f5cba7'',
  medium_light: ''#e8a87c'',
  medium: ''#c68642'',
  medium_dark: ''#8d5524'',
  dark: ''#4a2912'',
};

const KIT_COLORS: Record<string, string> = {
  red: ''#dc2626'',
  blue: ''#2563eb'',
  green: ''#16a34a'',
  black: ''#1f2937'',
  white: ''#f9fafb'',
  yellow: ''#ca8a04'',
  purple: ''#7c3aed'',
  orange: ''#ea580c'',
  elite_blue: ''#0ea5e9'',
  elite_black: ''#0f172a'',
  gold: ''#f59e0b'',
  chrome: ''#94a3b8'',
};

function AvatarSVG({ avatar, tier }: { avatar: AvatarData; tier: string }) {
  const skinColor = SKIN_COLORS[avatar.skinTone] || SKIN_COLORS.medium;
  const kitColor = KIT_COLORS[avatar.kitColour] || ''#dc2626'';
  const bootColor = KIT_COLORS[avatar.bootColour] || ''#1f2937'';
  const isElite = tier === ''elite'';

  return (
    <svg viewBox="0 0 100 130" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
      {/* Glow for elite */}
      {isElite && (
        <defs>
          <filter id="elite-glow">
            <feGaussianBlur stdDeviation="2" result="coloredBlur" />
            <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
      )}

      {/* Body / Kit */}
      <ellipse cx="50" cy="90" rx="20" ry="25" fill={kitColor} opacity="0.9" />
      
      {/* Kit pattern */}
      {avatar.kitPattern === ''stripes'' && (
        <>
          <line x1="44" y1="65" x2="44" y2="115" stroke="rgba(255,255,255,0.2)" strokeWidth="3" />
          <line x1="50" y1="65" x2="50" y2="115" stroke="rgba(255,255,255,0.2)" strokeWidth="3" />
          <line x1="56" y1="65" x2="56" y2="115" stroke="rgba(255,255,255,0.2)" strokeWidth="3" />
        </>
      )}
      {avatar.kitPattern === ''flame'' && (
        <path d="M40 115 Q35 95 45 80 Q40 90 50 85 Q45 95 55 90 Q50 100 60 95 Q55 110 60 115 Z" fill="rgba(251,191,36,0.4)" />
      )}

      {/* Neck */}
      <rect x="46" y="58" width="8" height="10" rx="2" fill={skinColor} />

      {/* Head */}
      <ellipse cx="50" cy="48" rx="16" ry="18" fill={skinColor} filter={isElite ? ''url(#elite-glow)'' : undefined} />

      {/* Hair */}
      {avatar.hairStyle === ''short'' && <ellipse cx="50" cy="34" rx="16" ry="8" fill={avatar.hairColour === ''gold'' ? ''#f59e0b'' : avatar.hairColour === ''blonde'' ? ''#fde68a'' : avatar.hairColour === ''black'' ? ''#111'' : avatar.hairColour === ''platinum'' ? ''#e2e8f0'' : ''#92400e''} />}
      {avatar.hairStyle === ''long'' && <path d="M34 34 Q34 60 36 65 L40 65 Q38 45 40 34 Q50 26 60 34 Q62 45 60 65 L64 65 Q66 60 66 34 Q57 22 50 23 Q43 22 34 34Z" fill={avatar.hairColour === ''gold'' ? ''#f59e0b'' : ''#92400e''} />}
      {avatar.hairStyle === ''bald'' && null}
      {avatar.hairStyle === ''curly'' && <ellipse cx="50" cy="32" rx="17" ry="10" fill="#1f1209" opacity="0.9" />}
      {avatar.hairStyle === ''fade'' && <>
        <ellipse cx="50" cy="34" rx="16" ry="7" fill="#111" />
        <ellipse cx="50" cy="40" rx="16" ry="4" fill={skinColor} opacity="0.5" />
      </>}

      {/* Eyes */}
      <ellipse cx="44" cy="47" rx="2.5" ry="2" fill="#1f2937" />
      <ellipse cx="56" cy="47" rx="2.5" ry="2" fill="#1f2937" />
      <ellipse cx="44.5" cy="46.5" rx="1" ry="0.8" fill="white" opacity="0.6" />
      <ellipse cx="56.5" cy="46.5" rx="1" ry="0.8" fill="white" opacity="0.6" />

      {/* Glasses */}
      {avatar.glasses && <>
        <rect x="39" y="44" width="10" height="7" rx="2" fill="none" stroke="#94a3b8" strokeWidth="1" />
        <rect x="51" y="44" width="10" height="7" rx="2" fill="none" stroke="#94a3b8" strokeWidth="1" />
        <line x1="49" y1="47" x2="51" y2="47" stroke="#94a3b8" strokeWidth="1" />
      </>}

      {/* Facial hair */}
      {avatar.facialHair === ''stubble'' && <ellipse cx="50" cy="56" rx="8" ry="3" fill="#4b2e2e" opacity="0.3" />}
      {avatar.facialHair === ''beard'' && <path d="M40 53 Q50 62 60 53 Q58 63 50 66 Q42 63 40 53Z" fill="#3b1f1f" opacity="0.6" />}
      {avatar.facialHair === ''moustache'' && <path d="M44 52 Q50 55 56 52 Q53 57 50 56 Q47 57 44 52Z" fill="#3b1f1f" opacity="0.7" />}

      {/* Arms */}
      <ellipse cx="30" cy="85" rx="6" ry="18" fill={kitColor} transform="rotate(-10 30 85)" />
      <ellipse cx="70" cy="85" rx="6" ry="18" fill={kitColor} transform="rotate(10 70 85)" />
      <ellipse cx="27" cy="97" rx="5" ry="7" fill={skinColor} transform="rotate(-10 27 97)" />
      <ellipse cx="73" cy="97" rx="5" ry="7" fill={skinColor} transform="rotate(10 73 97)" />

      {/* Wrist tape */}
      {avatar.wristTape && <>
        <rect x="22" y="97" width="10" height="3" rx="1" fill="white" opacity="0.8" />
        <rect x="68" y="97" width="10" height="3" rx="1" fill="white" opacity="0.8" />
      </>}

      {/* Legs */}
      <rect x="41" y="113" width="8" height="16" rx="3" fill="#1e3a5f" />
      <rect x="51" y="113" width="8" height="16" rx="3" fill="#1e3a5f" />

      {/* Boots */}
      <ellipse cx="45" cy="129" rx="7" ry="3" fill={bootColor} />
      <ellipse cx="55" cy="129" rx="7" ry="3" fill={bootColor} />

      {/* Headband */}
      {avatar.headband && <rect x="34" y="38" width="32" height="4" rx="2" fill="white" opacity="0.9" />}

      {/* Captain armband */}
      {avatar.captainArmband && <rect x="20" y="83" width="14" height="4" rx="2" fill="#f59e0b" opacity="0.9" />}

      {/* Gloves */}
      {avatar.gloves && <>
        <ellipse cx="27" cy="100" rx="6" ry="8" fill="white" opacity="0.8" />
        <ellipse cx="73" cy="100" rx="6" ry="8" fill="white" opacity="0.8" />
      </>}

      {/* Pose modifications */}
      {avatar.pose === ''celebration'' && (
        <line x1="70" y1="75" x2="85" y2="55" stroke={kitColor} strokeWidth="12" strokeLinecap="round" />
      )}
      {avatar.pose === ''power'' && (
        <line x1="30" y1="75" x2="15" y2="60" stroke={kitColor} strokeWidth="12" strokeLinecap="round" />
      )}
    </svg>
  );
}

export default function PlayerCard({ card, profile, avatar, animated = false, compact = false }: PlayerCardProps) {
  const [showBack, setShowBack] = useState(false);
  const tierConfig = TIER_CONFIG[card.tier as keyof typeof TIER_CONFIG] || TIER_CONFIG.bronze;
  const isElite = card.tier === ''elite'';

  const stats = [
    { label: ''PAC'', value: card.pace },
    { label: ''SHO'', value: card.shooting },
    { label: ''PAS'', value: card.passing },
    { label: ''DRI'', value: card.dribbling },
    { label: ''DEF'', value: card.defending },
    { label: ''PHY'', value: card.physical },
    { label: ''STA'', value: card.stamina },
    { label: ''REC'', value: card.recovery },
    { label: ''COM'', value: card.composure },
  ];

  return (
    <div
      className={`relative cursor-pointer select-none ${compact ? ''w-36 h-48'' : ''w-56 h-80''}`}
      onClick={() => setShowBack(!showBack)}
      style={{ perspective: ''1000px'' }}
    >
      <div
        className="relative w-full h-full transition-all duration-700"
        style={{ transformStyle: ''preserve-3d'', transform: showBack ? ''rotateY(180deg)'' : ''rotateY(0)'' }}
      >
        {/* Front */}
        <div
          className={`absolute inset-0 rounded-2xl overflow-hidden ${tierConfig.bgClass} ${isElite ? ''animate-pulse-glow'' : ''''}`}
          style={{
            backfaceVisibility: ''hidden'',
            border: `2px solid ${tierConfig.borderColor}`,
            boxShadow: isElite
              ? `0 0 30px rgba(167,139,250,0.5), 0 0 60px rgba(236,72,153,0.3)`
              : `0 4px 20px rgba(0,0,0,0.5)`,
          }}
        >
          {/* Elite shine overlay */}
          {isElite && (
            <div className="absolute inset-0 elite-shine opacity-60 z-10 pointer-events-none" />
          )}

          <div className="relative z-20 h-full flex flex-col p-3">
            {/* Header */}
            <div className="flex items-start justify-between mb-1">
              <div className="text-center">
                <div
                  className={`font-display font-black leading-none ${compact ? ''text-3xl'' : ''text-4xl''}`}
                  style={{ color: tierConfig.textColor }}
                >
                  {card.overall}
                </div>
                <div className={`font-display font-bold uppercase ${compact ? ''text-[8px]'' : ''text-[10px]''}`} style={{ color: tierConfig.accentColor }}>
                  {profile.position}
                </div>
              </div>
              <div className={`font-display font-black uppercase tracking-wider ${compact ? ''text-[7px]'' : ''text-[9px]''}`} style={{ color: tierConfig.accentColor }}>
                {tierConfig.label}
              </div>
            </div>

            {/* Avatar area */}
            <div className={`flex-1 flex items-center justify-center ${compact ? ''py-1'' : ''py-2''}`}>
              <div className={compact ? ''w-20 h-24'' : ''w-32 h-40''}>
                <AvatarSVG avatar={avatar} tier={card.tier} />
              </div>
            </div>

            {/* Name */}
            <div className="text-center mb-2">
              <div
                className={`font-display font-black uppercase tracking-wide ${compact ? ''text-xs'' : ''text-sm''}`}
                style={{ color: tierConfig.textColor }}
              >
                {profile.displayName.toUpperCase()}
              </div>
            </div>

            {/* Stats grid */}
            {!compact && (
              <div className="grid grid-cols-3 gap-1">
                {stats.map(({ label, value }) => (
                  <div key={label} className="text-center">
                    <div className="font-display font-black text-sm" style={{ color: tierConfig.textColor }}>{value}</div>
                    <div className="text-[8px] font-medium" style={{ color: tierConfig.accentColor, opacity: 0.8 }}>{label}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Back - full stats */}
        <div
          className={`absolute inset-0 rounded-2xl overflow-hidden ${tierConfig.bgClass}`}
          style={{
            backfaceVisibility: ''hidden'',
            transform: ''rotateY(180deg)'',
            border: `2px solid ${tierConfig.borderColor}`,
          }}
        >
          <div className="h-full flex flex-col p-3">
            <div className="text-center mb-2">
              <div className="font-display font-bold text-sm" style={{ color: tierConfig.textColor }}>FULL STATS</div>
            </div>
            <div className="flex-1 space-y-1.5">
              {stats.map(({ label, value }) => (
                <div key={label} className="flex items-center gap-2">
                  <div className="text-[9px] font-display font-bold w-8" style={{ color: tierConfig.accentColor }}>{label}</div>
                  <div className="flex-1 h-1.5 rounded-full bg-black/30">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${value}%`,
                        backgroundColor: value >= 80 ? ''#10b981'' : value >= 65 ? ''#f59e0b'' : tierConfig.accentColor,
                      }}
                    />
                  </div>
                  <div className="text-[10px] font-display font-black w-6 text-right" style={{ color: tierConfig.textColor }}>{value}</div>
                </div>
              ))}
            </div>
            <div className="text-center mt-2">
              <div className="text-[8px] text-gray-500">Tap to flip</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\components\dashboard\ReadinessRing.tsx' @'
interface ReadinessRingProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  showLabel?: boolean;
}

export default function ReadinessRing({ score, size = 120, strokeWidth = 10, showLabel = true }: ReadinessRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const color = score >= 70 ? ''#10b981'' : score >= 40 ? ''#f59e0b'' : ''#ef4444'';
  const label = score >= 70 ? ''MATCH READY'' : score >= 40 ? ''BUILDING'' : ''EARLY DAYS'';

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="readiness-ring">
          {/* Background ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#1a3460"
            strokeWidth={strokeWidth}
          />
          {/* Progress ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: ''stroke-dashoffset 1s ease-out, stroke 0.3s'' }}
            filter={`drop-shadow(0 0 6px ${color})`}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display font-black text-3xl text-white">{score}%</span>
          <span className="text-[9px] font-medium text-gray-400 uppercase tracking-wider">READY</span>
        </div>
      </div>
      {showLabel && (
        <div className="mt-1 text-xs font-display font-bold uppercase tracking-wider" style={{ color }}>
          {label}
        </div>
      )}
    </div>
  );
}

'@

Write-File 'frontend\src\components\dashboard\XPBar.tsx' @'
interface XPBarProps {
  level: number;
  current: number;
  needed: number;
  percent: number;
  totalXp: number;
}

export default function XPBar({ level, current, needed, percent, totalXp }: XPBarProps) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-electric-500/20 border border-electric-500/40 flex items-center justify-center">
            <span className="font-display font-black text-sm text-electric-400">{level}</span>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wider">Level</div>
            <div className="font-display font-bold text-white text-sm">{current.toLocaleString()} / {needed.toLocaleString()} XP</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-500">Total XP</div>
          <div className="font-display font-bold text-electric-400">{totalXp.toLocaleString()}</div>
        </div>
      </div>
      <div className="xp-bar">
        <div
          className="xp-bar-fill"
          style={{ width: `${percent}%` }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <div className="text-[10px] text-gray-500">Lv {level}</div>
        <div className="text-[10px] text-gray-500">Lv {level + 1}</div>
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\components\layout\Layout.tsx' @'
import { Outlet, NavLink, useNavigate } from ''react-router-dom'';
import {
  LayoutDashboard, CreditCard, User, Dumbbell, Trophy,
  Users, Activity, Heart, ClipboardList, FlaskConical,
  Settings, Watch, Zap, Menu, X, Bell
} from ''lucide-react'';
import { useState } from ''react'';
import { useAuthStore } from ''../../store/authStore'';

const navItems = [
  { to: ''/dashboard'', icon: LayoutDashboard, label: ''Home'' },
  { to: ''/player-card'', icon: CreditCard, label: ''Card'' },
  { to: ''/workout-planner'', icon: Dumbbell, label: ''Train'' },
  { to: ''/challenges'', icon: Trophy, label: ''Goals'' },
  { to: ''/leaderboards'', icon: Zap, label: ''Ranks'' },
];

const moreItems = [
  { to: ''/avatar'', icon: User, label: ''Avatar'' },
  { to: ''/workouts'', icon: Activity, label: ''History'' },
  { to: ''/health'', icon: Heart, label: ''Health'' },
  { to: ''/routine'', icon: ClipboardList, label: ''Routine'' },
  { to: ''/tests'', icon: FlaskConical, label: ''Tests'' },
  { to: ''/friends'', icon: Users, label: ''Friends'' },
  { to: ''/wearables'', icon: Watch, label: ''Wearables'' },
  { to: ''/settings'', icon: Settings, label: ''Settings'' },
];

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { logout, user } = useAuthStore();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-pitch-900 flex flex-col max-w-md mx-auto relative">
      {/* Top bar */}
      <div className="sticky top-0 z-40 bg-pitch-900/95 backdrop-blur border-b border-pitch-700 px-4 py-3 flex items-center justify-between">
        <div className="font-display font-black text-xl tracking-wider text-white">
          MATCH<span className="text-electric-400">FIT</span>
          <span className="text-xs text-gray-500 font-body font-normal ml-1">PRO</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(''/dashboard'')}
            className="relative p-2 rounded-lg bg-pitch-700 text-gray-400 hover:text-white transition-colors"
          >
            <Bell size={18} />
          </button>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="p-2 rounded-lg bg-pitch-700 text-gray-400 hover:text-white transition-colors"
          >
            {menuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {/* Slide-out menu */}
      {menuOpen && (
        <div className="fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMenuOpen(false)} />
          <div className="absolute right-0 top-0 h-full w-72 bg-pitch-800 border-l border-pitch-600 p-4 flex flex-col">
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="font-display font-bold text-white">{user?.profile?.displayName || user?.username}</div>
                <div className="text-xs text-gray-400">@{user?.username}</div>
              </div>
              <button onClick={() => setMenuOpen(false)} className="p-2 rounded-lg bg-pitch-700 text-gray-400">
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 space-y-1">
              {moreItems.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  onClick={() => setMenuOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm font-medium ${
                      isActive ? ''bg-electric-500/20 text-electric-400'' : ''text-gray-300 hover:bg-pitch-700 hover:text-white''
                    }`
                  }
                >
                  <Icon size={18} />
                  {label}
                </NavLink>
              ))}
            </div>
            <button
              onClick={() => { logout(); navigate(''/''); setMenuOpen(false); }}
              className="mt-4 w-full text-left px-3 py-2.5 rounded-lg text-red-400 hover:bg-red-400/10 transition-colors text-sm font-medium"
            >
              Sign Out
            </button>
          </div>
        </div>
      )}

      {/* Page content */}
      <main className="flex-1 pb-20 overflow-y-auto">
        <Outlet />
      </main>

      {/* Bottom nav */}
      <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-md bg-pitch-900/95 backdrop-blur border-t border-pitch-700 px-2 py-1 flex justify-around z-40">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `nav-item ${isActive ? ''active'' : ''''}`
            }
          >
            <Icon size={20} />
            <span className="text-[10px] font-medium">{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

'@

Write-File 'frontend\src\index.css' @'
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-pitch-900 text-white font-body;
    background-image: 
      radial-gradient(ellipse at 20% 50%, rgba(14,165,233,0.05) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 20%, rgba(167,139,250,0.05) 0%, transparent 50%);
    min-height: 100vh;
  }

  * {
    scrollbar-width: thin;
    scrollbar-color: #1a3460 #0a1628;
  }
}

@layer components {
  .card {
    @apply bg-pitch-800 border border-pitch-600 rounded-xl p-4;
  }

  .btn-primary {
    @apply bg-electric-500 hover:bg-electric-400 text-white font-semibold px-4 py-2.5 rounded-lg transition-all duration-200 active:scale-95;
  }

  .btn-secondary {
    @apply bg-pitch-700 hover:bg-pitch-600 border border-pitch-600 text-white font-medium px-4 py-2.5 rounded-lg transition-all duration-200 active:scale-95;
  }

  .btn-gold {
    @apply bg-gradient-to-r from-gold-500 to-gold-400 hover:from-gold-400 hover:to-gold-300 text-pitch-900 font-bold px-4 py-2.5 rounded-lg transition-all duration-200 active:scale-95;
  }

  .stat-badge {
    @apply flex flex-col items-center justify-center bg-pitch-700 rounded-lg p-2 text-center;
  }

  .xp-bar {
    @apply h-2 bg-pitch-700 rounded-full overflow-hidden;
  }

  .xp-bar-fill {
    @apply h-full bg-gradient-to-r from-electric-600 to-electric-400 rounded-full transition-all duration-1000;
  }

  .energy-green {
    @apply text-emerald-400 bg-emerald-400/10 border-emerald-400/30;
  }

  .energy-yellow {
    @apply text-yellow-400 bg-yellow-400/10 border-yellow-400/30;
  }

  .energy-red {
    @apply text-red-400 bg-red-400/10 border-red-400/30;
  }

  .nav-item {
    @apply flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg transition-all duration-200 cursor-pointer text-gray-500 hover:text-white;
  }

  .nav-item.active {
    @apply text-electric-400;
  }

  .input-field {
    @apply w-full bg-pitch-700 border border-pitch-600 text-white placeholder-gray-500 rounded-lg px-3 py-2.5 focus:outline-none focus:border-electric-500 transition-colors;
  }

  .section-title {
    @apply font-display text-2xl font-bold uppercase tracking-wide text-white;
  }

  .label {
    @apply text-xs text-gray-400 uppercase tracking-wider font-medium;
  }
}

/* Elite card animations */
.elite-card {
  background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460);
  animation: elite-pulse 3s ease-in-out infinite;
}

.elite-shine {
  background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%);
  background-size: 200% 100%;
  animation: shine 2s linear infinite;
}

@keyframes elite-pulse {
  0%, 100% { box-shadow: 0 0 20px rgba(167,139,250,0.4), 0 0 40px rgba(236,72,153,0.2); }
  50% { box-shadow: 0 0 40px rgba(167,139,250,0.8), 0 0 80px rgba(236,72,153,0.4); }
}

@keyframes shine {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.bronze-card { background: linear-gradient(135deg, #3d2314, #6b3a1f, #3d2314); }
.silver-card { background: linear-gradient(135deg, #1f2a3d, #334155, #1f2a3d); }
.gold-card { background: linear-gradient(135deg, #3d2e00, #78510f, #3d2e00); }
.rare-gold-card { background: linear-gradient(135deg, #2d1b00, #92400e, #b45309, #92400e, #2d1b00); }

.readiness-ring {
  transform: rotate(-90deg);
  transform-origin: center;
}

'@

Write-File 'frontend\src\lib\api.ts' @'
import axios from ''axios'';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || ''/api'',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(''token'');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem(''token'');
      window.location.href = ''/login'';
    }
    return Promise.reject(err);
  }
);

export default api;

'@

Write-File 'frontend\src\main.tsx' @'
import React from ''react'';
import ReactDOM from ''react-dom/client'';
import App from ''./App'';
import ''./index.css'';

ReactDOM.createRoot(document.getElementById(''root'')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

'@

Write-File 'frontend\src\pages\AvatarPage.tsx' @'
import { useEffect, useState } from ''react'';
import { Lock, Zap, Save } from ''lucide-react'';
import api from ''../lib/api'';
import PlayerCard from ''../components/card/PlayerCard'';

interface AvatarData {
  skinTone: string; hairStyle: string; hairColour: string; facialHair: string;
  kitColour: string; kitPattern: string; bootColour: string; bodyType: string;
  pose: string; headband: boolean; wristTape: boolean; gloves: boolean;
  captainArmband: boolean; glasses: boolean;
}

interface UnlockItem {
  key: string; label: string; type: string; value: string | boolean; xpRequired: number;
}

interface AvatarPageData {
  avatar: AvatarData;
  unlocks: UnlockItem[];
  unlockedKeys: string[];
  totalXp: number;
}

const SKIN_TONES = [
  { value: ''light'', label: ''Light'', color: ''#f5cba7'' },
  { value: ''medium_light'', label: ''Med Light'', color: ''#e8a87c'' },
  { value: ''medium'', label: ''Medium'', color: ''#c68642'' },
  { value: ''medium_dark'', label: ''Med Dark'', color: ''#8d5524'' },
  { value: ''dark'', label: ''Dark'', color: ''#4a2912'' },
];

const HAIR_STYLES = [''short'', ''long'', ''curly'', ''fade'', ''bald''];
const BASE_HAIR_COLOURS = [''brown'', ''black'', ''blonde'', ''red'', ''grey''];
const BASE_KIT_COLOURS = [''red'', ''blue'', ''green'', ''black'', ''white'', ''yellow'', ''purple'', ''orange''];
const BASE_KIT_PATTERNS = [''plain'', ''stripes'', ''halves''];
const BASE_BOOT_COLOURS = [''black'', ''white'', ''red'', ''blue'', ''green'', ''yellow''];
const FACIAL_HAIR = [''none'', ''stubble'', ''beard'', ''moustache''];
const BODY_TYPES = [''athletic'', ''lean'', ''stocky'', ''muscular''];
const POSES = [''ready'', ''arms_crossed''];

function ColourSwatch({ color, label, selected, onClick, locked }: {
  color: string; label: string; selected: boolean; onClick: () => void; locked?: boolean;
}) {
  return (
    <button
      onClick={locked ? undefined : onClick}
      className={`relative flex flex-col items-center gap-1 group ${locked ? ''opacity-40 cursor-not-allowed'' : ''cursor-pointer''}`}
    >
      <div
        className={`w-10 h-10 rounded-full border-2 transition-all ${selected ? ''border-electric-400 scale-110'' : ''border-transparent hover:border-gray-500''}`}
        style={{ backgroundColor: color }}
      >
        {locked && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Lock size={10} className="text-white" />
          </div>
        )}
      </div>
      <span className="text-[9px] text-gray-500 leading-none">{label}</span>
    </button>
  );
}

function OptionButton({ label, selected, onClick, locked, xpRequired }: {
  label: string; selected: boolean; onClick: () => void; locked?: boolean; xpRequired?: number;
}) {
  return (
    <button
      onClick={locked ? undefined : onClick}
      className={`relative px-3 py-2 rounded-lg text-xs font-medium border transition-all ${
        locked ? ''opacity-40 cursor-not-allowed bg-pitch-800 border-pitch-600 text-gray-600''
        : selected ? ''bg-electric-500/20 border-electric-500 text-electric-400''
        : ''bg-pitch-700 border-pitch-600 text-gray-300 hover:border-gray-500''
      }`}
    >
      {locked && <Lock size={8} className="inline mr-1 opacity-60" />}
      {label}
      {locked && xpRequired && (
        <span className="ml-1 text-yellow-500 text-[9px]">
          <Zap size={7} className="inline" />{xpRequired.toLocaleString()}
        </span>
      )}
    </button>
  );
}

function ToggleButton({ label, value, onChange, locked, xpRequired }: {
  label: string; value: boolean; onChange: (v: boolean) => void; locked?: boolean; xpRequired?: number;
}) {
  return (
    <button
      onClick={locked ? undefined : () => onChange(!value)}
      className={`flex items-center justify-between w-full px-3 py-2.5 rounded-lg border transition-all ${
        locked ? ''opacity-40 cursor-not-allowed bg-pitch-800 border-pitch-600''
        : value ? ''bg-electric-500/20 border-electric-500''
        : ''bg-pitch-700 border-pitch-600 hover:border-gray-500''
      }`}
    >
      <span className={`text-sm font-medium ${value ? ''text-electric-400'' : ''text-gray-300''}`}>{label}</span>
      <div className="flex items-center gap-2">
        {locked && xpRequired && (
          <span className="text-yellow-500 text-xs flex items-center gap-0.5">
            <Lock size={10} /> <Zap size={9} />{xpRequired.toLocaleString()} XP
          </span>
        )}
        <div className={`w-10 h-5 rounded-full transition-colors ${value && !locked ? ''bg-electric-500'' : ''bg-pitch-600''}`}>
          <div className={`w-4 h-4 rounded-full bg-white mt-0.5 transition-transform ${value && !locked ? ''translate-x-5'' : ''translate-x-0.5''}`} />
        </div>
      </div>
    </button>
  );
}

export default function AvatarPage() {
  const [pageData, setPageData] = useState<AvatarPageData | null>(null);
  const [avatar, setAvatar] = useState<AvatarData | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(''/avatar'').then(r => {
      setPageData(r.data);
      setAvatar(r.data.avatar);
      setLoading(false);
    });
  }, []);

  const update = (key: keyof AvatarData, val: string | boolean) => {
    setAvatar(a => a ? { ...a, [key]: val } : a);
    setSaved(false);
  };

  const isUnlocked = (key: string) => pageData?.unlockedKeys.includes(key) ?? false;
  const getXpRequired = (key: string) => pageData?.unlocks.find(u => u.key === key)?.xpRequired ?? 0;

  const isKitColourLocked = (colour: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === ''kitColour'' && u.value === colour);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isKitPatternLocked = (pattern: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === ''kitPattern'' && u.value === pattern);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isBootColourLocked = (colour: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === ''bootColour'' && u.value === colour);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isPoseLocked = (pose: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === ''pose'' && u.value === pose);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isBodyTypeLocked = (bt: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === ''bodyType'' && u.value === bt);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isHairColourLocked = (colour: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === ''hairColour'' && u.value === colour);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isAccessoryLocked = (type: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === type && u.value === true);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const getAccessoryXp = (type: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === type && u.value === true);
    return unlock ? getXpRequired(unlock.key) : 0;
  };

  const handleSave = async () => {
    if (!avatar) return;
    setSaving(true);
    try {
      await api.put(''/avatar'', avatar);
      setSaved(true);
    } catch (err: any) {
      alert(err.response?.data?.error || ''Save failed'');
    } finally {
      setSaving(false);
    }
  };

  if (loading || !avatar) {
    return <div className="flex items-center justify-center min-h-screen"><div className="text-electric-400 font-display font-bold animate-pulse">LOADING...</div></div>;
  }

  const dummyCard = { overall: 45, tier: ''bronze'', pace: 45, shooting: 45, passing: 45, dribbling: 45, defending: 45, physical: 45, stamina: 45, recovery: 45, composure: 45 };
  const dummyProfile = { displayName: ''YOU'', position: ''CM'' };

  const allHairColours = [...BASE_HAIR_COLOURS,
    ...(pageData?.unlocks.filter(u => u.type === ''hairColour'').map(u => u.value as string) || [])
  ];
  const allKitColours = [...BASE_KIT_COLOURS,
    ...(pageData?.unlocks.filter(u => u.type === ''kitColour'').map(u => u.value as string) || [])
  ];
  const allKitPatterns = [...BASE_KIT_PATTERNS,
    ...(pageData?.unlocks.filter(u => u.type === ''kitPattern'').map(u => u.value as string) || [])
  ];
  const allBootColours = [...BASE_BOOT_COLOURS,
    ...(pageData?.unlocks.filter(u => u.type === ''bootColour'').map(u => u.value as string) || [])
  ];
  const allPoses = [...POSES,
    ...(pageData?.unlocks.filter(u => u.type === ''pose'').map(u => u.value as string) || [])
  ];
  const allBodyTypes = [...BODY_TYPES];

  return (
    <div className="px-4 py-4 pb-8 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="section-title">Avatar</h1>
        <button onClick={handleSave} disabled={saving} className={`flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg font-medium transition-all ${saved ? ''bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'' : ''btn-primary''}`}>
          <Save size={14} /> {saving ? ''Saving...'' : saved ? ''Saved!'' : ''Save''}
        </button>
      </div>

      {/* XP unlock progress */}
      <div className="card bg-gradient-to-r from-yellow-500/5 to-orange-500/5 border border-yellow-500/20">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs text-gray-400 mb-0.5">Your XP</div>
            <div className="font-display font-black text-xl text-yellow-400 flex items-center gap-1">
              <Zap size={16} /> {(pageData?.totalXp || 0).toLocaleString()}
            </div>
          </div>
          <div className="text-right text-xs text-gray-500">
            <div>Earn XP by completing</div>
            <div>workouts & challenges</div>
            <div>to unlock avatar items</div>
          </div>
        </div>
      </div>

      {/* Preview */}
      <div className="flex justify-center py-2">
        <PlayerCard card={dummyCard} profile={dummyProfile} avatar={avatar} compact />
      </div>

      {/* Skin Tone */}
      <div className="card">
        <h3 className="label mb-3">Skin Tone</h3>
        <div className="flex gap-4 flex-wrap">
          {SKIN_TONES.map(s => (
            <ColourSwatch key={s.value} color={s.color} label={s.label} selected={avatar.skinTone === s.value} onClick={() => update(''skinTone'', s.value)} />
          ))}
        </div>
      </div>

      {/* Hair */}
      <div className="card">
        <h3 className="label mb-3">Hair Style</h3>
        <div className="flex flex-wrap gap-2 mb-4">
          {HAIR_STYLES.map(h => (
            <OptionButton key={h} label={h.charAt(0).toUpperCase() + h.slice(1)} selected={avatar.hairStyle === h} onClick={() => update(''hairStyle'', h)} />
          ))}
        </div>
        <h3 className="label mb-3">Hair Colour</h3>
        <div className="flex flex-wrap gap-2">
          {allHairColours.map(c => {
            const locked = isHairColourLocked(c);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === ''hairColour'' && u.value === c)?.key || '''') : 0;
            return (
              <OptionButton key={c} label={c.charAt(0).toUpperCase() + c.slice(1)} selected={avatar.hairColour === c} onClick={() => update(''hairColour'', c)} locked={locked} xpRequired={xpReq} />
            );
          })}
        </div>
      </div>

      {/* Facial Hair */}
      <div className="card">
        <h3 className="label mb-3">Facial Hair</h3>
        <div className="flex flex-wrap gap-2">
          {FACIAL_HAIR.map(f => (
            <OptionButton key={f} label={f.charAt(0).toUpperCase() + f.slice(1)} selected={avatar.facialHair === f} onClick={() => update(''facialHair'', f)} />
          ))}
        </div>
      </div>

      {/* Kit */}
      <div className="card">
        <h3 className="label mb-3">Kit Colour</h3>
        <div className="flex flex-wrap gap-2 mb-4">
          {allKitColours.map(c => {
            const locked = isKitColourLocked(c);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === ''kitColour'' && u.value === c)?.key || '''') : 0;
            return <OptionButton key={c} label={c.replace(''_'', '' '')} selected={avatar.kitColour === c} onClick={() => update(''kitColour'', c)} locked={locked} xpRequired={xpReq} />;
          })}
        </div>
        <h3 className="label mb-3">Kit Pattern</h3>
        <div className="flex flex-wrap gap-2">
          {allKitPatterns.map(p => {
            const locked = isKitPatternLocked(p);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === ''kitPattern'' && u.value === p)?.key || '''') : 0;
            return <OptionButton key={p} label={p.charAt(0).toUpperCase() + p.slice(1)} selected={avatar.kitPattern === p} onClick={() => update(''kitPattern'', p)} locked={locked} xpRequired={xpReq} />;
          })}
        </div>
      </div>

      {/* Boots */}
      <div className="card">
        <h3 className="label mb-3">Boot Colour</h3>
        <div className="flex flex-wrap gap-2">
          {allBootColours.map(c => {
            const locked = isBootColourLocked(c);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === ''bootColour'' && u.value === c)?.key || '''') : 0;
            return <OptionButton key={c} label={c.charAt(0).toUpperCase() + c.slice(1)} selected={avatar.bootColour === c} onClick={() => update(''bootColour'', c)} locked={locked} xpRequired={xpReq} />;
          })}
        </div>
      </div>

      {/* Body & Pose */}
      <div className="card">
        <h3 className="label mb-3">Body Type</h3>
        <div className="flex flex-wrap gap-2 mb-4">
          {allBodyTypes.map(b => {
            const locked = isBodyTypeLocked(b);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === ''bodyType'' && u.value === b)?.key || '''') : 0;
            return <OptionButton key={b} label={b.charAt(0).toUpperCase() + b.slice(1)} selected={avatar.bodyType === b} onClick={() => update(''bodyType'', b)} locked={locked} xpRequired={xpReq} />;
          })}
        </div>
        <h3 className="label mb-3">Pose</h3>
        <div className="flex flex-wrap gap-2">
          {allPoses.map(p => {
            const locked = isPoseLocked(p);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === ''pose'' && u.value === p)?.key || '''') : 0;
            return <OptionButton key={p} label={p.replace(''_'', '' '')} selected={avatar.pose === p} onClick={() => update(''pose'', p)} locked={locked} xpRequired={xpReq} />;
          })}
        </div>
      </div>

      {/* Accessories */}
      <div className="card">
        <h3 className="label mb-3">Accessories</h3>
        <div className="space-y-2">
          <ToggleButton label="Headband" value={avatar.headband} onChange={v => update(''headband'', v)} locked={isAccessoryLocked(''headband'')} xpRequired={getAccessoryXp(''headband'')} />
          <ToggleButton label="Wrist Tape" value={avatar.wristTape} onChange={v => update(''wristTape'', v)} locked={isAccessoryLocked(''wristTape'')} xpRequired={getAccessoryXp(''wristTape'')} />
          <ToggleButton label="GK Gloves" value={avatar.gloves} onChange={v => update(''gloves'', v)} locked={isAccessoryLocked(''gloves'')} xpRequired={getAccessoryXp(''gloves'')} />
          <ToggleButton label="Captain Armband 🏆" value={avatar.captainArmband} onChange={v => update(''captainArmband'', v)} locked={isAccessoryLocked(''captainArmband'')} xpRequired={getAccessoryXp(''captainArmband'')} />
          <ToggleButton label="Shades 😎" value={avatar.glasses} onChange={v => update(''glasses'', v)} locked={isAccessoryLocked(''glasses'')} xpRequired={getAccessoryXp(''glasses'')} />
        </div>
        <p className="text-xs text-gray-600 mt-3 flex items-center gap-1">
          <Lock size={10} /> Items with lock icon require XP to unlock — keep grinding!
        </p>
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\ChallengesPage.tsx' @'
import { useEffect, useState } from ''react'';
import { CheckCircle, Circle, Zap, Calendar, Trophy } from ''lucide-react'';
import api from ''../lib/api'';

interface UserChallenge {
  id: string;
  isCompleted: boolean;
  progress: number;
  expiresAt: string;
  xpAwarded: number;
  challenge: {
    title: string;
    description: string;
    xpReward: number;
    target: number;
    unit: string;
    category: string;
    difficulty: string;
    type: string;
  };
}

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: ''text-emerald-400 bg-emerald-400/10'',
  medium: ''text-yellow-400 bg-yellow-400/10'',
  hard: ''text-red-400 bg-red-400/10'',
};

function ChallengeCard({ uc, onComplete }: { uc: UserChallenge; onComplete: (id: string) => void }) {
  const progressPercent = Math.min(100, (uc.progress / uc.challenge.target) * 100);
  const expiry = new Date(uc.expiresAt);
  const hoursLeft = Math.max(0, Math.round((expiry.getTime() - Date.now()) / 3600000));

  return (
    <div className={`card transition-all ${uc.isCompleted ? ''opacity-60'' : ''''}`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5">
          {uc.isCompleted
            ? <CheckCircle size={22} className="text-emerald-400" />
            : <Circle size={22} className="text-gray-600" />
          }
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-semibold text-white text-sm leading-tight">{uc.challenge.title}</h3>
            <div className="flex items-center gap-1 flex-shrink-0">
              <Zap size={12} className="text-yellow-400" />
              <span className="text-yellow-400 font-bold text-xs">{uc.challenge.xpReward}</span>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-0.5 mb-2">{uc.challenge.description}</p>

          {/* Progress bar */}
          {!uc.isCompleted && uc.challenge.target > 1 && (
            <div className="mb-2">
              <div className="flex justify-between text-xs text-gray-600 mb-1">
                <span>{uc.progress} / {uc.challenge.target} {uc.challenge.unit}</span>
                <span>{Math.round(progressPercent)}%</span>
              </div>
              <div className="h-1.5 bg-pitch-700 rounded-full overflow-hidden">
                <div className="h-full bg-electric-500 rounded-full transition-all" style={{ width: `${progressPercent}%` }} />
              </div>
            </div>
          )}

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${DIFFICULTY_COLORS[uc.challenge.difficulty] || ''text-gray-400''}`}>
                {uc.challenge.difficulty}
              </span>
              <span className="text-xs text-gray-600 flex items-center gap-1">
                <Calendar size={10} />
                {hoursLeft}h left
              </span>
            </div>
            {!uc.isCompleted && (
              <button
                onClick={() => onComplete(uc.id)}
                className="text-xs btn-primary px-3 py-1.5"
              >
                Mark Done
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ChallengesPage() {
  const [daily, setDaily] = useState<UserChallenge[]>([]);
  const [weekly, setWeekly] = useState<UserChallenge[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<''daily'' | ''weekly''>(''daily'');

  const load = async () => {
    const [d, w] = await Promise.all([api.get(''/challenges/daily''), api.get(''/challenges/weekly'')]);
    setDaily(d.data);
    setWeekly(w.data);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleComplete = async (id: string) => {
    try {
      await api.post(`/challenges/${id}/complete`);
      load();
    } catch (err: any) {
      alert(err.response?.data?.error || ''Could not complete challenge'');
    }
  };

  const challenges = tab === ''daily'' ? daily : weekly;
  const completed = challenges.filter(c => c.isCompleted).length;
  const totalXp = challenges.filter(c => c.isCompleted).reduce((sum, c) => sum + c.challenge.xpReward, 0);

  return (
    <div className="px-4 py-4 space-y-4">
      <div className="flex items-center gap-3">
        <Trophy size={24} className="text-yellow-400" />
        <h1 className="section-title">Challenges</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 bg-pitch-800 p-1 rounded-xl">
        {([''daily'', ''weekly''] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${tab === t ? ''bg-electric-500 text-white'' : ''text-gray-400''}`}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Progress summary */}
      <div className="card flex items-center justify-between">
        <div>
          <div className="text-2xl font-display font-black text-white">{completed}<span className="text-gray-500">/{challenges.length}</span></div>
          <div className="text-xs text-gray-400 uppercase tracking-wider">Completed</div>
        </div>
        <div className="text-right">
          <div className="flex items-center gap-1 justify-end">
            <Zap size={16} className="text-yellow-400" />
            <span className="font-display font-black text-xl text-yellow-400">{totalXp}</span>
          </div>
          <div className="text-xs text-gray-400 uppercase tracking-wider">XP Earned</div>
        </div>
        <div>
          <div className="w-16 h-16">
            <svg viewBox="0 0 36 36">
              <circle cx="18" cy="18" r="15" fill="none" stroke="#1a3460" strokeWidth="3" />
              <circle
                cx="18" cy="18" r="15" fill="none"
                stroke="#0ea5e9" strokeWidth="3" strokeLinecap="round"
                strokeDasharray={`${challenges.length ? (completed / challenges.length) * 94 : 0} 94`}
                strokeDashoffset="23.5"
              />
            </svg>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading challenges...</div>
      ) : challenges.length === 0 ? (
        <div className="text-center py-8 text-gray-500">No {tab} challenges yet</div>
      ) : (
        <div className="space-y-3">
          {/* Active first */}
          {challenges.filter(c => !c.isCompleted).map(uc => (
            <ChallengeCard key={uc.id} uc={uc} onComplete={handleComplete} />
          ))}
          {challenges.filter(c => c.isCompleted).length > 0 && (
            <div className="text-xs text-gray-600 uppercase tracking-wider text-center py-2">Completed</div>
          )}
          {challenges.filter(c => c.isCompleted).map(uc => (
            <ChallengeCard key={uc.id} uc={uc} onComplete={handleComplete} />
          ))}
        </div>
      )}
    </div>
  );
}

'@

Write-File 'frontend\src\pages\DashboardPage.tsx' @'
import { useEffect, useState } from ''react'';
import { useNavigate } from ''react-router-dom'';
import { Dumbbell, Zap, Battery, Plus, ChevronRight, CheckCircle, Circle, Watch } from ''lucide-react'';
import api from ''../lib/api'';
import { useAuthStore } from ''../store/authStore'';
import ReadinessRing from ''../components/dashboard/ReadinessRing'';
import XPBar from ''../components/dashboard/XPBar'';

interface DashboardData {
  profile: { displayName: string; position: string } | null;
  playerCard: { overall: number; tier: string; totalXp: number; xpLevel: number } | null;
  readiness: number;
  level: number;
  xpProgress: { current: number; needed: number; percent: number };
  totalXp: number;
  todaySummary: { steps?: number; sleepHours?: number; restingHr?: number; energyLevel?: number } | null;
  energyState: ''green'' | ''yellow'' | ''red'' | null;
  wearables: { provider: string; lastSync: string | null }[];
  notifications: { id: string; title: string; body: string }[];
  dailyChallenges: { id: string; isCompleted: boolean; challenge: { title: string; xpReward: number } }[];
}

const TIER_COLORS: Record<string, string> = {
  bronze: ''#cd7f32'',
  silver: ''#94a3b8'',
  common_gold: ''#f59e0b'',
  rare_gold: ''#fbbf24'',
  elite: ''#a78bfa'',
};

const ENERGY_CONFIG = {
  green: { label: ''High Energy'', color: ''text-emerald-400'', bg: ''bg-emerald-400/10 border-emerald-400/20'', dot: ''bg-emerald-400'' },
  yellow: { label: ''Moderate Energy'', color: ''text-yellow-400'', bg: ''bg-yellow-400/10 border-yellow-400/20'', dot: ''bg-yellow-400'' },
  red: { label: ''Low Energy'', color: ''text-red-400'', bg: ''bg-red-400/10 border-red-400/20'', dot: ''bg-red-400'' },
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const { user } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    api.get(''/dashboard'').then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const handleLogEnergy = async () => navigate(''/health'');
  const handleGenerateWorkout = () => navigate(''/workout-planner'');

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-electric-400 font-display font-bold text-xl animate-pulse">LOADING...</div>
      </div>
    );
  }

  const energyState = data?.energyState;
  const energyCfg = energyState ? ENERGY_CONFIG[energyState] : null;

  return (
    <div className="px-4 py-4 space-y-4">
      {/* Greeting */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-sm">Welcome back,</p>
          <h1 className="font-display font-black text-2xl text-white">
            {data?.profile?.displayName || user?.username}
          </h1>
        </div>
        <div
          className="px-3 py-1.5 rounded-xl border text-xs font-display font-bold uppercase tracking-wider"
          style={{ color: TIER_COLORS[data?.playerCard?.tier || ''bronze''], borderColor: TIER_COLORS[data?.playerCard?.tier || ''bronze''] + ''40'', backgroundColor: TIER_COLORS[data?.playerCard?.tier || ''bronze''] + ''10'' }}
        >
          {(data?.playerCard?.tier || ''bronze'').replace(''_'', '' '')}
        </div>
      </div>

      {/* Readiness + Card Overall */}
      <div className="card flex items-center justify-between">
        <ReadinessRing score={data?.readiness || 0} size={110} />
        <div className="flex-1 flex flex-col items-center">
          <div className="text-gray-400 text-xs uppercase tracking-wider mb-1">Card Overall</div>
          <div
            className="font-display font-black text-5xl"
            style={{ color: TIER_COLORS[data?.playerCard?.tier || ''bronze''] }}
          >
            {data?.playerCard?.overall || 45}
          </div>
          <div className="text-gray-500 text-xs mt-1">OVERALL RATING</div>
          <button onClick={() => navigate(''/player-card'')} className="mt-2 text-xs text-electric-400 flex items-center gap-1">
            View Card <ChevronRight size={12} />
          </button>
        </div>
      </div>

      {/* XP Bar */}
      <XPBar
        level={data?.level || 1}
        current={data?.xpProgress.current || 0}
        needed={data?.xpProgress.needed || 500}
        percent={data?.xpProgress.percent || 0}
        totalXp={data?.totalXp || 0}
      />

      {/* Energy State */}
      {energyCfg ? (
        <div className={`card border flex items-center gap-3 ${energyCfg.bg}`}>
          <div className={`w-3 h-3 rounded-full ${energyCfg.dot} animate-pulse`} />
          <div className="flex-1">
            <div className={`font-semibold text-sm ${energyCfg.color}`}>{energyCfg.label}</div>
            <div className="text-xs text-gray-500">Energy logged today</div>
          </div>
          <button onClick={handleGenerateWorkout} className="btn-primary text-xs px-3 py-1.5">Train</button>
        </div>
      ) : (
        <button onClick={handleLogEnergy} className="card border border-pitch-600 w-full flex items-center gap-3 hover:border-electric-500/50 transition-colors">
          <div className="w-10 h-10 rounded-xl bg-pitch-700 flex items-center justify-center">
            <Battery size={20} className="text-gray-400" />
          </div>
          <div className="flex-1 text-left">
            <div className="text-white font-semibold text-sm">Log Today''s Energy</div>
            <div className="text-xs text-gray-500">Earn 10 XP + unlock smart workout</div>
          </div>
          <Plus size={16} className="text-gray-500" />
        </button>
      )}

      {/* Today''s stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: ''Steps'', value: data?.todaySummary?.steps?.toLocaleString() || ''—'', icon: ''👟'' },
          { label: ''Sleep'', value: data?.todaySummary?.sleepHours ? `${data.todaySummary.sleepHours}h` : ''—'', icon: ''😴'' },
          { label: ''Resting HR'', value: data?.todaySummary?.restingHr ? `${data.todaySummary.restingHr}bpm` : ''—'', icon: ''❤️'' },
        ].map(({ label, value, icon }) => (
          <div key={label} className="card text-center">
            <div className="text-xl mb-1">{icon}</div>
            <div className="font-display font-bold text-white text-lg leading-none">{value}</div>
            <div className="text-[10px] text-gray-500 mt-1 uppercase tracking-wider">{label}</div>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 gap-3">
        <button onClick={handleGenerateWorkout} className="card flex flex-col items-center gap-2 py-4 hover:border-electric-500/50 transition-colors border border-pitch-600">
          <div className="w-10 h-10 rounded-xl bg-electric-500/10 flex items-center justify-center">
            <Dumbbell size={20} className="text-electric-400" />
          </div>
          <span className="text-sm font-semibold text-white">Generate Workout</span>
        </button>
        <button
          onClick={() => api.post(''/workouts/minimum-viable'').then(() => navigate(''/workouts''))}
          className="card flex flex-col items-center gap-2 py-4 hover:border-yellow-500/50 transition-colors border border-pitch-600"
        >
          <div className="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center">
            <Zap size={20} className="text-yellow-400" />
          </div>
          <span className="text-sm font-semibold text-white">Min. Session</span>
        </button>
      </div>

      {/* Daily Challenges */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <span className="font-display font-bold text-white uppercase tracking-wide text-sm">Daily Challenges</span>
          <button onClick={() => navigate(''/challenges'')} className="text-xs text-electric-400">View All</button>
        </div>
        <div className="space-y-2">
          {(data?.dailyChallenges || []).slice(0, 3).map((uc) => (
            <div key={uc.id} className={`flex items-center gap-3 p-2 rounded-lg transition-colors ${uc.isCompleted ? ''opacity-50'' : ''hover:bg-pitch-700''}`}>
              {uc.isCompleted
                ? <CheckCircle size={18} className="text-emerald-400 flex-shrink-0" />
                : <Circle size={18} className="text-gray-600 flex-shrink-0" />
              }
              <div className="flex-1 text-sm text-white">{uc.challenge.title}</div>
              <div className="flex items-center gap-1">
                <Zap size={10} className="text-yellow-400" />
                <span className="text-xs text-yellow-400 font-bold">{uc.challenge.xpReward}</span>
              </div>
            </div>
          ))}
          {(!data?.dailyChallenges || data.dailyChallenges.length === 0) && (
            <p className="text-gray-500 text-sm text-center py-2">No challenges yet — check back shortly!</p>
          )}
        </div>
      </div>

      {/* Wearable status */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <span className="font-display font-bold text-white uppercase tracking-wide text-sm">Connected Devices</span>
          <button onClick={() => navigate(''/wearables'')} className="text-xs text-electric-400">Manage</button>
        </div>
        {data?.wearables && data.wearables.length > 0 ? (
          <div className="space-y-2">
            {data.wearables.map(w => (
              <div key={w.provider} className="flex items-center gap-3">
                <Watch size={16} className="text-electric-400" />
                <span className="text-sm text-white capitalize">{w.provider}</span>
                <span className="text-xs text-gray-500 ml-auto">
                  {w.lastSync ? `Synced ${new Date(w.lastSync).toLocaleDateString()}` : ''Never synced''}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <button onClick={() => navigate(''/wearables'')} className="w-full text-center text-sm text-gray-500 hover:text-electric-400 transition-colors py-1">
            + Connect a wearable for automatic tracking
          </button>
        )}
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\FriendsPage.tsx' @'
import { useEffect, useState } from ''react'';
import { UserPlus, Users, Check, X, Trash2, Copy } from ''lucide-react'';
import api from ''../lib/api'';
import { useAuthStore } from ''../store/authStore'';

interface Friend { id: string; userId: string; username: string; displayName: string; overall: number; tier: string; friendCode: string; }
interface FriendRequest { id: string; sender: { username: string; profile?: { displayName: string } } }

export default function FriendsPage() {
  const [friends, setFriends] = useState<Friend[]>([]);
  const [requests, setRequests] = useState<FriendRequest[]>([]);
  const [search, setSearch] = useState('''');
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [msg, setMsg] = useState('''');
  const { user } = useAuthStore();

  const load = async () => {
    const [f, r] = await Promise.all([api.get(''/friends''), api.get(''/friends/requests'')]);
    setFriends(f.data); setRequests(r.data); setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const sendRequest = async () => {
    if (!search.trim()) return;
    setAdding(true); setMsg('''');
    try {
      await api.post(''/friends/request'', { usernameOrCode: search.trim() });
      setMsg(''Friend request sent!''); setSearch('''');
    } catch (err: any) { setMsg(err.response?.data?.error || ''Error''); }
    finally { setAdding(false); }
  };

  const accept = async (id: string) => { await api.post(''/friends/accept'', { requestId: id }); load(); };
  const decline = async (id: string) => { await api.post(''/friends/decline'', { requestId: id }); load(); };
  const remove = async (id: string) => { await api.delete(`/friends/${id}`); load(); };

  const TIER_COLORS: Record<string, string> = { bronze: ''#cd7f32'', silver: ''#94a3b8'', common_gold: ''#f59e0b'', rare_gold: ''#fbbf24'', elite: ''#a78bfa'' };

  return (
    <div className="px-4 py-4 space-y-5">
      <div className="flex items-center gap-3">
        <Users size={24} className="text-electric-400" />
        <h1 className="section-title">Friends</h1>
      </div>

      {/* Your friend code */}
      <div className="card bg-electric-500/5 border-electric-500/20">
        <div className="text-xs text-gray-400 mb-1">Your Friend Code</div>
        <div className="flex items-center gap-2">
          <code className="flex-1 font-mono text-electric-400 text-sm bg-pitch-800 px-3 py-2 rounded-lg truncate">{user?.friendCode}</code>
          <button onClick={() => navigator.clipboard.writeText(user?.friendCode || '''')} className="btn-secondary p-2"><Copy size={14} /></button>
        </div>
        <p className="text-xs text-gray-600 mt-1">Share this with friends to connect</p>
      </div>

      {/* Add friend */}
      <div className="card">
        <h3 className="label mb-3">Add Friend</h3>
        {msg && <div className={`mb-3 text-sm px-3 py-2 rounded-lg ${msg.includes(''sent'') ? ''bg-emerald-500/10 text-emerald-400'' : ''bg-red-500/10 text-red-400''}`}>{msg}</div>}
        <div className="flex gap-2">
          <input className="input-field flex-1" placeholder="Username or friend code" value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === ''Enter'' && sendRequest()} />
          <button onClick={sendRequest} disabled={adding} className="btn-primary px-4"><UserPlus size={18} /></button>
        </div>
      </div>

      {/* Pending requests */}
      {requests.length > 0 && (
        <div className="card">
          <h3 className="label mb-3">Pending Requests ({requests.length})</h3>
          <div className="space-y-2">
            {requests.map(r => (
              <div key={r.id} className="flex items-center gap-3">
                <div className="flex-1">
                  <div className="text-white font-medium text-sm">{r.sender.profile?.displayName || r.sender.username}</div>
                  <div className="text-xs text-gray-500">@{r.sender.username}</div>
                </div>
                <button onClick={() => accept(r.id)} className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30"><Check size={16} /></button>
                <button onClick={() => decline(r.id)} className="p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30"><X size={16} /></button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Friends list */}
      <div>
        <h3 className="label mb-3">Friends ({friends.length})</h3>
        {loading ? <div className="text-gray-500 text-sm text-center py-4">Loading...</div>
          : friends.length === 0 ? <div className="card text-center py-6 text-gray-500 text-sm">No friends yet — add someone!</div>
          : (
            <div className="space-y-2">
              {friends.map(f => (
                <div key={f.id} className="card flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center font-display font-black text-lg" style={{ backgroundColor: (TIER_COLORS[f.tier] || ''#cd7f32'') + ''20'', color: TIER_COLORS[f.tier] || ''#cd7f32'', border: `2px solid ${TIER_COLORS[f.tier] || ''#cd7f32''}40` }}>
                    {f.overall}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-white font-semibold text-sm">{f.displayName}</div>
                    <div className="text-xs text-gray-500">@{f.username}</div>
                  </div>
                  <button onClick={() => remove(f.userId)} className="p-2 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-400/10 transition-colors"><Trash2 size={14} /></button>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\HealthPage.tsx' @'
import { useEffect, useState } from ''react'';
import { Heart, TrendingUp, Plus } from ''lucide-react'';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from ''recharts'';
import api from ''../lib/api'';
import { format } from ''date-fns'';

interface DailySummary {
  date: string; steps?: number; sleepHours?: number; restingHr?: number;
  weightKg?: number; energyLevel?: number; activeMinutes?: number;
}

const CHARTS = [
  { key: ''steps'', label: ''Steps'', color: ''#0ea5e9'', unit: '''' },
  { key: ''sleepHours'', label: ''Sleep'', color: ''#8b5cf6'', unit: ''h'' },
  { key: ''restingHr'', label: ''Resting HR'', color: ''#ef4444'', unit: ''bpm'' },
  { key: ''weightKg'', label: ''Weight'', color: ''#f59e0b'', unit: ''kg'' },
  { key: ''energyLevel'', label: ''Energy'', color: ''#10b981'', unit: ''/5'' },
  { key: ''activeMinutes'', label: ''Active Mins'', color: ''#06b6d4'', unit: ''min'' },
];

export default function HealthPage() {
  const [summaries, setSummaries] = useState<DailySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeChart, setActiveChart] = useState(''steps'');
  const [logForm, setLogForm] = useState({ energyLevel: ''3'', sleepHours: '''', steps: '''', restingHr: '''', weightKg: '''' });
  const [logMsg, setLogMsg] = useState('''');

  useEffect(() => {
    api.get(''/health?days=30'').then(r => { setSummaries(r.data.summaries); setLoading(false); });
  }, []);

  const chart = CHARTS.find(c => c.key === activeChart)!;
  const chartData = summaries
    .filter(s => s[activeChart as keyof DailySummary] != null)
    .map(s => ({
      date: format(new Date(s.date), ''dd MMM''),
      value: s[activeChart as keyof DailySummary],
    }));

  const submitLog = async () => {
    setLogMsg('''');
    const payload: Record<string, number> = {};
    if (logForm.energyLevel) payload.energyLevel = Number(logForm.energyLevel);
    if (logForm.sleepHours) payload.sleepHours = Number(logForm.sleepHours);
    if (logForm.steps) payload.steps = Number(logForm.steps);
    if (logForm.restingHr) payload.restingHr = Number(logForm.restingHr);
    if (logForm.weightKg) payload.weightKg = Number(logForm.weightKg);
    try {
      await api.post(''/health/log-energy'', payload);
      setLogMsg(''Logged! +10 XP'');
      api.get(''/health?days=30'').then(r => setSummaries(r.data.summaries));
    } catch { setLogMsg(''Error logging''); }
  };

  // Quick averages
  const avg = (key: keyof DailySummary) => {
    const vals = summaries.map(s => s[key]).filter(v => v != null) as number[];
    return vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : ''—'';
  };

  return (
    <div className="px-4 py-4 space-y-5">
      <div className="flex items-center gap-3">
        <Heart size={24} className="text-red-400" />
        <h1 className="section-title">Health Data</h1>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: ''Avg Steps'', value: Number(avg(''steps'')).toLocaleString(), icon: ''👟'' },
          { label: ''Avg Sleep'', value: `${avg(''sleepHours'')}h`, icon: ''😴'' },
          { label: ''Avg HR'', value: `${avg(''restingHr'')}bpm`, icon: ''❤️'' },
        ].map(s => (
          <div key={s.label} className="card text-center">
            <div className="text-xl mb-1">{s.icon}</div>
            <div className="font-display font-bold text-white text-base">{s.value}</div>
            <div className="text-[10px] text-gray-500 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Chart selector */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {CHARTS.map(c => (
          <button key={c.key} onClick={() => setActiveChart(c.key)} className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${activeChart === c.key ? ''border-2 text-white'' : ''bg-pitch-700 border-pitch-600 text-gray-400''}`} style={activeChart === c.key ? { borderColor: c.color, backgroundColor: c.color + ''20'', color: c.color } : {}}>
            {c.label}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display font-bold text-white">{chart.label}</h3>
          <TrendingUp size={16} style={{ color: chart.color }} />
        </div>
        {loading || chartData.length === 0 ? (
          <div className="h-40 flex items-center justify-center text-gray-600 text-sm">
            {loading ? ''Loading...'' : ''No data yet — start logging!''}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a3460" />
              <XAxis dataKey="date" tick={{ fill: ''#6b7280'', fontSize: 10 }} tickLine={false} />
              <YAxis tick={{ fill: ''#6b7280'', fontSize: 10 }} tickLine={false} width={35} />
              <Tooltip contentStyle={{ backgroundColor: ''#0d1f3c'', border: ''1px solid #1a3460'', borderRadius: 8, color: ''#fff'', fontSize: 12 }} formatter={(v: number) => [`${v}${chart.unit}`, chart.label]} />
              <Line type="monotone" dataKey="value" stroke={chart.color} strokeWidth={2} dot={{ fill: chart.color, r: 3 }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Log form */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Plus size={14} /> Log Today''s Data</h3>
        {logMsg && <div className={`mb-3 text-sm px-3 py-2 rounded-lg ${logMsg.includes(''XP'') ? ''bg-emerald-500/10 text-emerald-400'' : ''bg-red-500/10 text-red-400''}`}>{logMsg}</div>}
        <div className="space-y-3">
          <div>
            <label className="label mb-2 block">Energy Level: {logForm.energyLevel}/5</label>
            <input type="range" min={1} max={5} value={logForm.energyLevel} onChange={e => setLogForm(f => ({ ...f, energyLevel: e.target.value }))} className="w-full accent-electric-500" />
            <div className="flex justify-between text-xs text-gray-600 mt-1"><span>Low</span><span>High</span></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { key: ''sleepHours'', label: ''Sleep (hours)'', placeholder: ''7.5'' },
              { key: ''steps'', label: ''Steps'', placeholder: ''8500'' },
              { key: ''restingHr'', label: ''Resting HR'', placeholder: ''65'' },
              { key: ''weightKg'', label: ''Weight (kg)'', placeholder: ''75'' },
            ].map(f => (
              <div key={f.key}>
                <label className="label mb-1 block text-[10px]">{f.label}</label>
                <input type="number" className="input-field" placeholder={f.placeholder} value={logForm[f.key as keyof typeof logForm]} onChange={e => setLogForm(form => ({ ...form, [f.key]: e.target.value }))} />
              </div>
            ))}
          </div>
          <button onClick={submitLog} className="btn-primary w-full">Log Data (+10 XP)</button>
        </div>
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\LandingPage.tsx' @'
import { useNavigate } from ''react-router-dom'';
import { Zap, Trophy, Users, Activity, Shield, Star } from ''lucide-react'';

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-pitch-900 flex flex-col">
      {/* Hero */}
      <div className="relative overflow-hidden px-6 pt-16 pb-12 flex-1 flex flex-col justify-center">
        <div className="absolute inset-0 bg-gradient-to-br from-electric-600/10 via-transparent to-purple-600/10" />
        <div className="relative text-center">
          <div className="inline-block mb-4 px-3 py-1 bg-electric-500/10 border border-electric-500/30 rounded-full text-electric-400 text-xs font-medium uppercase tracking-wider">
            Football Fitness Gamification
          </div>
          <h1 className="font-display font-black text-6xl tracking-tight text-white mb-2">
            MATCH<span className="text-electric-400">FIT</span>
          </h1>
          <h2 className="font-display font-bold text-3xl text-gray-300 mb-6 tracking-wide">PRO</h2>
          <p className="text-gray-400 max-w-xs mx-auto mb-8 leading-relaxed">
            Level up your football fitness. Track readiness, earn XP, upgrade your player card, and compete with friends.
          </p>
          <div className="flex flex-col gap-3">
            <button onClick={() => navigate(''/register'')} className="btn-primary w-full text-lg py-3 font-display font-bold uppercase tracking-wide">
              Get Started Free
            </button>
            <button onClick={() => navigate(''/login'')} className="btn-secondary w-full">
              Sign In
            </button>
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="px-6 pb-12 space-y-4">
        {[
          { icon: Activity, title: ''Match Readiness %'', desc: ''Track exactly how ready you are for your next match or fitness goal'' },
          { icon: Star, title: ''Player Card'', desc: ''Earn XP and upgrade your football-style card from Bronze to Elite'' },
          { icon: Zap, title: ''XP & Challenges'', desc: ''Daily and weekly challenges to keep you grinding and improving'' },
          { icon: Trophy, title: ''Leaderboards'', desc: ''Compete with friends on XP, steps, workouts, and overall rating'' },
          { icon: Shield, title: ''Smart Workouts'', desc: ''AI-generated sessions adapted to your energy level and equipment'' },
          { icon: Users, title: ''Friends & Social'', desc: ''Add friends, compare player cards, and race up the leaderboard'' },
        ].map(({ icon: Icon, title, desc }) => (
          <div key={title} className="flex items-start gap-4 card">
            <div className="w-10 h-10 rounded-xl bg-electric-500/10 border border-electric-500/20 flex items-center justify-center flex-shrink-0">
              <Icon size={20} className="text-electric-400" />
            </div>
            <div>
              <div className="font-semibold text-white text-sm mb-0.5">{title}</div>
              <div className="text-gray-400 text-xs leading-relaxed">{desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\LeaderboardPage.tsx' @'
import { useEffect, useState } from ''react'';
import { Trophy, Zap, Star } from ''lucide-react'';
import api from ''../lib/api'';
import { useAuthStore } from ''../store/authStore'';

interface LeaderboardEntry {
  userId: string;
  displayName: string;
  username: string;
  weeklyXp: number;
  totalXp: number;
  overall: number;
  readiness: number;
  weeklySteps: number;
  weeklyWorkouts: number;
  currentStreak: number;
  isCurrentUser?: boolean;
}

const TIER_COLORS: Record<string, string> = {
  bronze: ''#cd7f32'', silver: ''#94a3b8'', common_gold: ''#f59e0b'',
  rare_gold: ''#fbbf24'', elite: ''#a78bfa'',
};

const TABS = [
  { key: ''weeklyXp'', label: ''Weekly XP'' },
  { key: ''totalXp'', label: ''Total XP'' },
  { key: ''overall'', label: ''Overall'' },
  { key: ''weeklyWorkouts'', label: ''Workouts'' },
];

export default function LeaderboardPage() {
  const [friends, setFriends] = useState<LeaderboardEntry[]>([]);
  const [global, setGlobal] = useState<LeaderboardEntry[]>([]);
  const [tab, setTab] = useState<''friends'' | ''global''>(''friends'');
  const [sortKey, setSortKey] = useState(''weeklyXp'');
  const [loading, setLoading] = useState(true);
  const { user } = useAuthStore();

  useEffect(() => {
    Promise.all([api.get(''/leaderboards/friends''), api.get(''/leaderboards/global'')])
      .then(([f, g]) => { setFriends(f.data); setGlobal(g.data); })
      .finally(() => setLoading(false));
  }, []);

  const data = tab === ''friends'' ? friends : global;
  const sorted = [...data].sort((a, b) => (b[sortKey as keyof LeaderboardEntry] as number) - (a[sortKey as keyof LeaderboardEntry] as number));

  const rankEmoji = (i: number) => i === 0 ? ''🥇'' : i === 1 ? ''🥈'' : i === 2 ? ''🥉'' : `${i + 1}`;

  return (
    <div className="px-4 py-4 space-y-4">
      <div className="flex items-center gap-3">
        <Trophy size={24} className="text-yellow-400" />
        <h1 className="section-title">Leaderboard</h1>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-2 bg-pitch-800 p-1 rounded-xl">
        {([''friends'', ''global''] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${tab === t ? ''bg-electric-500 text-white'' : ''text-gray-400''}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Sort tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setSortKey(t.key)} className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${sortKey === t.key ? ''bg-electric-500/20 border-electric-500 text-electric-400'' : ''bg-pitch-700 border-pitch-600 text-gray-400''}`}>
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : sorted.length === 0 ? (
        <div className="card text-center py-8">
          <p className="text-gray-400 text-sm">No data yet — add friends to compete!</p>
        </div>
      ) : (
        <div className="space-y-2">
          {sorted.map((entry, i) => {
            const isYou = entry.userId === user?.id || entry.isCurrentUser;
            const val = entry[sortKey as keyof LeaderboardEntry];
            return (
              <div key={entry.userId} className={`card flex items-center gap-3 transition-all ${isYou ? ''border-electric-500/50 bg-electric-500/5'' : ''''}`}>
                <div className="text-lg font-display font-black w-8 text-center flex-shrink-0">
                  {rankEmoji(i)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`font-semibold text-sm truncate ${isYou ? ''text-electric-400'' : ''text-white''}`}>
                      {entry.displayName}
                    </span>
                    {isYou && <span className="text-xs text-electric-400 bg-electric-400/10 px-1.5 py-0.5 rounded">You</span>}
                  </div>
                  <span className="text-xs text-gray-500">@{entry.username}</span>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="flex items-center gap-1 justify-end">
                    {sortKey === ''weeklyXp'' || sortKey === ''totalXp''
                      ? <><Zap size={12} className="text-yellow-400" /><span className="font-display font-bold text-white">{(val as number).toLocaleString()}</span></>
                      : sortKey === ''overall''
                      ? <><Star size={12} className="text-gold-400" /><span className="font-display font-bold text-white">{val}</span></>
                      : <span className="font-display font-bold text-white">{val}</span>
                    }
                  </div>
                  <div className="text-xs text-gray-600">{TABS.find(t => t.key === sortKey)?.label}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

'@

Write-File 'frontend\src\pages\LoginPage.tsx' @'
import { useState } from ''react'';
import { useNavigate, Link } from ''react-router-dom'';
import { useAuthStore } from ''../store/authStore'';
import { Eye, EyeOff, Zap } from ''lucide-react'';

export default function LoginPage() {
  const [email, setEmail] = useState('''');
  const [password, setPassword] = useState('''');
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState('''');
  const [loading, setLoading] = useState(false);
  const { login } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('''');
    setLoading(true);
    try {
      await login(email, password);
      navigate(''/dashboard'');
    } catch (err: any) {
      setError(err.response?.data?.error || ''Login failed'');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-pitch-900 flex flex-col justify-center px-6">
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 mb-4">
          <div className="w-10 h-10 rounded-xl bg-electric-500/20 border border-electric-500/30 flex items-center justify-center">
            <Zap size={20} className="text-electric-400" />
          </div>
        </div>
        <h1 className="font-display font-black text-4xl text-white tracking-wide">
          MATCH<span className="text-electric-400">FIT</span> PRO
        </h1>
        <p className="text-gray-400 mt-2 text-sm">Sign in to your account</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm">
            {error}
          </div>
        )}
        <div>
          <label className="label mb-1.5 block">Email</label>
          <input
            type="email"
            className="input-field"
            placeholder="you@example.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label mb-1.5 block">Password</label>
          <div className="relative">
            <input
              type={showPass ? ''text'' : ''password''}
              className="input-field pr-10"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
            />
            <button
              type="button"
              onClick={() => setShowPass(!showPass)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>
        <button type="submit" disabled={loading} className="btn-primary w-full py-3 font-display font-bold uppercase tracking-wide text-base mt-2 disabled:opacity-50">
          {loading ? ''Signing In...'' : ''Sign In''}
        </button>
      </form>

      <div className="mt-6 text-center">
        <p className="text-gray-500 text-sm">
          Don''t have an account?{'' ''}
          <Link to="/register" className="text-electric-400 hover:text-electric-300 font-medium">
            Sign Up
          </Link>
        </p>
      </div>

      <div className="mt-4 text-center">
        <p className="text-gray-600 text-xs">Demo: demo@matchfitpro.com / matchfit123</p>
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\OnboardingPage.tsx' @'
import { useState } from ''react'';
import { useNavigate } from ''react-router-dom'';
import { ChevronRight, ChevronLeft, Check } from ''lucide-react'';
import api from ''../lib/api'';
import { useAuthStore } from ''../store/authStore'';

const POSITIONS = [''GK'', ''CB'', ''FB/WB'', ''CDM'', ''CM'', ''CAM'', ''Winger'', ''ST'', ''Any''];
const FOOTBALL_LEVELS = [
  { value: ''complete_beginner'', label: ''Complete Beginner'' },
  { value: ''casual'', label: ''Casual'' },
  { value: ''5-a-side'', label: ''5-a-side'' },
  { value: ''sunday_league'', label: ''Sunday League'' },
  { value: ''club'', label: ''Club Level'' },
  { value: ''competitive'', label: ''Competitive'' },
];
const GOALS = [
  { value: ''get_match_fit'', label: ''Get Match Fit'' },
  { value: ''improve_stamina'', label: ''Improve Stamina'' },
  { value: ''improve_speed'', label: ''Improve Speed'' },
  { value: ''lose_weight'', label: ''Lose Weight'' },
  { value: ''gain_muscle'', label: ''Gain Muscle'' },
  { value: ''return_from_injury'', label: ''Return from Injury'' },
  { value: ''general_health'', label: ''General Health'' },
  { value: ''compete_with_friends'', label: ''Compete with Friends'' },
  { value: ''improve_football_skills'', label: ''Improve Football Skills'' },
];
const EQUIPMENT_OPTIONS = [
  ''none/bodyweight only'', ''walking pad'', ''treadmill'', ''exercise bike'', ''rowing machine'',
  ''cross trainer'', ''jump rope'', ''dumbbells'', ''kettlebells'', ''barbell'', ''squat rack'',
  ''bench'', ''resistance bands'', ''pull-up bar'', ''cable machine'', ''full gym access'',
  ''yoga mat'', ''foam roller'', ''massage gun'', ''cones'', ''agility ladder'', ''hurdles'',
  ''football'', ''rebound board'', ''goal/net'', ''weighted vest'', ''medicine ball'',
  ''heart rate monitor'', ''GPS tracker'',
];
const DIETARY_OPTIONS = [
  ''no preference'', ''high protein'', ''calorie deficit'', ''calorie surplus'', ''maintenance'',
  ''gluten-free'', ''dairy-free'', ''vegetarian'', ''vegan'', ''pescatarian'', ''halal'', ''kosher'',
  ''low sugar'', ''anti-inflammatory'', ''budget meals'', ''meal prep focused'', ''quick meals'',
];
const SUPPLEMENT_OPTIONS = [
  ''Vitamin D'', ''Magnesium Glycinate'', ''Omega-3'', ''Creatine'', ''Electrolytes'',
  ''Multivitamin'', ''Protein Powder'', ''Vitamin C'', ''Zinc'', ''Iron'',
];
const SUPPLEMENT_TIMINGS = [''morning'', ''lunchtime'', ''afternoon'', ''evening'', ''bedtime''];
const DAYS = [''Monday'', ''Tuesday'', ''Wednesday'', ''Thursday'', ''Friday'', ''Saturday'', ''Sunday''];

interface FormData {
  displayName: string;
  dateOfBirth: string;
  gender: string;
  heightCm: string;
  weightKg: string;
  country: string;
  timezone: string;
  units: ''metric'' | ''imperial'';
  mainGoal: string;
  targetDate: string;
  matchDate: string;
  fitnessLevel: number;
  footballLevel: string;
  position: string;
  fatigueSensitive: boolean;
  sleepDifficulty: boolean;
  injuryConcerns: string;
  energyBaseline: number;
  stressBaseline: number;
  preferredWorkoutDays: string[];
  preferredWorkoutTime: string;
  maxWorkoutDuration: number;
  preferredRestDays: string[];
  equipment: string[];
  dietaryPreferences: string[];
  supplements: { name: string; timing: string }[];
}

const STEPS = [
  ''About You'', ''Your Goal'', ''Health & Recovery'',
  ''Schedule'', ''Equipment'', ''Diet & Supplements''
];

function ToggleChip({ label, selected, onClick }: { label: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all border ${
        selected
          ? ''bg-electric-500/20 border-electric-500 text-electric-400''
          : ''bg-pitch-700 border-pitch-600 text-gray-400 hover:border-gray-500''
      }`}
    >
      {label}
    </button>
  );
}

function StarRating({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) {
  return (
    <div>
      <label className="label mb-2 block">{label}</label>
      <div className="flex gap-2">
        {[1, 2, 3, 4, 5].map(n => (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            className={`w-10 h-10 rounded-lg font-display font-bold text-lg transition-all ${
              n <= value ? ''bg-electric-500 text-white'' : ''bg-pitch-700 text-gray-500''
            }`}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { fetchMe } = useAuthStore();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('''');

  const [form, setForm] = useState<FormData>({
    displayName: '''',
    dateOfBirth: '''',
    gender: '''',
    heightCm: '''',
    weightKg: '''',
    country: '''',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    units: ''metric'',
    mainGoal: ''get_match_fit'',
    targetDate: '''',
    matchDate: '''',
    fitnessLevel: 3,
    footballLevel: ''casual'',
    position: ''Any'',
    fatigueSensitive: false,
    sleepDifficulty: false,
    injuryConcerns: '''',
    energyBaseline: 3,
    stressBaseline: 2,
    preferredWorkoutDays: [''Monday'', ''Wednesday'', ''Friday''],
    preferredWorkoutTime: ''morning'',
    maxWorkoutDuration: 45,
    preferredRestDays: [''Sunday''],
    equipment: [],
    dietaryPreferences: [''no preference''],
    supplements: [],
  });

  const update = (key: keyof FormData, val: unknown) => setForm(f => ({ ...f, [key]: val }));

  const toggleArr = (key: keyof FormData, val: string) => {
    const arr = form[key] as string[];
    update(key, arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]);
  };

  const addSupplement = (name: string) => {
    if (!form.supplements.find(s => s.name === name)) {
      update(''supplements'', [...form.supplements, { name, timing: ''morning'' }]);
    }
  };

  const updateSupplementTiming = (name: string, timing: string) => {
    update(''supplements'', form.supplements.map(s => s.name === name ? { ...s, timing } : s));
  };

  const removeSupplement = (name: string) => {
    update(''supplements'', form.supplements.filter(s => s.name !== name));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError('''');
    try {
      await api.post(''/onboarding'', {
        ...form,
        heightCm: form.heightCm ? parseFloat(form.heightCm) : undefined,
        weightKg: form.weightKg ? parseFloat(form.weightKg) : undefined,
      });
      await fetchMe();
      navigate(''/dashboard'');
    } catch (err: any) {
      setError(err.response?.data?.error || ''Something went wrong'');
    } finally {
      setLoading(false);
    }
  };

  const canContinue = () => {
    if (step === 0) return form.displayName.trim().length > 0;
    return true;
  };

  return (
    <div className="min-h-screen bg-pitch-900 flex flex-col max-w-md mx-auto">
      {/* Header */}
      <div className="px-4 pt-8 pb-4">
        <div className="font-display font-black text-2xl text-white mb-1">
          MATCH<span className="text-electric-400">FIT</span> PRO
        </div>
        <p className="text-gray-400 text-sm">Let''s set up your profile</p>
      </div>

      {/* Progress */}
      <div className="px-4 mb-6">
        <div className="flex items-center gap-1.5 mb-2">
          {STEPS.map((s, i) => (
            <div key={s} className={`flex-1 h-1 rounded-full transition-all ${i <= step ? ''bg-electric-500'' : ''bg-pitch-700''}`} />
          ))}
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400 font-medium">{STEPS[step]}</span>
          <span className="text-xs text-gray-600">{step + 1} / {STEPS.length}</span>
        </div>
      </div>

      {/* Steps */}
      <div className="flex-1 px-4 pb-4 overflow-y-auto">
        {error && <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm mb-4">{error}</div>}

        {/* Step 0: About You */}
        {step === 0 && (
          <div className="space-y-4">
            <div>
              <label className="label mb-1.5 block">Display Name *</label>
              <input className="input-field" placeholder="How should we call you?" value={form.displayName} onChange={e => update(''displayName'', e.target.value)} />
            </div>
            <div>
              <label className="label mb-1.5 block">Date of Birth</label>
              <input type="date" className="input-field" value={form.dateOfBirth} onChange={e => update(''dateOfBirth'', e.target.value)} />
            </div>
            <div>
              <label className="label mb-1.5 block">Gender (optional)</label>
              <div className="flex gap-2 flex-wrap">
                {[''Male'', ''Female'', ''Non-binary'', ''Prefer not to say''].map(g => (
                  <ToggleChip key={g} label={g} selected={form.gender === g} onClick={() => update(''gender'', g)} />
                ))}
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="label mb-1.5 block">Height (cm)</label>
                <input type="number" className="input-field" placeholder="178" value={form.heightCm} onChange={e => update(''heightCm'', e.target.value)} />
              </div>
              <div className="flex-1">
                <label className="label mb-1.5 block">Weight (kg)</label>
                <input type="number" className="input-field" placeholder="75" value={form.weightKg} onChange={e => update(''weightKg'', e.target.value)} />
              </div>
            </div>
            <div>
              <label className="label mb-1.5 block">Country</label>
              <input className="input-field" placeholder="United Kingdom" value={form.country} onChange={e => update(''country'', e.target.value)} />
            </div>
          </div>
        )}

        {/* Step 1: Your Goal */}
        {step === 1 && (
          <div className="space-y-5">
            <div>
              <label className="label mb-2 block">Main Goal</label>
              <div className="grid grid-cols-1 gap-2">
                {GOALS.map(g => (
                  <button
                    key={g.value}
                    type="button"
                    onClick={() => update(''mainGoal'', g.value)}
                    className={`w-full text-left px-4 py-3 rounded-xl border font-medium text-sm transition-all ${
                      form.mainGoal === g.value
                        ? ''bg-electric-500/20 border-electric-500 text-electric-400''
                        : ''bg-pitch-700 border-pitch-600 text-gray-300 hover:border-gray-500''
                    }`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-1.5 block">Target Date (optional)</label>
              <input type="date" className="input-field" value={form.targetDate} onChange={e => update(''targetDate'', e.target.value)} />
            </div>
            <div>
              <label className="label mb-1.5 block">Match Date (if applicable)</label>
              <input type="date" className="input-field" value={form.matchDate} onChange={e => update(''matchDate'', e.target.value)} />
            </div>
            <StarRating value={form.fitnessLevel} onChange={v => update(''fitnessLevel'', v)} label="Current Fitness Level (1-5)" />
            <div>
              <label className="label mb-2 block">Football Level</label>
              <div className="grid grid-cols-2 gap-2">
                {FOOTBALL_LEVELS.map(l => (
                  <ToggleChip key={l.value} label={l.label} selected={form.footballLevel === l.value} onClick={() => update(''footballLevel'', l.value)} />
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Preferred Position</label>
              <div className="flex flex-wrap gap-2">
                {POSITIONS.map(p => (
                  <ToggleChip key={p} label={p} selected={form.position === p} onClick={() => update(''position'', p)} />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Health & Recovery */}
        {step === 2 && (
          <div className="space-y-5">
            <StarRating value={form.energyBaseline} onChange={v => update(''energyBaseline'', v)} label="Typical Energy Level (1=Low, 5=High)" />
            <StarRating value={form.stressBaseline} onChange={v => update(''stressBaseline'', v)} label="Typical Stress Level (1=Low, 5=High)" />
            <div>
              <label className="label mb-2 block">Fatigue Sensitive?</label>
              <p className="text-xs text-gray-500 mb-2">Do you crash hard after intense effort or poor sleep?</p>
              <div className="flex gap-3">
                <ToggleChip label="Yes" selected={form.fatigueSensitive} onClick={() => update(''fatigueSensitive'', true)} />
                <ToggleChip label="No" selected={!form.fatigueSensitive} onClick={() => update(''fatigueSensitive'', false)} />
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Sleep Difficulties?</label>
              <div className="flex gap-3">
                <ToggleChip label="Yes" selected={form.sleepDifficulty} onClick={() => update(''sleepDifficulty'', true)} />
                <ToggleChip label="No" selected={!form.sleepDifficulty} onClick={() => update(''sleepDifficulty'', false)} />
              </div>
            </div>
            <div>
              <label className="label mb-1.5 block">Injury Concerns (optional)</label>
              <textarea
                className="input-field resize-none"
                rows={3}
                placeholder="e.g. left knee, lower back..."
                value={form.injuryConcerns}
                onChange={e => update(''injuryConcerns'', e.target.value)}
              />
            </div>
          </div>
        )}

        {/* Step 3: Schedule */}
        {step === 3 && (
          <div className="space-y-5">
            <div>
              <label className="label mb-2 block">Preferred Workout Days</label>
              <div className="flex flex-wrap gap-2">
                {DAYS.map(d => (
                  <ToggleChip key={d} label={d.slice(0, 3)} selected={form.preferredWorkoutDays.includes(d)} onClick={() => toggleArr(''preferredWorkoutDays'', d)} />
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Preferred Rest Days</label>
              <div className="flex flex-wrap gap-2">
                {DAYS.map(d => (
                  <ToggleChip key={d} label={d.slice(0, 3)} selected={form.preferredRestDays.includes(d)} onClick={() => toggleArr(''preferredRestDays'', d)} />
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Preferred Workout Time</label>
              <div className="flex flex-wrap gap-2">
                {[''morning'', ''lunchtime'', ''afternoon'', ''evening''].map(t => (
                  <ToggleChip key={t} label={t.charAt(0).toUpperCase() + t.slice(1)} selected={form.preferredWorkoutTime === t} onClick={() => update(''preferredWorkoutTime'', t)} />
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Max Workout Duration: {form.maxWorkoutDuration} mins</label>
              <input type="range" min={10} max={120} step={5} value={form.maxWorkoutDuration} onChange={e => update(''maxWorkoutDuration'', Number(e.target.value))} className="w-full accent-electric-500" />
              <div className="flex justify-between text-xs text-gray-600 mt-1">
                <span>10 min</span><span>120 min</span>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Equipment */}
        {step === 4 && (
          <div className="space-y-3">
            <p className="text-sm text-gray-400">Select all equipment you have access to:</p>
            <div className="flex flex-wrap gap-2">
              {EQUIPMENT_OPTIONS.map(e => (
                <ToggleChip key={e} label={e} selected={form.equipment.includes(e)} onClick={() => toggleArr(''equipment'', e)} />
              ))}
            </div>
          </div>
        )}

        {/* Step 5: Diet & Supplements */}
        {step === 5 && (
          <div className="space-y-5">
            <div>
              <label className="label mb-2 block">Dietary Preferences</label>
              <div className="flex flex-wrap gap-2">
                {DIETARY_OPTIONS.map(d => (
                  <ToggleChip key={d} label={d} selected={form.dietaryPreferences.includes(d)} onClick={() => toggleArr(''dietaryPreferences'', d)} />
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Supplements & Reminders</label>
              <div className="flex flex-wrap gap-2 mb-3">
                {SUPPLEMENT_OPTIONS.map(s => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => form.supplements.find(x => x.name === s) ? removeSupplement(s) : addSupplement(s)}
                    className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                      form.supplements.find(x => x.name === s)
                        ? ''bg-electric-500/20 border-electric-500 text-electric-400''
                        : ''bg-pitch-700 border-pitch-600 text-gray-400''
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
              {form.supplements.length > 0 && (
                <div className="space-y-2">
                  {form.supplements.map(s => (
                    <div key={s.name} className="card flex items-center gap-3">
                      <div className="flex-1 text-sm text-white font-medium">{s.name}</div>
                      <select
                        className="bg-pitch-700 border border-pitch-600 text-gray-300 text-xs rounded-lg px-2 py-1"
                        value={s.timing}
                        onChange={e => updateSupplementTiming(s.name, e.target.value)}
                      >
                        {SUPPLEMENT_TIMINGS.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-xs text-gray-600 mt-3">⚠️ This app does not provide medical advice. Always consult a professional for medication decisions.</p>
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="px-4 py-4 border-t border-pitch-700 flex gap-3">
        {step > 0 && (
          <button type="button" onClick={() => setStep(s => s - 1)} className="btn-secondary flex items-center gap-1 px-4">
            <ChevronLeft size={16} /> Back
          </button>
        )}
        {step < STEPS.length - 1 ? (
          <button
            type="button"
            onClick={() => setStep(s => s + 1)}
            disabled={!canContinue()}
            className="btn-primary flex-1 flex items-center justify-center gap-1 disabled:opacity-40"
          >
            Continue <ChevronRight size={16} />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="btn-primary flex-1 flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? ''Setting up...'' : <><Check size={16} /> Let''s Go!</>}
          </button>
        )}
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\PlayerCardPage.tsx' @'
import { useEffect, useState } from ''react'';
import { useNavigate } from ''react-router-dom'';
import { RefreshCw, Pencil } from ''lucide-react'';
import api from ''../lib/api'';
import PlayerCard from ''../components/card/PlayerCard'';

interface CardPageData {
  card: {
    overall: number; tier: string; pace: number; shooting: number; passing: number;
    dribbling: number; defending: number; physical: number; stamina: number;
    recovery: number; composure: number; totalXp: number; xpLevel: number;
  };
  profile: { displayName: string; position: string };
  avatar: {
    skinTone: string; kitColour: string; kitPattern: string; hairStyle: string;
    hairColour: string; facialHair: string; bootColour: string; bodyType: string;
    pose: string; headband: boolean; wristTape: boolean; gloves: boolean;
    captainArmband: boolean; glasses: boolean;
  };
}

const TIER_LABELS: Record<string, string> = {
  bronze: ''Bronze'', silver: ''Silver'', common_gold: ''Gold'',
  rare_gold: ''Rare Gold'', elite: ''Elite ⚡'',
};

export default function PlayerCardPage() {
  const [data, setData] = useState<CardPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    api.get(''/player-card'').then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const recalculate = async () => {
    setRecalculating(true);
    await api.post(''/player-card/recalculate'');
    await load();
    setRecalculating(false);
  };

  if (loading || !data) {
    return <div className="flex items-center justify-center min-h-screen"><div className="text-electric-400 font-display font-bold animate-pulse">LOADING CARD...</div></div>;
  }

  const nextTier = { bronze: ''Silver (60+)'', silver: ''Gold (75+)'', common_gold: ''Rare Gold (85+)'', rare_gold: ''Elite (90+)'', elite: ''MAX TIER'' };
  const toNext = nextTier[data.card.tier as keyof typeof nextTier] || '''';

  return (
    <div className="px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="section-title">Player Card</h1>
        <div className="flex gap-2">
          <button onClick={() => navigate(''/avatar'')} className="btn-secondary flex items-center gap-1.5 text-sm px-3 py-2">
            <Pencil size={14} /> Edit Avatar
          </button>
          <button onClick={recalculate} disabled={recalculating} className="btn-secondary p-2">
            <RefreshCw size={16} className={recalculating ? ''animate-spin'' : ''''} />
          </button>
        </div>
      </div>

      {/* Card display */}
      <div className="flex justify-center py-4">
        <PlayerCard card={data.card} profile={data.profile} avatar={data.avatar} animated />
      </div>

      {/* Tier info */}
      <div className="card text-center">
        <div className="text-gray-400 text-xs uppercase tracking-wider mb-1">Current Tier</div>
        <div className="font-display font-black text-2xl text-white mb-1">{TIER_LABELS[data.card.tier] || data.card.tier}</div>
        {data.card.tier !== ''elite'' && (
          <div className="text-xs text-gray-500">Next: <span className="text-electric-400">{toNext}</span></div>
        )}
      </div>

      {/* Full stats breakdown */}
      <div className="card">
        <h2 className="font-display font-bold text-white uppercase tracking-wide text-sm mb-4">Stats Breakdown</h2>
        <div className="space-y-3">
          {[
            { label: ''Pace'', value: data.card.pace, desc: ''Sprint tests, speed workouts'' },
            { label: ''Shooting'', value: data.card.shooting, desc: ''Shooting practice sessions'' },
            { label: ''Passing'', value: data.card.passing, desc: ''Wall passing, passing drills'' },
            { label: ''Dribbling'', value: data.card.dribbling, desc: ''Agility, cone drills'' },
            { label: ''Defending'', value: data.card.defending, desc: ''Agility & strength work'' },
            { label: ''Physical'', value: data.card.physical, desc: ''Strength training'' },
            { label: ''Stamina'', value: data.card.stamina, desc: ''Cardio, steps, active mins'' },
            { label: ''Recovery'', value: data.card.recovery, desc: ''Sleep, rest sessions'' },
            { label: ''Composure'', value: data.card.composure, desc: ''Routine consistency, streaks'' },
          ].map(({ label, value, desc }) => {
            const color = value >= 80 ? ''#10b981'' : value >= 65 ? ''#f59e0b'' : ''#0ea5e9'';
            return (
              <div key={label}>
                <div className="flex items-center justify-between mb-1">
                  <div>
                    <span className="text-sm font-semibold text-white">{label}</span>
                    <span className="text-xs text-gray-600 ml-2">{desc}</span>
                  </div>
                  <span className="font-display font-bold text-white">{value}</span>
                </div>
                <div className="h-2 bg-pitch-700 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${value}%`, backgroundColor: color }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <p className="text-xs text-gray-600 text-center pb-4">Tap the card to flip and see all stats. Complete workouts, tests, and challenges to improve your rating.</p>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\RegisterPage.tsx' @'
import { useState } from ''react'';
import { useNavigate, Link } from ''react-router-dom'';
import { useAuthStore } from ''../store/authStore'';
import { Eye, EyeOff, Zap } from ''lucide-react'';

export default function RegisterPage() {
  const [email, setEmail] = useState('''');
  const [username, setUsername] = useState('''');
  const [password, setPassword] = useState('''');
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState('''');
  const [loading, setLoading] = useState(false);
  const { register } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('''');
    if (password.length < 8) { setError(''Password must be at least 8 characters''); return; }
    setLoading(true);
    try {
      await register(email, username, password);
      navigate(''/onboarding'');
    } catch (err: any) {
      setError(err.response?.data?.error || ''Registration failed'');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-pitch-900 flex flex-col justify-center px-6 py-12">
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 mb-4">
          <div className="w-10 h-10 rounded-xl bg-electric-500/20 border border-electric-500/30 flex items-center justify-center">
            <Zap size={20} className="text-electric-400" />
          </div>
        </div>
        <h1 className="font-display font-black text-4xl text-white tracking-wide">
          CREATE ACCOUNT
        </h1>
        <p className="text-gray-400 mt-2 text-sm">Start your MatchFit Pro journey</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm">
            {error}
          </div>
        )}
        <div>
          <label className="label mb-1.5 block">Email</label>
          <input type="email" className="input-field" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} required />
        </div>
        <div>
          <label className="label mb-1.5 block">Username</label>
          <input type="text" className="input-field" placeholder="coolplayer99" value={username} onChange={e => setUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''''))} required minLength={3} maxLength={30} />
          <p className="text-xs text-gray-600 mt-1">Letters, numbers, underscores only</p>
        </div>
        <div>
          <label className="label mb-1.5 block">Password</label>
          <div className="relative">
            <input type={showPass ? ''text'' : ''password''} className="input-field pr-10" placeholder="Min 8 characters" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} />
            <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
              {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>
        <button type="submit" disabled={loading} className="btn-primary w-full py-3 font-display font-bold uppercase tracking-wide text-base mt-2 disabled:opacity-50">
          {loading ? ''Creating Account...'' : ''Create Account''}
        </button>
      </form>

      <p className="text-xs text-gray-600 text-center mt-4 px-4">
        By signing up you agree to our terms. Health data is stored securely and never sold.
      </p>

      <div className="mt-4 text-center">
        <p className="text-gray-500 text-sm">
          Already have an account?{'' ''}
          <Link to="/login" className="text-electric-400 hover:text-electric-300 font-medium">Sign In</Link>
        </p>
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\RoutinePage.tsx' @'
import { useEffect, useState } from ''react'';
import { CheckCircle, Circle, ClipboardList, Zap } from ''lucide-react'';
import api from ''../lib/api'';

interface RoutineItem { id: string; label: string; time: string; enabled: boolean; }
interface RoutineCompletion { completedItems: string[]; xpAwarded: number; }

const TIME_GROUPS = [
  { key: ''morning'', label: ''🌅 Morning'', color: ''text-yellow-400'' },
  { key: ''afternoon'', label: ''☀️ Afternoon'', color: ''text-orange-400'' },
  { key: ''evening'', label: ''🌆 Evening'', color: ''text-purple-400'' },
  { key: ''night'', label: ''🌙 Night'', color: ''text-blue-400'' },
];

export default function RoutinePage() {
  const [items, setItems] = useState<RoutineItem[]>([]);
  const [completion, setCompletion] = useState<RoutineCompletion | null>(null);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState('''');

  const load = async () => {
    const { data } = await api.get(''/routine/today'');
    setItems((data.checklist?.items as RoutineItem[]) || []);
    setCompletion(data.completion);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const toggle = async (itemId: string) => {
    setCompleting(itemId);
    try {
      await api.post(''/routine/complete'', { itemId });
      load();
    } finally { setCompleting(''''); }
  };

  const completedItems = completion?.completedItems || [];
  const enabledItems = items.filter(i => i.enabled);
  const completedCount = enabledItems.filter(i => completedItems.includes(i.id)).length;
  const percent = enabledItems.length > 0 ? Math.round((completedCount / enabledItems.length) * 100) : 0;
  const today = new Date().toLocaleDateString(''en-GB'', { weekday: ''long'', day: ''numeric'', month: ''long'' });

  return (
    <div className="px-4 py-4 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ClipboardList size={24} className="text-electric-400" />
          <h1 className="section-title">Daily Routine</h1>
        </div>
      </div>

      <p className="text-gray-400 text-sm">{today}</p>

      {/* Progress ring */}
      <div className="card flex items-center gap-5">
        <div className="relative w-20 h-20 flex-shrink-0">
          <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
            <circle cx="18" cy="18" r="15" fill="none" stroke="#1a3460" strokeWidth="3" />
            <circle
              cx="18" cy="18" r="15" fill="none"
              stroke={percent === 100 ? ''#10b981'' : ''#0ea5e9''} strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={`${(percent / 100) * 94} 94`}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-display font-black text-lg text-white">{percent}%</span>
          </div>
        </div>
        <div>
          <div className="font-display font-bold text-white text-xl">{completedCount} / {enabledItems.length}</div>
          <div className="text-gray-400 text-sm">items complete</div>
          {completion?.xpAwarded ? (
            <div className="flex items-center gap-1 mt-1 text-yellow-400 text-sm font-semibold">
              <Zap size={14} /> +{completion.xpAwarded} XP earned today
            </div>
          ) : percent === 100 ? (
            <div className="text-emerald-400 text-sm mt-1 font-semibold">All done! 🎉</div>
          ) : (
            <div className="text-gray-500 text-xs mt-1">Complete all for +25 XP</div>
          )}
        </div>
      </div>

      {/* Checklist by time */}
      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading routine...</div>
      ) : (
        TIME_GROUPS.map(group => {
          const groupItems = items.filter(i => i.time === group.key && i.enabled);
          if (groupItems.length === 0) return null;
          return (
            <div key={group.key} className="card">
              <h3 className={`font-display font-bold uppercase tracking-wide text-sm mb-3 ${group.color}`}>{group.label}</h3>
              <div className="space-y-1">
                {groupItems.map(item => {
                  const done = completedItems.includes(item.id);
                  const isCompleting = completing === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => !done && toggle(item.id)}
                      disabled={done || isCompleting}
                      className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all text-left ${
                        done
                          ? ''bg-emerald-500/5 border border-emerald-500/20''
                          : ''hover:bg-pitch-700 border border-transparent''
                      }`}
                    >
                      {done
                        ? <CheckCircle size={22} className="text-emerald-400 flex-shrink-0" />
                        : <Circle size={22} className={`flex-shrink-0 ${isCompleting ? ''text-electric-400 animate-pulse'' : ''text-gray-600''}`} />
                      }
                      <span className={`text-sm font-medium ${done ? ''text-gray-500 line-through'' : ''text-white''}`}>
                        {item.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })
      )}

      <p className="text-xs text-gray-600 text-center pb-4">
        Customise your routine in Settings → Routine
      </p>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\SettingsPage.tsx' @'
import { useEffect, useState } from ''react'';
import { Settings, User, Bell, Shield, Trash2, ChevronRight, LogOut } from ''lucide-react'';
import { useNavigate } from ''react-router-dom'';
import api from ''../lib/api'';
import { useAuthStore } from ''../store/authStore'';

interface UserSettings {
  notificationsEnabled: boolean;
  emailNotifications: boolean;
  privacyPublic: boolean;
  maxWorkoutDuration: number;
  preferredWorkoutTime: string;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    api.get(''/settings'').then(r => setSettings(r.data.settings || {
      notificationsEnabled: true, emailNotifications: false,
      privacyPublic: false, maxWorkoutDuration: 60, preferredWorkoutTime: ''morning'',
    }));
  }, []);

  const save = async () => {
    setSaving(true);
    await api.put(''/settings'', settings);
    setSaved(true); setSaving(false);
    setTimeout(() => setSaved(false), 2000);
  };

  const deleteAccount = async () => {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    setDeleting(true);
    await api.delete(''/auth/account'');
    logout();
    navigate(''/'');
  };

  const update = (key: keyof UserSettings, val: boolean | number | string) => {
    setSettings(s => s ? { ...s, [key]: val } : s);
    setSaved(false);
  };

  if (!settings) return <div className="flex items-center justify-center min-h-screen"><div className="text-electric-400 animate-pulse font-display font-bold">LOADING...</div></div>;

  return (
    <div className="px-4 py-4 space-y-5 pb-10">
      <div className="flex items-center gap-3">
        <Settings size={24} className="text-electric-400" />
        <h1 className="section-title">Settings</h1>
      </div>

      {/* Account info */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><User size={14} /> Account</h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center py-2">
            <span className="text-gray-400 text-sm">Username</span>
            <span className="text-white font-medium text-sm">@{user?.username}</span>
          </div>
          <div className="flex justify-between items-center py-2">
            <span className="text-gray-400 text-sm">Friend Code</span>
            <code className="text-electric-400 text-xs font-mono">{user?.friendCode?.slice(0, 12)}...</code>
          </div>
          <button onClick={() => navigate(''/onboarding'')} className="w-full flex items-center justify-between py-2 text-sm text-gray-400 hover:text-white transition-colors">
            <span>Edit Profile & Goals</span>
            <ChevronRight size={16} />
          </button>
          <button onClick={() => navigate(''/wearables'')} className="w-full flex items-center justify-between py-2 text-sm text-gray-400 hover:text-white transition-colors">
            <span>Manage Wearables</span>
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Notifications */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Bell size={14} /> Notifications</h3>
        <div className="space-y-3">
          {[
            { key: ''notificationsEnabled'', label: ''In-app notifications'' },
            { key: ''emailNotifications'', label: ''Email notifications'' },
          ].map(({ key, label }) => (
            <div key={key} className="flex items-center justify-between">
              <span className="text-sm text-gray-300">{label}</span>
              <button
                onClick={() => update(key as keyof UserSettings, !settings[key as keyof UserSettings])}
                className={`w-12 h-6 rounded-full transition-colors ${settings[key as keyof UserSettings] ? ''bg-electric-500'' : ''bg-pitch-600''}`}
              >
                <div className={`w-5 h-5 rounded-full bg-white mt-0.5 transition-transform ${settings[key as keyof UserSettings] ? ''translate-x-6.5'' : ''translate-x-0.5''} mx-0.5`} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Workout prefs */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Settings size={14} /> Workout Preferences</h3>
        <div className="space-y-4">
          <div>
            <label className="label mb-2 block">Max Workout Duration: {settings.maxWorkoutDuration} mins</label>
            <input type="range" min={10} max={120} step={5} value={settings.maxWorkoutDuration} onChange={e => update(''maxWorkoutDuration'', Number(e.target.value))} className="w-full accent-electric-500" />
          </div>
          <div>
            <label className="label mb-2 block">Preferred Workout Time</label>
            <div className="flex gap-2 flex-wrap">
              {[''morning'', ''lunchtime'', ''afternoon'', ''evening''].map(t => (
                <button key={t} onClick={() => update(''preferredWorkoutTime'', t)} className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${settings.preferredWorkoutTime === t ? ''bg-electric-500/20 border-electric-500 text-electric-400'' : ''bg-pitch-700 border-pitch-600 text-gray-400''}`}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Privacy */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Shield size={14} /> Privacy</h3>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-300">Public Profile</div>
            <div className="text-xs text-gray-600">Allow non-friends to see your card</div>
          </div>
          <button
            onClick={() => update(''privacyPublic'', !settings.privacyPublic)}
            className={`w-12 h-6 rounded-full transition-colors ${settings.privacyPublic ? ''bg-electric-500'' : ''bg-pitch-600''}`}
          >
            <div className={`w-5 h-5 rounded-full bg-white mt-0.5 transition-transform ${settings.privacyPublic ? ''translate-x-6'' : ''translate-x-0.5''} mx-0.5`} />
          </button>
        </div>
        <p className="text-xs text-gray-600 mt-3">
          Health data is stored securely and never sold to third parties. You can delete your account and all data at any time.
        </p>
      </div>

      {/* Save button */}
      <button onClick={save} disabled={saving} className={`w-full py-3 font-display font-bold uppercase tracking-wide text-base rounded-lg transition-all ${saved ? ''bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'' : ''btn-primary''}`}>
        {saving ? ''Saving...'' : saved ? ''Saved!'' : ''Save Settings''}
      </button>

      {/* Sign out */}
      <button onClick={() => { logout(); navigate(''/''); }} className="w-full flex items-center justify-center gap-2 py-3 rounded-lg border border-pitch-600 text-gray-400 hover:text-white hover:border-gray-500 transition-colors text-sm font-medium">
        <LogOut size={16} /> Sign Out
      </button>

      {/* Delete account */}
      <div className="card border-red-500/20">
        <h3 className="label mb-2 text-red-400 flex items-center gap-2"><Trash2 size={14} /> Danger Zone</h3>
        <p className="text-xs text-gray-500 mb-3">Permanently delete your account and all data. This cannot be undone.</p>
        <button
          onClick={deleteAccount}
          disabled={deleting}
          className={`w-full py-2.5 rounded-lg border text-sm font-semibold transition-all ${
            confirmDelete
              ? ''bg-red-500 border-red-500 text-white''
              : ''border-red-500/40 text-red-400 hover:bg-red-500/10''
          }`}
        >
          {deleting ? ''Deleting...'' : confirmDelete ? ''⚠️ Confirm — Delete Everything'' : ''Delete Account''}
        </button>
        {confirmDelete && <p className="text-xs text-red-400 mt-2 text-center">Tap again to permanently delete</p>}
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\TestsPage.tsx' @'
import { useEffect, useState } from ''react'';
import { FlaskConical, TrendingUp, Plus, Trophy } from ''lucide-react'';
import api from ''../lib/api'';

interface TestResult { id: string; testType: string; value: number; unit?: string; notes?: string; testedAt: string; }

const TEST_TYPES = [
  { value: ''20m_sprint'', label: ''20m Sprint'', unit: ''seconds'', desc: ''Time your 20m sprint'', lower_is_better: true },
  { value: ''5_10_5_shuttle'', label: ''5-10-5 Shuttle'', unit: ''seconds'', desc: ''Agility shuttle run'', lower_is_better: true },
  { value: ''cone_drill'', label: ''Cone Drill'', unit: ''seconds'', desc: ''Agility cone course'', lower_is_better: true },
  { value: ''plank'', label: ''Plank Hold'', unit: ''seconds'', desc: ''Core endurance hold'', lower_is_better: false },
  { value: ''push_ups'', label: ''Push-Ups'', unit: ''reps'', desc: ''Max reps in 60 seconds'', lower_is_better: false },
  { value: ''squats'', label: ''Bodyweight Squats'', unit: ''reps'', desc: ''Max reps in 60 seconds'', lower_is_better: false },
  { value: ''wall_passing'', label: ''Wall Passing'', unit: ''passes/min'', desc: ''First touch passes per minute'', lower_is_better: false },
  { value: ''shooting'', label: ''Shooting Practice'', unit: ''goals/10'', desc: ''Goals out of 10 shots'', lower_is_better: false },
  { value: ''beep_test'', label: ''Beep Test Level'', unit: ''level'', desc: ''Estimated VO2max level'', lower_is_better: false },
  { value: ''rower_trial'', label: ''Rower Time Trial'', unit: ''seconds'', desc: ''2000m row time'', lower_is_better: true },
];

export default function TestsPage() {
  const [history, setHistory] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTest, setSelectedTest] = useState('''');
  const [value, setValue] = useState('''');
  const [notes, setNotes] = useState('''');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ xpAwarded: number; isImprovement: boolean } | null>(null);

  const load = () => api.get(''/tests/history'').then(r => { setHistory(r.data); setLoading(false); });
  useEffect(() => { load(); }, []);

  const submit = async () => {
    if (!selectedTest || !value) return;
    setSubmitting(true); setResult(null);
    const test = TEST_TYPES.find(t => t.value === selectedTest)!;
    try {
      const { data } = await api.post(''/tests'', { testType: selectedTest, value: Number(value), unit: test.unit, notes });
      setResult(data);
      setValue(''''); setNotes('''');
      load();
    } finally { setSubmitting(false); }
  };

  // Group history by test type, get latest per type
  const latestByType = TEST_TYPES.map(t => ({
    ...t,
    latest: history.filter(h => h.testType === t.value).sort((a, b) => new Date(b.testedAt).getTime() - new Date(a.testedAt).getTime())[0],
    history: history.filter(h => h.testType === t.value).slice(0, 5),
  }));

  const selectedTestInfo = TEST_TYPES.find(t => t.value === selectedTest);

  return (
    <div className="px-4 py-4 space-y-5 pb-8">
      <div className="flex items-center gap-3">
        <FlaskConical size={24} className="text-electric-400" />
        <h1 className="section-title">Fitness Tests</h1>
      </div>

      {/* Log a test */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Plus size={14} /> Log a Test</h3>

        {result && (
          <div className={`mb-4 p-3 rounded-xl border ${result.isImprovement ? ''bg-yellow-500/10 border-yellow-500/30'' : ''bg-emerald-500/10 border-emerald-500/30''}`}>
            <div className="flex items-center gap-2">
              {result.isImprovement && <Trophy size={16} className="text-yellow-400" />}
              <span className={`font-semibold text-sm ${result.isImprovement ? ''text-yellow-400'' : ''text-emerald-400''}`}>
                {result.isImprovement ? ''🏆 New Personal Best!'' : ''Test logged!''}
              </span>
            </div>
            <div className="text-xs text-gray-400 mt-1">+{result.xpAwarded} XP awarded</div>
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="label mb-2 block">Select Test</label>
            <select className="input-field" value={selectedTest} onChange={e => setSelectedTest(e.target.value)}>
              <option value="">Choose a test...</option>
              {TEST_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>

          {selectedTestInfo && (
            <div className="text-xs text-gray-500 bg-pitch-700 px-3 py-2 rounded-lg">
              {selectedTestInfo.desc} · Measured in {selectedTestInfo.unit}
              {selectedTestInfo.lower_is_better ? '' · Lower is better ↓'' : '' · Higher is better ↑''}
            </div>
          )}

          <div>
            <label className="label mb-1.5 block">Result {selectedTestInfo ? `(${selectedTestInfo.unit})` : ''''}</label>
            <input type="number" step="0.01" className="input-field" placeholder="Enter your result..." value={value} onChange={e => setValue(e.target.value)} />
          </div>

          <div>
            <label className="label mb-1.5 block">Notes (optional)</label>
            <input className="input-field" placeholder="Conditions, how you felt..." value={notes} onChange={e => setNotes(e.target.value)} />
          </div>

          <button onClick={submit} disabled={submitting || !selectedTest || !value} className="btn-primary w-full disabled:opacity-50">
            {submitting ? ''Logging...'' : ''Log Test Result''}
          </button>
        </div>
      </div>

      {/* Personal bests */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><TrendingUp size={14} /> Personal Bests</h3>
        {loading ? (
          <div className="text-gray-500 text-sm text-center py-4">Loading...</div>
        ) : (
          <div className="space-y-3">
            {latestByType.filter(t => t.latest).map(t => (
              <div key={t.value} className="flex items-center gap-3 py-2 border-b border-pitch-700 last:border-0">
                <div className="flex-1">
                  <div className="text-white font-medium text-sm">{t.label}</div>
                  <div className="text-xs text-gray-500">
                    {new Date(t.latest!.testedAt).toLocaleDateString(''en-GB'')}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-display font-bold text-electric-400">
                    {t.latest!.value} <span className="text-xs text-gray-500">{t.unit}</span>
                  </div>
                </div>
              </div>
            ))}
            {latestByType.filter(t => t.latest).length === 0 && (
              <p className="text-gray-500 text-sm text-center py-2">No tests logged yet. Log your first test above!</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\WearablesPage.tsx' @'
import { useEffect, useState } from ''react'';
import { Watch, RefreshCw, Unlink, Plus, Upload } from ''lucide-react'';
import api from ''../lib/api'';

interface WearableConnection { id: string; provider: string; isActive: boolean; lastSync: string | null; }

const PROVIDERS = [
  { key: ''fitbit'', label: ''Fitbit'', icon: ''⌚'', desc: ''OAuth connection available'', supported: true },
  { key: ''garmin'', label: ''Garmin'', icon: ''🏃'', desc: ''API partner approval required'', supported: false },
  { key: ''apple'', label: ''Apple Health'', icon: ''🍎'', desc: ''Requires iOS companion app'', supported: false },
  { key: ''google'', label: ''Google Fit'', icon: ''🔵'', desc: ''Health Connect integration'', supported: false },
];

export default function WearablesPage() {
  const [connections, setConnections] = useState<WearableConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [manualForm, setManualForm] = useState({ steps: '''', sleepHours: '''', restingHr: '''', weightKg: '''' });
  const [manualMsg, setManualMsg] = useState('''');
  const [syncing, setSyncing] = useState('''');

  const load = () => api.get(''/wearables'').then(r => { setConnections(r.data); setLoading(false); });
  useEffect(() => { load(); }, []);

  const connectFitbit = async () => {
    const { data } = await api.get(''/wearables/fitbit/connect'');
    if (data.url) window.location.href = data.url;
  };

  const sync = async (provider: string) => {
    setSyncing(provider);
    try {
      if (provider === ''fitbit'') await api.post(''/wearables/fitbit/sync'');
      await load();
    } finally { setSyncing(''''); }
  };

  const disconnect = async (provider: string) => {
    await api.delete(`/wearables/${provider}`);
    load();
  };

  const submitManual = async () => {
    setManualMsg('''');
    const payload: Record<string, number> = {};
    if (manualForm.steps) payload.steps = Number(manualForm.steps);
    if (manualForm.sleepHours) payload.sleepHours = Number(manualForm.sleepHours);
    if (manualForm.restingHr) payload.restingHr = Number(manualForm.restingHr);
    if (manualForm.weightKg) payload.weightKg = Number(manualForm.weightKg);
    try {
      await api.post(''/wearables/manual'', payload);
      setManualMsg(''Data logged! +10 XP'');
      setManualForm({ steps: '''', sleepHours: '''', restingHr: '''', weightKg: '''' });
    } catch { setManualMsg(''Error saving data''); }
  };

  return (
    <div className="px-4 py-4 space-y-5">
      <div className="flex items-center gap-3">
        <Watch size={24} className="text-electric-400" />
        <h1 className="section-title">Wearables</h1>
      </div>

      {/* Connected */}
      {connections.filter(c => c.isActive).length > 0 && (
        <div className="card">
          <h3 className="label mb-3">Connected</h3>
          <div className="space-y-3">
            {connections.filter(c => c.isActive).map(c => (
              <div key={c.id} className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-lg">
                  {PROVIDERS.find(p => p.key === c.provider)?.icon || ''⌚''}
                </div>
                <div className="flex-1">
                  <div className="text-white font-semibold text-sm capitalize">{c.provider}</div>
                  <div className="text-xs text-gray-500">{c.lastSync ? `Last sync: ${new Date(c.lastSync).toLocaleString()}` : ''Never synced''}</div>
                </div>
                <button onClick={() => sync(c.provider)} disabled={syncing === c.provider} className="p-2 rounded-lg bg-pitch-700 text-gray-400 hover:text-white">
                  <RefreshCw size={14} className={syncing === c.provider ? ''animate-spin'' : ''''} />
                </button>
                <button onClick={() => disconnect(c.provider)} className="p-2 rounded-lg bg-pitch-700 text-red-400 hover:bg-red-400/10">
                  <Unlink size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Available providers */}
      <div className="card">
        <h3 className="label mb-3">Connect a Device</h3>
        <div className="space-y-2">
          {PROVIDERS.map(p => {
            const connected = connections.find(c => c.provider === p.key && c.isActive);
            return (
              <div key={p.key} className={`flex items-center gap-3 p-3 rounded-xl border ${connected ? ''border-emerald-500/30 bg-emerald-500/5'' : ''border-pitch-600 bg-pitch-700''}`}>
                <div className="text-2xl">{p.icon}</div>
                <div className="flex-1">
                  <div className="text-white font-semibold text-sm">{p.label}</div>
                  <div className="text-xs text-gray-500">{p.desc}</div>
                </div>
                {connected ? (
                  <span className="text-xs text-emerald-400 font-medium">Connected</span>
                ) : p.key === ''fitbit'' ? (
                  <button onClick={connectFitbit} className="btn-primary text-xs px-3 py-1.5 flex items-center gap-1"><Plus size={12} /> Connect</button>
                ) : (
                  <span className="text-xs text-gray-600 bg-pitch-800 px-2 py-1 rounded">Coming soon</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Manual entry */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Plus size={14} /> Manual Entry</h3>
        {manualMsg && <div className={`mb-3 text-sm px-3 py-2 rounded-lg ${manualMsg.includes(''XP'') ? ''bg-emerald-500/10 text-emerald-400'' : ''bg-red-500/10 text-red-400''}`}>{manualMsg}</div>}
        <div className="grid grid-cols-2 gap-3 mb-3">
          {[
            { key: ''steps'', label: ''Steps'', placeholder: ''8500'' },
            { key: ''sleepHours'', label: ''Sleep (hours)'', placeholder: ''7.5'' },
            { key: ''restingHr'', label: ''Resting HR (bpm)'', placeholder: ''62'' },
            { key: ''weightKg'', label: ''Weight (kg)'', placeholder: ''75'' },
          ].map(f => (
            <div key={f.key}>
              <label className="label mb-1 block text-[10px]">{f.label}</label>
              <input type="number" className="input-field" placeholder={f.placeholder} value={manualForm[f.key as keyof typeof manualForm]} onChange={e => setManualForm(m => ({ ...m, [f.key]: e.target.value }))} />
            </div>
          ))}
        </div>
        <button onClick={submitManual} className="btn-primary w-full text-sm">Log Data (+10 XP)</button>
      </div>

      {/* CSV import */}
      <div className="card">
        <h3 className="label mb-2 flex items-center gap-2"><Upload size={14} /> CSV Import</h3>
        <p className="text-xs text-gray-500 mb-3">Import historical data from your wearable export</p>
        <button className="btn-secondary w-full text-sm opacity-60" disabled>CSV Import (Coming Soon)</button>
      </div>
    </div>
  );
}

'@

Write-File 'frontend\src\pages\WorkoutPlannerPage.tsx' @'
import { useState } from ''react'';
import { useNavigate } from ''react-router-dom'';
import { Dumbbell, Clock, Zap, ChevronRight, CheckCircle } from ''lucide-react'';
import api from ''../lib/api'';

const DURATIONS = [5, 10, 15, 20, 30, 45, 60];
const INTENSITIES = [
  { value: ''recovery'', label: ''Recovery'', desc: ''Very gentle, mobility focus'', color: ''text-blue-400'', bg: ''bg-blue-400/10 border-blue-400/30'' },
  { value: ''easy'', label: ''Easy'', desc: ''Light effort, building base'', color: ''text-emerald-400'', bg: ''bg-emerald-400/10 border-emerald-400/30'' },
  { value: ''moderate'', label: ''Moderate'', desc: ''Challenging but sustainable'', color: ''text-yellow-400'', bg: ''bg-yellow-400/10 border-yellow-400/30'' },
  { value: ''hard'', label: ''Hard'', desc: ''High intensity, max effort'', color: ''text-red-400'', bg: ''bg-red-400/10 border-red-400/30'' },
];
const GOALS = [
  { value: ''stamina'', label: ''Stamina'', icon: ''🏃'' },
  { value: ''strength'', label: ''Strength'', icon: ''💪'' },
  { value: ''speed'', label: ''Speed'', icon: ''⚡'' },
  { value: ''agility'', label: ''Agility'', icon: ''🏃‍♂️'' },
  { value: ''mobility'', label: ''Mobility'', icon: ''🧘'' },
  { value: ''recovery'', label: ''Recovery'', icon: ''😴'' },
  { value: ''match_simulation'', label: ''Match Sim'', icon: ''⚽'' },
  { value: ''football_skill'', label: ''Football Skills'', icon: ''🎯'' },
];
const ENERGY_STATES = [
  { value: ''green'', label: ''🟢 Green – Feeling great'', desc: ''Full sessions allowed'' },
  { value: ''yellow'', label: ''🟡 Yellow – Moderate energy'', desc: ''Easy/moderate only'' },
  { value: ''red'', label: ''🔴 Red – Low / tired'', desc: ''Recovery only'' },
];

interface GeneratedWorkout {
  id: string;
  title: string;
  category: string;
  difficulty: string;
  durationMins: number;
  xpReward: number;
  estimatedFatigue: number;
  warmup: { name: string; duration?: string; sets?: string; reps?: string; notes?: string }[];
  mainSection: { name: string; sets?: string; reps?: string; duration?: string; rest?: string; intensity?: string; notes?: string }[];
  cooldown: { name: string; duration?: string }[];
  statsImproved: string[];
}

function ExerciseList({ exercises, title }: { exercises: GeneratedWorkout[''warmup'']; title: string }) {
  return (
    <div className="card">
      <h3 className="label mb-3">{title}</h3>
      <div className="space-y-2">
        {exercises.map((ex, i) => (
          <div key={i} className="flex items-start gap-3 py-2 border-b border-pitch-700 last:border-0">
            <div className="w-6 h-6 rounded-full bg-electric-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-electric-400 text-xs font-bold">{i + 1}</span>
            </div>
            <div className="flex-1">
              <div className="text-white font-medium text-sm">{ex.name}</div>
              <div className="text-xs text-gray-500 mt-0.5">
                {[
                  ex.sets && `${ex.sets} sets`,
                  ex.reps && `${ex.reps} reps`,
                  ex.duration && ex.duration,
                  ex.rest && `Rest: ${ex.rest}`,
                  ex.intensity && ex.intensity,
                  ex.notes && ex.notes,
                ].filter(Boolean).join('' · '')}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function WorkoutPlannerPage() {
  const [duration, setDuration] = useState(30);
  const [intensity, setIntensity] = useState(''moderate'');
  const [goal, setGoal] = useState(''stamina'');
  const [energyState, setEnergyState] = useState<''green'' | ''yellow'' | ''red''>(''green'');
  const [generating, setGenerating] = useState(false);
  const [workout, setWorkout] = useState<GeneratedWorkout | null>(null);
  const [completing, setCompleting] = useState(false);
  const [rpe, setRpe] = useState(7);
  const [completed, setCompleted] = useState(false);
  const navigate = useNavigate();

  // Auto-downgrade intensity on red/yellow
  const effectiveIntensity = energyState === ''red'' ? ''recovery'' : energyState === ''yellow'' && intensity === ''hard'' ? ''moderate'' : intensity;

  const generate = async () => {
    setGenerating(true);
    setWorkout(null);
    setCompleted(false);
    try {
      const { data } = await api.post(''/workouts/generate'', {
        durationMins: duration,
        intensity: effectiveIntensity,
        goal: energyState === ''red'' ? ''recovery'' : goal,
        equipment: [],
        energyState,
      });
      setWorkout(data);
    } finally {
      setGenerating(false);
    }
  };

  const complete = async () => {
    if (!workout) return;
    setCompleting(true);
    try {
      await api.post(''/workouts/complete'', { generatedWorkoutId: workout.id, rpe });
      setCompleted(true);
    } finally {
      setCompleting(false);
    }
  };

  const fatigueLabel = ['''', ''Very Low'', ''Low'', ''Moderate'', ''High'', ''Very High''];

  return (
    <div className="px-4 py-4 space-y-5 pb-8">
      <h1 className="section-title">Workout Planner</h1>

      {!workout ? (
        <>
          {/* Energy State */}
          <div className="card">
            <h3 className="label mb-3">How are you feeling?</h3>
            <div className="space-y-2">
              {ENERGY_STATES.map(e => (
                <button
                  key={e.value}
                  onClick={() => setEnergyState(e.value as ''green'' | ''yellow'' | ''red'')}
                  className={`w-full text-left px-4 py-3 rounded-xl border transition-all ${energyState === e.value ? ''bg-electric-500/10 border-electric-500'' : ''bg-pitch-700 border-pitch-600''}`}
                >
                  <div className="font-medium text-sm text-white">{e.label}</div>
                  <div className="text-xs text-gray-500">{e.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {energyState !== ''red'' && (
            <>
              {/* Duration */}
              <div className="card">
                <h3 className="label mb-3">Duration</h3>
                <div className="flex gap-2 flex-wrap">
                  {DURATIONS.map(d => (
                    <button key={d} onClick={() => setDuration(d)} className={`px-4 py-2 rounded-lg font-display font-bold text-sm transition-all border ${duration === d ? ''bg-electric-500/20 border-electric-500 text-electric-400'' : ''bg-pitch-700 border-pitch-600 text-gray-300''}`}>
                      {d}m
                    </button>
                  ))}
                </div>
              </div>

              {/* Intensity */}
              <div className="card">
                <h3 className="label mb-3">Intensity {energyState === ''yellow'' && intensity === ''hard'' ? <span className="text-yellow-400 text-xs">(downgraded to Moderate)</span> : ''''}</h3>
                <div className="grid grid-cols-2 gap-2">
                  {INTENSITIES.map(i => (
                    <button key={i.value} onClick={() => setIntensity(i.value)} className={`text-left px-3 py-2.5 rounded-xl border transition-all ${intensity === i.value ? i.bg : ''bg-pitch-700 border-pitch-600''}`}>
                      <div className={`font-semibold text-sm ${intensity === i.value ? i.color : ''text-gray-300''}`}>{i.label}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{i.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Goal */}
              <div className="card">
                <h3 className="label mb-3">Session Goal</h3>
                <div className="grid grid-cols-2 gap-2">
                  {GOALS.map(g => (
                    <button key={g.value} onClick={() => setGoal(g.value)} className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border transition-all ${goal === g.value ? ''bg-electric-500/20 border-electric-500'' : ''bg-pitch-700 border-pitch-600''}`}>
                      <span className="text-lg">{g.icon}</span>
                      <span className={`text-sm font-medium ${goal === g.value ? ''text-electric-400'' : ''text-gray-300''}`}>{g.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          <button onClick={generate} disabled={generating} className="btn-primary w-full py-4 font-display font-bold uppercase tracking-wide text-base flex items-center justify-center gap-2 disabled:opacity-50">
            <Dumbbell size={20} />
            {generating ? ''Generating...'' : ''Generate Workout''}
          </button>
        </>
      ) : (
        <>
          {/* Workout display */}
          {completed ? (
            <div className="card text-center py-8">
              <CheckCircle size={48} className="text-emerald-400 mx-auto mb-3" />
              <div className="font-display font-black text-2xl text-white mb-1">WORKOUT COMPLETE!</div>
              <div className="text-gray-400 mb-4">XP awarded and card stats updated</div>
              <div className="flex gap-3 justify-center">
                <button onClick={() => { setWorkout(null); setCompleted(false); }} className="btn-secondary">New Workout</button>
                <button onClick={() => navigate(''/player-card'')} className="btn-primary">View Card</button>
              </div>
            </div>
          ) : (
            <>
              <div className="card bg-gradient-to-r from-electric-600/10 to-purple-600/10 border-electric-500/30">
                <div className="flex items-start justify-between mb-2">
                  <h2 className="font-display font-bold text-white text-lg">{workout.title}</h2>
                  <button onClick={() => setWorkout(null)} className="text-xs text-gray-500 hover:text-white">Change</button>
                </div>
                <div className="flex items-center gap-4 text-sm text-gray-400">
                  <span className="flex items-center gap-1"><Clock size={14} /> {workout.durationMins} mins</span>
                  <span className="flex items-center gap-1 text-yellow-400"><Zap size={14} /> {workout.xpReward} XP</span>
                  <span>Fatigue: {fatigueLabel[workout.estimatedFatigue]}</span>
                </div>
                {workout.statsImproved.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {workout.statsImproved.map(s => (
                      <span key={s} className="px-2 py-0.5 bg-electric-500/10 border border-electric-500/30 rounded text-electric-400 text-xs">+{s}</span>
                    ))}
                  </div>
                )}
              </div>

              <ExerciseList exercises={workout.warmup} title="🔥 Warm-Up" />
              <ExerciseList exercises={workout.mainSection} title="💪 Main Session" />
              <ExerciseList exercises={workout.cooldown} title="❄️ Cool-Down" />

              {/* RPE slider */}
              <div className="card">
                <h3 className="label mb-3">Rate of Perceived Effort (RPE): {rpe}/10</h3>
                <input type="range" min={1} max={10} value={rpe} onChange={e => setRpe(Number(e.target.value))} className="w-full accent-electric-500" />
                <div className="flex justify-between text-xs text-gray-600 mt-1">
                  <span>Easy (1)</span><span>Max effort (10)</span>
                </div>
              </div>

              <button onClick={complete} disabled={completing} className="btn-gold w-full py-4 font-display font-bold uppercase tracking-wide text-base flex items-center justify-center gap-2 disabled:opacity-50">
                <Zap size={20} />
                {completing ? ''Submitting...'' : `Submit for ${workout.xpReward} XP`}
              </button>
            </>
          )}
        </>
      )}
    </div>
  );
}

'@

Write-File 'frontend\src\pages\WorkoutsPage.tsx' @'
import { useEffect, useState } from ''react'';
import { Activity, Zap, Clock, ChevronDown, ChevronUp } from ''lucide-react'';
import api from ''../lib/api'';
import { format } from ''date-fns'';

interface Workout {
  id: string; title: string; category: string; difficulty: string;
  durationMins: number; rpe?: number; notes?: string; xpAwarded: number;
  statsImproved: string[]; completedAt: string;
}

const DIFFICULTY_COLORS: Record<string, string> = {
  recovery: ''text-blue-400'', easy: ''text-emerald-400'',
  moderate: ''text-yellow-400'', hard: ''text-red-400'',
};

export default function WorkoutsPage() {
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    api.get(''/workouts/history'').then(r => { setWorkouts(r.data); setLoading(false); });
  }, []);

  const totalXp = workouts.reduce((s, w) => s + w.xpAwarded, 0);
  const totalMins = workouts.reduce((s, w) => s + w.durationMins, 0);

  return (
    <div className="px-4 py-4 space-y-4">
      <div className="flex items-center gap-3">
        <Activity size={24} className="text-electric-400" />
        <h1 className="section-title">Workout History</h1>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: ''Total Sessions'', value: workouts.length.toString(), icon: ''🏋️'' },
          { label: ''Total XP'', value: totalXp.toLocaleString(), icon: ''⚡'' },
          { label: ''Total Time'', value: `${Math.round(totalMins / 60)}h`, icon: ''⏱️'' },
        ].map(s => (
          <div key={s.label} className="card text-center">
            <div className="text-xl mb-1">{s.icon}</div>
            <div className="font-display font-bold text-white">{s.value}</div>
            <div className="text-[10px] text-gray-500 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : workouts.length === 0 ? (
        <div className="card text-center py-8">
          <p className="text-gray-400 text-sm">No workouts yet — head to the Workout Planner to get started!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {workouts.map(w => (
            <div key={w.id} className="card">
              <button className="w-full text-left" onClick={() => setExpanded(expanded === w.id ? null : w.id)}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-white text-sm truncate">{w.title}</div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className={`text-xs font-medium ${DIFFICULTY_COLORS[w.difficulty] || ''text-gray-400''}`}>
                        {w.difficulty}
                      </span>
                      <span className="flex items-center gap-1 text-xs text-gray-500">
                        <Clock size={10} /> {w.durationMins}m
                      </span>
                      <span className="flex items-center gap-1 text-xs text-yellow-400 font-bold">
                        <Zap size={10} /> {w.xpAwarded}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs text-gray-600">
                      {format(new Date(w.completedAt), ''dd MMM'')}
                    </span>
                    {expanded === w.id ? <ChevronUp size={14} className="text-gray-500" /> : <ChevronDown size={14} className="text-gray-500" />}
                  </div>
                </div>
              </button>

              {expanded === w.id && (
                <div className="mt-3 pt-3 border-t border-pitch-700 space-y-2">
                  {w.rpe && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">RPE</span>
                      <span className="text-white font-medium">{w.rpe}/10</span>
                    </div>
                  )}
                  {w.statsImproved.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {(w.statsImproved as string[]).map((s: string) => (
                        <span key={s} className="px-2 py-0.5 bg-electric-500/10 border border-electric-500/20 rounded text-electric-400 text-xs">
                          +{s}
                        </span>
                      ))}
                    </div>
                  )}
                  {w.notes && <p className="text-xs text-gray-500 italic">{w.notes}</p>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

'@

Write-File 'frontend\src\store\authStore.ts' @'
import { create } from ''zustand'';
import api from ''../lib/api'';

interface User {
  id: string;
  email: string;
  username: string;
  friendCode: string;
  profile?: {
    displayName: string;
    onboardingDone: boolean;
    position: string;
    footballLevel: string;
  };
  playerCard?: {
    overall: number;
    tier: string;
    totalXp: number;
    xpLevel: number;
  };
}

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem(''token''),
  loading: false,

  login: async (email, password) => {
    const { data } = await api.post(''/auth/login'', { email, password });
    localStorage.setItem(''token'', data.token);
    set({ token: data.token });
    const me = await api.get(''/auth/me'');
    set({ user: me.data });
  },

  register: async (email, username, password) => {
    const { data } = await api.post(''/auth/register'', { email, username, password });
    localStorage.setItem(''token'', data.token);
    set({ token: data.token });
    const me = await api.get(''/auth/me'');
    set({ user: me.data });
  },

  logout: () => {
    localStorage.removeItem(''token'');
    set({ user: null, token: null });
  },

  fetchMe: async () => {
    try {
      set({ loading: true });
      const { data } = await api.get(''/auth/me'');
      set({ user: data, loading: false });
    } catch {
      localStorage.removeItem(''token'');
      set({ user: null, token: null, loading: false });
    }
  },
}));

'@

Write-File 'frontend\tailwind.config.js' @'
/** @type {import(''tailwindcss'').Config} */
export default {
  content: [''./index.html'', ''./src/**/*.{js,ts,jsx,tsx}''],
  theme: {
    extend: {
      colors: {
        pitch: { 900: ''#0a1628'', 800: ''#0d1f3c'', 700: ''#112347'', 600: ''#1a3460'' },
        electric: { 400: ''#38bdf8'', 500: ''#0ea5e9'', 600: ''#0284c7'' },
        gold: { 300: ''#fde68a'', 400: ''#fbbf24'', 500: ''#f59e0b'', 600: ''#d97706'' },
        elite: { from: ''#a78bfa'', to: ''#ec4899'' },
      },
      fontFamily: {
        display: [''Barlow Condensed'', ''sans-serif''],
        body: [''Inter'', ''sans-serif''],
      },
      animation: {
        ''card-shine'': ''shine 2s linear infinite'',
        ''pulse-glow'': ''pulse-glow 2s ease-in-out infinite'',
        ''level-up'': ''level-up 0.6s ease-out'',
        ''xp-fill'': ''xp-fill 1s ease-out forwards'',
      },
      keyframes: {
        shine: { ''0%'': { backgroundPosition: ''-200% 0'' }, ''100%'': { backgroundPosition: ''200% 0'' } },
        ''pulse-glow'': { ''0%,100%'': { boxShadow: ''0 0 20px rgba(167,139,250,0.3)'' }, ''50%'': { boxShadow: ''0 0 40px rgba(167,139,250,0.8)'' } },
        ''level-up'': { ''0%'': { transform: ''scale(0.5)'', opacity: ''0'' }, ''60%'': { transform: ''scale(1.2)'' }, ''100%'': { transform: ''scale(1)'', opacity: ''1'' } },
        ''xp-fill'': { ''0%'': { width: ''0%'' }, ''100%'': { width: ''var(--xp-percent)'' } },
      },
    },
  },
  plugins: [],
};

'@

Write-File 'frontend\tsconfig.json' @'
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}

'@

Write-File 'frontend\tsconfig.node.json' @'
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}

'@

Write-File 'frontend\vite.config.ts' @'
import { defineConfig } from ''vite'';
import react from ''@vitejs/plugin-react'';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      ''/api'': { target: ''http://localhost:3001'', changeOrigin: true },
    },
  },
  build: { outDir: ''dist'' },
});

'@

Write-File 'nixpacks.toml' @'
[phases.setup]
nixPkgs = ["nodejs_20"]

[phases.install]
cmds = ["npm install --prefix backend", "npm install --prefix frontend"]

[phases.build]
cmds = [
  "npm run build --prefix backend",
  "npm run build --prefix frontend",
  "cd backend && npx prisma generate"
]

[start]
cmd = "cd backend && npx prisma migrate deploy && node dist/index.js"

'@

Write-File 'package.json' @'
{
  "name": "matchfit-pro",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "concurrently \"npm run dev --workspace=backend\" \"npm run dev --workspace=frontend\"",
    "build": "npm run build --workspace=backend && npm run build --workspace=frontend",
    "start": "npm run start --workspace=backend",
    "db:migrate": "npm run db:migrate --workspace=backend",
    "db:seed": "npm run db:seed --workspace=backend"
  },
  "workspaces": ["backend", "frontend"],
  "devDependencies": {
    "concurrently": "^8.2.2"
  }
}

'@

Write-File 'railway.json' @'
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "cd backend && npx prisma migrate deploy && node dist/index.js",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}

'@

Write-Host 'All files created successfully!' -ForegroundColor Cyan