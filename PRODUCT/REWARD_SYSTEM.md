# REWARD_SYSTEM.md

## Single write path

All grants go through `core.award` / spends through `core.spend`.

- XP/coins: append-only `xp_transactions` / `coin_transactions` with UNIQUE idempotency keys (`{idem}:xp` / `{idem}:coins`)
- Duplicate key → no-op, `xp_delta`/`coins_delta` 0, spend returns `applied: false`
- `award` also bumps `players.daily_xp` for the current day

## Sources (examples)

- `LESSON_REWARD` / `PRACTICE_REWARD` — `engine.finish`
- `DAILY_QUEST` — `learn.claim_daily_quest`
- Shop SKUs — `learn.buy` → `spend` then grant item/hearts
- Stickers — inventory rows, not a second currency

## Anti-abuse

No client-supplied amounts. Stable shop keys `shop:{pid}:{sku}:{n}`. Paid heart refill only.
