# Деплой Foxinburg World

Прод-домены (A → `89.169.132.104`):

- UI: https://world.dymova-english.ru
- API: https://world-api.dymova-english.ru

## Процессы

- Клиент: `world/` — Next.js, порт 3002, переменная `NEXT_PUBLIC_WORLD_API`.
- Сервер: `world-backend/` — FastAPI, порт 8010.

### Docker на VM (прод)

```bash
cd ~/Dymova-english
git fetch origin && git checkout foxinburg-world-v1 && git pull

# один раз: секрет игрока (не коммитить)
umask 077
SECRET=$(openssl rand -hex 32)
cat > world/.env.production <<EOF
WORLD_PLAYER_SECRET=$SECRET
WORLD_CORS_ORIGINS=https://world.dymova-english.ru
NEXT_PUBLIC_WORLD_API=https://world-api.dymova-english.ru
EOF

docker compose -f docker-compose.world.yml --env-file world/.env.production up -d --build
cd bot && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

Caddy-блоки в `bot/deploy/Caddyfile`: `world` / `world-api` → `host.docker.internal:3002` / `:8010`.

### Локально без Docker

```bash
cd world-backend && pip install -r requirements.txt
WORLD_PLAYER_SECRET=длинный-секрет uvicorn main:app --host 0.0.0.0 --port 8010
cd world && NEXT_PUBLIC_WORLD_API=http://127.0.0.1:8010 npm run build && npm start
```

## База

По умолчанию SQLite `world-backend/data/world.sqlite` (том `world_data` в Docker).

Postgres:

```bash
export WORLD_DATABASE_URL=postgresql://user:pass@host:5432/foxinburg_world
```

Слой `app/world/db.py` переводит SQLite-идиомы движка (`datetime('now')`,
`INSERT OR IGNORE`, `BEGIN IMMEDIATE`) и поднимает ту же схему. Миграции
идемпотентны. Это свой инстанс, не `bot.db`.

## Игрок

`WORLD_PLAYER_SECRET` включает HMAC-токен в `X-World-Player`. Клиент
получает `token` из `POST /api/world/players` и кладёт его в
`localStorage.world.playerToken`. Без секрета (dev) принимается сырой ключ.

## Озвучка

На macOS — `say`. На Linux — `espeak-ng` или `espeak`. Предгенерация:

```bash
cd world-backend && python scripts/pregen_tts.py
```
