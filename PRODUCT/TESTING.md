# TESTING.md

## Backend

```
cd world-backend && WORLD_UNLOCK_ALL=1 pytest -q
```

Critical: lesson progression, rewards, coins, XP, streak, quests, shop double-submit, hearts, sprint cap, **next_best_action**.

## Frontend

```
cd world && npx vitest run
```

Journey / hotspot unit tests.

## E2E

Playwright with `WORLD_E2E_UI=1` — registration-ish name, learn, lesson, world, album, sprint. Check behavior + persistence, not only DOM.

## Visual / a11y / responsive

Not covered by `tsc`. Screenshots on 390 and 1440 after UI changes.
