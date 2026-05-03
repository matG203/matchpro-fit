import { Router, Response } from ''express'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { xpToLevel, xpProgressInLevel } from ''../services/xpService'';
import { calculateReadiness } from ''../services/readinessService'';
import { ensureDailyChallenges } from ''../services/challengeService'';
import { startOfDay } from ''date-fns'';

export const dashboardRouter = Router();

dashboardRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const userId = req.userId!;
  const today = startOfDay(new Date());

  const [profile, card, todaySummary, wearables, notifications, dailyChallenges] = await Promise.all([
    prisma.profile.findUnique({ where: { userId } }),
    prisma.playerCard.findUnique({ where: { userId } }),
    prisma.dailySummary.findFirst({ where: { userId, date: { gte: today } } }),
    prisma.wearableConnection.findMany({ where: { userId, isActive: true } }),
    prisma.notification.findMany({ where: { userId, isRead: false }, orderBy: { createdAt: ''desc'' }, take: 5 }),
    ensureDailyChallenges(userId),
  ]);

  const latestReadiness = await prisma.readinessScore.findFirst({
    where: { userId },
    orderBy: { calculatedAt: ''desc'' },
  });

  const totalXp = card?.totalXp || 0;
  const level = xpToLevel(totalXp);
  const xpProgress = xpProgressInLevel(totalXp);

  const energyLevel = todaySummary?.energyLevel || null;
  const energyState = energyLevel ? (energyLevel >= 4 ? ''green'' : energyLevel >= 2 ? ''yellow'' : ''red'') : null;

  return res.json({
    profile,
    playerCard: card,
    readiness: latestReadiness?.score || 0,
    level,
    xpProgress,
    totalXp,
    todaySummary,
    energyState,
    wearables: wearables.map((w) => ({ provider: w.provider, lastSync: w.lastSync })),
    notifications,
    dailyChallenges,
  });
});
