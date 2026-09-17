# DUOLINGO_PATTERNS.md

Research of **mechanics / learning loops / retention only**.  
Do **not** copy UI, owl, copy, palette, screens, or compositions.

Cross-ref: [`REFERENCE_MATRIX.md`](./REFERENCE_MATRIX.md) · live gaps in §Gap list below.

---

## PATTERN: Next Best Action (single primary CTA)

**WHY IT WORKS:** Removes choice paralysis; one clear verb returns the user to the habit loop in &lt;3 seconds.  
**RISK:** Opaque “Continue” that ignores review debt; users feel railroaded.  
**FOXINBURG ADAPTATION:** Server `next_best_action` with `kind` + `why` + `href` + `analytic_id`. Priority: claimable daily → due review → next lesson. Foxy voices the reason; client never invents XP advice.  
**IMPLEMENTATION:** `world-backend/app/world/brain.py` (`next_best_action`, `learner_model`); exposed on `GET /api/world/learn/home`; UI: `world/src/app/learn/page.tsx`, `CastleHub` mission plaque. Prefer brain over local `missionFor` in `journey.ts`.

---

## PATTERN: Daily goal + streak + freeze

**WHY IT WORKS:** Habit loop; loss aversion on broken streak; freeze as recovery valve.  
**RISK:** Streak anxiety; empty XP farming to “save the flame”; milestones promised but unpaid.  
**FOXINBURG ADAPTATION:** `daily_xp` vs `DAILY_XP_GOAL` (config); streak bumps on lesson finish; freeze is a shop SKU and is **consumed** on gap days in `_bump_streak`. Goal framing = lessons/review progress, not raw XP theater. Milestone XP table exists in config but is **not wired** yet.  
**IMPLEMENTATION:** `engine._bump_streak`, `players.streak_days` / `streak_freeze`; `learn.home` streak payload; shop `streak_freeze`; **gap:** `config.STREAK_BONUSES` unused — no award at 7/14/30.

---

## PATTERN: Hearts / energy gate

**WHY IT WORKS:** Session boundary; wrong answers cost; wait or pay to continue — protects against endless grind and monetizes gently.  
**RISK:** Paywall on learning for kids; free restore exploits; punishing oral-first learners.  
**FOXINBURG ADAPTATION:** 5 hearts, regen `HEART_REGEN_SEC`, wrong answer leaks heart; empty hearts fail lesson (no XP). Restore **only** via shop / paid refill path — never free. Soft Foxy copy on heart loss (no shame).  
**IMPLEMENTATION:** `engine.refill_hearts`, answer path heart leak, `learn.restore_hearts` → `buy(hearts_refill)`; `POST /learn/hearts/restore`, `POST /learn/shop/buy`; UI `Hearts` in lesson + `WorldBar`.

---

## PATTERN: Lesson micro-loop (short session → stars → reward)

**WHY IT WORKS:** Predictable dopamine: start → item → feedback → finish ceremony → advance. Short sessions fit kids and parents.  
**RISK:** Shallow “tap to win”; stars inflate without mastery.  
**FOXINBURG ADAPTATION:** Server-graded items; stars 1–3 from accuracy; XP/coins via ledger; return pulse to castle. Practice finish is capped (daily coin cap).  
**IMPLEMENTATION:** `engine.start` / `answer` / `finish`; `POST /learn/lessons/start|…/answer|…/finish`; UI `world/src/app/learn/[lessonId]/page.tsx` finish screen + chest art (ceremony visual only — loot tables later).

---

## PATTERN: Skill path as ordered nodes

**WHY IT WORKS:** Clear next node; visible progress; unlocks create anticipation.  
**RISK:** Feels like a website course list; linear boredom.  
**FOXINBURG ADAPTATION:** Path data exists (`GET /learn/path`) but **presentation** is world trail / School door, not `/courses`. Locks when `UNLOCK_ALL=0`; checkpoint stars unlock next unit.  
**IMPLEMENTATION:** `engine.get_path`, `LearnTrail`, castle school hotspot; packs in `starter_course.py` / `phonics_course.py` / `catalog.py`.

---

## PATTERN: Spaced practice from mistakes (SRS)

**WHY IT WORKS:** Retrieval of weak items beats re-reading; spacing fights forgetting curve.  
**RISK:** Review boredom; queue explosion; “due” ignored by home CTA.  
**FOXINBURG ADAPTATION:** Leitner-ish strength 0–5 on `word_stats`; Training Yard pulls due words; Fox Brain prefers review when due &gt; 0 (after first lessons / debt). Weak words shape review copy.  
**IMPLEMENTATION:** `srs.py` (`touch`, `due_words`, `review_count`); practice start in `engine`; `GET /learn/review`, `POST /learn/practice/start`; Yard CTA in `CastleHub`.

