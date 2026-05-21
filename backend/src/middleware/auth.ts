import { NextFunction, Request, Response } from 'express';
import jwt from 'jsonwebtoken';

export interface AuthRequest extends Request {
  userId: string;
}

export const jwtSecret = () => process.env.JWT_SECRET || 'matchfit-dev-secret';

export function auth(req: Request, res: Response, next: NextFunction) {
  const token = req.headers.authorization?.replace(/^Bearer\s+/i, '');
  if (!token) return res.status(401).json({ error: 'Authentication required' });

  try {
    const payload = jwt.verify(token, jwtSecret()) as { userId?: string };
    if (!payload.userId) throw new Error('Missing user');
    (req as AuthRequest).userId = payload.userId;
    return next();
  } catch {
    return res.status(401).json({ error: 'Invalid or expired token' });
  }
}
