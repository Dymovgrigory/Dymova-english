# RECOMMENDATION_ENGINE.md

## Job

Answer: **what should this child do right now, and why?**

Not a generic “Продолжить”.

## Priority (v0, server)

1. **Claimable daily** — reward already earned; claiming closes the loop.  
2. **Due review** — SRS words with `due_at <= today`. Prefer this when due ≥ 1 **and** the child already finished ≥1 lesson (protect first-session flow). If due ≥ 8, review outranks a new lesson.  
3. **Next unstarred lesson** — `current_lesson_id` from path.  
4. **First lesson** — `family-L1` for empty progress.

## Payload

```
kind: quest | review | lesson
href: /world?pulse=quests | /learn/practice | /learn/{id}
title, hint, why
analytic_id
```

## v1+

- Weak grammar / listening / speaking from challenge attempts  
- Placement start path  
- Fatigue: shorten session if recent fail streak  
- Teacher assignment override (always wins)

## Integrity

Recommendation never grants XP. It only **points**. Economy stays in `core.award`.