---

## PATTERN: Leagues (weekly XP cohorts)

**WHY IT WORKS:** Social pressure without needing a friends graph; weekly reset renews motivation.  
**RISK:** XP farm; forever ORDER BY total XP; toxic competition for kids.  
**FOXINBURG ADAPTATION:** 7-day window from `xp_transactions`; tiers bronze/silver/gold by weekly XP thresholds; Glory room UI. No combat. True cohort buckets / promo / demotion **not** shipped — currently global child board.  
**IMPLEMENTATION:** `learn.league`; `GET /learn/league` + embedded in `home`; UI glory room in `CastleHub`. **gap:** no weekly cohort assignment, no demotion, no season chests.

---

## PATTERN: Shop for convenience (not curriculum)

**WHY IT WORKS:** Monetizes urgency (hearts/freeze) without selling grades.  
**RISK:** Pay-to-win stickers; kids pressure parents; non-idempotent buys.  
**FOXINBURG ADAPTATION:** SKUs: hearts refill, streak freeze, cosmetic stickers/items. Server spend + grant; shop room in castle.  
**IMPLEMENTATION:** `config.SHOP`, `learn.buy`; `GET/POST /learn/shop*`. Cosmetic items may lack full equip UX (**partial**).

---

## PATTERN: Sticker / achievement collection

**WHY IT WORKS:** Long-term collection goal beyond daily XP; identity via album.  
**RISK:** Sticker spam; client-minted collectibles.  
**FOXINBURG ADAPTATION:** Inventory stickers with rarity; album endpoint; unit stickers + perfect/streak kinds in catalog. Grant via lesson/shop/quest rewards only.  
**IMPLEMENTATION:** `learn.album`, `GET /learn/stickers`; UI album page + `StickerDrawer`. **gap:** chest loot tables / rarity drop rules incomplete vs `STICKER_SYSTEM.md`.

---

## PATTERN: Soft social (leaderboard without chat)

**WHY IT WORKS:** Motivation via rank without moderation hell.  
**RISK:** Names/avatars harassment; comparing kids unfairly.  
**FOXINBURG ADAPTATION:** Display names on weekly board only; no DMs, no friends graph in v1. Friends/gifts later per `SOCIAL_SYSTEM.md`.  
**IMPLEMENTATION:** league board only. **gap:** friends, gifts, co-op — missing.

---

## PATTERN: Experimentation + analytics IDs on CTAs

**WHY IT WORKS:** Duo ships habit changes behind flags; every CTA has a measurable event.  
**RISK:** Event soup; no funnel ownership.  
**FOXINBURG ADAPTATION:** `analytic_id` on NBA (`quest.daily.claim`, `world.yard.startPractice`, `world.school.startLesson`); `data-analytic-id` in UI. Full event bus / experiments **not** wired.  
**IMPLEMENTATION:** brain fields + DOM attrs. **gap:** no ingest to Metrika/GA for world app; `PRODUCT/EXPERIMENTS.md` / analytics pipeline missing in world.

---

## PATTERN: Placement → right difficulty

**WHY IT WORKS:** Avoids boredom (too easy) and quit (too hard).  
**RISK:** Long test drop-off; gaming the test for higher unlock.  
**FOXINBURG ADAPTATION:** Short adaptive placement specified; v1 always `family-L1`. No coins for placement.  
**IMPLEMENTATION:** **gap** — `PRODUCT/PLACEMENT_ENGINE.md` only; no API/UI.

---

## Gap list (Duo-shaped vs live)

| Pattern | Status |
|---|---|
| NBA + why | **Shipped** |
| Hearts + paid refill + regen | **Shipped** |
| Streak + freeze consume | **Shipped** |
| Streak milestone bonuses | **Fake/config only** |
| SRS + practice | **Shipped** |
| Daily quests claim | **Shipped** |
| League weekly window | **Shipped (global board)** |
| League cohorts/seasons | **Missing** |
| Path locks | **Shipped** (dev unlock flag) |
| Shop | **Shipped** (thin catalog) |
| Chests / loot | **Mostly visual** |
| Placement | **Missing** |
| Friends/social | **Missing** |
| World analytics ingest | **Missing** (IDs only) |
