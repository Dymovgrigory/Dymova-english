# Foxinburg Fantasy UI Kit — Design

**Date:** 2026-09-16  
**Budget:** up to 900 Meshy credits (`nano-banana-pro`, 9 cr/image). Call user when balance hits 0 for a new key.

## Goal

Replace cheap pill buttons, full-bleed stretched rows, and emoji icons with a **project-wide fantasy castle chrome** matching the user’s RPG frame references and Foxinburg brand (`#3a2953`, `#241a30`, `#f5ed75`, `#7fd8c9`).

## Visual system

| Element | Treatment |
|--------|-----------|
| Panels / fields | Centered max-width plaques (~min(92vw, 420px)), double gold/teal metallic borders, diamond mid-nodes, soft inner gradient + highlight |
| Primary CTA | Ornate horizontal banner button, touch target ≥44px, readable on phone |
| Secondary CTA | Same family, teal or ghost metal — not tiny text links |
| Stat rows | Compact framed rows: icon + label + value grouped, not label-left/value-far-right across full screen |
| Location header | Fantasy title plate (small white hint under gold title), not bare white caption |
| HUD icons | Drawn icons: heart, streak, coin, XP — no emoji |
| Stickers | 11 Banana Pro illustrated stickers; room shows CTA → animated slide-out collection drawer |
| Glory | Lemon logo (`brand-assets/logo-stamp-yellow.png`) on a fantasy flag; league stats in framed plaque |
| Map bottom nav | Fantasy chip buttons from kit, not rounded-full pills |

## Asset plan (Banana Pro)

1. **UI atlas — frames** (16:9): empty gold panels, square/rect, pointed ends  
2. **UI atlas — buttons** (16:9): primary gold, teal, ghost, close, arrows  
3. **UI atlas — ornaments** (16:9): dividers, corner brackets, gem nodes  
4. **Icons** (1:1): heart, streak flame, coin, XP bolt (brand colors)  
5. **Map chips** (16:9): horizontal building nav plaques  
6. **Glory flag** (image-to-image from logo): lemon stamp on purple/gold fantasy banner  
7. **Stickers ×11** (1:1): family, school, room, pets, food, play, satp, hello, perfect, streak, rainbow — premium die-cut sticker look, high detail, no text  

Retries allowed within budget. Prefer atlases + CSS/SVG 9-slice for crisp scaling; PNGs for icons/stickers/flag.

## Code standard

New module `world/src/ui/fantasy/`:

- `FantasyFrame`, `FantasyButton`, `FantasyStat`, `FantasyIcon`, `FantasyTitlePlate`, `StickerDrawer`
- `RoomChrome` re-exports these; `CastleHub` + learn pages migrate to the kit
- Stickers: `/world/ui/stickers/{id}.png`; API keeps `emoji` fallback until art loads

## Success

Opening any building shows more art than chrome, but every control is ornate, proportional, and tappable. Map nav and rooms share one visual language. Stickers open via a beautiful button into an animated drawer — not a cramped scroll of emoji.
