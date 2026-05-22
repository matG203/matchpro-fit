import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();
const challenges = [
  { title: 'Training Trio', description: 'Complete three workouts.', type: 'workouts', target: 3, xpReward: 180 },
  { title: '10K Engine', description: 'Log 10,000 steps in a health entry.', type: 'steps', target: 10000, xpReward: 140 },
  { title: 'Recovery Window', description: 'Log eight hours of sleep.', type: 'sleep', target: 8, xpReward: 120 },
  { title: 'Ready For Kickoff', description: 'Reach 75 match readiness.', type: 'readiness', target: 75, xpReward: 220 },
  { title: 'Testing Day', description: 'Log one fitness test block.', type: 'tests', target: 1, xpReward: 160 },
];

async function main() {
  if ((await prisma.challenge.count()) === 0) await prisma.challenge.createMany({ data: challenges });
}

main().finally(() => prisma.$disconnect());
