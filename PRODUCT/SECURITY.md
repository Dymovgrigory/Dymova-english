# SECURITY.md — World

Frontend is **not trusted**.

## Done (Phase 0)

- Lesson grading server-side; answers stripped from public items  
- Ledger UNIQUE idempotency on awards  
- Shop spend stable keys + `applied` flag  
- Hearts restore = paid  
- Quest complete requires all steps  
- TTS requires `X-World-Player`  
- Prod `UNLOCK_ALL` default 0  
- Optional HMAC on player key (`WORLD_PLAYER_SECRET`)

## Done (Phase 1 slice — 2026-09-16)

- Opaque sessions `wses.<id>.<secret>` in `auth_sessions` (revocable, 30d TTL)  
- Public `POST /players` is **child-only** (no self-admin/parent/teacher)  
- Legacy HMAC tokens still accepted when `WORLD_PLAYER_SECRET` is set  
- `guardianship` table + `core.link_guardian` / `list_wards` (family-ready)

## Open

| Issue | Severity |
|---|---|
| No email/OAuth accounts yet | Medium |
| Parent/teacher provisioning API | Medium |
| Token theft = full clone until revoke endpoint | High |
| Sprint score is client-supplied (capped daily) | Medium |
| No rate limit on TTS / answers | Medium |
| SQLite under many concurrent kids | Medium |

## Required on every value path

transactions · unique constraints · idempotency · no client amounts · RBAC when identity ships.
