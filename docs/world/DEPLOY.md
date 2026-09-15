# Деплой Foxinburg World

## Процессы

- Клиент: `world/` — Next.js, порт 3002, переменная `NEXT_PUBLIC_WORLD_API`.
- Сервер: `world-backend/` — FastAPI, порт 8010.

```bash
cd world-backend && pip install -r requirements.txt
WORLD_PLAYER_SECRET=длинный-секрет uvicorn main:app --host 0.0.0.0 --port 8010
cd world && NEXT_PUBLIC_WORLD_API=https://world-api.example.com npm run build && npm start
```

## База

По умолчанию SQLite `world-backend/data/world.sqlite`.

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
