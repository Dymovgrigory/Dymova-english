# EDTECH_PATTERNS.md

Premium EdTech / LMS / school-platform mechanics (not visual templates).

Cross-ref: [`REFERENCE_MATRIX.md`](./REFERENCE_MATRIX.md).

---

## PATTERN: Mastery-based progression

**WHY IT WORKS:** Don’t advance on weak foundations; stars/levels communicate readiness.  
**RISK:** Gate frustration; false mastery from lucky taps.  
**FOXINBURG ADAPTATION:** Stars 0–3 per lesson; unit unlock via checkpoint stars (`CHECKPOINT_STARS_TO_UNLOCK`); Fox Brain sends review before new when due is high. Dev `WORLD_UNLOCK_ALL` must never ship as default.  
**IMPLEMENTATION:** `lesson_progress.stars`, `engine.get_path` locks; `config.CHECKPOINT_*`; brain priority.

---

## PATTERN: Placement test → personal starting point

**WHY IT WORKS:** Right difficulty → higher D1 completion.  
**RISK:** Long test drop-off; parents skip; gaming for status.  
**FOXINBURG ADAPTATION:** Short adaptive 8–12 items; no coins; result → starting unit + tags for Fox Brain. World placement ≠ school CRM diagnostic booking.  
**IMPLEMENTATION:** **gap** — `PRODUCT/PLACEMENT_ENGINE.md` only.

---

## PATTERN: Parent dashboard (buyer journey)

**WHY IT WORKS:** Buyer sees learning outcomes, not coin theater; reduces churn.  
**RISK:** Copying student game UI; privacy between siblings.  
**FOXINBURG ADAPTATION:** Separate Parent journey; show skills/time/mistakes/streak health; guardianship links. Public signup is **child-only**.  
**IMPLEMENTATION:** `core.link_guardian`, `list_wards`; roles in `_ALLOWED_ROLES`. **gap:** parent HTTP API + UI; staff provisioning for elevated roles.

---

## PATTERN: Teacher assignment / classroom

**WHY IT WORKS:** Homework accountability; B2B school channel.  
**RISK:** Colliding with BigBen CRM timetable; double sources of truth.  
**FOXINBURG ADAPTATION:** World assignments ≠ CRM schedule. Link identities via `external_key` only; keep CRM isolated process.  
**IMPLEMENTATION:** **gap** — `PRODUCT/TEACHER_JOURNEY.md`; world-backend has no assignment tables yet. Isolation tests in `test_isolation.py`.

---

## PATTERN: Content CMS + version pin

**WHY IT WORKS:** Non-dev editors; safe live updates.  
**RISK:** Unversioned edits break active sessions.  
**FOXINBURG ADAPTATION:** Packs in Python now; session stores built items JSON at start — pin by construction. Future CMS must pin `content_version` on session.  
**IMPLEMENTATION:** engine session payload; CMS **gap**.

---

## PATTERN: Attempt metadata for learning science

**WHY IT WORKS:** Latency, hints, attempt_n feed personalization without changing rewards unfairly.  
**RISK:** Privacy; noisy features.  
**FOXINBURG ADAPTATION:** Persist answer metadata with no reward effect; feed Fox Brain v1+.  
**IMPLEMENTATION:** session `answers` JSON in DB; brain reads `wrong_count` / strength. **gap:** richer latency/hint fields not consistently stored/queried.

---

## PATTERN: Safety & child accounts

**WHY IT WORKS:** Compliance + trust for parents.  
**RISK:** Over-blocking speech mic; data retention.  
**FOXINBURG ADAPTATION:** Child-only public create; opaque `wses.*` sessions; logout revoke; TTS rate limit. No free chat AI in v0.  
**IMPLEMENTATION:** `auth.py`, `POST /players`, `POST /session/logout`; TTS limit in `api.py`.

---

## PATTERN: Analytics funnels (EdTech SaaS)

**WHY IT WORKS:** Know where onboarding dies; A/B lesson length.  
**RISK:** Vanity metrics (XP) over learning outcomes.  
**FOXINBURG ADAPTATION:** Prefer lesson completion, review adherence, speak attempts, streak health, abuse rate ≈ 0. Stable `analytic_id`s first.  
**IMPLEMENTATION:** IDs on NBA; **gap:** world event pipeline; site GA4 ≠ world app yet. Specs: `PRODUCT/ANALYTICS.md`, `PRODUCT_METRICS.md`.

---

## PATTERN: Offline / low-connectivity

**WHY IT WORKS:** Commute / countryside / school wifi fails.  
**RISK:** Client-trusted completion; sync conflicts mint XP.  
**FOXINBURG ADAPTATION:** If offline ever ships: queue answers, **server re-grade** on sync; never trust client XP. v1 = online-only.  
**IMPLEMENTATION:** **gap**.

---

## Gap summary

| Area | Status |
|---|---|
| Mastery stars + locks | **Shipped** |
| Placement | **Missing** |
| Parent surface | **Missing** (DB link only) |
| Teacher assignments | **Missing** |
| CMS | **Missing** (packs OK) |
| Attempt science depth | **Partial** |
| Child session identity | **Shipped** (Phase 1 slice) |
| Offline | **Missing** |
| World analytics ingest | **Missing** |
