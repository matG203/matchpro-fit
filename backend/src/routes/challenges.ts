port { Router, Response } from ''express'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { ensureDailyChallenges, ensureWeeklyChallenges, completeChallenge } from ''../services/challengeService'';

export const challengesRouter = Router();

challengesRouter.get(''/daily'', authenticate, async (req: AuthRequest, res: Response) => {
  const challenges = await ensureDailyChallenges(req.userId!);
  return res.json(challenges);
});

challengesRouter.get(''/weekly'', authenticate, async (req: AuthRequest, res: Response) => {
  const challenges = await ensureWeeklyChallenges(req.userId!);
  return res.json(challenges);
});

challengesRouter.post(''/:id/complete'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const result = await completeChallenge(req.userId!, req.params.id);
    return res.json(result);
  } catch (err) {
    return res.status(400).json({ error: (err as Error).message });
  }
});
