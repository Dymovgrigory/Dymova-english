# DESIGN_PRINCIPLES.md

Aligned with `PROMT_WORLD.md` art directions 01–20 and anti-AI-slop rules.

## World-first

UI should feel like objects in Foxinburg (doors, seals, plaques, flags), not Bootstrap cards on a wallpaper.

## Geometry

- Prefer ornamental / clipped metal frames over rounded-full pills  
- Proportional max-width plaques (≈ `min(92vw, 22rem)`), not full-bleed label↔value rows  
- Touch targets ≥ 44px  

## Brand materials

| Token | Value |
|---|---|
| Plum | `#3a2953` |
| Night | `#241a30` |
| Lemon gold | `#f5ed75` |
| Teal magic | `#7fd8c9` |

## Hierarchy

Every screen: **PRIMARY** action, **SECONDARY** context, **TERTIARY** on demand.

## Motion

Meaningful only: confirm action, show progress, reward reveal. No decorative noise. Honor `prefers-reduced-motion`.

## Icons

Drawn brand icons (heart, streak, coin, XP) — no emoji as product chrome. Stickers are illustrated assets, opened via collection drawer.

## QA gates

Premium Product · Game UI · EdTech · Mobile · A11y · Performance · Brand — before calling a screen done.
