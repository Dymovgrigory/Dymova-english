# Арт-дирекция Фоксинбурга: «живая миниатюра»

> 🔒 Стиль утверждён владельцем 2026-09-17 и зафиксирован: `docs/world/STYLE_LOCK.md`. Этот файл — единственный источник промптов; не менять без прямого указания владельца.

Референс владельца: фотография рукотворной миниатюры каменного домика с плющом,
светящимися окнами и мшистой дорожкой (`miniature-stone-cottage-...avif`).

**Формула:** каждое изображение — фотография настоящей рукотворной диорамы,
снятая макрообъективом. Объём, фактура, свет и глубина резкости — всегда.

**Модель:** Meshy `gpt-image-2-5-flare` (1536×864 для 16:9, 9 кредитов).
Сравнение с `nano-banana-pro` и `gpt-image-2` на одном промпте —
`world-pipeline/word-art/compare-*.png`: flare единственная попала в уровень
референса.

## 1. Ядро стиля (добавляется к каждому промпту)

```
Ultra-detailed photorealistic miniature diorama, a handcrafted tabletop model
photographed with a professional macro lens, tilt-shift look, shallow depth of
field, creamy bokeh. Real handmade materials with rich micro-texture:
hand-carved lavender-grey stone with visible mortar and chipped edges, soft
green moss and tiny ivy, weathered oak wood, aged brass, deep plum roof tiles,
hand-painted porcelain. Warm golden glow from windows and lanterns, soft
volumetric dusk light, cinematic colour grading with plum, gold and teal
accents. Intricate details, 8k, award-winning product photography.
No text, no letters, no numbers, no watermark.
```

Палитра бренда вшита в материалы: фиолетовый → черепица и камень с лавандовым
оттенком, жёлтый → свет окон и латунь, бирюзовый → магические отблески.

## 2. Типы ассетов

| Ассет | Формат | Промпт (после ядра) |
|---|---|---|
| Башня учебника (герой пути) | 9:16 | A tall fairy-tale castle tower as a miniature diorama: stacked round floors with glowing arched windows, an outer spiral stone staircase, ivy, tiny brass lanterns, a plum tiled conical roof with a golden flag, standing on a mossy rock base with a winding stone path to a small wooden door; misty evening forest bokeh. |
| Этаж = модуль | 16:9 | Cutaway of one cosy round room inside the tower: **{сцена модуля}**. Plum tiled roof edge above, stone wall with ivy around the opening, glowing small windows on the outer wall, misty dusk forest bokeh behind. |
| Предмет-слово | 1:1 | A single **{предмет}** as a handcrafted miniature, centered, standing on a small round mossy stone pedestal, whole object in frame, soft warm dusk bokeh background. |
| Персонаж-слово | 1:1 | A handcrafted miniature figurine of **{персонаж}**, painted resin, centered on a small round mossy stone pedestal, soft warm dusk bokeh background. |
| Цвет | 1:1 | A tiny hand-blown glass jar filled with vivid **{цвет}** paint, a little wooden brush beside it, on a small round mossy stone pedestal. |
| Окно-урок | 1:1, без фона | Front view of a single arched window from a miniature castle diorama, hand-carved stone frame with moss, **{состояние}**, isolated object. |
| Фактура | 1:1 | Orthographic top-down texture photo of **{материал}**, even soft lighting, fills the frame, seamless look. |

Состояния окна: `lit` — тёплый свет сквозь свинцовые переплёты и ящик с
цветами; `dark` — тёмное стекло с бирюзовым отблеском; `shutters` — закрытые
старые ставни с коваными петлями и латунным замочком; `chest` — ниша с
резным сундуком и латунной фурнитурой; `balcony` — каменный балкон с кованой
решёткой и сливовым знаменем с золотой звездой.

## 3. Правила качества

1. Один объект — один кадр; объект целиком, не обрезан.
2. Никакого текста, цифр, логотипов в кадре (кроме брендбука Foxy).
3. Фон всегда сумеречное боке — картинки ложатся на тёмный интерфейс без швов.
4. Отбраковка: плоский «мультяшный» вид, пластиковые материалы, белые плашки,
   пустые области, лишние объекты.

Генерация: `world-pipeline/diorama_art.py` (список ассетов и промпты — там же).
