port { prisma } from ''../utils/prisma'';
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
