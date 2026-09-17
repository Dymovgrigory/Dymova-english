# Foxinburg World — Journey, Emotions & Premium Experience

**Date:** 2026-09-16  
**Status:** approved-by-owner-autopilot (build A→B→C without further questions)  
**Scope:** emotional journey (A), castle game loop (B), premium UI language (C)

---

## 1. Product spine

**Promise:** the child *speaks* English aloud from lesson one — and feels like a hero in a fairytale castle, not a student in a worksheet app.

**Audience:** child 6–9 (player), parent nearby (payer, observer). Device: phone-first (360–414).

**North star emotion arc (one session):**

| Beat | Moment | Child feels |
|------|--------|-------------|
| 1 Arrival | Name + Foxy greet | Curious, welcome, “this is MY world” |
| 2 Mission | Today’s quest / next lesson | Clear purpose, not overwhelm |
| 3 Speak | Echo-gate success | Brave, capable (“I said it!”) |
| 4 Triumph | Lesson finish stars/XP | Proud, celebrated |
| 5 Return | Castle opens / building glows | Reward, belonging |
| 6 Hook | Tomorrow’s tease | Anticipation |

If any beat is missing, the loop feels like homework with a pretty skin.

---

## 2. Chosen approach

**Spine-first (recommended).** Journey state drives copy, CTAs, and castle highlights. Castle buildings stay rewards around the learning spine. Premium UI is a constraint on every screen, not a separate “redesign project.”

Alternatives rejected for v1:

- **Castle-first sandbox** — fun but dilutes speaking promise.  
- **UI-only polish** — expensive look without emotional spine = empty luxury.

Build order: **A (journey) → B (castle loop) → C (premium depth)** in waves that each ship playable.

---

## 3. Client path (start → habit)

### 3.1 First open (day 0)

1. Full-bleed establishing art. Brand **Foxinburg** is the hero signal.  
2. One field: name. One yellow CTA: «Войти в мир».  
3. Soft secondary: already returning? skip to mission.  
4. No dashboard clutter, no stats wall, no card grid in the first viewport.

### 3.2 First session (day 0 continued)

1. Foxy speaks the child’s name. Pose: wave → cheer.  
2. Single mission card: «Урок 1 · Family» (or current unfinished).  
3. Optional: «Сначала глянуть замок» — castle as preview, then soft nudge back to lesson.  
4. Lesson: existing echo-gate pipeline unchanged.  
5. Finish screen: stars + XP + coins animate; CTA primary «В замок за наградой», secondary «Ещё урок».  
6. Castle: school or glory softly highlighted once; tooltip «Foxy ждёт».

### 3.3 Return session (day 1+)

1. Skip name if stored.  
2. Greeting by streak: «Снова здесь!» / «День 3 — огонь».  
3. If SRS due > 0 → mission = Yard practice. Else → next lesson.  
4. After lesson → castle pulse on the building that matches the reward (lexicon if new words, stickers if drop, glory if league XP).

### 3.4 Parent-adjacent (no parent cabinet)

Visible proof without a portal: stars on trail, lexicon growth, streak. No chat, no social, no teacher cabinet (master prompt §1).

---

## 4. Emotion design rules

1. **One job per screen** — one headline, one primary CTA.  
2. **Celebrate speaking** — echo success gets micro-burst + Foxy pose change, not only green check.  
3. **Castle is dessert** — never unlock the full shop loop before first spoken word in a session when hearts allow. Soft nudge, not hard lock after day 0.  
4. **Copy voice** — short Russian “ты”, Foxy as friend-coach. No канцелярит.  
5. **Numbers animate** — XP/coins/hearts never pop in cold.  
6. **Failure is soft** — wrong answer: heart tick + Foxy calm line; never shame.

---

## 5. Castle loop (layer B)

| Building | Emotional job | When to pulse |
|----------|---------------|---------------|
| School | Purpose / “go learn” | Always default mission |
| Yard | Courage to review | When `due > 0` |
| Lexicon | Collection pride | After lesson with new words |
| Glory | Status / league | After weekly XP gain |
| Shop | Treat | After coins earned |
| Stickers | Collection | After drop |
| Nest | Identity | Level / streak up |
| Quests | Today’s checklist | Always subtle |

Locked scenery stays non-interactive (no padlocks).

---

## 6. Premium UI language (layer C)

**Visual gold standard:** `world/public/world/cinematic/` —
`establishing.jpg`, `gates-foxi.jpg`, `library-courtyard.jpg`.
Any new Meshy still must match: purple masonry, teal glass/magic, warm lanterns,
golden-hour sky, volumetric depth, Foxy readable silhouette. Reject flat/generic AI.

**Keep brand tokens** from master prompt (`#3a2953`, `#241a30`, `#f5ed75`, `#7fd8c9`). Fonts: Montserrat + Nunito.

**Hard rules (align with site frontend rules):**

- First viewport = one composition: brand, one headline, one line, one CTA group, one full-bleed visual.  
- No card stacks in heroes. Cards only for interactive lists (shop, lexicon).  
- No Duolingo greens/blues.  
- Motion: 2–3 intentional motions per key surface (arrival wash, CTA press, reward burst).  
- Avoid generic AI look: no purple-on-white dashboard, no pill spam, no emoji as primary art.

---

## 7. Journey state (client)

Module `world/src/lib/journey.ts` (localStorage, no new backend tables in wave 1):

```ts
type JourneyState = {
  name: string;
  firstEnteredAt: string | null;
  lessonsFinished: number;
  lastFinishAt: string | null;
  lastRewardBuilding: BuildingId | null;
  seenCastleIntro: boolean;
};
```

Derived helpers: `isFirstSession`, `greetingLine(name, streak)`, `missionKind(due, nextLessonId)`, `finishCta()`.

Server remains authority for XP/hearts/SRS; journey only orchestrates UX.

---

## 8. Waves

| Wave | Delivers | Done when |
|------|----------|-----------|
| **1** | Arrival, greetings, mission focus, finish→castle pulse, journey module + tests | Child feels welcome→mission→triumph→return on one playthrough |
| **2** | Building-specific reward routing, quest emphasis, nest identity moments | Castle reacts intelligently after every finish |
| **3** | Deeper premium motion, sound cues, establishing art refresh if Meshy allows | Surfaces feel “expensive game”, not template |

Meshy: spend only when a wave needs new stills; report when balance is low. Current balance at start of this work: **233**.

---

## 9. Out of scope (unless owner reopens)

Parent cabinet, teacher tools, child chat, BigBen copy, changing echo-gate rules, new lesson pedagogy stages.

---

## 10. Success checks

- First viewport brand test: remove nav → still obviously Foxinburg.  
- One primary yellow CTA per key screen.  
- After finish, castle highlights a meaningful building once.  
- `journey` unit tests green; world `npm test` + backend pytest green; build green.
