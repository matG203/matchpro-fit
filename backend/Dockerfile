FROM node:22-alpine
WORKDIR /app/backend
COPY backend/package*.json ./
RUN npm install --include=dev
COPY backend/ .
RUN node_modules/.bin/prisma generate
EXPOSE 3001
CMD ["sh", "-c", "node_modules/.bin/prisma migrate deploy && node_modules/.bin/ts-node --transpile-only src/index.ts"]