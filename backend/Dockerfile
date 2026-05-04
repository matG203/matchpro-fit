FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
COPY prisma ./prisma/
RUN npm install
RUN npx prisma generate
COPY . .
EXPOSE 3001
CMD ["sh, -c, npx prisma migrate deploy && npx ts-node --transpile-only src/index.ts]