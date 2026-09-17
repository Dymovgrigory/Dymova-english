# REFERENCE_MATRIX.md

Side-by-side mechanics matrix: **Duolingo | Puzzle English | Foxinburg now | Foxinburg target | priority**.

Rules (`PROMT_WORLD.md` §2): study mechanics / UX principles / learning loops only — **do not** copy UI, characters, texts, brand, illustrations, colors, screens, compositions, visual language.

Detail patterns: [`DUOLINGO_PATTERNS.md`](./DUOLINGO_PATTERNS.md) · [`PUZZLE_ENGLISH_PATTERNS.md`](./PUZZLE_ENGLISH_PATTERNS.md) · [`EDTECH_PATTERNS.md`](./EDTECH_PATTERNS.md) · [`GAME_UX_PATTERNS.md`](./GAME_UX_PATTERNS.md) · [`FOXINBURG_DIFFERENTIATORS.md`](./FOXINBURG_DIFFERENTIATORS.md).

**Priority legend:** P0 = next build · P1 = soon · P2 = later · — = keep / N/A

---

## Matrix

| Area | Duo | Puzzle | Foxinburg now | Foxinburg target | Priority |
|---|---|---|---|---|---|
| **Home / NBA** | Single primary CTA; habit return | Course home + trainers hub | `GET /learn/home` → Fox Brain `next_best_action` (`why`+`href`); learn + castle prefer server NBA | Always server NBA; Foxy voice; never opaque Continue | P0 polish |
| **Lesson loop** | Short session → feedback → XP → path | Theory/video → drills → vocab | Server start/answer/finish; stars; ledger XP/coins; finish ceremony | Same + richer item kinds (boss/timed); attempt metadata → Brain | P1 |
| **Hearts / energy** | Hearts; wait or Super | Energy/limits vary by product | 5 hearts; regen; leak on wrong; paid refill only | Same; soft Foxy on loss; no free restore forever | — keep |
| **Streak** | Streak + freeze + milestones | Weaker / different habit hooks | Streak + freeze buy + consume on gap; `STREAK_BONUSES` unused | Wire milestone awards; freeze UX clarity; recovery quest | **P0** |
| **SRS / review** | Practice from mistakes / Legendary | Vocab trainer + spaced lists | `srs.py` Leitner strength; Yard practice; review in NBA | Weak-word focused sessions; skill tags; parent-visible adherence | P1 |
| **Path vs world** | Linear skill path UI | Course tree + separate workouts | Path API + `LearnTrail`; castle locations are the product shell | Path data stays; **never** ship `/courses` as home; deepen location hooks | — keep |
| **Rewards / chests** | Chests, gems, seasonal | Points / achievements | Finish XP/coins + stickers; chest **art** on finish; no loot table | Server chests/loot; ceremony tied to stars; no casino override | **P0** loot v0 |
| **Leagues** | Weekly cohorts, promo/demo | Leaderboards less central | Weekly XP from ledger; global child board; Glory room | True cohorts (N players); soft promo/demo; season reset; kid-safe names | **P0** cohorts |
| **Shop** | Gems / Super / cosmetics | Subscription + extras | Coin shop: hearts, freeze, stickers, items | Expand cosmetics; equip in Nest; still no sell grades | P1 |
| **Social** | Friends, follows, quests | Community / weaker in-app social | League names only | Friends + gifts architecture; no open chat for kids | P2 |
| **Placement** | Placement / onboarding test | Level tests | Always `family-L1` | Short adaptive placement → profile → start unit | **P0** spec→API |
| **Parent** | Family plan / reports | Adult-first product | `guardianship` DB; no parent UI/API public | Parent journey: skills/time/mistakes; staff provision roles | **P0** provision |
| **Teacher** | Schools product | B2B / tutors less world-like | Isolated from BigBen CRM | Assignments in world ≠ CRM timetable; `external_key` link | P2 |
| **Analytics** | Heavy experimentation | Product analytics | `analytic_id` on NBA + DOM attrs; no world ingest | Event bus; funnels in `PRODUCT_METRICS`; experiments flags | P1 |
| **Offline** | Limited offline lessons | App caches vary | Online-only | If ever: queue + **server re-grade**; no client XP | P2 |
| **Speaking** | Speak exercises (ASR) | Listen/speak trainers | `EchoMic` client score; TTS listen; no speak ledger | Server speak attempts analytics; optional ASR upgrade; teacher/parent speak stats | **P0** wire analytics |

