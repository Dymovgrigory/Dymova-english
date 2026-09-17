# FOX_BRAIN.md

Fox Brain is the **learner model**, not a chatbot. Foxy the character is the voice of this model.

## Job

After every learning session:

```
USER STATE → FOX BRAIN → UPDATED LEARNER MODEL → NEXT BEST ACTION
```

Classify skills as: mastered · weak · forgotten · unstable · new.  
Track: confidence, recurring mistakes, recent mistakes, listen/speak/grammar/vocab weakness.

## v0 (shipped this phase)

Implemented in `world-backend/app/world/brain.py`.

Inputs:

- `lesson_progress` (how many lessons starred)  
- `srs.review_count` / due words  
- `daily_quests` claimable flags  
- `current_lesson_id`  

Outputs on `GET /api/world/learn/home` → `next_best_action`:

| Field | Meaning |
|---|---|
| kind | `quest` \| `review` \| `lesson` |
| href | Deep link |
| title / hint | Foxy-facing copy |
| why | Explicit reason (product rule: explain the CTA) |
| analytic_id | Stable ID |

Priority: claimable daily → due review (after first lesson, or due ≥ 8) → next lesson.

`learner_model()` exposes counts for tests and future parent/teacher views.

## v1

- Weak words from `word_stats.wrong_count` / low strength  
- Uncleared `mistakes`  
- Challenge latency / hint_used from session answers  
- Skill tags when content pack carries them  

## Character layer (separate)

Foxy states: idle, happy, thinking, celebrating, warning, teaching…  
v1: `foxi_poses.py` + `FoxiGuide`. Brain chooses **what to say**; poses choose **how it looks**.

Personality: warm coach, lemon/teal, never shame hearts loss. Soft fails stay in-world.

## Non-goals

- Free chat  
- Client-side XP advice  
- Overriding teacher assignments (when those exist)

## Reference-driven priorities

Duo-style NBA + Puzzle-style weak-vocab focus — without cloning either UI. Matrix: [`RESEARCH/REFERENCE_MATRIX.md`](../RESEARCH/REFERENCE_MATRIX.md).

**Keep:** server `why` + deep link; claim → review → lesson.  
**Next:** tune review vs lesson steal; ingest `analytic_id`; feed speak-attempt + latency into `learner_model` when telemetry lands.
