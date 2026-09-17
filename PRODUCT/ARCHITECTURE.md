# ARCHITECTURE.md — Foxinburg World

This is the **World** architecture. School CRM/bot: `docs/platform/ARCHITECTURE.md` (do not merge DBs).

## Chain

```
USER ACTION → DOMAIN EVENT → DB TRANSACTION → USER/LEARNING/GAME STATE
  → FOX BRAIN → RECOMMENDATION → SCREEN / WORLD → FOXY → REWARD → ANALYTICS
```

Client sends **actions**. Server returns **deltas + next_best_action**.

## Processes

| Process | Port | Code |
|---|---|---|
| Next.js | 3002 | `world/` |
| FastAPI | 8010 | `world-backend/` |
| Dev | `make world-dev` | `scripts/foxinburg-world-dev.sh` |

## Backend packages (today: flat `app/world/`)

| Module | Domain |
|---|---|
| db.py | connection + schema |
| auth.py | HMAC player token |
| core.py | player, award, spend, quests, inventory |
| engine.py | lessons, hearts, path, finish |
| learn.py | home, shop, league, dailies |
| brain.py | Fox Brain v0 / NBA |
| srs.py | spaced repetition |
| catalog.py + courses | content packs |
| api.py | HTTP contracts |
| tts.py | audio |

Target folders: `features/{learning,rewards,quests,world,social,...}` on the frontend; backend split to packages when a file exceeds ~500 lines.

## Auth (now → next)

Now: `X-World-Player` = opaque session `wses.<id>.<secret>` (from `POST /players`) **or** legacy `external_key.hmac` if `WORLD_PLAYER_SECRET`.  
Public signup is **child-only**. Elevated roles require staff provisioning.  
Family-ready: `guardianship` links parent→child players.  
Next: account email/OAuth, session revoke, parent portal.

## Frontend

App Router pages: `/`, `/learn`, `/learn/[lessonId]`, `/learn/album`, `/learn/sprint`, `/world`.  
Chrome: `ui/fantasy`, `WorldBar`, `CastleHub`.  
Journey chrome still client (`lib/journey.ts`) — presentation only; NBA must prefer server payload.

## Feature flags

`UNLOCK_ALL` — decorative locks. Prod default 0.
