import bcrypt from 'bcryptjs';
import compression from 'compression';
import cors from 'cors';
import express, { NextFunction, Request, Response } from 'express';
import rateLimit from 'express-rate-limit';
import helmet from 'helmet';
import jwt from 'jsonwebtoken';
import { Prisma, User } from '@prisma/client';
import { z } from 'zod';
import { auth, AuthRequest, jwtSecret } from './middleware/auth';
import { errorHandler } from './middleware/errorHandler';
import { prisma } from './utils/prisma';

const app = express();
const port = Number(process.env.PORT || 8080);
const levels = [
  { min: 41, tier: 'Elite' },
  { min: 31, tier: 'Platinum' },
  { min: 21, tier: 'Gold' },
  { min: 11, tier: 'Silver' },
  { min: 1, tier: 'Bronze' },
];
const avatarCatalog = [
  { id: 'academy', name: 'Academy Spark', level: 1, glyph: 'AC' },
  { id: 'box-to-box', name: 'Box To Box', level: 3, glyph: 'BB' },
  { id: 'playmaker', name: 'Playmaker', level: 6, glyph: 'PM' },
  { id: 'finisher', name: 'Finisher', level: 10, glyph: 'FN' },
  { id: 'captain', name: 'Captain', level: 16, glyph: 'CP' },
  { id: 'elite-ace', name: 'Elite Ace', level: 25, glyph: 'EA' },
];
const avatarParts = {
  skin: [
    { id: 'warm', name: 'Warm', level: 1 },
    { id: 'deep', name: 'Deep', level: 1 },
    { id: 'light', name: 'Light', level: 1 },
    { id: 'olive', name: 'Olive', level: 2 },
    { id: 'golden', name: 'Golden', level: 5 },
  ],
  face: [
    { id: 'focused', name: 'Focused', level: 1 },
    { id: 'smile', name: 'Smiling', level: 2 },
    { id: 'grit', name: 'Match Grit', level: 4 },
    { id: 'wink', name: 'Cheeky Wink', level: 7 },
    { id: 'freckles', name: 'Freckles', level: 9 },
    { id: 'beard', name: 'Short Beard', level: 13 },
    { id: 'visor', name: 'Game Visor', level: 20 },
  ],
  hair: [
    { id: 'fade', name: 'Fade', level: 1 },
    { id: 'crop', name: 'Sharp Crop', level: 2 },
    { id: 'curls', name: 'Curls', level: 3 },
    { id: 'parted', name: 'Side Part', level: 5 },
    { id: 'bun', name: 'Top Bun', level: 7 },
    { id: 'braids', name: 'Braids', level: 11 },
    { id: 'mohawk', name: 'Match Mohawk', level: 15 },
    { id: 'silver', name: 'Silver Streak', level: 24 },
  ],
  kit: [
    { id: 'academy', name: 'Academy Blue', level: 1 },
    { id: 'home-red', name: 'Home Red', level: 2 },
    { id: 'mint', name: 'Recovery Mint', level: 4 },
    { id: 'night', name: 'Night Match', level: 6 },
    { id: 'storm', name: 'Storm Grey', level: 8 },
    { id: 'stripes', name: 'Club Stripes', level: 12 },
    { id: 'platinum', name: 'Platinum Pulse', level: 18 },
    { id: 'gold', name: 'Gold Trim', level: 23 },
    { id: 'elite', name: 'Elite Blackout', level: 32 },
  ],
  accessory: [
    { id: 'none', name: 'No Accessory', level: 1 },
    { id: 'tape', name: 'Wrist Tape', level: 2 },
    { id: 'headband', name: 'Headband', level: 3 },
    { id: 'gloves', name: 'Cold Match Gloves', level: 5 },
    { id: 'sleeves', name: 'Compression Sleeves', level: 8 },
    { id: 'captain', name: 'Captain Band', level: 11 },
    { id: 'medal', name: 'Winner Medal', level: 14 },
    { id: 'scarf', name: 'Tunnel Scarf', level: 19 },
    { id: 'armour', name: 'Elite Arm Plates', level: 28 },
  ],
  boots: [
    { id: 'black', name: 'Black Boots', level: 1 },
    { id: 'white', name: 'White Boots', level: 2 },
    { id: 'speed-blue', name: 'Speed Blue', level: 4 },
    { id: 'citrus', name: 'Citrus Studs', level: 6 },
    { id: 'pink', name: 'Flair Pink', level: 9 },
    { id: 'ice', name: 'Ice Boots', level: 13 },
    { id: 'gold', name: 'Gold Boots', level: 21 },
    { id: 'glow', name: 'Glow Boots', level: 30 },
  ],
  aura: [
    { id: 'none', name: 'No Aura', level: 1 },
    { id: 'speed', name: 'Speed Lines', level: 5 },
    { id: 'pulse', name: 'Blue Pulse', level: 10 },
    { id: 'flare', name: 'Goal Flare', level: 16 },
    { id: 'platinum', name: 'Platinum Halo', level: 24 },
    { id: 'elite', name: 'Elite Sparks', level: 36 },
  ],
  pose: [
    { id: 'ready', name: 'Ready', level: 1 },
    { id: 'hands-hips', name: 'Hands On Hips', level: 3 },
    { id: 'celebrate', name: 'Celebration', level: 6 },
    { id: 'point', name: 'Point To Badge', level: 10 },
    { id: 'strike', name: 'Strike', level: 15 },
    { id: 'shield', name: 'Defender Shield', level: 22 },
    { id: 'icon', name: 'Icon Stance', level: 35 },
  ],
} as const;
const defaultChallenges = [
  { title: 'Training Trio', description: 'Complete three workouts.', type: 'workouts', target: 3, xpReward: 180 },
  { title: '10K Engine', description: 'Log 10,000 steps in a health entry.', type: 'steps', target: 10000, xpReward: 140 },
  { title: 'Recovery Window', description: 'Log eight hours of sleep.', type: 'sleep', target: 8, xpReward: 120 },
  { title: 'Ready For Kickoff', description: 'Reach 75 match readiness.', type: 'readiness', target: 75, xpReward: 220 },
  { title: 'Testing Day', description: 'Log one fitness test block.', type: 'tests', target: 1, xpReward: 160 },
];

