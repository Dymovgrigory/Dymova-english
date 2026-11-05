# Личный кабинет Фоксинбург (Next.js 16, standalone).
# Сборка (на сервере, из корня репозитория):
#   docker compose -f docker-compose.lk.yml --env-file world/.env.production build lk-web
#
# Build-аргументы (прокидываются из docker-compose.lk.yml):
#   WORLD_API            — внутренний адрес world-backend из сети bot_default
#                          (прокси /api/lk/*, см. next.config.ts).
#   NEXT_PUBLIC_WORLD_URL — публичный URL Мира для SSO (кнопка «Войти в Мир»).

FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:24-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG WORLD_API=http://world-api:8010
ARG NEXT_PUBLIC_WORLD_URL=https://new.dymova-english.ru
ENV WORLD_API=$WORLD_API
ENV NEXT_PUBLIC_WORLD_URL=$NEXT_PUBLIC_WORLD_URL
RUN npm run build

FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=7100
ENV HOSTNAME=0.0.0.0
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
# картинки слов (/wimg) и Фокси (/foxi)
COPY --from=builder --chown=node:node /app/public ./public
USER node
EXPOSE 7100
CMD ["node", "server.js"]