---

## Top 10 priorities for next build

1. **Streak milestone awards** — wire `config.STREAK_BONUSES` via `core.award` on threshold crossings (idempotent keys).  
2. **League cohorts** — bucket players into weekly groups of ~N; stop global board as final design.  
3. **Chest / loot v0** — server table for finish/perfect; stop chest-as-decoration-only.  
4. **Placement API stub** — even a fixed short quiz writing `placement_version` + start unit beats forever-L1 for older kids later.  
5. **Parent provisioning** — staff-only create parent/teacher + `link_guardian`; no public elevated signup.  
6. **Speak attempt telemetry** — log pass/fail + score to session answers / events (no XP from client echo alone).  
7. **Story quest depth** — connect lesson finish → `advance_quest_step` for first-day quest reliably.  
8. **World analytics ingest** — ship `analytic_id` hits to Metrika/GA or internal events table.  
9. **Shop equip / Nest** — owned cosmetics visible on hero (closes “fake shop” feel).  
10. **Fox Brain review threshold** — reintroduce due≥N / post-first-lesson nuance if review steals every open (product tune + tests).

---

## Gap list vs live code (`world-backend` + `world`)

### Shipped (real, tested)

| Capability | Where |
|---|---|
| Lesson start / answer / finish + stars + ledger | `engine.py`, `api.py` `/learn/lessons/*` |
| Hearts regen, leak, paid refill | `engine.refill_hearts`, `learn.restore_hearts` / shop |
| Streak bump + freeze consume | `engine._bump_streak` |
| Daily quests + claim idempotent | `learn.daily_quests`, `claim_daily_quest` |
| SRS + practice + review queue | `srs.py`, practice start, `GET /learn/review` |
| Sprint with server answers (anti-abuse) | `learn.sprint*` |
| Fox Brain NBA + weak_words copy | `brain.py`, `/learn/home` |
| League weekly XP board | `learn.league` |
| Shop buy SKUs | `learn.buy`, `config.SHOP` |
| Stickers album | `learn.album` |
| Path + locks | `engine.get_path` |
| TTS rate-limited | `api.py` `/tts` |
| Child session + logout revoke | `auth.py` |
| Guardianship primitives | `core.link_guardian` |
| Echo speaking gate (client) | `echo.ts`, `EchoMic` |
| Castle rooms wired to APIs | `CastleHub.tsx` |
| Story quest API (thin content) | `core` quests + `/quests*` |

### Fake / cosmetic / config-only

| Thing | Reality |
|---|---|
| Finish **chest** | Art + ceremony; **no** loot table / open-chest API |
| `STREAK_BONUSES` | Defined in `config.py`, **never awarded** |
| League “tiers” | Threshold labels on global board — **not** Duo-like cohorts/promo |
| Shop cosmetics (`foxi_cape`, banner) | Can grant inventory item; **equip/visual** thin or absent |
| `data-analytic-id` | Present in DOM; **no** world analytics pipeline |
| Local `journey.ts` mission | Fallback only; must not override server NBA as truth |
| Meshy reward bursts / podium assets | Present on disk; mostly **unwired** (see DEVLOG 117) |

### Missing

| Thing | Notes |
|---|---|
| Placement engine API/UI | Spec only: `PRODUCT/PLACEMENT_ENGINE.md` |
| Parent / teacher HTTP + surfaces | Roles exist; public create blocked; no dashboards |
| Friends / gifts / social graph | Spec: `SOCIAL_SYSTEM.md` |
| Offline mode | Explicitly out of v1 |
| Experiments framework | Spec: `EXPERIMENTS.md` |
| CMS / content versioning UI | Packs only |
| AI tutor chat | Spec: `AI_TUTOR.md`; Brain is deterministic |
| Server-authoritative speaking scores | Echo is client-side |
| True chest/loot + season rewards | Economy docs ahead of code |
| Postgres prod data plane | Still SQLite-oriented local (roadmap Phase 3) |

### Do not confuse

- Site GA4 / Tilda analytics ≠ World app events.  
- BigBen CRM offline groups ≠ World “offline mode.”  
- Another agent may polish Chrome visuals — this matrix is **product/logic truth**, not art direction.