type SafeUser = Omit<User, 'passwordHash'>;
type AsyncRoute = (req: Request, res: Response, next: NextFunction) => Promise<unknown>;
const asyncRoute = (route: AsyncRoute) => (req: Request, res: Response, next: NextFunction) =>
  Promise.resolve(route(req, res, next)).catch(next);
const clamp = (value: number, min = 0, max = 100) => Math.min(max, Math.max(min, value));
const intensityFactor = (intensity: string) => ({ low: 1, medium: 1.35, high: 1.75 }[intensity] || 1);
const selectUser = {
  id: true,
  email: true,
  username: true,
  displayName: true,
  position: true,
  teamName: true,
  age: true,
  height: true,
  weight: true,
  xp: true,
  level: true,
  tier: true,
  avatarId: true,
  matchReadiness: true,
  createdAt: true,
  updatedAt: true,
};

function tierFor(level: number) {
  return levels.find((entry) => level >= entry.min)?.tier || 'Bronze';
}

function levelState(xp: number) {
  const level = Math.floor(xp / 500) + 1;
  return { level, tier: tierFor(level), nextLevelXp: level * 500, levelFloorXp: (level - 1) * 500 };
}

function authId(req: Request) {
  return (req as AuthRequest).userId;
}

function jsonValue(value: unknown): Prisma.InputJsonValue {
  return (Array.isArray(value) ? value : []) as Prisma.InputJsonValue;
}

function frontendUrl() {
  return (process.env.FRONTEND_URL || 'https://matchpro-fit.vercel.app').replace(/\/$/, '');
}

function googleHealthConfig() {
  const clientId = process.env.GOOGLE_HEALTH_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_HEALTH_CLIENT_SECRET;
  const redirectUri = process.env.GOOGLE_HEALTH_REDIRECT_URI || `${process.env.BACKEND_URL || 'https://matchpro-fit-production-db0c.up.railway.app'}/api/wearables/google-health/callback`;
  return { clientId, clientSecret, redirectUri, ready: Boolean(clientId && clientSecret && redirectUri) };
}

async function googleHealthToken(params: URLSearchParams) {
  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params,
  });
  const data = await response.json() as { access_token?: string; refresh_token?: string; expires_in?: number; error_description?: string; error?: string };
  if (!response.ok || !data.access_token) throw new Error(data.error_description || data.error || 'Google Health token exchange failed.');
  return data;
}

async function validGoogleHealthAccessToken(userId: string) {
  const wearable = await prisma.wearable.findUniqueOrThrow({ where: { userId } });
  if (!wearable.accessToken) throw new Error('Connect Google Health before syncing.');
  if (!wearable.tokenExpiresAt || wearable.tokenExpiresAt.getTime() > Date.now() + 60_000) return { wearable, accessToken: wearable.accessToken };
  if (!wearable.refreshToken) throw new Error('Google Health needs to be connected again.');
  const config = googleHealthConfig();
  const token = await googleHealthToken(new URLSearchParams({ client_id: config.clientId!, client_secret: config.clientSecret!, grant_type: 'refresh_token', refresh_token: wearable.refreshToken }));
  const updated = await prisma.wearable.update({
    where: { userId },
    data: {
      accessToken: token.access_token,
      refreshToken: token.refresh_token || wearable.refreshToken,
      tokenExpiresAt: new Date(Date.now() + Number(token.expires_in || 3600) * 1000),
    },
  });
  return { wearable: updated, accessToken: token.access_token! };
}

async function googleHealthGet<T>(path: string, accessToken: string) {
  const response = await fetch(`https://health.googleapis.com${path}`, { headers: { Authorization: `Bearer ${accessToken}`, Accept: 'application/json' } });
  const data = await response.json() as T;
  if (!response.ok) throw new Error('Google Health data sync failed.');
  return data;
}

