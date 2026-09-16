# FOXINBURG_WORLD.md

The world is one interactive space. Routes exist; the child should feel **locations**, not `/courses`.

## v1 locations (live 2D castle)

| ID | Place | Learning purpose | Backend |
|---|---|---|---|
| school | School of Foxy | Next lesson | `learn/path`, `lessons/start` |
| yard | Training Yard | Review / sprint | `practice/start`, `sprint` |
| lexicon | Word Treasury | Word stats | `learn/words`, `review` |
| stickers | Sticker Tower | Collection | inventory `sticker-*` |
| shop | Marketplace | Economy spend | `learn/shop/buy` |
| glory | Tower of Glory | Weekly league + brand flag | `learn/league` |
| nest | Foxy Garden / nest | Profile stats | player snapshot |
| quests | Quest gazebo | Daily claims | `learn/quests/claim` |

Presentation: painterly `map.png` + SVG polygons (`world/src/castle/buildings.ts`) + room dock. Not a dashboard of cards.

## v2 locations (specified, not shipped)

Castle · Library · Arena · Workshop · Observatory · Adventure Gate · Garden depth · Future events.

Each new location **must** ship with: identity, purpose, hotspot, NPC/Foxy hook, learning mechanic, reward, unlock rule, analytic ID.

## Location FSM (target)

`locked → available → discovered → active → mastered` (+ `event` overlay).

Unlocks table already exists (`unlocks`). `UNLOCK_ALL` is 1 in local dev, **0 in prod**. `world_state` is reserved for presentation keys (camera, time-of-day) — currently unused.

## World-first UX

LOCATION → INTERACTION → LEARNING.

Door / plaque / chest / flag / book are the UI. HTML panels are HUD or focused mode, not the product.

## Composition

- **PRIMARY:** location + next best action  
- **SECONDARY:** HUD (XP, coins, hearts, streak)  
- **TERTIARY:** rooms, drawers, overlays  

Mobile: compact HUD, ≥44px targets, no giant bottom stack covering the map.
