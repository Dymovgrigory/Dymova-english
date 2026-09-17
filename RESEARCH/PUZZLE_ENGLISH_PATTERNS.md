# PUZZLE_ENGLISH_PATTERNS.md

Mechanics / learning design research only.  
Do **not** copy Puzzle UI, teacher faces, movie frames, brand, or screen layouts.

Cross-ref: [`REFERENCE_MATRIX.md`](./REFERENCE_MATRIX.md).

---

## PATTERN: Authentic input as core motivation (movies / media)

**WHY IT WORKS:** Adults feel “real English”; high engagement; vocabulary in context.  
**RISK:** Wrong for 6–8yo oral-first; licensing cost; passive watching without production.  
**FOXINBURG ADAPTATION:** Not movies. “Puzzle” = **word/phrase assembly**, match, listen, tap-build inside School of Foxy. Context = family/pets/school places of the world, not Netflix clips.  
**IMPLEMENTATION:** lesson item kinds in `items.py` / engine builders (`match`, `listen`, `word_card`, `tap_build`, `type_en`); packs `starter_course.py`, `phonics_course.py`.

---

## PATTERN: Teacher-ish explainer before drills

**WHY IT WORKS:** Trust + grammar clarity; reduces “why am I tapping?”  
**RISK:** Lecture breaks flow; YouTube-as-home kills world identity.  
**FOXINBURG ADAPTATION:** Short **theory cards** + Foxy teaching pose inside the lesson stage — not a video library as home. Theory is a stage, then words/listen/practice.  
**IMPLEMENTATION:** `lesson_theory.py`; UI `TheoryArt`, lesson stages in `[lessonId]/page.tsx`.

---

## PATTERN: Explicit vocabulary trainer + spaced lists

**WHY IT WORKS:** Learners see word progress; SRS lists make forgetting visible.  
**RISK:** Glossary grind disconnected from “course.”  
**FOXINBURG ADAPTATION:** Words live in **units of the world** (family, pets…) with images; `word_stats` strength; Yard is the trainer **place**. Sprint is a picture-choice micro-workout with server session (anti-abuse).  
**IMPLEMENTATION:** `word_library` / `vocabulary.py`; `srs.touch` on answers; `GET /learn/words/{unit_id}`, `GET /learn/review`; sprint `POST /learn/sprint` + answer + finish; UI `/learn/sprint`, Yard → practice.

---

## PATTERN: Separate “workouts” vs linear course

**WHY IT WORKS:** Flexible practice when course feels heavy; retention of weak skills.  
**RISK:** Product splits into two apps; home CTA unclear.  
**FOXINBURG ADAPTATION:** Yard is a **castle location**, not a second product. Fox Brain routes to review when due. Practice rewards capped so it cannot replace lessons for coin farm.  
**IMPLEMENTATION:** `/learn/practice` (same lesson player, `startPractice`); `PRACTICE_COINS_DAILY_CAP`; castle `yard` room.

---

## PATTERN: Listening as first-class skill

**WHY IT WORKS:** Comprehension before production; audio anchors pronunciation.  
**RISK:** TTS fatigue; autoplay hostility; no offline cache.  
**FOXINBURG ADAPTATION:** Listen items + SpeakButton; server TTS endpoint rate-limited; optional pregen clips. Auto-speak on some item advances.  
**IMPLEMENTATION:** `tts.py`, `GET /api/world/tts`; `SpeakButton`, `speak.ts`; pregen scripts under `world-backend/scripts/`. **gap:** offline pack / Service Worker — missing.

---

## PATTERN: Speaking / echo practice

**WHY IT WORKS:** Production closes the loop; parents hear “they speak.”  
**RISK:** Bad ASR UX; shame on fail; client-only scoring that unlocks rewards unfairly.  
**FOXINBURG ADAPTATION:** `EchoMic` + local `echoScore` (Web Speech) as **gate for item progress**, not for minting XP (XP still from server-graded lesson answers). Soft pass threshold; no public shame.  
**IMPLEMENTATION:** `world/src/lib/echo.ts`, `EchoMic.tsx`, `PhraseCard` / `WordCard`. **gap:** no server-side speak attempt analytics; no teacher-visible speak stats; ASR quality varies by browser.

---

## PATTERN: Translation / RU↔EN as scaffold

**WHY IT WORKS:** Clarity for RU-speaking parents & beginners.  
**RISK:** Translation dependency; never thinking in EN.  
**FOXINBURG ADAPTATION:** RU prompts early; push to EN production (echo, type_en, tap_build). Course meta `from: ru` on home.  
**IMPLEMENTATION:** item prompts in packs; home `course.from`.

---

## PATTERN: Progress dashboards for adult buyers

**WHY IT WORKS:** Puzzle’s adult users want stats; parents buy outcomes.  
**RISK:** Student UI becomes a spreadsheet.  
**FOXINBURG ADAPTATION:** Child stays in-world; **Parent journey** is a separate surface (skills, time, mistakes) — not a clone of Glory XP theater.  
**IMPLEMENTATION:** **gap** for parent UI; backend has `guardianship` / `link_guardian` / `list_wards` in `core.py` — provisioning API not public. Spec: `PRODUCT/PARENT_JOURNEY.md`.

---

## PATTERN: Content depth & themed packs

**WHY IT WORKS:** Retention via “new series”; editorial freshness.  
**RISK:** Unversioned live edits break mid-session.  
**FOXINBURG ADAPTATION:** Python course packs + pin session to built items at start; CMS later with version pin.  
**IMPLEMENTATION:** packs + `catalog.py`; CMS **gap**.

---

## Gap list (Puzzle-shaped vs live)

| Pattern | Status |
|---|---|
| Puzzle-like item kinds (match/listen/build) | **Shipped** |
| Theory before drills | **Shipped** |
| Vocab SRS + Yard | **Shipped** |
| Sprint workout | **Shipped** (server score) |
| TTS listen | **Shipped** (rate-limited) |
| Speaking echo | **Partial** (client score; no server speak ledger) |
| Parent progress surface | **Missing** (guardianship DB only) |
| Media/movie core | **Explicitly rejected** (by design) |
| Offline | **Missing** |
