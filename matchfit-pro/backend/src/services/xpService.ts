import { prisma } from '../utils/prisma';

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
          type: 'level_up',
          title: `Level Up! 🎉`,
          body: `You reached Level ${newLevel}! Keep grinding!`,
        },
      });
    }
  });
}

export function getCardTier(overall: number): string {
  if (overall >= 90) return 'elite';
  if (overall >= 85) return 'rare_gold';
  if (overall >= 75) return 'common_gold';
  if (overall >= 60) return 'silver';
  return 'bronze';
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
      orderBy: { date: 'desc' },
      take: 30,
    }),
  ]);

  if (!card) return;

  const speedWorkouts = workouts.filter((w) => w.category === 'speed' || w.category === 'agility');
  const staminaWorkouts = workouts.filter((w) => w.category === 'stamina');
  const strengthWorkouts = workouts.filter((w) => w.category === 'strength');
  const footballWorkouts = workouts.filter((w) => w.category === 'football_skill' || w.category === 'match_simulation');
  const recoveryWorkouts = workouts.filter((w) => w.category === 'recovery');

  const sprintTests = tests.filter((t) => t.testType === '20m_sprint');
  const avgSleep = summaries.length > 0 ? summaries.reduce((a, b) => a + (b.sleepHours || 7), 0) / summaries.length : 7;
  const avgSteps = summaries.length > 0 ? summaries.reduce((a, b) => a + (b.steps || 0), 0) / summaries.length : 0;

  const paceDelta = speedWorkouts.length * 0.3 + (sprintTests.length > 1 ? 1 : 0);
  const staminaDelta = staminaWorkouts.length * 0.4 + (avgSteps > 8000 ? 1 : 0);
  const physicalDelta = strengthWorkouts.length * 0.5;
  const shootingDelta = footballWorkouts.filter((w) => w.title.toLowerCase().includes('shoot')).length * 0.5;
  const passingDelta = footballWorkouts.filter((w) => w.title.toLowerCase().includes('pass')).length * 0.5;
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
