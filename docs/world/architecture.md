# Foxinburg World — Architecture Proposal (STEP 3)

Статус: v1 (2026-09-13). Основано на аудите репозитория (STEP 1–2) и брифе
«промт World» (§1–259). Решения приняты самостоятельно (§254); существующие
системы не ломаем (§238) — World строится как изолированный модуль.

## 1. Что уже есть (аудит — вход для решений)

| Слой | Существующее | Решение для World |
|---|---|---|
| Сайт | Статический Python-билд (`prototype/`, 185 страниц, прод `dymova-english.ru`) | Не трогаем. World — отдельное приложение `world.` поддомен / `/world` |
| Backend | FastAPI-бот (`bot/app`), BigBen CRM = source of truth, miniapp-auth (TG/MAX), биллинг, аналитика | Расширяем новым саб-доменом `world` внутри того же FastAPI (один сервер, один деплой) |
| Auth | `miniapp_auth.py` (initData TG/MAX) + BigBen identities | Реиспольз; child profile привязан к ученику CRM |
| 3D маскот | `foxi-rigged.glb` 726 КБ, 6 клипов, draco+webp pipeline (gltf-transform) | Базовый аватар/компаньон мира |
| Node-стек | **Отсутствует** (нет ни одного package.json) | Создаём `world/` монорепо с нуля |
| PostgreSQL | Нет (SQLite read-model) | Новый Postgres (Docker) — игровая транзакционная БД |
| AI | LLM gateway OpenAI-совместимый; новый Gemini-прокси (ключ получен) | AIProvider abstraction (§100–101): reasoning gemini-3.1-pro, fast gemini-3.8-flash |
| 3D-генерация | Meshy web-UI вручную | Meshy API (ключ получен, 1286 кредитов) → `world-pipeline/` |

## 2. Выбор World Engine (§6): PlayCanvas vs Three.js/R3F

Критерии брифа: GPU performance, mobile, WebGPU, WebGL fallback, scene
streaming, physics, asset management, React integration, scalability,
maintainability, DX.

| Критерий | PlayCanvas (Engine) | Three.js + React Three Fiber |
|---|---|---|
| WebGPU | Да, с авто-fallback на WebGL2 | Да (через three/webgpu renderer), fallback ручной |
| React integration | Официальная `@playcanvas/react`, но экосистема моложе | R3F — зрелая модель «сцена как компоненты», огромная экосистема (drei, postprocessing, rapier) |
| Scene streaming | Встроенный asset registry/loading | Делаем сами (manifest + hooks) — и так нужен data-driven world (§166–167) |
| Physics | Нужен внешний (ammo/cannon) | Rapier — first-class, WASM, именно он назван в брифе §42 |
| Mobile / perf тюнинг | Хорошо | Хорошо + привычный инструментарий (уже использован в `prototype/mascot/mascot.js` — Three.js!) |
| Команда/наследие | Ноль кода в проекте | Уже есть production Three.js код (маскот на сайте), отработанный GLB pipeline |
| Editor | PlayCanvas Editor — платный/облачный, нам не нужен (свой CMS §76) | Не нужен — data-driven мир |
| Lock-in | Своя сущность-graph модель | Three.js — индустриальный стандарт, легко нанимать |

**Решение: Three.js + React Three Fiber (+ drei, @react-three/rapier,
@react-three/postprocessing).** Обоснование: (1) в проекте уже есть
production Three.js и отработанный GLB→draco→webp pipeline; (2) экосистема
R3F покрывает physics (Rapier, §42), post-processing (§39), instancing/LOD
(§50) без внешних сервисов; (3) WebGPU через three WebGPURenderer с
обязательным WebGL fallback (§49); (4) data-driven архитектура мира (§166)
уравнивает движки по streaming — решает наш manifest loader, а не движок.
PlayCanvas остаётся documented alternative (§105): граница — все вызовы
движка через `world-engine` package, перенос возможен без переписывания
game systems.

## 3. Гибридная архитектура (§7)

```
world/                         ← новый монорепо-модуль (pnpm workspaces)
├── apps/
│   └── web/                   Next.js (App Router) — shell, HUD, Game OS UI,
│                              parent/teacher/admin, R3F canvas
├── packages/
│   ├── world-engine/          R3F scene runtime: renderer, camera system (§44),
│   │                          lighting (§38), post-FX (§39), particles (§40),
│   │                          shaders (§41), adaptive quality (§48), streaming (§50)
│   ├── game-systems/          quests, rewards, XP, levels, streak, achievements (client glue)
│   ├── education/             learning activities, mini-games framework (§68–69)
│   ├── economy/               FoxCoins client SDK (server-authoritative §84)
│   ├── progression/           levels/titles/skill tree client
│   ├── ui/                    Game OS design system (§55, §232)
│   └── config/                feature flags (§79), economy config (§83), world manifest types
└── world-pipeline/            (уже создан) asset pipeline: Gemini concept →
                               Meshy 3D → gltf-transform → manifest → CDN

bot/app/world/                 ← backend-модуль в существующем FastAPI
├── api/                       typed routes (§158): /api/world/{player,quests,rewards,...}
├── domain/                    progression, economy, quests (server-authoritative)
├── db/                        Postgres (SQLAlchemy/asyncpg), migrations (Alembic)
└── ai/                        AIProvider abstraction → Gemini-прокси
```

