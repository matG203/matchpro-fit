import { Router, Response } from 'express';
import { z } from 'zod';
import { prisma } from '../utils/prisma';
import { authenticate, AuthRequest } from '../middleware/auth';
import { awardXp, XP_REWARDS } from '../services/xpService';

export const wearablesRouter = Router();

wearablesRouter.get('/', authenticate, async (req: AuthRequest, res: Response) => {
  const connections = await prisma.wearableConnection.findMany({ where: { userId: req.userId } });
  return res.json(connections);
});

// ── Fitbit OAuth ─────────────────────────────────────────────────────────────
wearablesRouter.get('/fitbit/connect', authenticate, async (req: AuthRequest, res: Response) => {
  const clientId = process.env.FITBIT_CLIENT_ID;
  if (!clientId) return res.status(500).json({ error: 'Fitbit not configured' });
  const redirect = process.env.FITBIT_REDIRECT_URI;
  const scope = 'activity heartrate sleep weight profile';
  const url = `https://www.fitbit.com/oauth2/authorize?response_type=code&client_id=${clientId}&redirect_uri=${redirect}&scope=${encodeURIComponent(scope)}`;
  return res.json({ url });
});

wearablesRouter.get('/fitbit/callback', authenticate, async (req: AuthRequest, res: Response) => {
  // TODO: Exchange code for token using Fitbit API
  // For now, store placeholder connection
  const { code } = req.query;
  if (!code) return res.status(400).json({ error: 'No code provided' });
  await prisma.wearableConnection.upsert({
    where: { userId_provider: { userId: req.userId!, provider: 'fitbit' } },
    update: { isActive: true, metadata: { note: 'Token exchange required' } },
    create: { userId: req.userId!, provider: 'fitbit', isActive: true, metadata: { code } },
  });
  return res.json({ success: true, message: 'Fitbit connected (TODO: token exchange)' });
});

wearablesRouter.post('/fitbit/sync', authenticate, async (req: AuthRequest, res: Response) => {
  // TODO: Call Fitbit Web API with stored access token to pull real data
  await awardXp(req.userId!, XP_REWARDS.wearable_sync, 'wearable_sync', 'Synced Fitbit');
  await prisma.wearableConnection.update({
    where: { userId_provider: { userId: req.userId!, provider: 'fitbit' } },
    data: { lastSync: new Date() },
  });
  return res.json({ success: true, message: 'Fitbit sync triggered (TODO: real API call)' });
});

// ── Garmin ───────────────────────────────────────────────────────────────────
wearablesRouter.get('/garmin/connect', authenticate, (_req: AuthRequest, res: Response) => {
  // TODO: Garmin requires approved API partner access
  // Implement OAuth once approved: https://developer.garmin.com/gc-developer-program/overview/
  return res.json({ message: 'Garmin integration requires partner API approval. Connect manually below.' });
});

// ── Apple Health ──────────────────────────────────────────────────────────────
wearablesRouter.post('/apple-health/ingest', authenticate, async (req: AuthRequest, res: Response) => {
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
        source: 'apple',
      })),
      skipDuplicates: true,
    });
    await awardXp(req.userId!, XP_REWARDS.wearable_sync, 'wearable_sync', 'Apple Health sync');
    return res.json({ success: true, count: metrics.length });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

// ── Google Fit ────────────────────────────────────────────────────────────────
wearablesRouter.post('/google-health/ingest', authenticate, async (req: AuthRequest, res: Response) => {
  // TODO: Implement Google Health Connect OAuth and data pull
  return res.json({ message: 'Google Health Connect ingestion endpoint ready (TODO: OAuth implementation)' });
});

// ── Manual entry ──────────────────────────────────────────────────────────────
wearablesRouter.post('/manual', authenticate, async (req: AuthRequest, res: Response) => {
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
      .filter(([k, v]) => k !== 'date' && v !== undefined)
      .map(([type, value]) => ({ userId: req.userId!, metricType: type, value: value as number, date, source: 'manual' }));

    if (metrics.length > 0) {
      await prisma.healthMetric.createMany({ data: metrics });
    }

    await awardXp(req.userId!, XP_REWARDS.manual_health_log, 'manual_entry', 'Manual health data entry');
    return res.json({ success: true, count: metrics.length });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

// ── CSV Import ────────────────────────────────────────────────────────────────
wearablesRouter.post('/csv-import', authenticate, async (_req: AuthRequest, res: Response) => {
  // TODO: Parse uploaded CSV and bulk-insert health metrics
  return res.json({ message: 'CSV import endpoint ready (TODO: multipart upload + CSV parser)' });
});

wearablesRouter.delete('/:provider', authenticate, async (req: AuthRequest, res: Response) => {
  await prisma.wearableConnection.update({
    where: { userId_provider: { userId: req.userId!, provider: req.params.provider } },
    data: { isActive: false, accessToken: null, refreshToken: null },
  });
  return res.json({ success: true });
});
