FROM node:22-alpine
WORKDIR /app
COPY . .
RUN npm install --include=dev && npm install prisma@5.10.0 --save-dev
RUN node_modules/.bin/prisma generate
EXPOSE 3001
CMD ["sh, -c, node_modules/.bin/prisma migrate deploy && node_modules/.bin/ts-node --transpile-only src/index.ts]