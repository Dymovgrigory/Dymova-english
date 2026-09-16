# Foxinburg World — рекомендуемые сервисы, API и MCP

Статус: v1.1 (2026-09-13). Ключи Gemini-прокси и Meshy получены и проверены. Формат по §104 брифа «промт World»:
каждый сервис — назначение, зачем, альтернатива, стоимость, приоритет, способ интеграции.
Правило §105: у каждого внешнего сервиса — abstraction layer, fallback, env-переменная,
чёткая граница интеграции. Ничего платного без необходимости.

## P0 — нужны для первого vertical slice

### 1. Meshy API (3D-генерация) — «новая внешняя модель»
- **Purpose:** text-to-3D / image-to-3D / auto-rig / animation для ассетов мира
  (здания, props, collectibles, NPC-модели, вариации Фокси).
- **Why needed:** бриф §35/§221 — мир не моделируется вручную кодом; нужен
  production asset pipeline. У нас уже есть отработанная связка: Meshy GLB →
  правка скиннинга (Python) → `@gltf-transform/cli optimize --compress draco
  --texture-compress webp` (пример: 51,85 МБ → 726 КБ, `prototype/mascot/`).
  Сейчас генерация идёт руками через web-UI; API переводит это в скриптовый pipeline.
- **Alternative:** Tripo3D (уже использовался — `foxi_v1_tripo3d.glb`), Rodin,
  ручное моделирование в Blender (долго, дорого по времени).
- **Estimated cost:** подписка Meshy с API-доступом (уточнить текущий тариф;
  генерация списывает кредиты за модель/текстуру/риг).
- **Priority:** P0.
- **Integration:** `world-pipeline/` скрипты (Python/Node): prompt → Meshy API →
  GLB → gltf-transform (draco+webp+LOD) → asset manifest → CDN. Env:
  `MESHY_API_KEY`. Нужен от владельца: **API-ключ Meshy** (или подтверждение,
  что продолжаем генерировать через web-UI вручную).

### 2. PostgreSQL (production БД World)
- **Purpose:** player profiles, XP/coin ledgers, quests, inventory, world state
  (бриф §86). SQLite текущего бота — read-model, не подходит под транзакционную
  игровую экономику с конкурентной записью.
- **Why needed:** server-authoritative rewards (§84), idempotency (§160),
  transaction ledger (§85) — нужны настоящие транзакции и constraints.
- **Alternative:** Supabase Postgres (managed + Realtime из коробки);
  self-hosted Postgres на том же сервере Yandex Cloud (дёшево, контроль).
- **Estimated cost:** 0 ₽ (self-hosted на существующем VPS) или ~0–25 $/мес (Supabase).
- **Priority:** P0.
- **Integration:** Docker-сервис рядом с ботом; доступ только из backend.
  Env: `WORLD_DATABASE_URL`.

### 3. Object Storage + CDN (ассеты мира)
- **Purpose:** GLB/текстуры/аудио (бриф §164) — не отдавать бинарники с app-сервера.
- **Why needed:** world streaming (§50), lazy loading по зонам; текущий паттерн
  jsDelivr-пина на git-коммит не масштабируется на сотни ассетов с версиями.
- **Alternative:** Yandex Object Storage + CDN (та же инфраструктура, что VPS —
  рекомендуется), Cloudflare R2 (нулевой egress), jsDelivr/GitHub (текущий костыль).
- **Estimated cost:** ~копейки за ГБ (YC S3); R2 — 0 ₽ на малых объёмах.
- **Priority:** P0.
- **Integration:** `world-pipeline` заливает оптимизированные GLB, пишет
  `world-manifest.json` (§166); клиент грузит по манифесту. Env:
  `WORLD_CDN_BASE_URL`, `YC_S3_KEY/SECRET` (или R2).

## P1 — нужны в первые 1–2 фазы

### 4. Аутентификация World (дети/родители/учителя/админ)
- **Purpose:** роли §8, child profiles §87, не ломать существующие аккаунты (§240).
- **Why needed:** уже есть работающая связка miniapp_auth (Telegram/MAX initData)
  + BigBen CRM как source of truth по ученикам. Строим поверх, а не вторую CRM.
- **Alternative:** Supabase Auth / NextAuth — если решим делать полностью
  отдельный стек (не рекомендуется: дублирует существующее).
- **Estimated cost:** 0 ₽.
- **Priority:** P1 (в slice — сперва guest/child profile через существующий miniapp-auth).
- **Integration:** reuse `bot/app/miniapp_auth.py` + новый `world` модуль FastAPI.

### 5. MCP: Figma (design pipeline)
- **Purpose:** UI/Game OS дизайн-система (§55, §232) — макеты HUD, карт, профиля,
  reward-карточек до кода; выгрузка токенов бренда.
