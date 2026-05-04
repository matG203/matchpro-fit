import { Router, Response } from 'express';
import { z } from 'zod';
import { prisma } from '../utils/prisma';
import { authenticate, AuthRequest } from '../middleware/auth';

export const settingsRouter = Router();

settingsRouter.get('/', authenticate, async (req: AuthRequest, res: Response) => {
  const settings = await prisma.userSettings.findUnique({ where: { userId: req.userId } });
  const supplements = await prisma.supplementReminder.findMany({ where: { userId: req.userId } });
  const equipment = await prisma.userEquipment.findMany({ where: { userId: req.userId } });
  const dietary = await prisma.dietaryPreference.findMany({ where: { userId: req.userId } });
  return res.json({ settings, supplements, equipment: equipment.map((e) => e.equipment), dietary: dietary.map((d) => d.preference) });
});

settingsRouter.put('/', authenticate, async (req: AuthRequest, res: Response) => {
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

settingsRouter.put('/equipment', authenticate, async (req: AuthRequest, res: Response) => {
  const { equipment } = req.body as { equipment: string[] };
  await prisma.userEquipment.deleteMany({ where: { userId: req.userId } });
  if (equipment?.length) {
    await prisma.userEquipment.createMany({ data: equipment.map((e) => ({ userId: req.userId!, equipment: e })) });
  }
  return res.json({ success: true });
});

settingsRouter.put('/supplements', authenticate, async (req: AuthRequest, res: Response) => {
  const { supplements } = req.body as { supplements: Array<{ name: string; timing: string }> };
  await prisma.supplementReminder.deleteMany({ where: { userId: req.userId } });
  if (supplements?.length) {
    await prisma.supplementReminder.createMany({ data: supplements.map((s) => ({ userId: req.userId!, ...s })) });
  }
  return res.json({ success: true });
});
