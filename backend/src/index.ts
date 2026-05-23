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
  { title: 'Daily Session', description: 'Complete one programmed workout or sport session today.', type: 'programWorkout', period: 'daily', target: 1, xpReward: 80, tier: 'Bronze' },
  { title: 'Daily Tracker Sync', description: 'Sync wearable steps, sleep, or heart-rate data today.', type: 'wearableSync', period: 'daily', target: 1, xpReward: 45, tier: 'Bronze' },
  { title: 'Daily 8K Engine', description: 'Reach 8,000 verified wearable steps today.', type: 'steps', period: 'daily', target: 8000, xpReward: 70, tier: 'Bronze' },
  { title: 'Daily Recovery Window', description: 'Record at least seven hours of wearable sleep today.', type: 'sleep', period: 'daily', target: 7, xpReward: 70, tier: 'Bronze' },
  { title: 'Weekly Training Block', description: 'Complete four programmed workouts or sport sessions this week.', type: 'programWorkout', period: 'weekly', target: 4, xpReward: 320, tier: 'Silver' },
  { title: 'Weekly Match Engine', description: 'Complete 180 verified training minutes this week.', type: 'trainingMinutes', period: 'weekly', target: 180, xpReward: 360, tier: 'Silver' },
  { title: 'Weekly Test Marker', description: 'Log one fitness test block this week.', type: 'tests', period: 'weekly', target: 1, xpReward: 260, tier: 'Gold' },
  { title: 'Campaign Kickoff', description: 'Complete your first programmed workout.', type: 'programWorkout', period: 'campaign', target: 1, xpReward: 180, tier: 'Bronze' },
  { title: 'Campaign Engine Builder', description: 'Complete 600 verified training minutes.', type: 'trainingMinutes', period: 'campaign', target: 600, xpReward: 650, tier: 'Silver' },
  { title: 'Campaign Recovery Habit', description: 'Sync wearable recovery data 10 times.', type: 'wearableSync', period: 'campaign', target: 10, xpReward: 500, tier: 'Silver' },
  { title: 'Campaign Testing Baseline', description: 'Log three fitness test blocks.', type: 'tests', period: 'campaign', target: 3, xpReward: 700, tier: 'Gold' },
  { title: 'Campaign Speed Base', description: 'Complete five pace-focused running or sprint sessions.', type: 'paceTraining', period: 'campaign', target: 5, xpReward: 620, tier: 'Gold' },
  { title: 'Campaign Strength Base', description: 'Complete five gym or strength sessions.', type: 'physicalTraining', period: 'campaign', target: 5, xpReward: 620, tier: 'Gold' },
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
  const data = await response.json() as T & { error?: { message?: string; status?: string }; message?: string };
  if (!response.ok) throw new Error(`Google Health ${response.status}: ${data.error?.message || data.message || path}`);
  return data;
}

async function googleHealthPost<T>(path: string, accessToken: string, body: unknown) {
  const response = await fetch(`https://health.googleapis.com${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}`, Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json() as T & { error?: { message?: string; status?: string }; message?: string };
  if (!response.ok) throw new Error(`Google Health ${response.status}: ${data.error?.message || data.message || path}`);
  return data;
}

function todayCivilRange() {
  const now = new Date();
  const date = { year: now.getFullYear(), month: now.getMonth() + 1, day: now.getDate() };
  return {
    dataSourceFamily: 'users/me/dataSourceFamilies/google-wearables',
    range: {
      start: { date, time: { hours: 0, minutes: 0, seconds: 0, nanos: 0 } },
      end: { date, time: { hours: 23, minutes: 59, seconds: 59, nanos: 0 } },
    },
    windowSizeDays: 1,
  };
}

function todayDateString() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function ukParts(at = new Date()) {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: false, weekday: 'short' }).formatToParts(at);
  const value = (type: string) => parts.find((part) => part.type === type)?.value || '0';
  return { year: Number(value('year')), month: Number(value('month')), day: Number(value('day')), hour: Number(value('hour')), minute: Number(value('minute')), second: Number(value('second')), weekday: value('weekday') };
}

function ukCivilToDate(year: number, month: number, day: number, hour = 0, minute = 0, second = 0) {
  const guess = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  const parts = ukParts(guess);
  const drift = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second) - Date.UTC(year, month - 1, day, hour, minute, second);
  return new Date(guess.getTime() - drift);
}

function startOfPeriod(period: string, at = new Date()) {
  if (period === 'campaign') return new Date('2026-01-01T00:00:00.000Z');
  const parts = ukParts(at);
  const start = ukCivilToDate(parts.year, parts.month, parts.day);
  if (period === 'weekly') {
    const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    start.setUTCDate(start.getUTCDate() - weekdays.indexOf(parts.weekday));
  }
  return start;
}

