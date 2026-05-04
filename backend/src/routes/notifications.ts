import { Router, Response } from ''express'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';

export const notificationsRouter = Router();

notificationsRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const notifications = await prisma.notification.findMany({
    where: { userId: req.userId },
    orderBy: { createdAt: ''desc'' },
    take: 50,
  });
  return res.json(notifications);
});

notificationsRouter.post(''/read'', authenticate, async (req: AuthRequest, res: Response) => {
  const { ids } = req.body as { ids?: string[] };
  if (ids?.length) {
    await prisma.notification.updateMany({ where: { id: { in: ids }, userId: req.userId }, data: { isRead: true } });
  } else {
    await prisma.notification.updateMany({ where: { userId: req.userId }, data: { isRead: true } });
  }
  return res.json({ success: true });
});
