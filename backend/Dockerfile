FROM node:22-alpine
WORKDIR /app
COPY . .
RUN npm install
RUN ./node_modules/.bin/prisma generate
EXPOSE 3001
CMD ["sh, -c, ./node_modules/.bin/prisma migrate deploy && npx ts-node --transpile-only src/index.ts]