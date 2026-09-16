# QUEST_SYSTEM.md

## Daily quests (live)

Three fixed dailies, reset by `engine._day()`:

| id | Goal | Claim |
|----|------|-------|
| `xp-goal` | `DAILY_XP_GOAL` XP today | +`XP_REWARDS.daily_quest` once/day |
| `lesson-1` | 1 lesson finished today | same |
| `perfect-1` | 1 perfect (3★) lesson today | same |

API:
- `GET /api/world/learn/home` → `quests[]` with `done`, `claimed`, `claimable`
- `POST /api/world/learn/quests/claim` `{quest_id}` — server-authoritative; ledger key `daily-quest:{pid}:{day}:{id}`

UI: castle room `quests` — claimable tiles show «Забрать», claimed «Получено».

## Story / zone quests

`core.complete_quest` requires all steps done (Phase 0). Rewards from `config.quests` only via `core.award`.
