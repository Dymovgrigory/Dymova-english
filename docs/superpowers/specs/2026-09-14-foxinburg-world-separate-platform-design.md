# Foxinburg World — отдельная платформа (не CRM, не бот)

Дата: 2026-09-14. Статус: утверждено владельцем (вариант A).
Контекст: `docs/world/architecture.md` (устаревает в части «backend = модуль бота»),
игровой цикл School Hub уже работает в браузере
(`docs/superpowers/specs/2026-09-13-foxinburg-world-game-loop-design.md`).

## 1. Цель

Сделать World **отдельной игровой платформой** в том же git-репозитории:
свой процесс, своя БД, свои игроки. Бот школы, BigBen CRM и miniapp-auth
**не используются и не планируются** на этом этапе.

Игровой цикл School Hub (двор → школа → Фокси → vocabulary → награда)
не переписывается. Меняется только то, **кто** отдаёт `/api/world/*`.

## 2. Принятые решения

| Развилка | Решение | Причина |
|---|---|---|
| Репозиторий | Тот же `Dymova-english` | Бренд, GLB, словарь сайта рядом; не плодим второй git |
| Backend | Новый пакет `world-backend/` в корне, не `bot/app/world/` | Один процесс бота не должен знать про игру |
| Порт API (dev) | `8010` | `8000` занят ботом; фронт мира не должен путаться с ботом |
| БД v1 | Своя SQLite, путь `world-backend/data/world.sqlite` | Не `bot.db` и не `bot/data/world.sqlite`. Postgres — отдельный шаг после выноса |
| Игрок | Ник + заголовок `X-World-Player` | Не ученик CRM, не Telegram/MAX initData |
| Прод бота | Маршруты мира **не** монтируются | Игра не должна открываться на `bot.dymova-english.ru` |

Отвергнуто: отдельный репозиторий (вариант B); оставить API в боте без вызовов CRM (вариант C).

## 3. Границы

**World включает:** игроки мира, XP/FoxCoins ledger, квесты, активности,
инвентарь, unlocks, 3D-клиент `world/`, пайплайн ассетов `world-pipeline/`.

**World не включает:** заявки, ученики, расписание, счета, Control Center,
MAX/Telegram, `/api/lead`, miniapp школы.

Жёсткое правило: в `world-backend/` и `world/` запрещены импорты
`app.crm*`, `miniapp_auth`, BigBen-клиентов и `bot.app` вообще.
Обратно: `bot/` не импортирует `world_backend`.

Идентичность мира — только игровой ключ. Связка «игрок ↔ ученик школы»
не делается, даже как «следующий шаг в комментариях кода».

## 4. Целевая раскладка

```
world-backend/                 FastAPI только мира
  app/world/                   перенос файлов из bot/app/world/ (api, core, db, …)
  tests/                       перенос test_world*.py (кроме флага бота)
  data/world.sqlite            gitignored
  requirements.txt             fastapi, uvicorn, pydantic — без CRM-стека бота
  main.py                      CORS + роутер /api/world + seed_quests
  .env.example

world/                         Next.js как сейчас
  NEXT_PUBLIC_WORLD_API=http://localhost:8010

bot/                           школьный бот; мира нет
```

Импорты остаются `from app.world …`, но `PYTHONPATH` — каталог `world-backend/`,
не `bot/`. Это другой процесс: пакет `app` бота сюда не попадает.
Тесты гоняются из `world-backend/`, не из `bot/`.
`test_world_feature_flag.py` не переносится: флага больше нет; вместо него —
проверка, что бот не монтирует `/api/world`.

HTTP-контракт `/api/world/*` и заголовок `X-World-Player` **не меняются**.
Клиент `world/src/lib/api.ts` меняет только базовый URL по умолчанию:
`http://localhost:8010`.

## 5. Вырезание из бота

Удалить из `bot/`:

