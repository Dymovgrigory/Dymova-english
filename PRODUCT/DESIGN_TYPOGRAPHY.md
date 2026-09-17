# DESIGN_TYPOGRAPHY.md

Live fonts (`world/src/app/layout.tsx`):

| Role | Face | Use |
|---|---|---|
| Display | Montserrat | titles, plaques, level |
| UI | Nunito | body, buttons, HUD labels |

Both cover RU + EN. Numeric HUD uses the same faces (tabular nums via CSS where needed).

## Roles (target)

Display · UI · Numeric · Caption · Reward · Level · XP · Coin · Badge · Royal accent.

Royal/fantasy accent may be a **display cut of Montserrat** + lemon, not a blackletter that fails Cyrillic.

## Rules

- Readable at 14px on 390px width  
- No random third font in a screen  
- Reward numbers animate but remain readable (`prefers-reduced-motion` → static)