async function googleHealthPost<T>(path: string, accessToken: string, body: unknown) {
  const response = await fetch(`https://health.googleapis.com${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}`, Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json() as T;
  if (!response.ok) throw new Error('Google Health data sync failed.');
  return data;
}

function todayCivilRange() {
  const now = new Date();
  const date = { year: now.getFullYear(), month: now.getMonth() + 1, day: now.getDate() };
  return {
    range: {
      start: { date, time: { hours: 0, minutes: 0, seconds: 0, nanos: 0 } },
      end: { date, time: { hours: 23, minutes: 59, seconds: 59, nanos: 0 } },
    },
    windowSizeDays: 1,
  };
}

function publicWearable<T extends { accessToken?: string | null; refreshToken?: string | null }>(wearable: T) {
  const { accessToken: _accessToken, refreshToken: _refreshToken, ...safe } = wearable;
  return safe;
}

async function applyWearableMetrics(userId: string, metrics: { steps?: number | null; heartRate?: number | null; sleepHours?: number | null }) {
  await prisma.healthMetric.create({ data: { userId, steps: metrics.steps, heartRate: metrics.heartRate, sleepHours: metrics.sleepHours } });
  await awardXp(userId, 20, 'wearable sync');
  if (metrics.steps) await applyChallengeProgress(userId, 'steps', metrics.steps, 'max');
  if (metrics.sleepHours) await applyChallengeProgress(userId, 'sleep', metrics.sleepHours, 'max');
  const readiness = await calculateReadiness(userId);
  await applyChallengeProgress(userId, 'readiness', readiness.score, 'max');
  return readiness;
}

const cardKeys = ['pace', 'shooting', 'passing', 'dribbling', 'defending', 'physical'] as const;

function overallOf(stats: Record<(typeof cardKeys)[number], number>) {
  return Math.round(cardKeys.reduce((sum, key) => sum + stats[key], 0) / cardKeys.length);
}

function clampStat(value: number) {
  return Math.round(clamp(value, 1, 99));
}

async function progressCard(userId: string, gains: Partial<Record<(typeof cardKeys)[number], number>>, reason: string) {
  const card = await prisma.playerCard.upsert({ where: { userId }, create: { userId }, update: {} });
  const stats = Object.fromEntries(cardKeys.map((key) => [key, clampStat(card[key] + (gains[key] || 0))])) as Record<(typeof cardKeys)[number], number>;
  const next = await prisma.playerCard.update({ where: { userId }, data: { ...stats, overall: overallOf(stats) } });
  const boosts = Object.entries(gains).filter(([, value]) => value).map(([key, value]) => `${key} +${value}`).join(', ');
  if (boosts) await prisma.notification.create({ data: { userId, type: 'card', message: `${reason} improved your card: ${boosts}.` } });
  return next;
}

function workoutGains(type: string, duration: number, intensity: string) {
  const gain = Math.max(1, Math.min(4, Math.round(duration * intensityFactor(intensity) / 35)));
  const byType: Record<string, Partial<Record<(typeof cardKeys)[number], number>>> = {
    running: { pace: gain, physical: gain },
    cycling: { pace: Math.max(1, gain - 1), physical: gain },
    swimming: { physical: gain, defending: Math.max(1, gain - 1) },
    gym: { physical: gain + 1, defending: gain },
    football: { pace: gain, passing: gain, dribbling: gain, shooting: Math.max(1, gain - 1) },
    other: { physical: gain },
  };
  return byType[type] || byType.other;
}

function testGains(test: { sprint30m?: number; run5kMinutes?: number; yoyoLevel?: number; plankSeconds?: number; jumpCm?: number }) {
  return {
    pace: (test.sprint30m && test.sprint30m <= 5 ? 2 : 1) + (test.run5kMinutes && test.run5kMinutes <= 25 ? 1 : 0),
    shooting: test.jumpCm && test.jumpCm >= 35 ? 1 : 0,
    passing: test.yoyoLevel && test.yoyoLevel >= 14 ? 1 : 0,
    dribbling: test.sprint30m && test.sprint30m <= 5.5 ? 1 : 0,
    defending: test.plankSeconds && test.plankSeconds >= 90 ? 1 : 0,
    physical: (test.yoyoLevel ? 1 : 0) + (test.plankSeconds && test.plankSeconds >= 60 ? 1 : 0),
  };
}

async function awardXp(userId: string, amount: number, reason: string) {
  const user = await prisma.user.findUniqueOrThrow({ where: { id: userId } });
  const xp = Math.max(0, user.xp + Math.round(amount));
  const state = levelState(xp);
  const updated = await prisma.user.update({
    where: { id: userId },
    data: { xp, level: state.level, tier: state.tier },
    select: selectUser,
  });
  if (state.level > user.level) {
    await prisma.notification.create({
      data: { userId, type: 'level', message: `Level ${state.level} reached. ${state.tier} form unlocked.` },
    });
  }
  return { user: updated, amount: Math.round(amount), reason, ...state };
}

async function calculateReadiness(userId: string) {
  const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const [workouts, health] = await Promise.all([
    prisma.workout.findMany({ where: { userId, completedAt: { gte: since } } }),
    prisma.healthMetric.findMany({ where: { userId }, orderBy: { date: 'desc' }, take: 7 }),
  ]);
  const workoutScore = clamp(workouts.reduce((total, item) => total + item.duration * intensityFactor(item.intensity), 0) / 3);
  const latestSleep = health.find((item) => item.sleepHours !== null)?.sleepHours || 0;
  const sleepScore = clamp((latestSleep / 8) * 100);
  const latestSteps = health.find((item) => item.steps !== null)?.steps || 0;
  const stepScore = clamp((latestSteps / 10000) * 100);
  const latestHydration = health.find((item) => item.hydration !== null)?.hydration || 0;
  const hydrationScore = clamp((latestHydration / 2.5) * 100);
  const score = Math.round(workoutScore * 0.4 + sleepScore * 0.25 + stepScore * 0.2 + hydrationScore * 0.15);
  await prisma.user.update({ where: { id: userId }, data: { matchReadiness: score } });
  return { score, factors: { workouts: Math.round(workoutScore), sleep: Math.round(sleepScore), steps: Math.round(stepScore), hydration: Math.round(hydrationScore) } };
}

async function ensureChallenges(userId: string) {
  await Promise.all(defaultChallenges.map(async (challenge) => {
    const exists = await prisma.challenge.findFirst({ where: { title: challenge.title } });
    if (!exists) await prisma.challenge.create({ data: challenge });
  }));
  const challenges = await prisma.challenge.findMany({ where: { isActive: true }, orderBy: { createdAt: 'asc' } });
  const assigned = await prisma.userChallenge.findMany({ where: { userId } });
  const assignedIds = new Set(assigned.map((item) => item.challengeId));
  await Promise.all(challenges.filter((item) => !assignedIds.has(item.id)).map((item) =>
    prisma.userChallenge.create({ data: { userId, challengeId: item.id } })));
}

async function applyChallengeProgress(userId: string, type: string, value: number, mode: 'add' | 'max' = 'add') {
  await ensureChallenges(userId);
  const assignments = await prisma.userChallenge.findMany({
    where: { userId, completed: false, challenge: { type, isActive: true } },
    include: { challenge: true },
  });
  await Promise.all(assignments.map(async (item) => {
    const progress = Math.min(item.challenge.target, mode === 'max' ? Math.max(item.progress, value) : item.progress + value);
    const complete = progress >= item.challenge.target;
    await prisma.userChallenge.update({
      where: { id: item.id },
      data: { progress, completed: complete, completedAt: complete ? new Date() : null },
    });
    if (complete) await awardXp(userId, item.challenge.xpReward, item.challenge.title);
  }));
}

async function recentStreak(userId: string) {
  const workouts = await prisma.workout.findMany({
    where: { userId },
    select: { completedAt: true },
    orderBy: { completedAt: 'desc' },
    take: 60,
  });
  const days = new Set(workouts.map((item) => item.completedAt.toISOString().slice(0, 10)));
  let streak = 0;
  const cursor = new Date();
  while (days.has(cursor.toISOString().slice(0, 10))) {
    streak += 1;
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return streak;
}

app.set('trust proxy', 1);
app.use(helmet());
app.use(compression());
app.use(cors({ origin: true, credentials: true }));
app.use(express.json({ limit: '2mb' }));
app.use('/api', rateLimit({ windowMs: 15 * 60 * 1000, limit: 300, standardHeaders: 'draft-7', legacyHeaders: false }));
app.get('/health', (_req, res) => res.json({ status: 'ok' }));

app.post('/api/auth/register', asyncRoute(async (req, res) => {
  const body = z.object({
    email: z.string().trim().email(),
    username: z.string().trim().toLowerCase().regex(/^[a-z0-9_]{3,30}$/),
    password: z.string().min(8).max(120),
  }).parse(req.body);
  const found = await prisma.user.findFirst({ where: { OR: [{ email: body.email.toLowerCase() }, { username: body.username }] } });
  if (found) return res.status(409).json({ error: 'That email or username is already in use.' });
  const user = await prisma.user.create({
    data: {
      email: body.email.toLowerCase(),
      username: body.username,
      passwordHash: await bcrypt.hash(body.password, 12),
      avatarId: avatarCatalog[0].id,
      playerCard: { create: {} },
      settings: { create: {} },
      avatarLoadout: { create: {} },
    },
    select: selectUser,
  });
  const token = jwt.sign({ userId: user.id }, jwtSecret(), { expiresIn: '14d' });
  return res.status(201).json({ token, user });
}));

app.post('/api/auth/login', asyncRoute(async (req, res) => {
  const body = z.object({ email: z.string().trim(), password: z.string().min(1) }).parse(req.body);
  const user = await prisma.user.findFirst({ where: { OR: [{ email: body.email.toLowerCase() }, { username: body.email.toLowerCase() }] } });
  if (!user || !(await bcrypt.compare(body.password, user.passwordHash))) return res.status(401).json({ error: 'Incorrect login details.' });
  const { passwordHash: _passwordHash, ...safeUser } = user;
  return res.json({ token: jwt.sign({ userId: user.id }, jwtSecret(), { expiresIn: '14d' }), user: safeUser });
}));

app.get('/api/auth/me', auth, asyncRoute(async (req, res) => {
  const user = await prisma.user.findUniqueOrThrow({ where: { id: authId(req) }, select: selectUser });
  res.json({ user, onboardingComplete: Boolean(user.position && user.age && user.height && user.weight) });
}));

app.get('/api/profile', auth, asyncRoute(async (req, res) => {
  res.json(await prisma.user.findUniqueOrThrow({ where: { id: authId(req) }, select: selectUser }));
}));
app.put('/api/profile', auth, asyncRoute(async (req, res) => {
  const body = z.object({
    displayName: z.string().trim().max(80).optional().nullable(),
    position: z.string().trim().max(40).optional().nullable(),
    teamName: z.string().trim().max(80).optional().nullable(),
    age: z.coerce.number().int().min(8).max(90).optional().nullable(),
    height: z.coerce.number().positive().max(260).optional().nullable(),
    weight: z.coerce.number().positive().max(400).optional().nullable(),
  }).parse(req.body);
  res.json(await prisma.user.update({ where: { id: authId(req) }, data: body, select: selectUser }));
}));

app.get('/api/onboarding', auth, asyncRoute(async (req, res) => {
  const profile = await prisma.user.findUniqueOrThrow({ where: { id: authId(req) }, select: selectUser });
  res.json({ profile, completed: Boolean(profile.position && profile.age && profile.height && profile.weight) });
}));
app.post('/api/onboarding', auth, asyncRoute(async (req, res) => {
  const body = z.object({
    displayName: z.string().trim().max(80).optional(),
    position: z.string().trim().min(1).max(40),
    teamName: z.string().trim().max(80).optional(),
    age: z.coerce.number().int().min(8).max(90),
    height: z.coerce.number().min(80).max(260),
    weight: z.coerce.number().min(25).max(400),
  }).parse(req.body);
  res.json(await prisma.user.update({ where: { id: authId(req) }, data: body, select: selectUser }));
}));

app.get('/api/avatar', auth, asyncRoute(async (req, res) => {
  const user = await prisma.user.findUniqueOrThrow({ where: { id: authId(req) }, select: { xp: true, level: true, avatarId: true } });
  const loadout = await prisma.avatarLoadout.upsert({ where: { userId: authId(req) }, create: { userId: authId(req) }, update: {} });
  res.json({
    level: user.level,
    xp: user.xp,
    equipped: user.avatarId || avatarCatalog[0].id,
    avatars: avatarCatalog.map((item) => ({ ...item, unlocked: user.level >= item.level })),
    loadout,
    parts: Object.fromEntries(Object.entries(avatarParts).map(([part, options]) => [part, options.map((item) => ({ ...item, unlocked: user.level >= item.level }))])),
  });
}));
app.put('/api/avatar', auth, asyncRoute(async (req, res) => {
  const body = z.object({
    avatarId: z.string().optional(),
    skin: z.string().optional(),
    face: z.string().optional(),
    hair: z.string().optional(),
    kit: z.string().optional(),
    accessory: z.string().optional(),
    boots: z.string().optional(),
    aura: z.string().optional(),
    pose: z.string().optional(),
  }).parse(req.body);
  const user = await prisma.user.findUniqueOrThrow({ where: { id: authId(req) }, select: { level: true } });
  if (body.avatarId) {
    const avatar = avatarCatalog.find((item) => item.id === body.avatarId);
    if (!avatar || avatar.level > user.level) return res.status(403).json({ error: 'Reach the unlock level to equip that crest.' });
    return res.json({ user: await prisma.user.update({ where: { id: authId(req) }, data: { avatarId: body.avatarId }, select: selectUser }) });
  }
  const nextLoadout = Object.fromEntries(Object.entries(body).filter(([key]) => key !== 'avatarId'));
  for (const [part, value] of Object.entries(nextLoadout)) {
    const option = avatarParts[part as keyof typeof avatarParts]?.find((item) => item.id === value);
    if (!option || option.level > user.level) return res.status(403).json({ error: 'That player option is still locked by level.' });
  }
  res.json({ loadout: await prisma.avatarLoadout.upsert({ where: { userId: authId(req) }, create: { userId: authId(req), ...nextLoadout }, update: nextLoadout }) });
}));

app.get('/api/xp', auth, asyncRoute(async (req, res) => {
  const user = await prisma.user.findUniqueOrThrow({ where: { id: authId(req) }, select: selectUser });
  res.json({ xp: user.xp, ...levelState(user.xp) });
}));
app.post('/api/xp/award', auth, asyncRoute(async (req, res) => {
  const body = z.object({ amount: z.coerce.number().int().min(1).max(500), reason: z.string().trim().max(80).default('manual award') }).parse(req.body);
  res.json(await awardXp(authId(req), body.amount, body.reason));
}));

app.get('/api/workout', auth, asyncRoute(async (req, res) => {
  res.json(await prisma.workout.findMany({ where: { userId: authId(req) }, orderBy: { completedAt: 'desc' }, take: 60 }));
}));
app.post('/api/workout', auth, asyncRoute(async (req, res) => {
  const body = z.object({
    type: z.enum(['running', 'gym', 'football', 'swimming', 'cycling', 'other']),
    duration: z.coerce.number().int().min(5).max(360),
    intensity: z.enum(['low', 'medium', 'high']),
    exercises: z.array(z.union([z.string(), z.object({ name: z.string(), reps: z.string().optional() })])).default([]),
  }).parse(req.body);
  const xpEarned = Math.max(20, Math.round(body.duration * intensityFactor(body.intensity)));
  const workout = await prisma.workout.create({ data: { ...body, userId: authId(req), exercises: jsonValue(body.exercises), xpEarned } });
  await awardXp(authId(req), xpEarned, `${body.type} workout`);
  await progressCard(authId(req), workoutGains(body.type, body.duration, body.intensity), `${body.type} training`);
  await applyChallengeProgress(authId(req), 'workouts', 1);
  await calculateReadiness(authId(req));
  res.status(201).json(workout);
}));

app.get('/api/health', auth, asyncRoute(async (req, res) => {
  res.json(await prisma.healthMetric.findMany({ where: { userId: authId(req) }, orderBy: { date: 'desc' }, take: 45 }));
}));
app.post('/api/health', auth, asyncRoute(async (req, res) => {
  const body = z.object({
    date: z.coerce.date().optional(),
    steps: z.coerce.number().int().min(0).optional(),
    sleepHours: z.coerce.number().min(0).max(24).optional(),
    heartRate: z.coerce.number().int().min(20).max(260).optional(),
    weight: z.coerce.number().positive().max(400).optional(),
    hydration: z.coerce.number().min(0).max(20).optional(),
  }).parse(req.body);
  const metric = await prisma.healthMetric.create({ data: { ...body, userId: authId(req) } });
  await awardXp(authId(req), 35, 'health log');
  if (metric.steps) await applyChallengeProgress(authId(req), 'steps', metric.steps, 'max');
  if (metric.sleepHours) await applyChallengeProgress(authId(req), 'sleep', metric.sleepHours, 'max');
  const readiness = await calculateReadiness(authId(req));
  if (readiness.score >= 70) await progressCard(authId(req), { physical: 1 }, 'recovery consistency');
  await applyChallengeProgress(authId(req), 'readiness', readiness.score, 'max');
  res.status(201).json({ metric, readiness });
}));

app.get('/api/challenges', auth, asyncRoute(async (req, res) => {
  await ensureChallenges(authId(req));
  res.json(await prisma.userChallenge.findMany({ where: { userId: authId(req), challenge: { isActive: true } }, include: { challenge: true }, orderBy: { createdAt: 'asc' } }));
}));
app.post('/api/challenges/:id/progress', auth, asyncRoute(async (req, res) => {
  const { progress } = z.object({ progress: z.coerce.number().int().min(0) }).parse(req.body);
  const item = await prisma.userChallenge.findFirstOrThrow({ where: { id: req.params.id, userId: authId(req) }, include: { challenge: true } });
  const next = Math.min(item.challenge.target, progress);
  const completed = next >= item.challenge.target;
  const updated = await prisma.userChallenge.update({ where: { id: item.id }, data: { progress: next, completed, completedAt: completed ? new Date() : null }, include: { challenge: true } });
  if (completed && !item.completed) await awardXp(authId(req), item.challenge.xpReward, item.challenge.title);
  res.json(updated);
}));

app.get('/api/readiness', auth, asyncRoute(async (req, res) => res.json(await calculateReadiness(authId(req)))));
app.get('/api/tests', auth, asyncRoute(async (req, res) => {
  res.json(await prisma.fitnessTest.findMany({ where: { userId: authId(req) }, orderBy: { testedAt: 'desc' }, take: 20 }));
}));
app.post('/api/tests', auth, asyncRoute(async (req, res) => {
  const body = z.object({
    sprint30m: z.coerce.number().positive().max(30).optional(),
    run5kMinutes: z.coerce.number().positive().max(180).optional(),
    yoyoLevel: z.coerce.number().positive().max(30).optional(),
    plankSeconds: z.coerce.number().int().positive().max(3600).optional(),
    jumpCm: z.coerce.number().positive().max(200).optional(),
    notes: z.string().trim().max(280).optional(),
    testedAt: z.coerce.date().optional(),
  }).parse(req.body);
  if (!Object.values(body).some((value) => typeof value === 'number')) return res.status(400).json({ error: 'Log at least one test result.' });
  const xpEarned = 70 + Object.values(body).filter((value) => typeof value === 'number').length * 12;
  const test = await prisma.fitnessTest.create({ data: { ...body, xpEarned, userId: authId(req) } });
  const [xp, card] = await Promise.all([
    awardXp(authId(req), xpEarned, 'fitness tests'),
    progressCard(authId(req), testGains(body), 'fitness tests'),
    applyChallengeProgress(authId(req), 'tests', 1),
  ]);
  res.status(201).json({ test, xp, card });
}));
app.get('/api/dashboard', auth, asyncRoute(async (req, res) => {
  const monday = new Date();
  monday.setUTCHours(0, 0, 0, 0);
  monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay() + 6) % 7));
  const [user, recentWorkouts, workoutsThisWeek, notifications, readiness, streak] = await Promise.all([
    prisma.user.findUniqueOrThrow({ where: { id: authId(req) }, select: { ...selectUser, playerCard: true, avatarLoadout: true } }),
    prisma.workout.findMany({ where: { userId: authId(req) }, orderBy: { completedAt: 'desc' }, take: 5 }),
    prisma.workout.count({ where: { userId: authId(req), completedAt: { gte: monday } } }),
    prisma.notification.findMany({ where: { userId: authId(req) }, orderBy: { createdAt: 'desc' }, take: 6 }),
    calculateReadiness(authId(req)),
    recentStreak(authId(req)),
  ]);
  res.json({ user: { ...user, matchReadiness: readiness.score }, recentWorkouts, notifications, stats: { totalXp: user.xp, workoutsThisWeek, streak }, xp: levelState(user.xp), readiness });
}));