- каталог `bot/app/world/`
- `WORLD_API_ENABLED` в `bot/app/config.py` и `bot/.env.example`
- условный CORS GET / `X-World-Player` в `bot/app/main.py`
- `seed_quests` на старте бота
- `include_router` мира
- `bot/tests/test_world.py`, `test_world_api.py`, `test_world_activities.py`,
  `test_world_vocabulary.py`, `test_world_feature_flag.py`

После выноса полный сьют бота (`cd bot && pytest -q`) проходит **без**
world-тестов; число тестов бота меньше на число перенесённых. Регрессия
бота: нет 404/500 на бывших `/api/world/*` — маршрутов нет (404), это
ожидаемо.

Флаг `WORLD_API_ENABLED` не сохраняем «на всякий случай»: мира в боте нет.

## 6. Свой процесс World

`world-backend/main.py`:

- CORS: `http://localhost:3000`, `http://localhost:3002` (и позже origin
  прода мира, когда появится). Не `SITE_CORS_ORIGINS` бота.
- Методы: GET, POST. Заголовки: `Content-Type`, `X-World-Player`.
- Старт: миграции SQLite + `seed_quests`.
- Health: `GET /health` → `{ok: true}` без проверок LLM/MAX/BigBen.

Запуск dev:

```bash
cd world-backend && uvicorn main:app --port 8010
cd world && npm run dev
```

Compose мира — отдельный файл `world-backend/docker-compose.yml` (или
профиль), не сервис внутри `bot/docker-compose.yml`. На этом шаге достаточно
локального uvicorn; прод-деплой мира на ВМ бота **не** делаем.

`WORLD_DB_PATH` по умолчанию указывает в `world-backend/data/world.sqlite`.
`WORLD_DATABASE_URL` (Postgres) не реализуем в этом плане: заглушка
«ещё не подключено» может остаться, но не блокирует SQLite-dev.

## 7. Документы, которые лгут сейчас

При выносе поправить одной правкой смысла (не переписывать бриф целиком):

- `docs/world/architecture.md` §1 и §3: backend больше не модуль FastAPI-бота;
  auth больше не «реиспольз miniapp + CRM child».
- `world/README.md` и `world/.env.example`: API на `:8010`, не `bot/` `:8000`.
- Комментарии в `bot/app/world/api.py` про «следующий шаг miniapp-auth/CRM»
  уезжают вместе с файлом и **вычёркиваются** — такого шага нет.
- `DEVLOG.md`: запись сессии + блок «где остановились» про отдельную платформу.

## 8. Ошибки и совместимость

- Старый URL `http://localhost:8000/api/world/*`: после выноса 404 (бот)
  или отсутствие маршрута. Это не баг — клиент обязан ходить на `:8010`.
- Локальный `bot/.env` с `SITE_CORS_ORIGINS` под порты мира: после выноса
  эти origin'ы миру не нужны; боту достаточно продовых origin'ов сайта.
- Данные `bot/data/world.sqlite` не мигрируем автоматически: dev-прогресс
  пересоздаётся на новой БД. Прод-мира ещё не было.

## 9. Проверки готовности

1. `cd world-backend && pytest -q` — все бывшие world-тесты зелёные
   (импорты `app.world` с `PYTHONPATH` пакета, не бота).
2. В `world-backend/` нет упоминаний crm / bigben / miniapp_auth
   (поиск по дереву).
3. `cd bot && pytest -q` — зелёный, без world-тестов; импорта `app.world` нет.
4. `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/world/player`
   при запущенном боте → `404`.
5. Живой цикл в браузере: фронт `:3000`/`:3002` + API `:8010` — boot → двор
   → школа → Фокси → 5 слов → награда. CORS без ошибок в консоли.
6. `cd world && npm test && npm run build` — как сейчас.

## 10. Вне скоупа этого выноса

- Postgres-слой.
- Отдельный домен/прод-деплой мира.
- Модель школы через Meshy, зона Library Courtyard, звук.
- Регистрация email/пароль (достаточно текущего ключа игрока).
- Новый git-репозиторий.