- **Why needed:** качество UI уровня «game OS», а не dashboard; брендбук уже
  существует (`brand-assets/brand-guide.pdf`), переносим в Figma-токены.
- **Alternative:** дизайн сразу в коде (медленнее итерации, хуже консистентность).
- **Estimated cost:** 0 ₽ (Figma MCP уже доступен в среде, нужен OAuth-логин).
- **Priority:** P1.
- **Integration:** `mcp__figma__*` уже подключён в CLI — нужно пройти OAuth
  (один раз, в браузере). Desktop Bridge для записи — опционально.

### 6. MCP: GitHub (PR-flow)
- **Purpose:** обязательный PR-flow с DEVLOG (foxinburg-release), code review.
- **Estimated cost:** 0 ₽. **Priority:** P1.
- **Integration:** `mcp__github__*` уже подключён — ничего не нужно.

### 7. Аналитика событий (§80–82, §153)
- **Purpose:** learning/product analytics + telemetry FPS/WebGPU.
- **Why needed:** North Star = learning engagement (§251), нужны данные с day 1.
- **Alternative:** (a) расширить существующий `product_events` бота (SQLite→PG) —
  рекомендуется; (b) PostHog self-hosted/cloud; (c) Яндекс.Метрика (уже есть на сайте,
  но не подходит под игровые события).
- **Estimated cost:** 0 ₽ (вариант a).
- **Priority:** P1.
- **Integration:** `POST /api/world/events` → тот же pipeline, что `platform/analytics.py`.

## P2 — фазы 2–3 (заложить в архитектуру, не подключать сейчас)

### 8. Realtime (уведомления, presence, события)
- **Purpose:** §63 — notifications, class activity, live events.
- **Alternative:** Supabase Realtime (managed) / собственный WebSocket в FastAPI
  (у бота уже есть long-poll опыт) / Centrifugo.
- **Estimated cost:** 0–25 $/мес. **Priority:** P2.

### 9. Colyseus (multiplayer)
- **Purpose:** §62 — shared spaces, classmates в одной зоне (Phase 3).
- **Estimated cost:** 0 ₽ self-hosted. **Priority:** P2/P3. Сейчас — только
  архитектурная закладка (room/state протокол не проектировать в v1 жёстко).

### 10. AI Voice / Speaking practice
- **Purpose:** §67 speaking lessons, §100 AI-модуль (Phase 4): speech-to-text
  (Whisper/аналог), TTS для NPC-диалогов (§99), pronunciation scoring.
- **Why needed:** speaking — ключевой навык школы; но это отдельный модуль
  через AIProvider abstraction (§100–101), не ядро v1.
- **Alternative:** OpenAI Realtime / Yandex SpeechKit (RU, дешевле, уже в инфре YC) /
  браузерный Web Speech API (бесплатный MVP для v1).
- **Estimated cost:** SpeechKit ~от 150 ₽/час аудио; Web Speech API — 0 ₽.
- **Priority:** P2 (v1 использует Web Speech API + fallback).

## Что НЕ подключаем (осознанно)

- **Платежи в World** — §13/§139: одна валюта FoxCoins, никакого pay-to-win,
  monetized season pass запрещён брифом без отдельной оценки. CloudPayments
  школы остаётся в боте (уже интегрирован, ждёт ключи владельца).
- **Отдельный CRM/Backend-as-a-Service целиком** — BigBen CRM остаётся
  source of truth по ученикам/группам/оплатам (docs/platform/ARCHITECTURE.md).
- **Push-уведомления** — через существующего бота (MAX/Telegram), не новый сервис.

## Чек-лист «что нужно от владельца»

1. ~~Meshy API key~~ — **ПОЛУЧЕН 2026-09-13**, проверен (`/v1/balance` → 1286
   кредитов). Хранится в `world-pipeline/.env` (gitignored).
2. ~~Gemini-прокси key~~ — **ПОЛУЧЕН 2026-09-13**, проверен (`/v1/models` →
   gemini-3.1-pro, gemini-3.6/3.7/3.8-flash; тестовый completion OK). Это и есть
   «новая внешняя модель»: LLM-слой World (AIProvider §100-101) — reasoning:
   `gemini-3.1-pro`, fast: `gemini-3.8-flash`. Хранится в `world-pipeline/.env`.
3. Решение по БД: **self-hosted Postgres на текущем VPS** (рекомендую) или Supabase.
4. Решение по storage: **Yandex Object Storage + CDN** (рекомендую) — нужен
   сервисный аккаунт YC с ключами S3.
5. Figma OAuth — пройти по ссылке при первом использовании figma-MCP (разово).
6. (Уже висит) CloudPayments public_id/api_secret — не блокирует World.

### Примечание по безопасности
Ключи были присланы в чате — сохранены только в `world-pipeline/.env`
(gitignored). Если этот чат где-либо публикуется/логируется третьими
сервисами — ключи стоит ротировать.
