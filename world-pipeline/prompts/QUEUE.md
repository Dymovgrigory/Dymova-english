# Очередь генерации Meshy

Ключ — `secrets/meshy.env`. Модель и промпты не менять (STYLE_LOCK). Качество — модель flare (без `--budget`).

## Готово (2026-09-17)
Все слова Spotlight 1–4, эмоции SP4, 30 этажей, 4 башни классов, фоны, спрайты окон.

## Замок — цельная диорама (2026-09-17, сессия 121)
Итог: `castle-diorama.webp` — спрайты зданий на площадках `castle-grounds.webp`, сплавленные flare image-to-image.
Клик/hover — карта зон `castle-hotspots.png` + маски `masks/*.png` + `world/src/castle/castle-hotspots.json`.
Переставить здание: поправить `SLOTS` в `castle_compose.py`, затем
```bash
python3 world-pipeline/castle_compose.py compose            # коллаж, бесплатно
python3 world-pipeline/castle_compose.py fuse --variants 2  # flare, 12 кр. за вариант
python3 world-pipeline/castle_compose.py masks --pick world-pipeline/word-art/castle/fused-XXXX.png
```
