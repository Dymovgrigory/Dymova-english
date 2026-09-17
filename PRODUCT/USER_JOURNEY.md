# USER_JOURNEY.md

```
REGISTRATION → ONBOARDING → (PLACEMENT later) → PERSONAL GOAL
  → FOXINBURG HOME → FIRST MISSION → FIRST LESSON → FIRST REWARD
  → WORLD UNLOCK → DAILY QUEST → STREAK → REVIEW → SOCIAL → MASTERY
```

## v1 live path

1. Open `/` → name in localStorage (`world.name`) + `POST /players`.  
2. `/learn` Game Home: Foxy greeting, mission plaque, trail of units.  
3. Lesson fullscreen (`/learn/[id]`) — hearts gated.  
4. Finish → server award → journey pulse building (`?pulse=`).  
5. Castle `/world` — claim dailies, album, shop, yard.  
6. Return tomorrow: streak + due words.

## First-screen rule

Within seconds the child knows: where (castle/school), what (mission), why (Foxy hint), what they get (stars / sticker / XP).

## Gaps vs prompt

- No real registration / family account.  
- Placement skipped.  
- Journey chrome (`world.journey.v1`) is still client — must sync from server.  
- Social / mastery map not shipped.
