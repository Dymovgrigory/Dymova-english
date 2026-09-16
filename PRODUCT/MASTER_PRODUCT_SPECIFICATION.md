# MASTER PRODUCT SPECIFICATION — Мир Фоксинбурга

**Status:** living source of truth  
**Date:** 2026-09-16  
**Inputs:** `PROMT_WORLD.md`, `PROJECT_AUDIT.md`  
**Product type:** Next-generation educational game platform (EN learning)

---

## 1. Mission

Build **Мир Фоксинбурга** — one living world where learning, character, economy, social, AI, content, and analytics are one system.

**Feeling:** “Я возвращаюсь в свой Мир Фоксинбурга” — not “открываю раздел сайта.”

---

## 2. Non-goals (explicit)

- Landing / brochure site  
- Generic LMS dashboard  
- Duolingo clone UI  
- Background-image “world” with HTML panels only  
- Client-trusted XP / coins / rewards  
- Casino gamification that overrides learning outcomes  

---

## 3. Core loop

```
USER ACTION → DOMAIN EVENT → DB TRANSACTION → USER/LEARNING/GAME STATE
  → RECOMMENDATION → SCREEN / WORLD REACTION → FOXY → REWARD → ANALYTICS
```

Learning outcome **>** engagement metric.

---

## 4. Current baseline (from audit)

| Layer | Reality today |
|---|---|
| World | 2D castle hub (`/world`) — keep as v1 shell |
| Learning | Server-graded lessons + practice + SRS |
| Economy | Ledger XP/coins — harden hearts/shop/quests |
| Identity | localStorage player key — must become real sessions |
| 3D | Not shipped — optional later behind flag |
| Parent/Teacher/Admin | Not shipped |

Full detail: [`PROJECT_AUDIT.md`](../PROJECT_AUDIT.md).

---

## 5. Target platform pillars

1. **World** — locations with purpose, hotspots, state, unlocks  
2. **Learning Engine** — lessons, challenges, SRS, mastery  
3. **Fox Brain** — weak/strong skills → next best action  
4. **Economy** — transactional coins/XP/keys/chests  
5. **Progression** — path, stickers, achievements, leagues  
6. **Social** — friends, gifts (architecture first)  
7. **AI Tutor** — assisted practice under curriculum rules  
8. **CMS / Admin / Teacher / Parent** — separate journeys  
9. **Analytics + Experiments** — event IDs, funnels, flags  

---

## 6. World locations (v1 → v2)

**v1 (shipped / polish):** Castle map → School, Shop, Glory, Lexicon, Stickers, Yard, Nest, Quests  

**v2 (expand):** Library, Arena, Workshop, Observatory, Adventure Gate, Garden, Marketplace depth  

Each location: identity, purpose, hotspots, learning hook, rewards, unlock rules, analytics.

---

## 7. UX principles (World-first)

- Fullscreen-first primary action  
- UI *is* world when possible (door = enter, chest = reward, flag = brand)  
- HUD light; secondary in modal / focused overlay  
- Mobile = separate composition, not shrunk desktop  
- No giant stacked panels under a hero image  

Design system docs live in `/PRODUCT/DESIGN_PRINCIPLES.md` and `FOXINBURG_VISUAL_LANGUAGE.md` (to be filled).

---

## 8. Engineering rules

- Frontend never source of truth for balances or completion  
- Idempotent reward transactions  
- Typed API contracts  
- Feature/domain folders over giant components  
- Preserve working learn loop while migrating  

---

## 9. Phased roadmap (binding order)

| Phase | Name | Exit criteria |
|---|---|---|
| 0 | Harden | Quest gate, hearts, shop idempotency, TTS auth, abuse tests green |
| 1 | Identity | Signed sessions; family-ready keys |
| 2 | Unifyменты /PRODUCT | Specs for economy, learning, quests, world, visual language |
| 3 | Data plane | Postgres prod; constraints + indexes |
| 4 | Fox Brain v0 | Weak skills + next-best-action API |
| 5 | Design system | Fox* components; kill generic pills |
| 6 | World polish | Location chrome; logo-in-world; navigation |
| 7 | Quests / rewards | Daily claims, chests, achievements |
| 8 | Personalization | Placement + recommendation |
| 9 | Social / Teacher / Parent / Admin | Separate surfaces |
| 10 | AI Tutor | Safety + curriculum gates |
| 11 | Analytics / Experiments | Stable analytic IDs |
| 12 | QA | Playwright E2E + visual + security |

**Do not start Phase 6–12 polish as if Phase 0 is optional.**

---

## 10. Success metrics (product)

- Lesson completion & retention (D1/D7)  
- Review completion (SRS adherence)  
- Speaking attempts / successful echoes  
- Streak health (with freeze/recovery)  
- Time-to-first-reward (onboarding)  
- Abuse rate (duplicate rewards ≈ 0)  

---

## 11. Document map

| Doc | Role |
|---|---|
| `PROMT_WORLD.md` | Master directive |
| `PROJECT_AUDIT.md` | As-is technical truth |
| `MASTER_PRODUCT_SPECIFICATION.md` | This file |
| `/PRODUCT/*` | Domain specs |
| `/RESEARCH/*` | Pattern research (no UI cloning) |
| [`RESEARCH/REFERENCE_MATRIX.md`](../RESEARCH/REFERENCE_MATRIX.md) | Duo \| Puzzle \| now \| target \| priority |

---

## 11b. Reference-driven priorities

Owner mandate: Duo + Puzzle English are references for **logic and functionality**, not visual clones (`PROMT_WORLD.md` §2).

Binding matrix + gap list (shipped / fake / missing): **[`RESEARCH/REFERENCE_MATRIX.md`](../RESEARCH/REFERENCE_MATRIX.md)**.

**Next build (P0 from matrix):** streak milestone awards · league cohorts · chest/loot v0 · placement stub · parent provisioning · speak attempt telemetry.  
Learning-loop detail: [`LEARNING_ENGINE.md`](./LEARNING_ENGINE.md) · NBA: [`FOX_BRAIN.md`](./FOX_BRAIN.md).

---

## 12. Immediate execution (next session)

1. ~~Phase 0 security/economy patches~~ done  
2. ~~Fill `/PRODUCT` + `/RESEARCH` + architecture/DB~~ done 2026-09-16  
3. ~~Fox Brain v0 `next_best_action` on `/learn/home`~~ done  
4. ~~Phase 1 Identity slice~~ done 2026-09-16: `wses.*` sessions, child-only public create, guardianship  
5. ~~Reference matrix expand~~ done 2026-09-16 — see §11b  
6. **Next code (reference-driven):** wire `STREAK_BONUSES`; league cohorts; chest loot v0; parent provisioning API; speak telemetry  
7. Visual chrome / Meshy wiring — parallel agent; do not block on art for economy/Brain P0  

