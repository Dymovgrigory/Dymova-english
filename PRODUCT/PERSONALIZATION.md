# PERSONALIZATION.md

Personalization is **Fox Brain + Recommendation**, not a skin picker.

## Inputs (available today)

- `lesson_progress` (stars, last touch)  
- `word_stats` (strength, due_at, correct/wrong)  
- `mistakes` (uncleared items)  
- `players` (level, streak, daily_xp, hearts)  
- daily quest claim flags  
- inventory / stickers  

## Outputs

| Output | Consumer |
|---|---|
| Next Best Action | Home, castle pulse, Foxy line |
| Review set | Training Yard |
| Weak-skill copy | “Past Simple нестабилен” (v1: word-level) |
| Starting path | Placement Engine (not shipped) |
| Daily quest mix | Quest engine (today: 3 fixed) |

## Rules

1. Recommendation **explains why**.  
2. Personalization cannot skip curriculum gates (hearts, locks, content packs).  
3. No dark-pattern “personalized” FOMO.  
4. Parent / teacher see the same learner model, different UX.

## v0 (this phase)

`GET /api/world/learn/home` includes `next_best_action` computed server-side from due words, claimable dailies, and current lesson. Client `missionFor()` is a fallback, not source of truth.
