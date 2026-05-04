port { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { awardXp } from ''../services/xpService'';
import { startOfDay } from ''date-fns'';

export const routineRouter = Router();

routineRouter.get(''/today'', authenticate, async (req: AuthRequest, res: Response) => {
  const userId = req.userId!;
  const today = startOfDay(new Date());
  const checklist = await prisma.routineChecklist.findUnique({ where: { userId } });
  const completion = await prisma.routineCompletion.findUnique({
    where: { userId_date: { userId, date: today } },
  });
  return res.json({ checklist, completion });
});

routineRouter.post(''/complete'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({ itemId: z.string() });
    const { itemId } = schema.parse(req.body);
    const userId = req.userId!;
    const today = startOfDay(new Date());
    const checklist = await prisma.routineChecklist.findUnique({ where: { userId } });
    if (!checklist) return res.status(404).json({ error: ''No routine found'' });

    const existing = await prisma.routineCompletion.findUnique({
      where: { userId_date: { userId, date: today } },
    });

    let completedItems: string[] = existing ? (existing.completedItems as string[]) : [];
    if (!completedItems.includes(itemId)) completedItems.push(itemId);

    const items = checklist.items as Array<{ id: string; enabled: boolean }>;
    const enabledItems = items.filter((i) => i.enabled);
    const isFullyComplete = enabledItems.every((i) => completedItems.includes(i.id));
    const xpAwarded = isFullyComplete && !existing?.xpAwarded ? 25 : 0;

    const completion = await prisma.routineCompletion.upsert({
      where: { userId_date: { userId, date: today } },
      update: { completedItems, xpAwarded: existing?.xpAwarded || xpAwarded },
      create: {
        userId,
        routineChecklistId: checklist.id,
        date: today,
        completedItems,
        xpAwarded,
      },
    });

    if (xpAwarded > 0) {
      await awardXp(userId, xpAwarded, ''routine_complete'', ''Completed daily routine'');
    }

    return res.json({ completion, isFullyComplete });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

routineRouter.put(''/settings'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({ items: z.array(z.object({ id: z.string(), label: z.string(), time: z.string(), enabled: z.boolean() })) });
    const { items } = schema.parse(req.body);
    const checklist = await prisma.routineChecklist.update({
      where: { userId: req.userId },
      data: { items },
    });
    return res.json(checklist);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});
