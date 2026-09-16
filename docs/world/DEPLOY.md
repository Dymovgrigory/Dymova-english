# Деплой Foxinburg World

Прод-домены (A → `89.169.132.104`):

- UI: https://world.dymova-english.ru (пока DNS нет — превью https://new.dymova-english.ru)
- API: https://world-api.dymova-english.ru (на превью: тот же хост `new.` + `/api/world/*`)

## Docker на VM

Контейнеры `world-api` / `world-web` в сети `bot_default` (общая с Caddy).
Caddy резолвит их по имени сервиса.

```bash
cd ~/Dymova-english
git fetch origin && git checkout foxinburg-world-v1 && git pull

# один раз
umask 077
SECRET=$(openssl rand -hex 32)
cat > world/.env.production <<EOF
WORLD_PLAYER_SECRET=$SECRET
WORLD_CORS_ORIGINS=https://world.dymova-english.ru,https://new.dymova-english.ru
NEXT_PUBLIC_WORLD_API=https://new.dymova-english.ru
EOF

docker compose -f docker-compose.world.yml --env-file world/.env.production up -d --build
cd bot && docker compose up -d --force-recreate caddy
```

После A-записей `world` / `world-api` смени
`NEXT_PUBLIC_WORLD_API=https://world-api.dymova-english.ru` и пересобери `world-web`.

## База

SQLite в томе `world_data`. Postgres:

```bash
export WORLD_DATABASE_URL=postgresql://user:pass@host:5432/foxinburg_world
```

## Игрок

`WORLD_PLAYER_SECRET` включает HMAC в `X-World-Player`.

## Озвучка

Прод: **edge-tts** (`en-US-AriaNeural`). Локально на Mac — `say` Samantha.
Запасной — `espeak-ng`. Предгенерация:

```bash
cd world-backend && python scripts/pregen_tts.py
```
