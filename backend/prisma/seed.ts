import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  console.log('Seeding database...');

  // Demo user
  const passwordHash = await bcrypt.hash('matchfit123', 12);
  const user = await prisma.user.upsert({
    where: { email: 'demo@matchfitpro.com' },
    update: {},
    create: {
      email: 'demo@matchfitpro.com',
      username: 'matchfit_demo',
      passwordHash,
      profile: {
        create: {
          displayName: 'Demo Player',
          footballLevel: '5-a-side',
          position: 'CM',
          currentLevel: 3,
          energyBaseline: 3,
          stressBaseline: 2,
          onboardingDone: true,
          heightCm: 178,
          weightKg: 75,
          country: 'GB',
          timezone: 'Europe/London',
        },
      },
      avatar: { create: { kitColour: 'red', bootColour: 'black' } },
      playerCard: {
        create: {
          overall: 52,
          tier: 'bronze',
          pace: 54,
          shooting: 50,
          passing: 53,
          dribbling: 51,
          defending: 49,
          physical: 52,
          stamina: 53,
          recovery: 50,
          composure: 51,
          totalXp: 350,
          xpLevel: 1,
        },
      },
      userSettings: {
        create: {
          preferredWorkoutDays: ['Monday', 'Wednesday', 'Friday', 'Saturday'],
          maxWorkoutDuration: 60,
          minWorkoutDuration: 20,
        },
      },
    },
  });

  // Default goals
  await prisma.goal.upsert({
    where: { id: 'demo-goal' },
    update: {},
    create: {
      id: 'demo-goal',
      userId: user.id,
      mainGoal: 'get_match_fit',
      fitnessLevel: 3,
      targetDate: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000),
    },
  });

  // Routine checklist
  await prisma.routineChecklist.upsert({
    where: { userId: user.id },
    update: {},
    create: {
      userId: user.id,
      items: [
        { id: 'wake', label: 'Wake up', time: 'morning', enabled: true },
        { id: 'water', label: 'Drink water', time: 'morning', enabled: true },
        { id: 'breakfast', label: 'Breakfast', time: 'morning', enabled: true },
        { id: 'movement', label: 'Movement', time: 'afternoon', enabled: true },
        { id: 'recovery', label: 'Recovery block', time: 'evening', enabled: true },
        { id: 'sleep', label: 'Sleep', time: 'night', enabled: true },
      ],
    },
  });

  // Sample supplement reminders
  await prisma.supplementReminder.createMany({
    data: [
      { userId: user.id, name: 'Vitamin D', timing: 'morning' },
      { userId: user.id, name: 'Creatine', timing: 'morning' },
      { userId: user.id, name: 'Magnesium Glycinate', timing: 'bedtime' },
    ],
    skipDuplicates: true,
  });

  // Sample equipment
  await prisma.userEquipment.createMany({
    data: [
      { userId: user.id, equipment: 'dumbbells' },
      { userId: user.id, equipment: 'football' },
      { userId: user.id, equipment: 'resistance_bands' },
      { userId: user.id, equipment: 'foam_roller' },
    ],
    skipDuplicates: true,
  });

  console.log(`âœ… Seeded demo user: demo@matchfitpro.com / matchfit123`);
  console.log('âœ… Database seeded successfully');
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
