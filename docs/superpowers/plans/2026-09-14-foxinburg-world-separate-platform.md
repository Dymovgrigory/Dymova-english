# Foxinburg World Separate Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline). Owner asked to execute automatically.

**Goal:** Вынести игровой API из школьного бота в отдельный процесс `world-backend/` без CRM и без miniapp-auth.

**Architecture:** Код `bot/app/world/` переезжает в `world-backend/app/world/`. Бот больше не импортирует мир. Фронт `world/` ходит на `http://localhost:8010`. Идентичность — только `X-World-Player`.

**Tech Stack:** FastAPI, SQLite, pytest, Next.js (без смены контракта `/api/world/*`).

## Global Constraints

- Нет импортов CRM / BigBen / miniapp_auth в `world-backend/` и `world/`.
- Нет `WORLD_API_ENABLED` в боте: мира в боте нет.
- Dev API порт `8010`. HTTP-контракт `/api/world/*` не менять.
- Не коммитить, пока владелец не попросит.

---

### Task 1: Контракт «бота мира нет»

**Files:**
- Create: `bot/tests/test_world_absent.py`
- Delete after green: `bot/app/world/`, world-тесты бота, флаг в config/main

- [ ] **Step 1:** Тест: `importlib.import_module("app.world")` → `ModuleNotFoundError`; `GET /api/world/player` на `app.main` → 404.
- [ ] **Step 2:** Убедиться, что тест красный, пока пакет ещё в боте.
- [ ] **Step 3:** Вырезать мир из бота (после Task 2, чтобы код не потерять).
- [ ] **Step 4:** Тест зелёный. `cd bot && pytest -q`.

### Task 2: `world-backend/`

**Files:**
- Create: `world-backend/` (app/world copy, tests copy except feature flag, main.py, requirements.txt, pytest.ini, .env.example)
- Modify: `app/world/api.py` docstring — убрать CRM/miniapp «следующий шаг»
- Modify: CORS в `main.py` только localhost:3000/3002

- [ ] Перенести файлы, `GET /health` → `{ok: true}`
- [ ] `cd world-backend && pytest -q` зелёный

### Task 3: Фронт на :8010

**Files:** `world/src/lib/api.ts`, `world/.env.example`, `world/README.md`

- [ ] Дефолт `NEXT_PUBLIC_WORLD_API=http://localhost:8010`
- [ ] `cd world && npm test && npm run build`

### Task 4: Документы + CI

**Files:** `docs/world/architecture.md`, `DEVLOG.md`, `.gitignore`, `.github/workflows/world-ci.yml`

- [ ] Architecture: backend = `world-backend`, не бот/CRM
- [ ] DEVLOG сессия выноса
- [ ] CI pytest для `world-backend/**`
