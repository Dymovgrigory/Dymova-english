# LMS Full Learning Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the LMS subdomain into a complete child learning platform with Cambridge-aligned lessons, mastery, ranks, achievements, and 100 collectible cards.

**Scope:** LMS only. Do not modify `world/`, World UI, World routes, or World content. Shared backend infrastructure may be reused only through explicit LMS adapters; LMS progress and rewards remain authoritative in `app/lk`.

**Architecture:** Create an LMS learning domain under `world-backend/app/lk/learning/` with content manifests, server-owned sessions, challenge grading, mastery and progress. Keep the existing word trainer as a compatibility route while the new `/learn` route becomes the primary learning surface. Add a separate collection catalog and rank system under `app/lk`, with assets served from `lk/public/collection/`.

**Tech Stack:** FastAPI, SQLite/PostgreSQL-compatible SQL, Python 3, pytest; Next.js 16, React 19, TypeScript strict; generated raster card art with a consistent collection art direction.

## Product tracks

1. **Learning core:** levels Pre-A1/A1/A2/B1, topic/module prerequisites, vocabulary, grammar, reading, listening, writing, speaking, Cambridge-style tests.
2. **Mastery:** per-skill states, SRS, retries, diagnostic routing, server-side grading, session integrity and analytics.
3. **Progression:** points, ranks beginning at “Гость Фоксинбурга”, achievements, daily/weekly assignments and completion rewards.
4. **Collection:** 10 named collections × 10 cards, rarity, unlock rules, card gallery, card detail and achievement links.
5. **LMS UX:** home learning path, lesson player, result screen, collection gallery, progress dashboard and teacher/admin content hooks.

## Tasks

### Task 1: LMS learning domain and content schema

- Create `world-backend/app/lk/learning/` modules for content loading, challenge models, grading, mastery and sessions.
- Add versioned LMS content manifests under `world-backend/app/lk/content/learning/`.
- Include challenge types: `teach_word`, `listen_pick`, `image_pick`, `translate`, `spell`, `build_phrase`, `grammar_choice`, `read_text_choice`, `read_true_false`, `listen_choice`, `write`, `speak`.
- Add tests for malformed content, deterministic task generation, safe distractors, prerequisites, retries and session expiry.

### Task 2: LMS API

- Add `/api/lk/learning/home`, `/path`, `/sessions`, `/sessions/{id}/answer`, `/finish`, `/collection`, `/achievements`.
- Resolve the existing bearer session and `student_id` through the same `_profile()` guard as words.
- Persist sessions, attempts, mastery events and idempotency keys in additive tables.
- Do not expose correct answers in public challenge payloads.

### Task 3: Levels, points and ranks

- Replace word-only progression with a points ledger while preserving old word progress.
- Keep “Гость Фоксинбурга” as rank zero and add rank thresholds for 1000+ points.
- Award points for first-try accuracy, skill coverage, topic completion and tests; never award points for duplicate events.

### Task 4: LMS lesson path UI

- Create `lk/app/learn/page.tsx` and focused components for path, lesson player, challenge renderers and results.
- Render every challenge type with images/audio where supplied, keyboard and accessible controls.
- Add responsive states for loading, error, retry, skipped speaking and session recovery.

### Task 5: Collection catalog and generated assets

- Create 10 collection manifests with 10 cards each, stable IDs, rarity, unlock conditions and localized copy.
- Generate and validate 100 card images; store them under `lk/public/collection/<collection>/<card>.webp`.
- Add gallery/detail UI and unlock animation that is driven by server state.

### Task 6: Dashboard and admin/content operations

- Add learning path, mastery summary, ranks, achievements and collection progress to the LMS dashboard.
- Add protected content/catalog validation endpoints for staff and a content audit script.
- Validate every referenced image/audio asset and report missing/duplicate IDs before deployment.

### Task 7: Verification and deployment

- TDD each domain rule and API transition.
- Run backend full suite, LMS frontend lint/build, content audit and LMS end-to-end flows.
- Deploy only LMS services; leave `world/` and World routes unchanged.
- Verify public LMS routes, auth gate, session flow, answer grading, finish rewards and collection unlocks on production.

## Definition of done

- A learner can enter the LMS, choose a level/topic, complete a mixed Cambridge-aligned lesson, receive a server-verified result and see mastery change.
- Reading, grammar, listening, writing and speaking are real graded tasks, not placeholder buttons.
- All 100 cards exist as validated assets and unlock only from verified achievements.
- Existing word progress remains available and no World files are changed.
- Production deployment has fresh health and end-to-end evidence.
