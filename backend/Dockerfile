FROM node:22-alpine
WORKDIR /app
COPY . .
RUN npm install --include=dev
RUN npx prisma generate
EXPOSE 3001
CMD ["sh, -c, npx prisma migrate deploy && npx ts-node --transpile-only src/index.ts]