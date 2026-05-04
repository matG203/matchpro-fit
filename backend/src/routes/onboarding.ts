port { Router, Response } from ''express'';
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
