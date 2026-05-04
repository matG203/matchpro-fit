mport express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import rateLimit from 'express-rate-limit';
import { authRouter } from './routes/auth';
import { profileRouter } from './routes/profile';
import { avatarRouter } from './routes/avatar';
import { onboardingRouter } from './routes/onboarding';
import { dashboardRouter } from './routes/dashboard';
import { workoutRouter } from './routes/workout';
import { challengesRouter } from './routes/challenges';
import { xpRouter } from './routes/xp';
import { leaderboardRouter } from './routes/leaderboard';
import { friendsRouter } from './routes/friends';
import { wearablesRouter } from './routes/wearables';
import { healthRouter } from './routes/health';
import { routineRouter } from './routes/routine';
import { testsRouter } from './routes/tests';
import { notificationsRouter } from './routes/notifications';
import { readinessRouter } from './routes/readiness';
import { playerCardRouter } from './routes/playerCard';
import { settingsRouter } from './routes/settings';
import { errorHandler } from './middleware/errorHandler';

const app = express();
const PORT = process.env.PORT || 3001;

app.use(helmet());
app.use(compression());
app.use(cors({
  origin: process.env.APP_URL || 'http://localhost:5173',
  credentials: true,
}));
app.use(express.json({ limit: '10mb' }));

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 200,
  standardHeaders: true,
  legacyHeaders: false,
});
app.use('/api', limiter);

app.get('/health', (_req, res) => res.json({ status: 'ok', app: 'MatchFit Pro' }));

app.use('/api/auth', authRouter);
app.use('/api/profile', profileRouter);
app.use('/api/avatar', avatarRouter);
app.use('/api/onboarding', onboardingRouter);
app.use('/api/dashboard', dashboardRouter);
app.use('/api/workouts', workoutRouter);
app.use('/api/challenges', challengesRouter);
app.use('/api/xp', xpRouter);
app.use('/api/leaderboards', leaderboardRouter);
app.use('/api/friends', friendsRouter);
app.use('/api/wearables', wearablesRouter);
app.use('/api/health', healthRouter);
app.use('/api/routine', routineRouter);
app.use('/api/tests', testsRouter);
app.use('/api/notifications', notificationsRouter);
app.use('/api/readiness', readinessRouter);
app.use('/api/player-card', playerCardRouter);
app.use('/api/settings', settingsRouter);

app.use(errorHandler);

app.listen(PORT, () => {
  console.log(`MatchFit Pro API running on port ${PORT}`);
});

export default app;
