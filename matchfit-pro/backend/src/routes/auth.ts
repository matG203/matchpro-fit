mport { Router, Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { z } from 'zod';
import { prisma } from '../utils/prisma';
import { authenticate, AuthRequest } from '../middleware/auth';

export const authRouter = Router();

const registerSchema = z.object({
  email: z.string().email(),
  username: z.string().min(3).max(30).regex(/^[a-zA-Z0-9_]+$/),
  password: z.string().min(8),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string(),
});

authRouter.post('/register', async (req: Request, res: Response) => {
  try {
    const body = registerSchema.parse(req.body);
    const existing = await prisma.user.findFirst({
      where: { OR: [{ email: body.email }, { username: body.username }] },
    });
    if (existing) {
      return res.status(409).json({ error: 'Email or username already taken' });
    }
    const passwordHash = await bcrypt.hash(body.password, 12);
    const user = await prisma.user.create({
      data: {
        email: body.email,
        username: body.username,
        passwordHash,
        playerCard: {
          create: {
            overall: 45,
            tier: 'bronze',
            pace: Math.floor(Math.random() * 5) + 43,
            shooting: Math.floor(Math.random() * 5) + 43,
            passing: Math.floor(Math.random() * 5) + 43,
            dribbling: Math.floor(Math.random() * 5) + 43,
            defending: Math.floor(Math.random() * 5) + 43,
            physical: Math.floor(Math.random() * 5) + 43,
            stamina: Math.floor(Math.random() * 5) + 43,
            recovery: Math.floor(Math.random() * 5) + 43,
            composure: Math.floor(Math.random() * 5) + 43,
          },
        },
        avatar: { create: {} },
      },
    });
    const token = jwt.sign({ userId: user.id }, process.env.JWT_SECRET || 'dev-secret', { expiresIn: '30d' });
    return res.status(201).json({ token, userId: user.id, username: user.username });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

authRouter.post('/login', async (req: Request, res: Response) => {
  try {
    const body = loginSchema.parse(req.body);
    const user = await prisma.user.findUnique({ where: { email: body.email } });
    if (!user) return res.status(401).json({ error: 'Invalid credentials' });
    const valid = await bcrypt.compare(body.password, user.passwordHash);
    if (!valid) return res.status(401).json({ error: 'Invalid credentials' });
    const token = jwt.sign({ userId: user.id }, process.env.JWT_SECRET || 'dev-secret', { expiresIn: '30d' });
    return res.json({ token, userId: user.id, username: user.username });
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});

authRouter.get('/me', authenticate, async (req: AuthRequest, res: Response) => {
  const user = await prisma.user.findUnique({
    where: { id: req.userId },
    include: { profile: true, playerCard: true },
  });
  if (!user) return res.status(404).json({ error: 'User not found' });
  const { passwordHash: _pw, ...safeUser } = user;
  return res.json(safeUser);
});

authRouter.delete('/account', authenticate, async (req: AuthRequest, res: Response) => {
  await prisma.user.delete({ where: { id: req.userId } });
  return res.json({ message: 'Account deleted' });
});
