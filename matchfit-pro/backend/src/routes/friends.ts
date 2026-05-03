import { Router, Response } from 'express';
import { z } from 'zod';
import { prisma } from '../utils/prisma';
import { authenticate, AuthRequest } from '../middleware/auth';

export const friendsRouter = Router();

friendsRouter.get('/', authenticate, async (req: AuthRequest, res: Response) => {
  const userId = req.userId!;
  const friendships = await prisma.friendship.findMany({
    where: { OR: [{ userAId: userId }, { userBId: userId }] },
    include: {
      userA: { include: { profile: true, playerCard: true, avatar: true } },
      userB: { include: { profile: true, playerCard: true, avatar: true } },
    },
  });
  const friends = friendships.map((f) => {
    const friend = f.userAId === userId ? f.userB : f.userA;
    return {
      id: f.id,
      userId: friend.id,
      username: friend.username,
      friendCode: friend.friendCode,
      displayName: friend.profile?.displayName || friend.username,
      overall: friend.playerCard?.overall || 45,
      tier: friend.playerCard?.tier || 'bronze',
      avatar: friend.avatar,
    };
  });
  return res.json(friends);
});

friendsRouter.get('/requests', authenticate, async (req: AuthRequest, res: Response) => {
  const requests = await prisma.friendRequest.findMany({
    where: { receiverId: req.userId, status: 'pending' },
    include: { sender: { include: { profile: true } } },
  });
  return res.json(requests);
});

friendsRouter.post('/request', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const schema = z.object({ usernameOrCode: z.string() });
    const { usernameOrCode } = schema.parse(req.body);
    const target = await prisma.user.findFirst({
      where: { OR: [{ username: usernameOrCode }, { friendCode: usernameOrCode }] },
    });
    if (!target) return res.status(404).json({ error: 'User not found' });
    if (target.id === req.userId) return res.status(400).json({ error: 'Cannot add yourself' });

    const existing = await prisma.friendship.findFirst({
      where: { OR: [{ userAId: req.userId, userBId: target.id }, { userAId: target.id, userBId: req.userId }] },
    });
    if (existing) return res.status(400).json({ error: 'Already friends' });

    const request = await prisma.friendRequest.upsert({
      where: { senderId_receiverId: { senderId: req.userId!, receiverId: target.id } },
      update: { status: 'pending' },
      create: { senderId: req.userId!, receiverId: target.id },
    });
    return res.status(201).json(request);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

friendsRouter.post('/accept', authenticate, async (req: AuthRequest, res: Response) => {
  const schema = z.object({ requestId: z.string() });
  const { requestId } = schema.parse(req.body);
  const request = await prisma.friendRequest.findUnique({ where: { id: requestId } });
  if (!request || request.receiverId !== req.userId) return res.status(404).json({ error: 'Request not found' });

  await prisma.$transaction([
    prisma.friendRequest.update({ where: { id: requestId }, data: { status: 'accepted' } }),
    prisma.friendship.create({ data: { userAId: request.senderId, userBId: request.receiverId } }),
  ]);
  return res.json({ success: true });
});

friendsRouter.post('/decline', authenticate, async (req: AuthRequest, res: Response) => {
  const schema = z.object({ requestId: z.string() });
  const { requestId } = schema.parse(req.body);
  await prisma.friendRequest.update({ where: { id: requestId }, data: { status: 'declined' } });
  return res.json({ success: true });
});

friendsRouter.delete('/:id', authenticate, async (req: AuthRequest, res: Response) => {
  await prisma.friendship.deleteMany({
    where: {
      OR: [
        { userAId: req.userId, userBId: req.params.id },
        { userAId: req.params.id, userBId: req.userId },
      ],
    },
  });
  return res.json({ success: true });
});
