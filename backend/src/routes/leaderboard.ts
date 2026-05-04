import { Router, Response } from ''express'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { startOfWeek } from ''date-fns'';

export const leaderboardRouter = Router();

leaderboardRouter.get(''/friends'', authenticate, async (req: AuthRequest, res: Response) => {
  const userId = req.userId!;
  const weekStart = startOfWeek(new Date(), { weekStartsOn: 1 });

  // Get all friend IDs
  const friendships = await prisma.friendship.findMany({
    where: { OR: [{ userAId: userId }, { userBId: userId }] },
  });
  const friendIds = friendships.map((f) => (f.userAId === userId ? f.userBId : f.userAId));
  const allIds = [userId, ...friendIds];

  const snapshots = await prisma.leaderboardSnapshot.findMany({
    where: { userId: { in: allIds }, weekStart: { gte: weekStart } },
    include: { user: { include: { profile: true, playerCard: true } } },
    orderBy: { weeklyXp: ''desc'' },
  });

  // Users without snapshots yet - create placeholder data
  const snapshotUserIds = snapshots.map((s) => s.userId);
  const missing = allIds.filter((id) => !snapshotUserIds.includes(id));
  const missingUsers = await prisma.user.findMany({
    where: { id: { in: missing } },
    include: { profile: true, playerCard: true },
  });

  const combined = [
    ...snapshots.map((s) => ({
      userId: s.userId,
      displayName: s.user.profile?.displayName || s.user.username,
      username: s.user.username,
      weeklyXp: s.weeklyXp,
      totalXp: s.totalXp,
      overall: s.overall,
      readiness: s.readiness,
      weeklySteps: s.weeklySteps,
      weeklyWorkouts: s.weeklyWorkouts,
      currentStreak: s.currentStreak,
      isCurrentUser: s.userId === userId,
    })),
    ...missingUsers.map((u) => ({
      userId: u.id,
      displayName: u.profile?.displayName || u.username,
      username: u.username,
      weeklyXp: 0,
      totalXp: u.playerCard?.totalXp || 0,
      overall: u.playerCard?.overall || 45,
      readiness: 0,
      weeklySteps: 0,
      weeklyWorkouts: 0,
      currentStreak: 0,
      isCurrentUser: u.id === userId,
    })),
  ].sort((a, b) => b.weeklyXp - a.weeklyXp);

  return res.json(combined);
});

leaderboardRouter.get(''/global'', authenticate, async (_req: AuthRequest, res: Response) => {
  const weekStart = startOfWeek(new Date(), { weekStartsOn: 1 });
  const snapshots = await prisma.leaderboardSnapshot.findMany({
    where: { weekStart: { gte: weekStart } },
    include: { user: { include: { profile: true, playerCard: true } } },
    orderBy: { weeklyXp: ''desc'' },
    take: 100,
  });
  return res.json(snapshots.map((s) => ({
    userId: s.userId,
    displayName: s.user.profile?.displayName || s.user.username,
    username: s.user.username,
    weeklyXp: s.weeklyXp,
    totalXp: s.totalXp,
    overall: s.overall,
    weeklyWorkouts: s.weeklyWorkouts,
  })));
});
