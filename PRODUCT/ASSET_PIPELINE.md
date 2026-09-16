# ASSET_PIPELINE.md

1. Still: Meshy `nano-banana-pro` 16:9 (9 cr) → `world/public/world/...`
2. Optional refine / 3D only after owner OK
3. Compress large PNG (≤~700KB for ornaments)
4. Never change map hitboxes when swapping map art without re-tracing polys
5. Interiors: Meshy `nano-banana-pro` image-to-image from current room + `logo-stamp-yellow.png` so brand lives **in** the location. Keep `*-prev.png` before overwrite.
6. **2026-09-16 batch (~52 tasks, ~492 cr):** logo i2i on yard/shop/lexicon/stickers/quests (+ learn/gates/library/establishing); UI atlases (frames/buttons/ornaments/nav/chrome AD06); chrome icons lock/check/warning/info/audio/mic/settings/back/forward; rewards chest/bursts; Foxi poses; cinematic variants. Manifest: `world/public/world/_gen/meshy-manifest-2026-09-16.json`. **map.png untouched.** school/glory/nest already branded — skipped.
