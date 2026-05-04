import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';

export const profileRouter = Router();

profileRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const profile = await prisma.profile.findUnique({ where: { userId: req.userId } });
  return res.json(profile);
});

profileRouter.put(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const schema = z.object({
    displayName: z.string().min(1).max(50).optional(),
    heightCm: z.number().optional(),
    weightKg: z.number().optional(),
    country: z.string().optional(),
    timezone: z.string().optional(),
    units: z.enum([''metric'', ''imperial'']).optional(),
    position: z.string().optional(),
    footballLevel: z.string().optional(),
  });
  try {
    const data = schema.parse(req.body);
    const profile = await prisma.profile.update({ where: { userId: req.userId }, data });
    return res.json(profile);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});