function resetTimes() {
  const today = startOfPeriod('daily');
  const nextDaily = new Date(today);
  nextDaily.setUTCDate(nextDaily.getUTCDate() + 1);
  const week = startOfPeriod('weekly');
  const nextWeekly = new Date(week);
  nextWeekly.setUTCDate(nextWeekly.getUTCDate() + 7);
  return { daily: nextDaily, weekly: nextWeekly };
}

function publicWearable<T extends { accessToken?: string | null; refreshToken?: string | null }>(wearable: T) {
  const { accessToken: _accessToken, refreshToken: _refreshToken, ...safe } = wearable;
  return safe;
}

async function applyWearableMetrics(userId: string, metrics: { steps?: number | null; heartRate?: number | null; sleepHours?: number | null }) {
  await prisma.healthMetric.create({ data: { userId, steps: metrics.steps, heartRate: metrics.heartRate, sleepHours: metrics.sleepHours } });
  await awardXp(userId, 20, 'wearable sync');
  await applyChallengeProgress(userId, 'wearableSync', 1);
  if (metrics.steps) await applyChallengeProgress(userId, 'steps', metrics.steps, 'max');
  if (metrics.sleepHours) await applyChallengeProgress(userId, 'sleep', metrics.sleepHours, 'max');
  if (metrics.steps && metrics.steps >= 8000) await progressCard(userId, { pace: 1, physical: 1 }, 'wearable steps');
  const readiness = await calculateReadiness(userId);
  return readiness;
}

const cardKeys = ['pace', 'shooting', 'passing', 'dribbling', 'defending', 'physical'] as const;
const trainedAtKey = {
  pace: 'paceTrainedAt',
  shooting: 'shootingTrainedAt',
  passing: 'passingTrainedAt',
  dribbling: 'dribblingTrainedAt',
  defending: 'defendingTrainedAt',
  physical: 'physicalTrainedAt',
} as const;

function overallOf(stats: Record<(typeof cardKeys)[number], number>) {
  return Math.round(cardKeys.reduce((sum, key) => sum + stats[key], 0) / cardKeys.length);
}

function clampStat(value: number) {
  return Math.round(clamp(value, 1, 99));
}

async function progressCard(userId: string, gains: Partial<Record<(typeof cardKeys)[number], number>>, reason: string) {
  const card = await applyCardDecay(userId);
  const stats = Object.fromEntries(cardKeys.map((key) => [key, clampStat(card[key] + (gains[key] || 0))])) as Record<(typeof cardKeys)[number], number>;
  const now = new Date();
  const trainedDates = Object.fromEntries(cardKeys.filter((key) => gains[key]).map((key) => [trainedAtKey[key], now]));
  const next = await prisma.playerCard.update({ where: { userId }, data: { ...stats, ...trainedDates, overall: overallOf(stats) } });
  const boosts = Object.entries(gains).filter(([, value]) => value).map(([key, value]) => `${key} +${value}`).join(', ');
  if (boosts) await prisma.notification.create({ data: { userId, type: 'card', message: `${reason} improved your card: ${boosts}.` } });
  return next;
}

async function applyTestBenchmarks(userId: string, benchmarks: Partial<Record<(typeof cardKeys)[number], number>>) {
  const card = await applyCardDecay(userId);
  const now = new Date();
  const stats = Object.fromEntries(cardKeys.map((key) => [key, Math.max(card[key], benchmarks[key] || 0)])) as Record<(typeof cardKeys)[number], number>;
  const trainedDates = Object.fromEntries(cardKeys.filter((key) => benchmarks[key] && benchmarks[key]! > card[key]).map((key) => [trainedAtKey[key], now]));
  const next = await prisma.playerCard.update({ where: { userId }, data: { ...stats, ...trainedDates, overall: overallOf(stats) } });
  const boosts = cardKeys.filter((key) => benchmarks[key] && benchmarks[key]! > card[key]).map((key) => `${key} set to ${stats[key]}`);
  if (boosts.length) await prisma.notification.create({ data: { userId, type: 'card', message: `Testing benchmark achieved: ${boosts.join(', ')}.` } });
  return next;
}

