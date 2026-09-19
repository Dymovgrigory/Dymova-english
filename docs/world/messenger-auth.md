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
телефон подтверждается на `/api/v2/registration/verify` кодом из SMS/звонка
либо на `/api/v2/registration/confirm-bot` через бота Telegram — см. ниже;
при `PHONE_VERIFICATION_REQUIRED=0` код возвращается как `dev_code`).

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

## Кнопка «🏰 Мир Фоксинбурга» в школьном боте

Существующий бот (`bot/`) показывает кнопку мира первой строкой меню `/start`
и `/menu`:

- **Telegram** — inline web_app-кнопка (`_telegram_menu_buttons` в
  `bot/app/main.py`): открывает мир прямо внутри Telegram с initData —
  вход проходит автоматически. Показывается всем (в отличие от «Личного
  кабинета»), регистрация перехватывается гейтом самого мира.
- **MAX** — link-кнопка (`_main_menu`): у MAX Bot API нет web_app-кнопок,
  нативный запуск мини-приложения привязывается к боту в кабинете
  MAX Бизнес (кнопка появляется в чате сама).

URL: env `WORLD_APP_URL` бота (default `https://new.dymova-english.ru/world`;
не-https значение скрывает кнопку).

Дополнительные точки входа:

- **Menu Button чата** (кнопка слева от поля ввода, видна постоянно): при
  старте бот вызывает `setChatMenuButton` с web_app-кнопкой «🏰 Мир
  Фоксинбурга» на весь бот (`telegram_client.set_menu_button`, вызов в
  startup `bot/app/main.py`). Сбой установки не роняет запуск.
- **Баннеры в мини-приложениях бота**: сверху Telegram ЛК
  (`bot/app/tgapp/index.html`, кнопка `#world-banner`; внутри Telegram клик
  закрывает мини-апп — человек попадает в чат с Menu Button, в браузере —
  новая вкладка) и MAX-приложения (`bot/app/miniapp/index.html`, обычная
  ссылка). Дизайн-правило «никаких системных emoji» соблюдено: иконка —
  фирменная голова Фокси + SVG-стрелка.

## Единая регистрация: мост бот → world (prefill анкеты)

Если родитель уже общался с ботом (оставил ФИО, телефон, день рождения
ребёнка), анкета мира предзаполняется этими данными — повторно вбивать не
нужно.

- Бот отдаёт `GET /world-bridge/profile?provider=…&user_id=…&ts=…&sign=…`
  (`bot/app/world_bridge.py`), где `sign = HMAC_SHA256(key=WORLD_BRIDGE_SECRET,
  msg="{provider}\n{user_id}\n{ts}")`, свежесть ts ≤ 300 c. Без секрета в env
  бота endpoint отвечает 404 (фича выключена). Данные — только непустые поля
  лида: `fio_parent`, `fio_child`, `birthday`, `phone`, плюс флаг
  `phone_confirmed: bool` (True — номер прислан нативным контактом Telegram).
- World-backend (`app/identity/bridge.py`, `fetch_bot_prefill`) при входе
  через мессенджер и **незавершённой** регистрации спрашивает бота
  (`WORLD_BOT_BRIDGE_URL`, default `http://bot:8000/world-bridge/profile` —
  обе машины в docker-сети `bot_default`; таймаут 2.5 с, fail-open: мир не
  зависит от доступности бота) и возвращает `prefill` в ответе
  `/api/world/auth/{telegram,max}`.
- Фронт (`buildRegistrationPrefill` в `lib/messenger.ts`) мапит: `fio_child`
  → имя/фамилия ученика, `birthday` ДД.ММ.ГГГГ → дата рождения, `phone` →
  телефон родителя. Подтверждение телефона всё равно обязательно — SMS/звонком
  или через бота Telegram (следующий раздел).

Env: `WORLD_BRIDGE_SECRET` (одинаковый в `bot/.env` и `world/.env.production`),
`WORLD_BOT_BRIDGE_URL` (на проде default уже верный).

## Подтверждение телефона через Telegram (без SMS)

Внутри Telegram WebApp регистрация предлагает третий канал «Telegram (без
SMS)» — он же дефолтный. SMS/звонок остаются для браузера и MAX.

1. Фронт (`RegistrationFlow`) видит `window.Telegram.WebApp.requestContact`
   (`supportsTelegramContact` в `lib/messenger.ts`) и показывает выбор канала.
2. `POST /api/v2/registration/start` с `channel: "telegram"`: анкета и
   согласия сохраняются, SMS **не** отправляется, `phone_verifications` не
   пишется, rate-limit кодов не применяется; ответ
   `{"status": "awaiting_bot", "cooldown_sec": 0, …}`.
3. Фронт показывает шаг «Подтверждение в Telegram»: кнопка «Поделиться
   номером» → системный `requestContact` → контакт уходит боту сообщением.
4. Бот помечает номер подтверждённым (`Lead.phone_confirmed=True`,
   `identify.handle_contact(..., confirmed=True)`) — только если
   `contact.user_id == from.id` (собственный контакт отправителя; чужая
   визитка из адресной книги подтверждением не считается). Номер, введённый
   текстом, флаг сбрасывает (`Lead.set_phone`).
5. Фронт зовёт `POST /api/v2/registration/confirm-bot` (с ретраями 3×2 с —
   бот на long-polling может отставать). Сервер (`service.confirm_via_bot`):
   нет анкеты → 409 `no_pending_verification`; уже подтверждён → 200
   идемпотентно (мост не дёргается); нет TG-привязки в `external_identities`
   → 409 `no_telegram_link`; мост недоступен / номера нет /
   `phone_confirmed != True` → 409 `bot_phone_unconfirmed`; номер из бота не
   совпадает с анкетой → 409 `phone_mismatch`; иначе `phone_verified_at`
   проставляется → 200 `{"status": "verified"}`.

Почему это безопасно как замена SMS: нативный контакт Telegram платформа
отдаёт только по явному жесту владельца аккаунта, а мост закрыт
HMAC-подписью — подделать «подтверждённый» номер снаружи нельзя.

## Тестирование

Валидный `init_data` в тестах фабрикуется тем же алгоритмом с тестовым
токеном (см. `world-backend/tests/test_messenger_auth.py::make_init_data`):
пары `auth_date`/`user`/`query_id` → подпись тестовым `TELEGRAM_BOT_TOKEN` →
`urlencode(pairs) + "&hash=" + signature`.

- Бэкенд: `cd world-backend && .venv/bin/python -m pytest -q`
  (`test_registration_gate.py`, `test_messenger_auth.py`, `test_bridge.py`).
- Бот: `cd bot && pytest -q` (`tests/test_world_bridge.py` — подпись,
  свежесть, трим полей, кнопки меню TG/MAX).
- Фронт: `cd world && npx vitest run`
  (`src/lib/messenger.test.ts`, `src/features/gate/AppGate.test.tsx`,
  `src/features/registration/RegistrationFlow.test.tsx`).
- Ручная проверка в Telegram: «🏰 Мир Фоксинбурга» в меню бота → вход без
  онбординга; если лид уже есть в боте — анкета предзаполнена; в браузере
  вне мессенджера — обычный онбординг.
