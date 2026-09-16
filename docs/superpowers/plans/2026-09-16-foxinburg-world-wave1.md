# Foxinburg World Wave 1 — Journey Spine Implementation Plan

> **For agentic workers:** execute task-by-task. Checkboxes track progress.

**Goal:** Ship the emotional spine: cinematic arrival → today’s mission → lesson triumph → castle return pulse.

**Architecture:** Client `journey.ts` orchestrates copy/CTA/highlights; server stays authority for progress. UI surfaces (home, learn, lesson finish, castle) read journey helpers.

**Tech Stack:** Next.js 16, React 19, Tailwind 4, Vitest, existing `worldApi`.

## Global Constraints

- Brand tokens only from `globals.css` / master prompt.  
- Russian “ты” copy, short lines.  
- Echo-gate and pedagogy stages unchanged.  
- No parent cabinet / social.  
- TDD for `journey.ts`.  
- Do not commit unless owner asks.

---

## File map

| File | Role |
|------|------|
| `world/src/lib/journey.ts` | Journey state + copy helpers |
| `world/src/lib/journey.test.ts` | Unit tests |
| `world/src/app/page.tsx` | Cinematic arrival |
| `world/src/app/learn/page.tsx` | Mission-first learn home |
| `world/src/app/learn/[lessonId]/page.tsx` | Finish → journey + castle CTA |
| `world/src/ui/CastleHub.tsx` | Return pulse / highlight |
| `world/src/app/globals.css` | Arrival / reward motion |
| `world/src/castle/buildings.ts` | BuildingId reuse for pulse |

---

## Task 1: Journey module (TDD)

- [x] Write failing tests for `loadJourney`, `saveJourney`, `greetingLine`, `missionFor`, `recordLessonFinish`
- [x] Implement `journey.ts`
- [x] `npm test` — green

## Task 2: Cinematic arrival

- [x] Redesign `page.tsx`: full-bleed establishing, brand hero, name, one yellow CTA
- [x] Persist name + `firstEnteredAt` via journey
- [x] Returning users: greeting + jump to mission (`/learn`) or castle

## Task 3: Mission-first learn home

- [x] Top: Foxi greeting from journey + streak
- [x] One primary mission CTA (lesson or practice if due)
- [x] Demote shop/stats noise below fold; keep WorldBar
- [x] Link to castle as secondary

## Task 4: Finish → castle pulse

- [x] On `finishLesson`, `recordLessonFinish` with suggested `lastRewardBuilding`
- [x] Primary CTA «В замок за наградой» → `/world?pulse=<building>`
- [x] CastleHub reads `pulse` query + journey; glow matching building once

## Task 5: Motion + verify

- [x] CSS: arrival fade, reward pop (respect reduced-motion)
- [x] Full `npm test` + `npm run build`
- [x] DEVLOG session note

---

## Rollback

Revert the listed files; journey keys in localStorage are harmless if abandoned (`world.journey.v1`).
