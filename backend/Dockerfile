FROM node:22-bookworm-slim
RUN apt-get update -y && apt-get install -y openssl libssl-dev ca-certificates
WORKDIR /app/backend
COPY backend/package*.json ./
RUN npm install --include=dev
COPY backend/ .
RUN node_modules/.bin/prisma generate
EXPOSE 3001
CMD ["node_modules/.bin/ts-node", "--transpile-only", "src/index.ts"]
