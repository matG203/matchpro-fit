import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';
import { awardXp, XP_REWARDS } from ''../services/xpService'';

export const testsRouter = Router();

testsRouter.post(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({
      testType: z.string(),
      value: z.number(),
      unit: z.string().optional(),
      notes: z.string().optional(),
    });
    const data = schema.parse(req.body);
    const userId = req.userId!;

    // Check if this is an improvement
    const previous = await prisma.manualTestResult.findFirst({
      where: { userId, testType: data.testType },
      orderBy: { testedAt: ''desc'' },
    });

    const result = await prisma.manualTestResult.create({
      data: { userId, ...data },
    });

    let xpAwarded = 50;
    let isImprovement = false;

    if (previous) {
      // For time-based tests, lower is better; for reps, higher is better
      const timeBasedTests = [''20m_sprint'', ''5_10_5_shuttle'', ''cone_drill'', ''beep_test''];
      const improved = timeBasedTests.includes(data.testType)
        ? data.value < previous.value
        : data.value > previous.value;

      if (improved) {
        xpAwarded = XP_REWARDS.test_improvement;
        isImprovement = true;
        await prisma.notification.create({
          data: {
            userId,
            type: ''test_improvement'',
            title: ''New Personal Best! ðŸ†'',
            body: `You improved your ${data.testType.replace(/_/g, '' '')} result!`,
          },
        });
      }
    }

    await awardXp(userId, xpAwarded, ''test'', `Test: ${data.testType}`);
    return res.status(201).json({ result, xpAwarded, isImprovement });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

testsRouter.get(''/history'', authenticate, async (req: AuthRequest, res: Response) => {
  const results = await prisma.manualTestResult.findMany({
    where: { userId: req.userId },
    orderBy: { testedAt: ''desc'' },
  });
  return res.json(results);
});
