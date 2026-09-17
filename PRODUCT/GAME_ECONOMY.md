# GAME_ECONOMY.md

## Currencies (target)

COINS · XP · STARS · ENERGY/HEARTS · KEYS · TOKENS  

## Current

XP + coins via append-only ledgers; hearts; stickers as inventory.

## Rules

1. Every balance change = transaction row with reason + source + idempotency key.  
2. Never `balance += N` from client-supplied N.  
3. Shop spends use **stable** idempotency keys (not random UUID per click).  
4. Hearts restore is paid or earned — not free API.  
5. Quests grant rewards only when completion rules pass.  

## Phase 0 fixes (mandatory)

- Gate `complete_quest` on all steps done  
- Remove / charge heart restore; stop silent auto-restore in lesson UI  
- Fix shop idempotency  
- Auth + rate-limit TTS  

See `PROJECT_AUDIT.md` Security section.
