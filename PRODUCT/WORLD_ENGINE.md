# WORLD_ENGINE.md

## Purpose

Define how Foxinburg locations, hotspots, unlocks, and presentation connect to backend state.

## v1 (current)

| Location ID | Purpose | Entry |
|---|---|---|
| school | Lessons | `/learn/{lessonId}` |
| shop | Spend coins | buy API |
| glory | League + flag brand | league API |
| lexicon | Learned words | words + review |
| stickers | Album collection | inventory |
| yard | Practice / sprint | practice + sprint |
| nest | Player profile stats | player snapshot |
| quests | Daily quest display | learn/quests |

Presentation: 2D map (`map.png`) + SVG polygons (`buildings.ts`) + room overlays.

## Rules

1. Location state comes from server (`unlocks`, progress), not local flags alone.  
2. Hotspot ≠ page route only — it starts an **interaction** (lesson, shop, drawer).  
3. Brand logo (lemon stamp) belongs **in** glory / location art where specified.  
4. Bottom nav is contextual dock — must not dominate viewport height.  

## v2 targets

- Location FSM: `locked | available | discovered | active | mastered | event`  
- Ambient living world (performance-budgeted)  
- Optional R3F zone behind feature flag — same APIs  

## Analytics IDs (examples)

- `world.school.startLesson`  
- `world.yard.startPractice`  
- `world.stickers.openCollection`  
- `world.glory.viewLeague`  
