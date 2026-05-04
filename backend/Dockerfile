FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npx prisma generate --schema=./prisma/schema.prisma
EXPOSE 3001
CMD ["sh, -c, npx prisma migrate deploy --schema=./prisma/schema.prisma && npx ts-node --transpile-only src/index.ts]