mport { prisma } from '../utils/prisma';

export async function calculateReadiness(userId: string): Promise<number> {
  const fourteenDaysAgo = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000);
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);

  const [workouts, summaries, tests, goal] = await Promise.all([
    prisma.workout.findMany({ where: { userId, completedAt: { gte: thirtyDaysAgo } } }),
    prisma.dailySummary.findMany({ where: { userId, date: { gte: fourteenDaysAgo } }, orderBy: { date: 'desc' } }),
    prisma.manualTestResult.findMany({ where: { userId }, orderBy: { testedAt: 'desc' } }),
    prisma.goal.findFirst({ where: { userId, isActive: true }, orderBy: { createdAt: 'desc' } }),
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
  const footballWorkouts = workouts.filter((w) => ['football_skill', 'match_simulation', 'agility', 'speed'].includes(w.category));
  const footballConditioning = Math.min(15, footballWorkouts.length * 2.5);

  // 4. Strength / Physical (15 pts)
  const strengthWorkouts = workouts.filter((w) => w.category === 'strength');
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
