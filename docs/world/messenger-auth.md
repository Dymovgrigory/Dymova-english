# Вход через Telegram / MAX и обязательная регистрация

Два связанных механизма:

1. **Гейт регистрации** — без заполненной анкеты, обязательных согласий (152-ФЗ)
   и подтверждённого телефона ученические API закрыты.
2. **Вход через мессенджер** — мини-приложение (Telegram / MAX) открывается
   сразу авторизованным: сервер проверяет подпись `initData`, находит или
   создаёт игрока и возвращает сессионный токен. Прогресс привязан к аккаунту
   мессенджера и сохраняется между устройствами.

## Гейт регистрации

Регистрация считается завершённой, когда у игрока есть `player_identity` с
`phone_verified_at` (анкета + согласия пишутся на `/api/v2/registration/start`,
телефон подтверждается на `/api/v2/registration/verify`; при
`PHONE_VERIFICATION_REQUIRED=0` код возвращается как `dev_code`).

Middleware `RegistrationGateMiddleware` (`world-backend/app/identity/gate.py`)
для всех `/api/v2/*` и `/api/world/*` с валидным `X-World-Player` проверяет
игрока; незарегистрированному отвечает:

```
HTTP 403
{"detail": {"code": "registration_required"}}
```

Открыты без регистрации:

- `POST /api/world/players` — создание игрока (bootstrap),
- `/api/v2/registration/*` — анкета, коды телефона, статус,
- `/api/world/auth/*` — вход через Telegram/MAX,
- `/api/v2/admin/*` — админка (свой Bearer),
- `/health`, статика и всё вне `/api/*`.

Старые игроки (созданные до фичи) незарегистрированы по определению — гейт
потребует анкету при следующем входе. Выключить гейт: `REGISTRATION_GATE=0`
(локальная отладка; по умолчанию включён).

Фронт: `AppGate` (`world/src/features/gate/AppGate.tsx`) обёрнут вокруг всех
страниц в `app/layout.tsx`. Открыты `/`, `/onboarding`, `/legal/*`, `/admin/*`.
Остальные: проверка `registration/status` → незарегистрированным показывается
экран с `RegistrationFlow` (режим `gate`, без кнопки «Заполню позже»).

## Вход через Telegram

1. В [@BotFather](https://t.me/BotFather): `/newapp` (или Menu Button) для
   бота, URL мини-приложения: `https://new.dymova-english.ru/world`.
2. `TELEGRAM_BOT_TOKEN=<токен бота>` в env бэкенда (`world-backend/.env`).
3. Клиент мини-приложения видит `window.Telegram.WebApp.initData` → фронт
   (`world/src/lib/messenger.ts`) шлёт `POST /api/world/auth/telegram
   {init_data}`.

Валидация на сервере (`app/identity/messenger.py`): data-check-string — все
поля кроме `hash`, отсортированные `key=value` через `\n`;
`secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)`;
`hash == HMAC_SHA256(key=secret_key, msg=data_check_string)` в hex; плюс
свежесть `auth_date` (≤ 24 ч).

## Вход через MAX

Аналогично: MAX mini apps используют ту же схему подписи HMAC
([dev.max.ru/docs/webapps/validation](https://dev.max.ru/docs/webapps/validation)).
Клиент: `window.WebApp.initData` → `POST /api/world/auth/max {init_data}`.
Токен бота MAX — в env `MAX_BOT_TOKEN`. Бот и мини-приложение заводятся на
платформе MAX для партнёров; URL тот же `https://new.dymova-english.ru/world`.

Если токен провайдера не задан — `503 {"detail": {"code": "provider_not_configured"}}`.

## Привязка аккаунтов

Таблица `external_identities` (provider, provider_user_id, player_id,
UNIQUE(provider, provider_user_id)). Первый вход создаёт игрока с
`external_key = "{provider}:{user_id}"` и `display_name` из профиля
мессенджера; повторный — отдаёт того же игрока. Ответ обоих эндпоинтов:
`{token, ...player, is_registered}` — `token` кладётся в
`localStorage world.playerToken`, при `is_registered=false` фронт показывает
гейт регистрации (имя предзаполнено из профиля мессенджера).

## Тестирование

Валидный `init_data` в тестах фабрикуется тем же алгоритмом с тестовым
токеном (см. `world-backend/tests/test_messenger_auth.py::make_init_data`):
пары `auth_date`/`user`/`query_id` → подпись тестовым `TELEGRAM_BOT_TOKEN` →
`urlencode(pairs) + "&hash=" + signature`.

- Бэкенд: `cd world-backend && .venv/bin/python -m pytest -q`
  (`test_registration_gate.py`, `test_messenger_auth.py`).
- Фронт: `cd world && npx vitest run`
  (`src/lib/messenger.test.ts`, `src/features/gate/AppGate.test.tsx`).
- Ручная проверка в Telegram: открыть мини-приложение из бота — вход должен
  пройти без онбординга; в браузере вне мессенджера — обычный онбординг.