app.get('/api/leaderboard', auth, asyncRoute(async (_req, res) => {
  res.json(await prisma.user.findMany({ orderBy: [{ xp: 'desc' }, { createdAt: 'asc' }], take: 50, select: { id: true, username: true, displayName: true, level: true, tier: true, xp: true, avatarId: true } }));
}));
app.get('/api/leaderboard/friends', auth, asyncRoute(async (req, res) => {
  const links = await prisma.friendship.findMany({ where: { status: 'accepted', OR: [{ userId: authId(req) }, { friendId: authId(req) }] } });
  const ids = [authId(req), ...links.map((item) => item.userId === authId(req) ? item.friendId : item.userId)];
  res.json(await prisma.user.findMany({ where: { id: { in: ids } }, orderBy: { xp: 'desc' }, select: { id: true, username: true, displayName: true, level: true, tier: true, xp: true, avatarId: true } }));
}));

app.get('/api/friends', auth, asyncRoute(async (req, res) => {
  const [links, activity] = await Promise.all([
    prisma.friendship.findMany({ where: { OR: [{ userId: authId(req) }, { friendId: authId(req) }] }, include: { user: { select: selectUser }, friend: { select: selectUser } }, orderBy: { createdAt: 'desc' } }),
    prisma.workout.findMany({ where: { user: { OR: [{ friends: { some: { friendId: authId(req), status: 'accepted' } } }, { friendOf: { some: { userId: authId(req), status: 'accepted' } } }] } }, include: { user: { select: { username: true, avatarId: true } } }, orderBy: { completedAt: 'desc' }, take: 12 }),
  ]);
  res.json({ requests: links.filter((item) => item.status === 'pending'), friends: links.filter((item) => item.status === 'accepted'), activity });
}));
app.post('/api/friends/request', auth, asyncRoute(async (req, res) => {
  const { username } = z.object({ username: z.string().trim().toLowerCase() }).parse(req.body);
  const friend = await prisma.user.findUnique({ where: { username } });
  if (!friend || friend.id === authId(req)) return res.status(404).json({ error: 'Player not found.' });
  const existing = await prisma.friendship.findFirst({ where: { OR: [{ userId: authId(req), friendId: friend.id }, { userId: friend.id, friendId: authId(req) }] } });
  if (existing) return res.status(409).json({ error: 'A friendship request already exists.' });
  const request = await prisma.friendship.create({ data: { userId: authId(req), friendId: friend.id } });
  await prisma.notification.create({ data: { userId: friend.id, type: 'friend', message: 'A new friend request is waiting.' } });
  res.status(201).json(request);
}));
app.put('/api/friends/:id/accept', auth, asyncRoute(async (req, res) => {
  const request = await prisma.friendship.findFirstOrThrow({ where: { id: req.params.id, friendId: authId(req), status: 'pending' } });
  res.json(await prisma.friendship.update({ where: { id: request.id }, data: { status: 'accepted' } }));
}));
app.delete('/api/friends/:id', auth, asyncRoute(async (req, res) => {
  const request = await prisma.friendship.findFirstOrThrow({ where: { id: req.params.id, OR: [{ userId: authId(req) }, { friendId: authId(req) }] } });
  await prisma.friendship.delete({ where: { id: request.id } });
  res.status(204).send();
}));

