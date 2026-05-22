# MatchFit Pro

MatchFit Pro is a full-stack football fitness gamification app. Players register, finish onboarding, log workouts and health metrics, earn XP, unlock avatars, build FIFA-style cards, complete challenges, and compare progress with friends.

## Apps

- `backend/`: Node.js, Express, TypeScript, Prisma, JWT auth.
- `frontend/`: React, Vite, TypeScript, Tailwind CSS, Zustand.

## Local Run

Install dependencies inside each app folder:

```sh
cd backend
npm install
npx prisma generate
npm run build
node dist/index.js
```

```sh
cd frontend
npm install
npm run dev
```

The backend reads `DATABASE_URL`, `JWT_SECRET`, and `PORT`. The frontend reads `VITE_API_URL`; production uses the Railway API URL ending in `/api`.

Google Health live wearable sync additionally uses these Railway variables:

```text
GOOGLE_HEALTH_CLIENT_ID=
GOOGLE_HEALTH_CLIENT_SECRET=
GOOGLE_HEALTH_REDIRECT_URI=https://matchpro-fit-production-db0c.up.railway.app/api/wearables/google-health/callback
FRONTEND_URL=https://matchpro-fit.vercel.app
BACKEND_URL=https://matchpro-fit-production-db0c.up.railway.app
```

The Google Cloud OAuth redirect URL must exactly match `GOOGLE_HEALTH_REDIRECT_URI`.

## Deployment

Railway must build from `backend/Dockerfile` with repository root as the Docker build context. The Docker image runs compiled JavaScript from `dist/index.js`.

Vercel should use `frontend` as the project root and set:

```text
VITE_API_URL=https://matchpro-fit-production-db0c.up.railway.app/api
```

`frontend/vercel.json` includes the React Router fallback rewrite.
