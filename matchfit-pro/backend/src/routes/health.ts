mport { Router, Response } from 'express';
import { z } from 'zod';
import { prisma } from '../utils/prisma';
import { authenticate, AuthRequest } from '../middleware/auth';
import { awardXp, XP_REWARDS } from '../services/xpService';
import { startOfDay } from 'date-fns';

export const healthRouter = Router();

healthRouter.get('/', authenticate, async (req: AuthRequest, res: Response) => {
  const { days = '30', type } = req.query;
  const since = new Date(Date.now() - Number(days) * 24 * 60 * 60 * 1000);
  const where: Record<string, unknown> = { userId: req.userId, date: { gte: since } };
  if (type) where.metricType = type as string;
  const metrics = await prisma.healthMetric.findMany({ where, orderBy: { date: 'asc' } });
  const summaries = await prisma.dailySummary.findMany({
    where: { userId: req.userId, date: { gte: since } },
    orderBy: { date: 'asc' },
  });
  return res.json({ metrics, summaries });
});

healthRouter.post('/log-energy', authenticate, async (req: AuthRequest, res: Response) => {
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

    await awardXp(req.userId!, XP_REWARDS.energy_log, 'energy_log', 'Logged energy');
    return res.json(summary);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

healthRouter.post('/metric', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({
      date: z.string(),
      metricType: z.string(),
      value: z.number(),
      unit: z.string().optional(),
      source: z.string().default('manual'),
      notes: z.string().optional(),
    });
    const data = schema.parse(req.body);
    const metric = await prisma.healthMetric.create({
      data: { userId: req.userId!, ...data, date: new Date(data.date) },
    });
    await awardXp(req.userId!, XP_REWARDS.manual_health_log, 'health_log', `Logged ${data.metricType}`);
    return res.status(201).json(metric);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});