app.get('/api/notifications', auth, asyncRoute(async (req, res) => res.json(await prisma.notification.findMany({ where: { userId: authId(req) }, orderBy: { createdAt: 'desc' }, take: 30 }))));
app.put('/api/notifications/:id/read', auth, asyncRoute(async (req, res) => {
  const note = await prisma.notification.findFirstOrThrow({ where: { id: req.params.id, userId: authId(req) } });
  res.json(await prisma.notification.update({ where: { id: note.id }, data: { read: true } }));
}));

app.get('/api/playerCard', auth, asyncRoute(async (req, res) => {
  const card = await prisma.playerCard.upsert({ where: { userId: authId(req) }, create: { userId: authId(req) }, update: {} });
  const user = await prisma.user.findUniqueOrThrow({ where: { id: authId(req) }, select: { username: true, displayName: true, tier: true, avatarId: true, position: true } });
  const [workouts, tests, loadout] = await Promise.all([
    prisma.workout.count({ where: { userId: authId(req) } }),
    prisma.fitnessTest.count({ where: { userId: authId(req) } }),
    prisma.avatarLoadout.upsert({ where: { userId: authId(req) }, create: { userId: authId(req) }, update: {} }),
  ]);
  res.json({ ...card, user: { ...user, avatarLoadout: loadout }, progression: { workouts, tests, nextFocus: card.overall < 60 ? 'Build a base with football and running sessions.' : 'Use tests to sharpen card stats.' } });
}));
app.put('/api/playerCard', auth, asyncRoute(async (req, res) => {
  const body = z.object({ pace: z.number().int().min(1).max(99), shooting: z.number().int().min(1).max(99), passing: z.number().int().min(1).max(99), dribbling: z.number().int().min(1).max(99), defending: z.number().int().min(1).max(99), physical: z.number().int().min(1).max(99) }).partial().parse(req.body);
  const stats = Object.values(body);
  const overall = stats.length ? Math.round(stats.reduce((sum, value) => sum + Number(value), 0) / stats.length) : undefined;
  res.json(await prisma.playerCard.upsert({ where: { userId: authId(req) }, create: { userId: authId(req), ...body, overall }, update: { ...body, overall } }));
}));