async function applyCardDecay(userId: string) {
  const card = await prisma.playerCard.upsert({ where: { userId }, create: { userId }, update: {} });
  const nextStats: Partial<Record<(typeof cardKeys)[number], number>> = {};
  const now = Date.now();
  for (const key of cardKeys) {
    const last = card[trainedAtKey[key]] || card.updatedAt;
    const quietDays = Math.max(0, (now - last.getTime()) / 86_400_000 - 14);
    if (quietDays <= 0 || card[key] <= 45) {
      nextStats[key] = card[key];
      continue;
    }
    const weeks = quietDays / 7;
    const drop = Math.floor((card[key] - 45) * (1 - Math.exp(-0.16 * weeks)));
    nextStats[key] = clampStat(Math.max(45, card[key] - drop));
  }
  const changed = cardKeys.some((key) => nextStats[key] !== card[key]);
  if (!changed) return card;
  return prisma.playerCard.update({ where: { userId }, data: { ...nextStats, overall: overallOf(nextStats as Record<(typeof cardKeys)[number], number>) } });
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

function exerciseGains(type: string, exercises: unknown[], duration: number, intensity: string) {
  const gains = workoutGains(type, duration, intensity);
  const names = exercises.map((item) => typeof item === 'string' ? item : item && typeof item === 'object' ? String((item as { name?: string }).name || '') : '').join(' ').toLowerCase();
  const add = (key: (typeof cardKeys)[number], amount = 1) => { gains[key] = (gains[key] || 0) + amount; };
  if (/sprint|acceleration|tempo|run|a-skip|bound/.test(names) || type === 'running') add('pace');
  if (/wall pass|passing|first touch|ball/.test(names) || type === 'football') add('passing');
  if (/dribble|agility|cone/.test(names) || type === 'football') add('dribbling');
  if (/shot|finish|shoot/.test(names)) add('shooting');
  if (/squat|deadlift|lunge|bench|press|row|pull|plank|calf|gym|strength/.test(names) || type === 'gym') add('physical');
  if (/lateral|split squat|core|plank|defend|shield/.test(names) || type === 'gym') add('defending');
  return gains;
}

type ProgramExercise = {
  name: string;
  sets: number;
  reps: string;
  weightKg: number;
  restSeconds: number;
  equipment: string;
  instruction: string;
  progression: string;
};

const exerciseLibrary: Record<string, ProgramExercise[]> = {
  strength: [
    { name: 'Goblet squat', sets: 4, reps: '8', weightKg: 0, restSeconds: 90, equipment: 'dumbbells', instruction: 'Hold one dumbbell tight to your chest, sit hips down between knees, then drive up through the floor.', progression: '' },
    { name: 'Romanian deadlift', sets: 4, reps: '8', weightKg: 0, restSeconds: 90, equipment: 'barbell', instruction: 'Soft knees, push hips back, keep the bar close, stand tall by squeezing glutes.', progression: '' },
    { name: 'Dumbbell bench press', sets: 4, reps: '8', weightKg: 0, restSeconds: 90, equipment: 'bench', instruction: 'Shoulder blades tucked, lower under control, press up without bouncing.', progression: '' },
    { name: 'Walking lunge', sets: 3, reps: '10 each leg', weightKg: 0, restSeconds: 75, equipment: 'dumbbells', instruction: 'Step long, back knee down, front foot flat, stand through the front leg.', progression: '' },
    { name: 'Split squat', sets: 3, reps: '10 each leg', weightKg: 0, restSeconds: 75, equipment: 'bodyweight', instruction: 'Back foot planted, drop straight down, keep the front knee tracking over toes.', progression: '' },
    { name: 'Standing calf raise', sets: 3, reps: '15', weightKg: 0, restSeconds: 45, equipment: 'dumbbells', instruction: 'Rise high onto toes, pause briefly, lower slowly for ankle and sprint stiffness.', progression: '' },
    { name: 'Plank', sets: 3, reps: '45 seconds', weightKg: 0, restSeconds: 45, equipment: 'bodyweight', instruction: 'Ribs down, glutes tight, keep a straight line from shoulders to ankles.', progression: '' },
  ],
  speed: [
    { name: 'A-skip drill', sets: 3, reps: '20m', weightKg: 0, restSeconds: 45, equipment: 'bodyweight', instruction: 'Pop off the ground, knee up, toe up, stay tall.', progression: '' },
    { name: 'Acceleration sprint', sets: 6, reps: '20m', weightKg: 0, restSeconds: 90, equipment: 'cones', instruction: 'Lean forward, powerful first three steps, full recovery between reps.', progression: '' },
    { name: 'Lateral bound', sets: 3, reps: '6 each side', weightKg: 0, restSeconds: 60, equipment: 'bodyweight', instruction: 'Jump sideways, stick the landing, keep knee stable.', progression: '' },
  ],
  endurance: [
    { name: 'Tempo run', sets: 4, reps: '4 minutes', weightKg: 0, restSeconds: 120, equipment: 'running shoes', instruction: 'Run at controlled hard pace, able to speak only short phrases.', progression: '' },
    { name: 'Recovery jog', sets: 4, reps: '2 minutes', weightKg: 0, restSeconds: 30, equipment: 'running shoes', instruction: 'Keep this genuinely easy so the next tempo block is clean.', progression: '' },
  ],
  ball: [
    { name: 'Wall pass first touch', sets: 4, reps: '60 seconds', weightKg: 0, restSeconds: 30, equipment: 'ball', instruction: 'One touch to set, one touch to pass. Alternate feet every rep.', progression: '' },
    { name: 'Cone dribble changes', sets: 4, reps: '45 seconds', weightKg: 0, restSeconds: 45, equipment: 'cones', instruction: 'Attack each cone, change direction sharply, keep ball close.', progression: '' },
    { name: 'Fatigue finishing', sets: 5, reps: '5 shots', weightKg: 0, restSeconds: 60, equipment: 'ball', instruction: 'Short shuttle before each shot, compose yourself, hit the target.', progression: '' },
  ],
  recovery: [
    { name: 'Zone 2 bike or jog', sets: 1, reps: '25 minutes', weightKg: 0, restSeconds: 0, equipment: 'bike', instruction: 'Easy effort, nose-breathable pace, finish feeling better than you started.', progression: '' },
    { name: 'Hip flexor mobility', sets: 2, reps: '60 seconds each side', weightKg: 0, restSeconds: 20, equipment: 'mat', instruction: 'Squeeze back-leg glute and gently shift hips forward.', progression: '' },
    { name: 'Ankle rocks', sets: 2, reps: '12 each side', weightKg: 0, restSeconds: 20, equipment: 'bodyweight', instruction: 'Keep heel down and drive knee over toes with control.', progression: '' },
  ],
};

function roundLoad(value: number) {
  return Math.max(0, Math.round(value / 2.5) * 2.5);
}

function exerciseLoad(exercise: ProgramExercise, weightKg: number, age: number) {
  const ageFactor = age < 16 ? 0.45 : age < 19 ? 0.65 : age > 45 ? 0.75 : 1;
  const ratios: Record<string, number> = {
    'Goblet squat': 0.32,
    'Romanian deadlift': 0.55,
    'Dumbbell bench press': 0.22,
    'Walking lunge': 0.18,
    'Split squat': 0,
    'Standing calf raise': 0.22,
  };
  return roundLoad((ratios[exercise.name] || 0) * weightKg * ageFactor);
}

function repsNumber(reps: string) {
  return Number(reps.match(/\d+/)?.[0] || 1);
}

function workoutLoad(exercises: unknown[]) {
  return exercises.reduce<number>((total, item) => {
    if (!item || typeof item !== 'object') return total;
    const exercise = item as Partial<ProgramExercise>;
    return total + Number(exercise.sets || 1) * repsNumber(String(exercise.reps || '1')) * Math.max(1, Number(exercise.weightKg || 1));
  }, 0);
}

function xpForWorkout(duration: number, intensity: string, exercises: unknown[]) {
  const base = Math.round(duration * intensityFactor(intensity));
  const loadBonus = Math.min(80, Math.round(workoutLoad(exercises) / 120));
  return Math.max(20, base + loadBonus);
}

async function previousExercise(userId: string, name: string) {
  const workouts = await prisma.workout.findMany({ where: { userId, source: 'program' }, orderBy: { completedAt: 'desc' }, take: 20 });
  for (const workout of workouts) {
    const exercises = Array.isArray(workout.exercises) ? workout.exercises : [];
    const found = exercises.find((item) => item && typeof item === 'object' && (item as { name?: string }).name === name);
    if (found) return found as Partial<ProgramExercise>;
  }
  return null;
}

async function buildProgram(userId: string, input: { equipment: string[]; goal: string; minutes: number; type: string }) {
  const user = await prisma.user.findUniqueOrThrow({ where: { id: userId }, select: { age: true, weight: true } });
  const equipment = new Set(input.equipment);
  const base = exerciseLibrary[input.goal] || exerciseLibrary.ball;
  const available = base.filter((item) => item.equipment === 'bodyweight' || equipment.has(item.equipment) || equipment.has('gym'));
  const selected = (available.length ? available : base).slice(0, input.minutes >= 60 ? 6 : 4);
  const exercises = await Promise.all(selected.map(async (item) => {
    const last = await previousExercise(userId, item.name);
    const baseWeight = exerciseLoad(item, Number(user.weight || 70), Number(user.age || 24));
    const previousWeight = Number(last?.weightKg || 0);
    const nextWeight = previousWeight ? previousWeight + (previousWeight >= 40 ? 2.5 : 1) : baseWeight;
    return {
      ...item,
      weightKg: roundLoad(nextWeight),
      progression: previousWeight ? `Last time was ${previousWeight}kg. Target is a small increase if form stays clean.` : `Starting target based on your profile: age ${user.age || 'unknown'}, weight ${user.weight || 70}kg.`,
    };
  }));
  const intensity = input.goal === 'recovery' ? 'low' : input.goal === 'speed' || input.goal === 'strength' ? 'high' : 'medium';
  const type = input.goal === 'ball' ? 'football' : input.goal === 'strength' ? 'gym' : input.type;
  return { type, duration: input.minutes, intensity, exercises };
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

function ratingFromLowerIsBetter(value: number | undefined, levels: Array<[number, number]>) {
  if (!value) return 0;
  return levels.find(([target]) => value <= target)?.[1] || 0;
}

function ratingFromHigherIsBetter(value: number | undefined, levels: Array<[number, number]>) {
  if (!value) return 0;
  return levels.find(([target]) => value >= target)?.[1] || 0;
}

function testBenchmarks(test: Record<string, number | string | Date | undefined>) {
  const pace = Math.max(
    ratingFromLowerIsBetter(test.sprint30m as number | undefined, [[3.8, 95], [4.1, 90], [4.4, 84], [4.7, 78], [5.0, 70], [5.4, 62], [5.9, 55]]),
    ratingFromLowerIsBetter(test.run5kMinutes as number | undefined, [[16, 88], [18, 82], [20, 75], [23, 68], [26, 60], [30, 54]]),
    ratingFromHigherIsBetter(test.yoyoLevel as number | undefined, [[22, 94], [20, 88], [18, 80], [16, 72], [14, 64], [12, 56]]),
  );
  const shooting = Math.max(
    ratingFromHigherIsBetter(test.shootingScore as number | undefined, [[95, 92], [85, 84], [75, 76], [65, 68], [55, 60]]),
    ratingFromHigherIsBetter(test.jumpCm as number | undefined, [[75, 88], [65, 80], [55, 72], [45, 64], [35, 56]]),
  );
  const passing = ratingFromHigherIsBetter(test.passingScore as number | undefined, [[95, 92], [85, 84], [75, 76], [65, 68], [55, 60]]);
  const dribbling = Math.max(
    ratingFromLowerIsBetter(test.dribbleSeconds as number | undefined, [[9, 92], [10, 84], [11.5, 76], [13, 68], [15, 60]]),
    ratingFromLowerIsBetter(test.agility505Seconds as number | undefined, [[2.1, 90], [2.25, 82], [2.45, 74], [2.7, 66], [3, 58]]),
  );
  const defending = Math.max(
    ratingFromLowerIsBetter(test.shuttleRunSeconds as number | undefined, [[8.4, 88], [8.9, 80], [9.5, 72], [10.2, 64], [11, 56]]),
    ratingFromHigherIsBetter(test.plankSeconds as number | undefined, [[240, 86], [180, 78], [120, 70], [75, 62], [45, 55]]),
  );
  const physical = Math.max(
    ratingFromHigherIsBetter(test.deadliftKg as number | undefined, [[180, 92], [150, 84], [120, 76], [90, 66], [60, 56]]),
    ratingFromHigherIsBetter(test.squatKg as number | undefined, [[150, 90], [125, 82], [100, 74], [75, 64], [50, 55]]),
    ratingFromHigherIsBetter(test.benchKg as number | undefined, [[110, 88], [90, 80], [70, 72], [50, 62], [35, 55]]),
    ratingFromHigherIsBetter(test.pullUps as number | undefined, [[20, 88], [15, 80], [10, 70], [5, 60], [1, 52]]),
    ratingFromHigherIsBetter(test.pushUps as number | undefined, [[70, 84], [50, 76], [35, 68], [20, 58]]),
    ratingFromHigherIsBetter(test.broadJumpCm as number | undefined, [[290, 90], [260, 82], [230, 74], [200, 64], [170, 55]]),
  );
  return { pace, shooting, passing, dribbling, defending, physical };
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
  const fourWeeks = new Date(Date.now() - 28 * 24 * 60 * 60 * 1000);
  const twelveWeeks = new Date(Date.now() - 84 * 24 * 60 * 60 * 1000);
  const [user, card, recentWorkouts, longWorkouts, health] = await Promise.all([
    prisma.user.findUniqueOrThrow({ where: { id: userId }, select: { createdAt: true } }),
    applyCardDecay(userId),
    prisma.workout.findMany({ where: { userId, completedAt: { gte: fourWeeks } } }),
    prisma.workout.findMany({ where: { userId, completedAt: { gte: twelveWeeks } } }),
    prisma.healthMetric.findMany({ where: { userId }, orderBy: { date: 'desc' }, take: 28 }),
  ]);
  const cardStats = cardKeys.map((key) => card[key]);
  const cardScore = clamp(card.overall);
  const weakestStat = Math.min(...cardStats);
  const balanceScore = clamp((weakestStat / 70) * 100);
  const weeklyTrainingMinutes = recentWorkouts.reduce((total, item) => total + item.duration * intensityFactor(item.intensity), 0) / 4;
  const trainingScore = clamp((weeklyTrainingMinutes / 180) * 100);
  const longTermMinutes = longWorkouts.reduce((total, item) => total + item.duration * intensityFactor(item.intensity), 0);
  const baseScore = clamp((longTermMinutes / 2160) * 100);
  const avgSleep = health.filter((item) => item.sleepHours !== null).slice(0, 14).reduce((sum, item) => sum + Number(item.sleepHours), 0) / Math.max(1, health.filter((item) => item.sleepHours !== null).slice(0, 14).length);
  const avgSteps = health.filter((item) => item.steps !== null).slice(0, 14).reduce((sum, item) => sum + Number(item.steps), 0) / Math.max(1, health.filter((item) => item.steps !== null).slice(0, 14).length);
  const avgHydration = health.filter((item) => item.hydration !== null).slice(0, 14).reduce((sum, item) => sum + Number(item.hydration), 0) / Math.max(1, health.filter((item) => item.hydration !== null).slice(0, 14).length);
  const recoveryScore = Math.round(clamp(((avgSleep / 8) * 45) + ((avgSteps / 10000) * 35) + ((avgHydration / 2.5) * 20)));
  const weeksSinceStart = Math.max(0, (Date.now() - user.createdAt.getTime()) / (7 * 24 * 60 * 60 * 1000));
  const campaignScore = clamp((weeksSinceStart / 16) * 100);
  const score = Math.round(cardScore * 0.35 + trainingScore * 0.2 + recoveryScore * 0.18 + baseScore * 0.15 + balanceScore * 0.07 + campaignScore * 0.05);
  await prisma.user.update({ where: { id: userId }, data: { matchReadiness: score } });
  return {
    score,
    target: 'Build toward one match several months from now',
    factors: {
      card: Math.round(cardScore),
      training: Math.round(trainingScore),
      recovery: Math.round(recoveryScore),
      base: Math.round(baseScore),
      balance: Math.round(balanceScore),
      campaign: Math.round(campaignScore),
    },
  };
}

async function ensureChallenges(userId: string) {
  const activeTitles = defaultChallenges.map((challenge) => challenge.title);
  await prisma.challenge.updateMany({ where: { title: { notIn: activeTitles } }, data: { isActive: false } });
  await Promise.all(defaultChallenges.map(async (challenge) => {
    const exists = await prisma.challenge.findFirst({ where: { title: challenge.title } });
    if (exists) await prisma.challenge.update({ where: { id: exists.id }, data: { ...challenge, source: 'verified', isActive: true } });
    if (!exists) await prisma.challenge.create({ data: { ...challenge, source: 'verified' } });
  }));
  const challenges = await prisma.challenge.findMany({ where: { isActive: true }, orderBy: { createdAt: 'asc' } });
  await Promise.all(challenges.map(async (item) => {
    const periodStart = startOfPeriod(item.period);
    const exists = await prisma.userChallenge.findFirst({ where: { userId, challengeId: item.id, periodStart } });
    if (!exists) await prisma.userChallenge.create({ data: { userId, challengeId: item.id, periodStart } });
  }));
}

async function applyChallengeProgress(userId: string, type: string, value: number, mode: 'add' | 'max' = 'add') {
  await ensureChallenges(userId);
  const assignments = await prisma.userChallenge.findMany({
    where: {
      userId,
      completed: false,
      challenge: { type, isActive: true, source: 'verified' },
      OR: [
        { challenge: { period: 'daily' }, periodStart: startOfPeriod('daily') },
        { challenge: { period: 'weekly' }, periodStart: startOfPeriod('weekly') },
        { challenge: { period: 'campaign' }, periodStart: startOfPeriod('campaign') },
      ],
    },
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

app.post('/api/auth/forgot-password', asyncRoute(async (req, res) => {
  z.object({ email: z.string().trim().email() }).parse(req.body);
  res.json({ message: 'If that account exists, password reset instructions will be sent when email delivery is enabled.' });
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
    source: z.enum(['program', 'sport', 'wearable', 'manual']).default('sport'),
  }).parse(req.body);
  const xpEarned = xpForWorkout(body.duration, body.intensity, body.exercises);
  const workout = await prisma.workout.create({ data: { ...body, userId: authId(req), exercises: jsonValue(body.exercises), xpEarned } });
  await awardXp(authId(req), xpEarned, `${body.type} workout`);
  await progressCard(authId(req), exerciseGains(body.type, body.exercises, body.duration, body.intensity), `${body.type} training`);
  if (body.source !== 'manual') {
    await applyChallengeProgress(authId(req), 'programWorkout', 1);
    await applyChallengeProgress(authId(req), 'trainingMinutes', body.duration);
    if (['running', 'football', 'cycling'].includes(body.type)) await applyChallengeProgress(authId(req), 'paceTraining', 1);
    if (body.type === 'gym') await applyChallengeProgress(authId(req), 'physicalTraining', 1);
  }
  await calculateReadiness(authId(req));
  res.status(201).json(workout);
}));

app.post('/api/program/generate', auth, asyncRoute(async (req, res) => {
  const body = z.object({
    equipment: z.array(z.string()).default([]),
    goal: z.enum(['speed', 'endurance', 'strength', 'ball', 'recovery']).default('ball'),
    minutes: z.coerce.number().int().min(20).max(120).default(45),
    type: z.enum(['running', 'gym', 'football', 'swimming', 'cycling', 'other']).default('football'),
  }).parse(req.body);
  res.json({ program: await buildProgram(authId(req), body) });
}));

app.post('/api/program/complete', auth, asyncRoute(async (req, res) => {
  const exerciseSchema = z.object({
    name: z.string().trim().min(1),
    sets: z.coerce.number().int().min(1).max(10),
    reps: z.string().trim().min(1).max(40),
    weightKg: z.coerce.number().min(0).max(500),
    restSeconds: z.coerce.number().int().min(0).max(600),
    equipment: z.string().trim().max(40),
    instruction: z.string().trim().max(500),
    progression: z.string().trim().max(500).optional(),
  });
  const body = z.object({
    type: z.enum(['running', 'gym', 'football', 'swimming', 'cycling', 'other']),
    duration: z.coerce.number().int().min(5).max(360),
    intensity: z.enum(['low', 'medium', 'high']),
    exercises: z.array(exerciseSchema).min(1),
  }).parse(req.body);
  const xpEarned = xpForWorkout(body.duration, body.intensity, body.exercises);
  const workout = await prisma.workout.create({ data: { ...body, source: 'program', userId: authId(req), exercises: jsonValue(body.exercises), xpEarned } });
  await awardXp(authId(req), xpEarned, 'programmed workout');
  const card = await progressCard(authId(req), exerciseGains(body.type, body.exercises, body.duration, body.intensity), 'programmed training');
  await applyChallengeProgress(authId(req), 'programWorkout', 1);
  await applyChallengeProgress(authId(req), 'trainingMinutes', body.duration);
  if (['running', 'football', 'cycling'].includes(body.type)) await applyChallengeProgress(authId(req), 'paceTraining', 1);
  if (body.type === 'gym') await applyChallengeProgress(authId(req), 'physicalTraining', 1);
  const readiness = await calculateReadiness(authId(req));
  res.status(201).json({ workout, card, readiness });
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
    bodyFat: z.coerce.number().min(1).max(70).optional(),
    hydration: z.coerce.number().min(0).max(20).optional(),
  }).parse(req.body);
  const metric = await prisma.healthMetric.create({ data: { ...body, userId: authId(req) } });
  const readiness = await calculateReadiness(authId(req));
  if (readiness.score >= 70) await progressCard(authId(req), { physical: 1 }, 'recovery consistency');
  res.status(201).json({ metric, readiness });
}));

app.get('/api/challenges', auth, asyncRoute(async (req, res) => {
  await ensureChallenges(authId(req));
  const items = await prisma.userChallenge.findMany({
    where: {
      userId: authId(req),
      challenge: { isActive: true },
      OR: [
        { challenge: { period: 'daily' }, periodStart: startOfPeriod('daily') },
        { challenge: { period: 'weekly' }, periodStart: startOfPeriod('weekly') },
        { challenge: { period: 'campaign' }, periodStart: startOfPeriod('campaign') },
      ],
    },
    include: { challenge: true },
    orderBy: [{ challenge: { period: 'asc' } }, { createdAt: 'asc' }],
  });
  res.json({ items, resets: resetTimes() });
}));
app.post('/api/challenges/:id/progress', auth, asyncRoute(async (req, res) => {
  res.status(403).json({ error: 'Objectives only progress from verified training, tests, and wearable syncs.' });
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
    broadJumpCm: z.coerce.number().positive().max(500).optional(),
    agility505Seconds: z.coerce.number().positive().max(30).optional(),
    shuttleRunSeconds: z.coerce.number().positive().max(60).optional(),
    pushUps: z.coerce.number().int().positive().max(300).optional(),
    pullUps: z.coerce.number().int().positive().max(100).optional(),
    squatKg: z.coerce.number().positive().max(500).optional(),
    benchKg: z.coerce.number().positive().max(400).optional(),
    deadliftKg: z.coerce.number().positive().max(600).optional(),
    passingScore: z.coerce.number().int().min(0).max(100).optional(),
    dribbleSeconds: z.coerce.number().positive().max(120).optional(),
    shootingScore: z.coerce.number().int().min(0).max(100).optional(),
    notes: z.string().trim().max(280).optional(),
    testedAt: z.coerce.date().optional(),
  }).parse(req.body);
  if (!Object.values(body).some((value) => typeof value === 'number')) return res.status(400).json({ error: 'Log at least one test result.' });
  const xpEarned = 70 + Object.values(body).filter((value) => typeof value === 'number').length * 12;
  const test = await prisma.fitnessTest.create({ data: { ...body, xpEarned, userId: authId(req) } });
  const [xp, _smallGain] = await Promise.all([
    awardXp(authId(req), xpEarned, 'fitness tests'),
    progressCard(authId(req), testGains(body), 'fitness tests'),
    applyChallengeProgress(authId(req), 'tests', 1),
  ]);
  const card = await applyTestBenchmarks(authId(req), testBenchmarks(body));
  const readiness = await calculateReadiness(authId(req));
  res.status(201).json({ test, xp, card, readiness });
}));
app.get('/api/dashboard', auth, asyncRoute(async (req, res) => {
  const monday = new Date();
  monday.setUTCHours(0, 0, 0, 0);
  monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay() + 6) % 7));
  const [user, recentWorkouts, workoutsThisWeek, notifications, readiness, streak, wearable] = await Promise.all([
    prisma.user.findUniqueOrThrow({ where: { id: authId(req) }, select: { ...selectUser, playerCard: true, avatarLoadout: true } }),
    prisma.workout.findMany({ where: { userId: authId(req) }, orderBy: { completedAt: 'desc' }, take: 5 }),
    prisma.workout.count({ where: { userId: authId(req), completedAt: { gte: monday } } }),
    prisma.notification.findMany({ where: { userId: authId(req) }, orderBy: { createdAt: 'desc' }, take: 6 }),
    calculateReadiness(authId(req)),
    recentStreak(authId(req)),
    prisma.wearable.upsert({ where: { userId: authId(req) }, create: { userId: authId(req) }, update: {} }),
  ]);
  res.json({ user: { ...user, matchReadiness: readiness.score }, recentWorkouts, notifications, stats: { totalXp: user.xp, workoutsThisWeek, streak }, xp: levelState(user.xp), readiness, wearable: publicWearable(wearable), googleHealthReady: googleHealthConfig().ready, resets: resetTimes() });
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
  const trackerQuery = new URLSearchParams({
    dataSourceFamily: 'users/me/dataSourceFamilies/google-wearables',
    filter: `sleep.interval.civil_end_time >= "${todayDateString()}"`,
  }).toString();
  const [stepsResult, sleepResult, heartResult] = await Promise.allSettled([
    googleHealthPost<{ rollupDataPoints?: Array<{ steps?: { countSum?: string } }> }>('/v4/users/me/dataTypes/steps/dataPoints:dailyRollUp', accessToken, body),
    googleHealthGet<{ dataPoints?: Array<{ sleep?: { summary?: { minutesAsleep?: string } } }> }>(`/v4/users/me/dataTypes/sleep/dataPoints:reconcile?${trackerQuery}`, accessToken),
    googleHealthPost<{ rollupDataPoints?: Array<{ heartRate?: { beatsPerMinuteAvg?: number } }> }>('/v4/users/me/dataTypes/heart-rate/dataPoints:dailyRollUp', accessToken, body),
  ]);
  const errors = [stepsResult, sleepResult, heartResult]
    .filter((result): result is PromiseRejectedResult => result.status === 'rejected')
    .map((result) => result.reason instanceof Error ? result.reason.message : String(result.reason));
  const steps = stepsResult.status === 'fulfilled' ? stepsResult.value : undefined;
  const sleep = sleepResult.status === 'fulfilled' ? sleepResult.value : undefined;
  const heart = heartResult.status === 'fulfilled' ? heartResult.value : undefined;
  const totalSteps = steps?.rollupDataPoints?.reduce((sum, item) => sum + Number(item.steps?.countSum || 0), 0) || null;
  const sleepMinutes = sleep?.dataPoints?.reduce((sum, item) => sum + Number(item.sleep?.summary?.minutesAsleep || 0), 0) || null;
  const heartValues = heart?.rollupDataPoints?.map((item) => Number(item.heartRate?.beatsPerMinuteAvg || 0)).filter(Boolean);
  const heartRate = heartValues?.length ? Math.round(heartValues.reduce((sum, value) => sum + value, 0) / heartValues.length) : null;
  if (!totalSteps && !sleepMinutes && !heartRate) {
    return res.status(502).json({ error: errors.length ? errors.join(' | ') : 'Google Health returned no tracker data for today.' });
  }
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
  res.json({ device: publicWearable(device), readiness, warnings: errors });
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
