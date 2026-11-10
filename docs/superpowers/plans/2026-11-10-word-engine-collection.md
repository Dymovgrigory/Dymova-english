# Word Engine and Collection Game Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move vocabulary learning decisions and reward events into a deterministic server-side engine, then connect them to an idempotent collectible-card and achievement system.

**Architecture:** Keep the existing FastAPI + SQLite LMS and current client routes. Add a pure learning-domain module for skill scoring, task selection, and SRS transitions; expose session/task/answer endpoints from the existing words service; persist collection state and achievement grants as append-only learner events with unique keys. The current trainer will consume the new contract through a compatibility adapter before the visual UI is redesigned.

**Tech Stack:** Python 3, FastAPI-style service layer, SQLite, pytest; Next.js 16, React 19, TypeScript strict.

**Spec:** `docs/superpowers/specs/2026-11-10-word-engine-collection-design.md`

## Global Constraints

- Do not reset or discard existing learner word progress.
- Server is the source of truth for task selection, answer validation, skill progress, SRS, and rewards.
- SRS intervals are exactly `1, 1, 3, 7, 14, 30` days for the first version.
- Repeated answer/finish requests must not duplicate coins, cards, or achievements.
- 3D Foxi is not rendered inside the trainer.
- Grammar and reading use the shared task contract but are not required in this migration.

## Review Focus

- Duplicate answer submissions: one event and one reward at most.
- Stale or malformed task payloads: reject without mutating progress.
- Wrong answers: reduce/hold the relevant skill and schedule a retry, not a silent success.
- Existing learners with old progress rows: preserve strength and derive missing skill state safely.
- Empty sets and insufficient distractors: return a valid fallback task or an explicit no-task state.

### Task 1: Pure learning engine

**Files:**
- Create: `world-backend/app/lk/learning_engine.py`
- Test: `world-backend/tests/test_learning_engine.py`

**Interfaces:**
- Produces `SkillState`, `TaskSpec`, `AnswerResult`, `select_task()`, and `apply_answer()` with no database access.

- [ ] Write failing tests for interval transitions, skill-specific scoring, retry selection, distractor safety, and no-task behavior.
- [ ] Run `pytest world-backend/tests/test_learning_engine.py -q` and observe the expected import/behavior failures.
- [ ] Implement deterministic pure functions with injectable `today` and seeded RNG inputs; preserve legacy overall strength as the minimum/derived skill where no skill history exists.
- [ ] Run the focused tests, then the backend test suite.

### Task 2: Persist skill state and learner events

**Files:**
- Modify: `world-backend/app/world/db.py` or the existing schema initialization file
- Modify: `world-backend/app/lk/words.py`
- Test: `world-backend/tests/test_lk_words.py`

**Interfaces:**
- Consumes Task 1 `apply_answer()` and persists skill JSON, next-review date, attempt id, and event key.
- Produces atomic `submit_answer()` behavior with duplicate protection.

- [ ] Write failing API/service tests for first answer, wrong-answer retry, legacy-row backfill, and duplicate event key.
- [ ] Run the focused tests and confirm they fail for missing schema/behavior.
- [ ] Add idempotent schema creation and transactional upsert logic; never overwrite stronger legacy progress with a weaker backfill.
- [ ] Run focused and full backend tests.

### Task 3: Server session/task contract

**Files:**
- Modify: `world-backend/app/lk/words.py`
- Modify: the existing LK route registration file found by `rg` before implementation
- Test: `world-backend/tests/test_lk_words.py`

**Interfaces:**
- Produces `start_session`, `next_task`, `submit_answer`, and `finish_session` HTTP payloads containing `session_id`, `task_id`, `task_type`, `word_id`, prompt data, options, and progress.

- [ ] Write failing tests for deterministic session composition, server-side correct answer checking, malformed task ids, and finish idempotency.
- [ ] Run the focused tests and verify failure.
- [ ] Implement session snapshots with signed/opaque ids backed by SQLite; select due words before new words and cap sessions at current limits.
- [ ] Run backend tests and API contract checks.

### Task 4: Collection and achievement domain

**Files:**
- Create: `world-backend/app/lk/collection.py`
- Modify: schema initialization and `world-backend/app/lk/words.py`
- Test: `world-backend/tests/test_lk_collection.py`

**Interfaces:**
- Consumes learner events from Tasks 2–3.
- Produces `CollectionState`, `AchievementState`, and idempotent `grant_for_event()`.

- [ ] Write failing tests for first-lesson, word-count, topic-completion, streak, and multi-skill unlocks; include duplicate event replay.
- [ ] Run focused tests and verify failure.
- [ ] Seed a small versioned starter catalog and grant only from confirmed events in the same transaction.
- [ ] Run collection and full backend tests.

### Task 5: TypeScript client adapter

**Files:**
- Modify: `lk/lib/api.ts`
- Modify: `lk/app/words/train/[setId]/page.tsx`
- Test: add pure client contract tests only if the existing test setup supports them; otherwise use TypeScript/build verification.

**Interfaces:**
- Consumes Task 3 payloads and maps legacy trainer modes to server task types.
- Produces answer/finish calls with stable `session_id`, `task_id`, and idempotency key.

- [ ] Add API types and failing TypeScript references for the new contract.
- [ ] Implement a compatibility path so the current route can render server tasks while retaining the existing mode URLs.
- [ ] Remove trainer-only 3D Foxi rendering without changing the rest of the app shell.
- [ ] Run `npm run lint` and `npm run build` in `lk`.

### Task 6: Collection/achievement read model and production verification

**Files:**
- Modify: `world-backend/app/lk/words.py` and `lk/lib/api.ts`
- Create or modify: the smallest existing LMS page needed to expose collection state
- Test: backend API tests and existing frontend checks

- [ ] Add read endpoints for collection progress and achievements with stable ordering.
- [ ] Add the collection state to the words/dashboard data without a visual redesign.
- [ ] Run backend tests, frontend typecheck, production build, and the existing end-to-end word smoke test if its dependencies are available.
- [ ] Review the diff for unrelated files, migration safety, security, accessibility, and performance; document any deferred UI work.

## Rollback

Disable the new session route via the compatibility flag and keep legacy `/api/lk/words/train`, `/answer`, and `/finish` available. New tables and event rows are additive; no existing progress rows are deleted.