const routineShape = z.record(z.array(z.string())).default({});
app.get('/api/routine', auth, asyncRoute(async (req, res) => res.json(await prisma.routine.upsert({ where: { userId: authId(req) }, create: { userId: authId(req) }, update: {} }))));
app.put('/api/routine', auth, asyncRoute(async (req, res) => {
  const entries = routineShape.parse(req.body);
  const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const;
  const data = Object.fromEntries(days.map((day) => [day, jsonValue(entries[day])]));
  res.json(await prisma.routine.upsert({ where: { userId: authId(req) }, create: { userId: authId(req), ...data }, update: data }));
}));

app.get('/api/wearables', auth, asyncRoute(async (req, res) => {
  const device = await prisma.wearable.upsert({ where: { userId: authId(req) }, create: { userId: authId(req) }, update: {} });
  res.json({ device: publicWearable(device), googleHealthReady: googleHealthConfig().ready });
}));
app.put('/api/wearables', auth, asyncRoute(async (req, res) => {
  const body = z.object({ deviceType: z.string().trim().max(60).optional().nullable(), deviceName: z.string().trim().max(80).optional().nullable(), connected: z.boolean().optional(), dailySteps: z.coerce.number().int().min(0).optional().nullable(), heartRate: z.coerce.number().int().min(20).max(260).optional().nullable(), sleepHours: z.coerce.number().min(0).max(24).optional().nullable() }).parse(req.body);
  const data = { ...body, lastSync: body.connected ? new Date() : undefined };
  const device = await prisma.wearable.upsert({ where: { userId: authId(req) }, create: { userId: authId(req), ...data }, update: data });
  let readiness;
  if (device.connected && (device.dailySteps || device.heartRate || device.sleepHours)) {
    readiness = await applyWearableMetrics(authId(req), { steps: device.dailySteps, heartRate: device.heartRate, sleepHours: device.sleepHours });
  }
  res.json({ device: publicWearable(device), readiness });
}));
app.get('/api/wearables/google-health/connect', auth, asyncRoute(async (req, res) => {
  const config = googleHealthConfig();
  if (!config.ready) return res.status(503).json({ error: 'Google Health is not configured yet.' });
  const state = jwt.sign({ userId: authId(req), kind: 'google-health' }, jwtSecret(), { expiresIn: '10m' });
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: config.clientId!,
    redirect_uri: config.redirectUri,
    scope: [
      'openid',
      'https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly',
      'https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly',
      'https://www.googleapis.com/auth/googlehealth.sleep.readonly',
      'https://www.googleapis.com/auth/googlehealth.profile.readonly',
    ].join(' '),
    access_type: 'offline',
    prompt: 'consent',
    state,
  });
  res.json({ url: `https://accounts.google.com/o/oauth2/v2/auth?${params}` });
}));
app.get('/api/wearables/google-health/callback', asyncRoute(async (req, res) => {
  const code = z.string().min(1).parse(req.query.code);
  const state = z.string().min(1).parse(req.query.state);
  const payload = jwt.verify(state, jwtSecret()) as { userId?: string; kind?: string };
  if (!payload.userId || payload.kind !== 'google-health') return res.status(400).send('Invalid Google Health connection state.');
  const config = googleHealthConfig();
  if (!config.ready) return res.status(503).send('Google Health is not configured.');
  const token = await googleHealthToken(new URLSearchParams({ client_id: config.clientId!, client_secret: config.clientSecret!, grant_type: 'authorization_code', code, redirect_uri: config.redirectUri }));
  let identity: { userId?: string; googleUserId?: string } = {};
  try {
    identity = await googleHealthGet<{ userId?: string; googleUserId?: string }>('/v4/users/me/identity', token.access_token!);
  } catch {
    identity = {};
  }
  await prisma.wearable.upsert({
    where: { userId: payload.userId },
    create: {
      userId: payload.userId,
      provider: 'google-health',
      providerUserId: identity.userId || identity.googleUserId || null,
      accessToken: token.access_token,
      refreshToken: token.refresh_token,
      tokenExpiresAt: new Date(Date.now() + Number(token.expires_in || 3600) * 1000),
      connected: true,
      deviceType: 'Google Health',
      deviceName: 'Google Health account',
    },
    update: {
      provider: 'google-health',
      providerUserId: identity.userId || identity.googleUserId || null,
      accessToken: token.access_token,
      refreshToken: token.refresh_token,
      tokenExpiresAt: new Date(Date.now() + Number(token.expires_in || 3600) * 1000),
      connected: true,
      deviceType: 'Google Health',
      deviceName: 'Google Health account',
    },
  });
  res.redirect(`${frontendUrl()}/wearables?googleHealth=connected`);
}));
app.post('/api/wearables/google-health/sync', auth, asyncRoute(async (req, res) => {
  const { wearable, accessToken } = await validGoogleHealthAccessToken(authId(req));
  const body = todayCivilRange();
  const [steps, sleep, heart] = await Promise.all([
    googleHealthPost<{ rollupDataPoints?: Array<{ steps?: { countSum?: string } }> }>('/v4/users/me/dataTypes/steps/dataPoints:dailyRollUp', accessToken, body),
    googleHealthPost<{ sessions?: Array<{ summary?: { minutesAsleep?: string } }> }>('/v4/users/me/dataTypes/sleep/sessions:reconcile', accessToken, { range: body.range }),
    googleHealthPost<{ rollupDataPoints?: Array<{ heartRate?: { bpmAvg?: number; beatsPerMinuteAvg?: number } }> }>('/v4/users/me/dataTypes/heart-rate/dataPoints:dailyRollUp', accessToken, body),
  ]);
  const totalSteps = steps.rollupDataPoints?.reduce((sum, item) => sum + Number(item.steps?.countSum || 0), 0) || null;
  const sleepMinutes = sleep.sessions?.reduce((sum, item) => sum + Number(item.summary?.minutesAsleep || 0), 0) || null;
  const heartValues = heart.rollupDataPoints?.map((item) => item.heartRate?.bpmAvg || item.heartRate?.beatsPerMinuteAvg).filter(Boolean) as number[] | undefined;
  const heartRate = heartValues?.length ? Math.round(heartValues.reduce((sum, value) => sum + value, 0) / heartValues.length) : null;
  const device = await prisma.wearable.update({
    where: { userId: authId(req) },
    data: {
      connected: true,
      provider: 'google-health',
      dailySteps: totalSteps,
      sleepHours: sleepMinutes ? Number((sleepMinutes / 60).toFixed(2)) : null,
      heartRate,
      lastSync: new Date(),
      deviceName: wearable.deviceName || 'Google Health account',
    },
  });
  const readiness = await applyWearableMetrics(authId(req), { steps: device.dailySteps, sleepHours: device.sleepHours, heartRate: device.heartRate });
  res.json({ device: publicWearable(device), readiness });
}));
app.delete('/api/wearables/google-health', auth, asyncRoute(async (req, res) => {
  const device = await prisma.wearable.upsert({
    where: { userId: authId(req) },
    create: { userId: authId(req) },
    update: { provider: null, providerUserId: null, accessToken: null, refreshToken: null, tokenExpiresAt: null, connected: false },
  });
  res.json({ device: publicWearable(device) });
}));

app.get('/api/settings', auth, asyncRoute(async (req, res) => res.json(await prisma.userSettings.upsert({ where: { userId: authId(req) }, create: { userId: authId(req) }, update: {} }))));
app.put('/api/settings', auth, asyncRoute(async (req, res) => {
  const body = z.object({ notifications: z.boolean().optional(), publicProfile: z.boolean().optional(), weeklyGoal: z.coerce.number().int().min(1).max(14).optional(), theme: z.enum(['dark', 'light']).optional(), units: z.enum(['metric', 'imperial']).optional() }).parse(req.body);
  res.json(await prisma.userSettings.upsert({ where: { userId: authId(req) }, create: { userId: authId(req), ...body }, update: body }));
}));

app.use((_req, res) => res.status(404).json({ error: 'Route not found.' }));
app.use(errorHandler);

if (require.main === module) {
  app.listen(port, () => console.log(`MatchFit Pro API listening on ${port}`));
}

export default app;
