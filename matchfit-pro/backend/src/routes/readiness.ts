mport { Router, Response } from 'express';
import { prisma } from '../utils/prisma';
import { authenticate, AuthRequest } from '../middleware/auth';
import { calculateReadiness } from '../services/readinessService';

export const readinessRouter = Router();

readinessRouter.get('/', authenticate, async (req: AuthRequest, res: Response) => {
  const latest = await prisma.readinessScore.findFirst({
    where: { userId: req.userId },
    orderBy: { calculatedAt: 'desc' },
  });
  return res.json(latest || { score: 0 });
});

readinessRouter.post('/recalculate', authenticate, async (req: AuthRequest, res: Response) => {
  const score = await calculateReadiness(req.userId!);
  return res.json({ score });
});
