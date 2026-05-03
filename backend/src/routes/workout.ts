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
