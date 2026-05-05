FROM node:22-bookworm-slim
WORKDIR /app/backend
RUN apt-get update -y && apt-get install -y openssl
COPY backend/package*.json ./
RUN npm install --include=dev
COPY backend/ .
RUN sed -i "s/origin: process.env.APP_URL || 'http:\/\/localhost:5173'/origin: true/" src/index.ts || true
RUN node_modules/.bin/prisma generate
EXPOSE 3001
CMD ["node_modules/.bin/ts-node", "--transpile-only", "src/index.ts"]