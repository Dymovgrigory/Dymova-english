# GAME_UX_PATTERNS.md

Game UX / casual RPG / AAA-adjacent **interaction** patterns.  
Not visual cloning: no copying HUD chrome, fonts, or compositions from any reference app.

Cross-ref: [`REFERENCE_MATRIX.md`](./REFERENCE_MATRIX.md).

---

## PATTERN: Game home vs admin dashboard

**WHY IT WORKS:** One primary verb; HUD not a table; identity of “my place.”  
**RISK:** Hiding progress so deep that parents can’t see it.  
**FOXINBURG ADAPTATION:** `/learn` + castle `/world` as Game Home; stats live in nest/glory rooms; mission plaque = NBA.  
**IMPLEMENTATION:** `WorldBar`, `CastleHub`, `LearnTrail`, mission plaque / fantasy chrome.

---

## PATTERN: Next best action with WHY

**WHY IT WORKS:** Removes paralysis; trust when reason is visible.  
**RISK:** Opaque “Continue”; lying CTAs.  
**FOXINBURG ADAPTATION:** CTA includes **why** from Fox Brain; deep link into school/yard/quests.  
**IMPLEMENTATION:** `brain.next_best_action`; learn + castle banner prefer server payload over local `missionFor`.

---

## PATTERN: Reward ceremony

**WHY IT WORKS:** Explains WHAT / WHY / HOW MUCH; marks session end.  
**RISK:** Slot-machine feel; fake chests with no server loot.  
**FOXINBURG ADAPTATION:** Finish screen with stars, XP/coins from server, Foxy cheer; chest art is ceremony. Real chests = server loot tables later.  
**IMPLEMENTATION:** lesson finish UI; `core.award` ledger. **gap:** chest idle/glow assets unused; no loot engine.

---

## PATTERN: World as hub (locations with purpose)

**WHY IT WORKS:** Identity + return; each place has a job (school learn, yard review, shop spend…).  
**RISK:** Wallpaper + HTML panels; dead hotspots.  
**FOXINBURG ADAPTATION:** Hotspots are interactions; rooms are docks over the map; pulse opens the right room after finish.  
**IMPLEMENTATION:** `CastleHub` + `buildings.ts`; rooms school/shop/glory/lexicon/stickers/yard/nest/quests.

---

## PATTERN: Lightweight HUD

**WHY IT WORKS:** World stays visible; currency awareness without dashboard.  
**RISK:** Missing hearts/streak → surprise fail.  
**FOXINBURG ADAPTATION:** XP, coins, hearts, streak on bar; stickers on demand. Sync from `/learn/home`, not localStorage invent.  
**IMPLEMENTATION:** `WorldBar`; home sync in CastleHub / learn pages.

---

## PATTERN: Fullscreen activity

**WHY IT WORKS:** Lesson is the sport, not a widget in a scroll page.  
**RISK:** Losing world context; harsh back navigation.  
**FOXINBURG ADAPTATION:** Fullscreen lesson; Foxy + hearts remain; return pulse to castle.  
**IMPLEMENTATION:** `/learn/[lessonId]`, `/learn/sprint`.

---

## PATTERN: Soft fail & recovery

**WHY IT WORKS:** Keeps kids in flow; loss without rage-quit.  
**RISK:** Infinite free retries destroy economy.  
**FOXINBURG ADAPTATION:** Hearts + paid refill + regen; streak freeze on gap; practice still available when hearts empty for review path (practice uses own start). No shame copy.  
**IMPLEMENTATION:** engine hearts; shop; soft Foxy states in `foxi_poses` / `FoxiGuide`.

---

## PATTERN: Quests as world narrative (not checklist app)

**WHY IT WORKS:** Goals feel like adventures; multi-step teaches the map.  
**RISK:** Parallel quest systems confuse; client completes without steps.  
**FOXINBURG ADAPTATION:** (1) **Story quests** in `core` with server-ordered steps; (2) **Daily quests** in `learn` with claim ledger. Gazebo room for dailies.  
**IMPLEMENTATION:** `/quests*` + `advance_quest_step`; `/learn/quests` + claim. UI claim in CastleHub. **gap:** story quest content sparse (e.g. first-day); few steps wired from lesson finish.

---

## PATTERN: Economy that is felt, not displayed as a ledger

**WHY IT WORKS:** Coins mean “I can buy freeze”; XP means “league moves.”  
**RISK:** Spreadsheet economy; client mint.  
**FOXINBURG ADAPTATION:** All mint via `core.award` / `spend` with idempotency keys; types like `DAILY_QUEST`, `SHOP_BUY`, `PRACTICE_REWARD`.  
**IMPLEMENTATION:** `core.py` ledger; config XP/COIN tables.

---

## PATTERN: Motion for hierarchy, not noise

**WHY IT WORKS:** Directs eye to CTA and reward; presence.  
**RISK:** Confetti addiction; accessibility issues.  
**FOXINBURG ADAPTATION:** Pulse building, sticker drawer enter, finish cheer — intentional 2–3 motions. No casino spin.  
**IMPLEMENTATION:** `Fx.tsx`, pulse query `?pulse=quests`, fantasy chrome. Visual polish may continue on another agent — do not fight UI for this research task.

---

## Gap list

| Pattern | Status |
|---|---|
| Game home / castle | **Shipped** |
| NBA + why | **Shipped** |
| Reward ceremony | **Partial** (real XP; chest loot fake) |
| Location purposes | **Shipped** |
| HUD sync from server | **Mostly shipped** |
| Story quests depth | **Thin / partial** |
| Daily claim | **Shipped** |
| Loot / chests engine | **Missing** |
