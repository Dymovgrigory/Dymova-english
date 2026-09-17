# DATABASE.md — Foxinburg World target model

**Live:** SQLite (`WORLD_DB_PATH`) with optional Postgres (`WORLD_DATABASE_URL`). Schema: `world-backend/app/world/db.py`.

Giant `players` table is already a smell — balances live both on `players` **and** in ledgers. Rule: **ledgers are source of truth**; `players.xp/coins` are cached totals updated only inside `core.award` / `spend`.

## Live tables (keep)

| Table | Role |
|---|---|
| players | identity cache + streak/hearts/daily |
| xp_transactions / coin_transactions | append-only economy |
| quests / quest_progress | story quests |
| items / inventory | shop + stickers |
| unlocks | zone FSM |
| world_state | unused presentation KV |
| activity_sessions | lessons + practice payloads |
| auth_sessions | opaque login tokens (Phase 1) |
| guardianship | parent↔child links (Phase 1) |
| lesson_progress | stars / best |
| word_stats | SRS |
| mistakes | yard feed |

Indexes to add: `(player_id, created_at)` on ledgers; `(player_id, due_at)` on word_stats (filter already sequential).

## Target extras (do not invent UI first)

```
accounts (id, email, locale, tz)
sessions (id, account_id, token_hash, expires)
guardianship (parent_account_id, child_player_id)
user_skill (player_id, skill, mastery, confidence)
challenge_attempts (session_id, index, correctness, latency_ms, hint_used)
reward_transactions (unify xp/coin/item grants)
achievements / user_achievements
chests / chest_opens
league_seasons / league_participants
analytics_events
feature_flags / experiment_assignments
assets / asset_versions
content_packs
```

## Constraints (non-negotiable)

- UNIQUE idempotency on value grants  
- FK to players  
- timestamps  
- no client-written balances  
- soft-delete only where history matters (accounts), not on ledgers  

## Migration

Phase 3: Postgres in prod (adapter already in `db.py`). Add tables incrementally with ` _TABLE_EXTRAS` / `CREATE TABLE IF NOT EXISTS`.
