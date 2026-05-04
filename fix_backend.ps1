$base = "$env:USERPROFILE\Documents\matchpro-fit\backend"
function Write-File($path, $content) {
    $full = "$base\$path"
    $dir = Split-Path $full -Parent
    if (!(Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($full, $content, $utf8NoBom)
    Write-Host "Written: $path" -ForegroundColor Green
}

Write-File 'package.json' @'
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

Write-File 'prisma\schema.prisma' @'
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

Write-File 'prisma\seed.ts' @'
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

Write-File 'src\index.ts' @'
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

Write-File 'src\middleware\auth.ts' @'
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

Write-File 'src\middleware\errorHandler.ts' @'
import { Request, Response, NextFunction } from ''express'';

export const errorHandler = (err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error(err.stack);
  res.status(500).json({ error: ''Internal server error'', message: err.message });
};

'@

Write-File 'src\routes\auth.ts' @'
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

Write-File 'src\routes\avatar.ts' @'
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

Write-File 'src\routes\challenges.ts' @'
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

Write-File 'src\routes\dashboard.ts' @'
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

Write-File 'src\routes\friends.ts' @'
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

Write-File 'src\routes\health.ts' @'
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

Write-File 'src\routes\leaderboard.ts' @'
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

Write-File 'src\routes\notifications.ts' @'
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

Write-File 'src\routes\onboarding.ts' @'
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

Write-File 'src\routes\playerCard.ts' @'
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

Write-File 'src\routes\profile.ts' @'
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

Write-File 'src\routes\readiness.ts' @'
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

Write-File 'src\routes\routine.ts' @'
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

Write-File 'src\routes\settings.ts' @'
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

Write-File 'src\routes\tests.ts' @'
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

Write-File 'src\routes\wearables.ts' @'
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

Write-File 'src\routes\workout.ts' @'
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

Write-File 'src\routes\xp.ts' @'
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

Write-File 'src\services\challengeService.ts' @'
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

Write-File 'src\services\readinessService.ts' @'
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

Write-File 'src\services\workoutService.ts' @'
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

Write-File 'src\services\xpService.ts' @'
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

Write-File 'src\utils\prisma.ts' @'
import { PrismaClient } from ''@prisma/client'';

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };
export const prisma = globalForPrisma.prisma || new PrismaClient();
if (process.env.NODE_ENV !== ''production'') globalForPrisma.prisma = prisma;

'@

Write-File 'tsconfig.json' @'
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

Write-Host 'All backend files written!' -ForegroundColor Cyan