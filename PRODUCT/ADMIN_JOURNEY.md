# ADMIN_JOURNEY.md

Admin operates the platform, not a player HUD.

## Scope

users, content packs, quests, rewards, chests, locations, assets, AI prompts, experiments, flags, economy knobs, leaderboards.

## Status

Anyone can `POST /players` with `role=admin` today. **Forbidden in prod once identity ships.** Admin UI does not exist.

## Target

- Separate admin app or `/admin` with staff SSO.  
- RBAC: `staff.admin` ≠ player.role.  
- Audit log on economy edits.  
- Feature flags + experiment assignment.  
- Impersonate player **read-only** for support.
