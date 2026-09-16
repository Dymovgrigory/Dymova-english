# FOXINBURG_DIFFERENTIATORS.md

What we **keep** from Duo/Puzzle **logic**, and what must stay uniquely Foxinburg.

Owner mandate: references concern design **and** logic/functionality — but `PROMT_WORLD.md` §2 forbids copying UI/brand/visual language. Differentiate by **world identity + school reality + Foxy brain**.

Cross-ref: [`REFERENCE_MATRIX.md`](./REFERENCE_MATRIX.md).

---

## Industry vs Foxinburg

| Industry pattern | Foxinburg differentiator |
|---|---|
| Owl / generic mascot | Foxy as **guide + reaction system** bound to Fox Brain (not a sticker in the corner) |
| Skill tree website | **Castle locations** with learning purpose (school / yard / glory / shop…) |
| XP as client truth | **Ledger** XP/coins; client cannot mint |
| Sticker spam | Album with **rarity + acquisition rules** (target; partial now) |
| Black-box AI tutor | AI later, **curriculum-gated**; v0/v1 deterministic Foxy + weak_words |
| League = all-time XP | **Weekly window** from transactions (cohorts later) |
| LMS for parents | Separate parent/teacher/admin journeys (specified; not child HUD) |
| Movie/puzzle as core | Oral-first world units + listen/echo; media not licensed movies |
| 3D as the product | **Learn loop first**; 2D world shell; R3F optional later |
| Second “workouts app” | Yard is a **place in the same world** |
| CRM = game | School CRM (BigBen) and World are **isolated processes** |

---

## Technical differentiator

- World: `world/` (Next) + `world-backend/` (FastAPI) — not Tilda, not the MAX bot.  
- Identity: opaque sessions `wses.*`; child-only public signup; guardianship rows for family-ready links.  
- Content: version-pinned by session payload construction from Python packs.  
- Isolation: bot/CRM must not share DB or auth with world game economy.

---

## Emotional differentiator

“Я возвращаюсь в свой мир” — own hero, path, mistakes remembered, next step **explained** (`why` on NBA).

---

## Reference-driven priorities (what to steal as logic)

1. Duo: NBA, hearts, streak+freeze, SRS, weekly league, daily claim.  
2. Puzzle: theory→drill, vocab trainer as place, listen+speak production, adult/parent clarity.  
3. Neither: our castle metaphor, Foxy poses, school CRM isolation, oral Year-1 packs.

See matrix for **now vs target** and P0–P2.

---

## Anti-patterns we refuse

- Cloning Duo green path UI or Puzzle video grid.  
- Client-graded XP.  
- Free heart restore.  
- League on lifetime XP.  
- Parent dashboard that is just the child’s HUD with a “Parent” tab.  
- Casino chests that override learning outcomes.
