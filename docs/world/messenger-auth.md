# Вход через Telegram / MAX и обязательная регистрация

Два связанных механизма:

1. **Гейт регистрации** — без заполненной анкеты, обязательных согласий (152-ФЗ),
   пароля и подтверждённого контакта родителя ученические API закрыты.
2. **Вход через мессенджер** — мини-приложение (Telegram / MAX) открывается
   сразу авторизованным: сервер проверяет подпись `initData`, находит или
   создаёт игрока и возвращает сессионный токен. Прогресс привязан к аккаунту
   мессенджера и сохраняется между устройствами.

## Гейт регистрации

Регистрация считается завершённой, когда у игрока есть `player_identity` с
паролем (`password_hash`) и подтверждённым контактом: `email_verified_at`
(код из письма на `/api/v2/registration/verify` — браузер и MAX) или
`phone_verified_at` (нативный контакт Telegram на `/api/v2/registration/confirm-bot`).
После Telegram `confirm-bot` выставляются **оба** флага (email заявлен + личность
доказана через TG) — сразу можно логиниться в браузере по email+пароль.

Анкета, пароль и согласия пишутся на `/api/v2/registration/start`. При
`EMAIL_VERIFICATION_REQUIRED=0` код возвращается как `dev_code` (тестовый режим).

Middleware `RegistrationGateMiddleware` (`world-backend/app/identity/gate.py`)
для всех `/api/v2/*` и `/api/world/*` с валидным `X-World-Player` проверяет
игрока; незарегистрированному отвечает:

```
HTTP 403
{"detail": {"code": "registration_required"}}
```

Открыты без регистрации:

- `POST /api/world/players` — создание игрока (bootstrap),
- `/api/v2/registration/*` — анкета, коды, recovery, статус,
- `/api/v2/auth/login` — вход email+пароль,
- `/api/world/auth/*` — вход через Telegram/MAX,
- `/api/v2/admin/*` — админка (свой Bearer),
- `/health`, статика и всё вне `/api/*`.

Фронт: `AppGate` — незарегистрированным показывает `RegistrationFlow` или
`LoginFlow` / `RecoveryFlow`.

## Три канала, один аккаунт

| Где | Вход | Подтверждение | Пароль |
|-----|------|---------------|--------|
| Telegram | кнопка «Мир» + initData | «Поделиться номером» | сразу в анкете |
| MAX | мини-приложение + initData | код на email | сразу в анкете |
| Браузер | email + пароль (`POST /api/v2/auth/login`) | код на email при регистрации | сразу / вход |

Склейка: совпал подтверждённый **телефон** или подтверждённый **email** → один
`player` (`_merge_into`). Привязки `telegram` / `max` в `external_identities`.

Восстановление: `recovery/start` → `recovery/verify` → `reset_token` →
`recovery/password` (новый пароль) → сессия.

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
Токен бота MAX — в env `MAX_BOT_TOKEN`. Нативного `requestContact` у MAX нет —
подтверждение при регистрации через код на email (канал `email`).

## Кнопка «Мир Фоксинбурга» в школьном боте

Существующий бот (`bot/`) показывает кнопку мира первой строкой меню `/start`
и `/menu`:

- **Telegram** — inline web_app-кнопка: открывает мир с initData.
- **MAX** — link-кнопка / кнопка мини-приложения в кабинете MAX Бизнес.

URL: env `WORLD_APP_URL` бота (default `https://new.dymova-english.ru/world`).

## Подтверждение телефона через Telegram

1. `RegistrationFlow` в Telegram: channel=`telegram`, пароль в анкете.
2. `POST /registration/start` → `awaiting_bot` (письмо не шлётся).
3. «Поделиться номером» → `requestContact` → бот помечает `phone_confirmed`.
4. `POST /registration/confirm-bot` → `phone_verified_at` + `email_verified_at`.

## SMTP

`EMAIL_VERIFICATION_REQUIRED=1` + `WORLD_SMTP_*` — реальные письма.
Иначе fake-провайдер и `dev_code` в ответе.

## Тестирование

- Бэкенд: `cd world-backend && .venv/bin/python -m pytest -q`
- Фронт: `cd world && npx vitest run src/features/registration src/features/recovery src/features/gate`
- Ручная проверка: Telegram «Мир Фоксинбурга» → анкета + пароль + контакт;
  браузер — login email/пароль тем же аккаунтом.