**Почему backend — в существующем FastAPI, а не Next API routes:**
(1) server-authoritative rewards (§84) и BigBen-интеграция уже там;
(2) auth ученика/родителя уже там (miniapp-auth + CRM); (3) один деплой,
один мониторинг, один домен `bot.dymova-english.ru`; (4) Next.js остаётся
тонким — shell + рендер. Next API используется только для BFF-прокси
и SSR-персонализации.

**Почему Postgres, а не расширение SQLite:** транзакционный ledger (§85),
идемпотентность (§160), конкурентная запись (streak/XP с нескольких
устройств), JSONB для world state (§28). SQLite read-model бота не трогаем.

## 4. Доменные границы (§156)

Education, Player, Progression, Economy, Quest, Inventory, World, Events,
Social(Phase 3), Parent, Teacher, Analytics — каждый = отдельный модуль
с публичным интерфейсом; запрет циклических импортов (eslint boundaries).

## 5. Ключевые потоки (server-authoritative)

```
Client action (answer submitted)
  → POST /api/world/quests/{id}/complete (Idempotency-Key)
  → FastAPI: validate (Zod-экв. pydantic) → проверка состояния в PG-транзакции
  → economy ledger: XPTransactions + CoinTransactions (append-only)
  → progression: пересчёт level → unlocks → world flags
  → response: {xp_delta, coins_delta, level_up?, unlocks?, rewards[]}
  → Client: cinematic reward sequence (§93, §111) по данным ответа
```

Client никогда не хранит authoritative значения XP/coins — только отображает
последний server snapshot + optimistic UI с подтверждением.

## 6. Data-driven мир (§166–170)

- `world-manifest.json` (per zone): objects, assets (LOD variants), positions,
  interactivity, NPC refs, quests refs, music, environment preset.
- Quests/rewards/events/items — записи в PG с JSON-config, не React-компоненты.
- Remote config: admin CMS редактирует БД → клиент подхватывает без redeploy (§206).

## 7. Adaptive Rendering System (§48)

Detector (GPU string, deviceMemory, DPR, WebGPU availability, network,
rolling FPS) → профиль ULTRA/HIGH/MEDIUM/LOW/FALLBACK: разрешение рендера,
тени, post-FX цепочка, particle density, LOD bias, texture size (мобильные
варианты ассетов из manifest). FALLBACK = 2.5D режим (упрощённая сцена) —
никогда не белый экран (§50, §152).

## 8. Feature flags (§79)

`world3D, webGPU, multiplayer, social, seasons, weather, newShop,
newQuestEngine, mobileHighQuality, experimentalShader` — таблица в PG +
env override; клиент получает снапшот при boot.

## 9. Безопасность и дети (§88–89)

RBAC (child/parent/teacher/admin) на каждом route; pydantic-валидация;
rate limiting; audit log админских изменений (§161); privacy-by-design:
публично — только display name + avatar; никаких реальных имён/контактов
в world API.

## 10. Производительность (§151–153)

Бюджеты: shell LCP < 2.5s, world boot → first interaction < 5s на среднем
desktop, 60 FPS где возможно, graceful degradation. Telemetry: FPS buckets,
load times, asset failures → `/api/world/events`. E2E: Playwright (§150).

## 11. Что осознанно НЕ в v1

Multiplayer/Colyseus (Phase 3), AI-voice NPC (Phase 4, Web Speech API для
speaking-MVP), seasons/weather (flags есть, контент Phase 2), season pass,
платежи внутри World (запрещено §139).

## 12. Документированные альтернативы (§105)

| Решение | Выбрано | Альтернатива | Граница замены |
|---|---|---|---|
| Engine | Three.js/R3F | PlayCanvas | `packages/world-engine` — единственный импортёр three |
| Backend | FastAPI `bot/app/world` | отдельный NestJS | REST-контракт `/api/world/*` |
| DB | self-hosted Postgres | Supabase | `WORLD_DATABASE_URL` |
| Storage | локально → YC S3+CDN | Cloudflare R2 | `WORLD_CDN_BASE_URL` + manifest |
| LLM | Gemini-прокси | OpenAI/OpenRouter | `AIProvider` adapter |
| 3D-gen | Meshy API | Tripo3D | `world-pipeline/providers/` |
