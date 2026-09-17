# LEARNING_ENGINE.md

## Purpose

Server-authoritative lesson / practice / review pipeline.

## Current (preserve)

- Course packs: starter oral + phonics  
- Session start → answer (server grade) → finish → stars + XP/coins + SRS  
- Practice from mistakes + due words  
- Public items strip answers  

## Target

```
DISCOVER → LEARN → PRACTICE → ANSWER → FEEDBACK
  → REINFORCE → REPEAT → MASTER → REWARD → ADVANCE
```

Challenge types (roadmap): vocab, grammar, listen, speak, match, fill, order, timed, boss.

## Fox Brain (v0+)

Inputs: mistakes, word_stats, recent sessions.  
Outputs: weak skills, next review set, **next best action** copy + deep link.

## Non-negotiables

- No client-graded value that mints XP/coins  
- Persist attempt metadata (latency, hints, attempt_n) in session answers (no reward effect)  
- Idempotent lesson rewards per player+lesson  

## Live loop (2026-09-16)

Finish screen → if daily XP goal met, CTA opens `/world?pulse=quests` (room auto-opens).
Claim via `POST /learn/quests/claim`; UI shows claimable pulse on nav chip.

`GET /learn/home` includes Fox Brain `next_best_action` (claim → review → lesson) with `why` + `analytic_id`. `/learn` and castle banner prefer this payload over local `missionFor`.

## Reference-driven priorities

Duo/Puzzle inform **loops**, not UI. Full matrix: [`RESEARCH/REFERENCE_MATRIX.md`](../RESEARCH/REFERENCE_MATRIX.md).

Learning P0/P1 from matrix: streak milestone XP · SRS weak-word sessions · placement stub · speak attempt telemetry (echo stays non-minting) · chest loot on finish · richer item kinds later.
