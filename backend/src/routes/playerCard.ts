import { Router, Response } from ''express'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { recalculatePlayerCard } from ''../services/xpService'';

export const playerCardRouter = Router();

playerCardRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const card = await prisma.playerCard.findUnique({ where: { userId: req.userId } });
  const profile = await prisma.profile.findUnique({ where: { userId: req.userId } });
  const avatar = await prisma.avatar.findUnique({ where: { userId: req.userId } });
  return res.json({ card, profile, avatar });
});

playerCardRouter.post(''/recalculate'', authenticate, async (req: AuthRequest, res: Response) => {
  const result = await recalculatePlayerCard(req.userId!);
  return res.json(result);
});

playerCardRouter.get(''/history'', authenticate, async (req: AuthRequest, res: Response) => {
  const history = await prisma.playerStatHistory.findMany({
    where: { userId: req.userId },
    orderBy: { createdAt: ''desc'' },
    take: 50,
  });
  return res.json(history);
});
