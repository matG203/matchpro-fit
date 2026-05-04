port { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { awardXp, xpToLevel, xpProgressInLevel } from ''../services/xpService'';

export const xpRouter = Router();

xpRouter.get(''/history'', authenticate, async (req: AuthRequest, res: Response) => {
  const events = await prisma.xPEvent.findMany({
    where: { userId: req.userId },
    orderBy: { createdAt: ''desc'' },
    take: 100,
  });
  const card = await prisma.playerCard.findUnique({ where: { userId: req.userId } });
  const totalXp = card?.totalXp || 0;
  return res.json({ events, totalXp, level: xpToLevel(totalXp), progress: xpProgressInLevel(totalXp) });
});

xpRouter.post(''/award'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({ amount: z.number().min(1).max(1000), source: z.string(), description: z.string().optional() });
    const { amount, source, description } = schema.parse(req.body);
    await awardXp(req.userId!, amount, source, description);
    return res.json({ success: true });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});
