# Единая регистрация Мира: Telegram / MAX / email+пароль

Дата: 2026-09-25  
Статус: approved

## Цель

Один `player` на родителя. Три входа синхронизируются:

| Где | Вход | Подтверждение | Пароль |
|-----|------|---------------|--------|
| Telegram | кнопка «Мир» + initData | номер через «Поделиться контактом» | сразу в анкете |
| MAX | мини-приложение + initData | код на email | сразу в анкете |
| Браузер | email + пароль | код на email при регистрации | сразу / вход |

Склейка: совпал подтверждённый **телефон** или подтверждённый **email** → один игрок.  
Восстановление: код на почту → **новый пароль** → сессия.

## Данные

- `player_identity.password_hash` — pbkdf2 (`salt_hex$digest_hex`), общий модуль с админкой.
- Регистрация завершена: есть `password_hash` и (`phone_verified_at` или `email_verified_at`).
- После Telegram `confirm-bot`: ставятся и `phone_verified_at`, и `email_verified_at` (email заявлен + доказательство через TG).

## API

- `POST /registration/start` — `password` (min 8); channel `telegram` | `email`.
- `POST /registration/verify` — код email (браузер/MAX).
- `POST /registration/confirm-bot` — Telegram contact.
- `POST /api/v2/auth/login` — `{email, password}`.
- `POST /recovery/start` + `verify` → `reset_token`; `POST /recovery/password` → новый пароль + сессия.

## UI

- Анкета: пароль + повтор.
- Telegram: канал contact по умолчанию.
- MAX/браузер: email-код.
- «Уже есть аккаунт» → login; «Забыли пароль» → recovery.

## Вне скоупа

SMS; несколько детей на одного родителя; смена email без повторного подтверждения.
