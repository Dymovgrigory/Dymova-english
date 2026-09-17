#!/usr/bin/env python3
"""Замок Фоксинбург: одна цельная диорама с кликабельными зданиями.

Почему так: 12 спрайтов поверх плашки не садятся на площадки (у модели другая перспектива,
а число площадок она не соблюдает). Поэтому:

  1. compose — ставим спрайты зданий на измеренные площадки `castle-grounds.webp`
     (точка посадки считается по альфе спрайта, без ручных смещений) → коллаж + маски.
  2. fuse    — Meshy image-to-image `gpt-image-2-5-flare` сплавляет коллаж в одну диораму
     (стиль CORE из diorama_art.py), здания остаются на своих местах.
  3. masks   — уточняем положение каждого здания на итоговом кадре и пишем карту зон
     (`castle-hotspots.png`, `masks/*.png`, `world/src/castle/castle-hotspots.json`) для интерфейса.

Usage:
  python3 world-pipeline/castle_compose.py compose
  python3 world-pipeline/castle_compose.py fuse [--variants 2]
  python3 world-pipeline/castle_compose.py masks --pick world-pipeline/word-art/castle/fused-XXXX.png
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diorama_art import CORE, MODEL  # noqa: E402
from word_art import api, load_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CASTLE = ROOT / "world" / "public" / "content" / "castle"
WORK = ROOT / "world-pipeline" / "word-art" / "castle"
API = "https://api.meshy.ai/openapi/v1/image-to-image"
PLATE = CASTLE / "castle-grounds.webp"
SIZE = (1536, 864)
SCENE = ROOT / "world" / "public" / "content" / "scenes" / "scene-forest-wide.webp"
# Плашка уменьшена и стоит по центру леса: вокруг замка нужен пейзаж, чтобы сцена
# растягивалась на весь экран, а сверху — место для башен классов.
PLATE_SCALE = 0.64
PLATE_OFFSET = (276, 250)

# Каменные угловые башни плашки (px плашки) — стираем: их место занимают башни классов.
TURRETS = [(228, 60, 362, 205), (1172, 60, 1308, 215), (82, 292, 214, 512), (1298, 312, 1448, 520)]

# Площадки измерены по castle-grounds.webp (px): центр основания и ширина основания здания.
# Порядок = порядок отрисовки (сзади вперёд). Башни классов стоят от земли в углах стен.
SLOTS: list[tuple[str, int, int, int]] = [
    ("tower-sp3", 295, 205, 150),   # угол сзади слева — вместо каменной башни
    ("tower-sp4", 1240, 215, 150),  # угол сзади справа
    ("glory", 650, 222, 120),       # у задней стены, левее купола Сокровищницы
    ("shop", 985, 250, 150),        # трава во дворе справа сзади
    ("school", 445, 342, 190),      # левая площадка
    ("lexicon", 790, 358, 195),     # центральная площадка
    ("stickers", 1108, 344, 150),   # правая площадка
    ("tower-sp1", 148, 512, 170),   # угол спереди слева
    ("tower-sp2", 1373, 520, 175),  # угол спереди справа
    ("nest", 220, 660, 185),        # холм снаружи слева
    ("quests", 530, 712, 190),      # площадка у подхода к воротам
    ("yard", 1348, 752, 250),       # загон за ручьём справа
]


def erase(image: Image.Image, boxes: list[tuple[int, int, int, int]]) -> Image.Image:
    """Грубо закрашивает области окружением (нормированное размытие) — flare перерисует начисто."""
    pixels = np.asarray(image.convert("RGB"), dtype=np.float32)
    known = np.ones(pixels.shape[:2], dtype=np.float32)
    for x0, y0, x1, y1 in boxes:
        known[y0:y1, x0:x1] = 0
    weight = ndimage.gaussian_filter(known, 40) + 1e-6
    fill = np.stack([ndimage.gaussian_filter(pixels[..., c] * known, 40) for c in range(3)], axis=2) / weight[..., None]
    result = np.where(known[..., None] > 0, pixels, fill)
    return Image.fromarray(result.clip(0, 255).astype(np.uint8))


def sprite_base(alpha: np.ndarray) -> tuple[float, int, int]:
    """Центр X, низ Y и ширина мшистой базы спрайта — по непрозрачным пикселям."""
    solid = alpha > 128
    rows = np.where(solid.any(axis=1))[0]
    bottom = int(rows[-1])
    height = bottom - int(rows[0])
    band = solid[bottom - int(height * 0.12): bottom + 1]
    cols = np.where(band.any(axis=0))[0]
    return (cols[0] + cols[-1]) / 2, bottom, int(cols[-1] - cols[0])


def fade_plinth(sprite: Image.Image) -> Image.Image:
    """Растворяет круглую подставку снизу спрайта: здание должно стоять на земле, а не на диске."""
    alpha = np.asarray(sprite.getchannel("A"), dtype=np.float32)
    rows = np.where((alpha > 128).any(axis=1))[0]
    fade = max(1, int((rows[-1] - rows[0]) * 0.1))
    ramp = np.ones(alpha.shape[0], dtype=np.float32)
    ramp[rows[-1] - fade: rows[-1] + 1] = np.linspace(1, 0.15, fade + 1)
    ramp[rows[-1] + 1:] = 0
    sprite = sprite.copy()
    sprite.putalpha(Image.fromarray((alpha * ramp[:, None]).astype(np.uint8)))
    return sprite


def placed_sprites() -> list[dict]:
    items = []
    for spot, plate_x, plate_y, plate_w in SLOTS:
        cx = PLATE_OFFSET[0] + plate_x * PLATE_SCALE
        by = PLATE_OFFSET[1] + plate_y * PLATE_SCALE
        base_w = plate_w * PLATE_SCALE
        sprite = Image.open(CASTLE / f"{spot}.webp").convert("RGBA")
        sprite = sprite.crop(sprite.getchannel("A").getbbox())
        sx, sy, sw = sprite_base(np.array(sprite.getchannel("A")))
        scale = base_w / sw
        sprite = sprite.resize((round(sprite.width * scale), round(sprite.height * scale)), Image.LANCZOS)
        sprite = fade_plinth(sprite)
        left, top = round(cx - sx * scale), round(by - sy * scale)
        items.append({"id": spot, "image": sprite, "left": left, "top": top})
    return items


def compose() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    plate = erase(Image.open(PLATE).convert("RGB").resize(SIZE, Image.LANCZOS), TURRETS).convert("RGBA")
    collage = Image.open(SCENE).convert("RGBA").resize(SIZE, Image.LANCZOS)
    small = plate.resize((round(SIZE[0] * PLATE_SCALE), round(SIZE[1] * PLATE_SCALE)), Image.LANCZOS)
    feather = Image.new("L", small.size, 0)
    feather.paste(255, (40, 70, small.width - 40, small.height - 30))
    small.putalpha(feather.filter(ImageFilter.GaussianBlur(28)))
    collage.alpha_composite(small, PLATE_OFFSET)
    labels = np.zeros((SIZE[1], SIZE[0]), dtype=np.uint8)
    layout = []
    for index, item in enumerate(placed_sprites(), start=1):
        sprite = item["image"]
        collage.alpha_composite(sprite, (item["left"], item["top"]))
        mask = Image.new("L", SIZE)
        mask.paste(sprite.getchannel("A"), (item["left"], item["top"]))
        labels[np.array(mask) > 128] = index  # передние здания перекрывают задние
        layout.append({"id": item["id"], "left": item["left"], "top": item["top"],
                       "width": sprite.width, "height": sprite.height})
        sprite.save(WORK / f"placed-{item['id']}.png")
    collage.convert("RGB").save(WORK / "collage.png")
    Image.fromarray(labels).save(WORK / "collage-labels.png")
    (WORK / "layout.json").write_text(json.dumps(layout, indent=2, ensure_ascii=False))
    print(f"коллаж: {WORK / 'collage.png'}")


FUSE_PROMPT = (
    "Re-photograph this exact layout as ONE single continuous handcrafted miniature diorama of Foxinburg Castle "
    "standing on a mossy hill in a misty forest valley, pine trees and rocks in the soft blurred foreground, "
    "plum mountains and warm sunset sky behind — the landscape fills the whole frame around the castle. "
    "Keep the camera, the framing, the castle walls, the gate, the bridge, the stream and every building exactly "
    "where they are in the reference, with the same size, silhouette, roof colours and character. "
    "The FOUR CORNER TOWERS OF THE CASTLE ARE these four distinctive towers, rising straight from the ground as the "
    "real corner towers of the fortress, the curtain walls run directly into their stone bodies: back-left — the "
    "observatory tower with a brass telescope dome; back-right — the lighthouse tower with a hot-air balloon; "
    "front-left — the slim ivy tower with a spiral stair and a yellow flag; front-right — the workshop tower with a "
    "water wheel. There are NO other round stone turrets at the corners and no tower standing on top of another tower. "
    "Inside the walls: the slim trophy tower at the back wall, the shop with a striped awning, the schoolhouse with a "
    "bell, the round treasury vault with an open round door, the tower covered in colourful badges. Outside: the fox "
    "burrow in a mossy hill, the gazebo with a notice board, the fenced training paddock beyond the stream. "
    "Every building stands directly on the same ground as the courtyard — no display plinths, no round wooden "
    "bases, no discs, no raised platforms; the paddock fence and yard are level with the surrounding meadow and "
    "follow the same perspective as the castle walls. Bases merge into moss and cobblestones with contact shadows. "
    "No floating cutouts, no halos, no pasted edges, no collage look. Do not add or remove buildings. "
    "No text, no letters, no people."
)


REFINE_PROMPT = (
    "Edit this photo of a miniature castle diorama. Keep EVERYTHING exactly the same — camera, framing, landscape, "
    "walls, gate, every building, colours and light — except the two BACK corner towers. "
    "Back-left: the observatory tower with the brass telescope dome must rise straight from the ground as the real "
    "corner tower of the fortress, its stone body continuing down to the ground behind the wall, both walls running "
    "directly into its body. Back-right: the same for the lighthouse tower with the hot-air balloon. "
    "Remove the round mossy platforms and discs under these two towers — no tower standing on a platform, no "
    "floating island. Same for the front-right water-wheel tower: it grows from the ground at the wall corner. "
    "No text, no letters, no people."
)


def data_uri(path: Path) -> str:
    buffer = io.BytesIO()
    Image.open(path).convert("RGB").save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def fuse_once(key: str, reference: str, index: int, prompt: str = FUSE_PROMPT) -> str:
    payload = {"ai_model": MODEL, "prompt": CORE + prompt, "reference_image_urls": [reference], "aspect_ratio": "16:9"}
    task = api("POST", API, key, payload)["result"]
    while True:
        try:
            status = api("GET", f"{API}/{task}", key)
        except OSError:  # сетевой сбой при опросе — задача на стороне Meshy продолжается
            time.sleep(10)
            continue
        if status["status"] == "SUCCEEDED":
            out = WORK / f"fused-{task[-12:]}.png"
            for attempt in range(4):
                try:
                    urllib.request.urlretrieve(status["image_urls"][0], out)
                    break
                except OSError:
                    time.sleep(10)
            return f"вариант {index}: {out}"
        if status["status"] in ("FAILED", "CANCELED"):
            return f"вариант {index}: ОШИБКА {status.get('task_error')}"
        time.sleep(8)


def fuse(variants: int, source: Path | None = None) -> None:
    """Без --pick — сплавить коллаж; с --pick — точечная правка готовой диорамы (REFINE_PROMPT)."""
    key = load_key()
    reference = data_uri(source or WORK / "collage.png")
    prompt = REFINE_PROMPT if source else FUSE_PROMPT
    with ThreadPoolExecutor(max_workers=variants) as pool:
        for line in pool.map(lambda i: fuse_once(key, reference, i, prompt), range(1, variants + 1)):
            print(line)


def edges(image: Image.Image) -> np.ndarray:
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    magnitude = np.hypot(ndimage.sobel(gray, 0), ndimage.sobel(gray, 1))
    return ndimage.gaussian_filter(magnitude, 2)


def correlation(a: np.ndarray, b: np.ndarray, where: np.ndarray) -> float:
    a = np.where(where, a - a[where].mean(), 0)
    b = np.where(where, b - b[where].mean(), 0)
    return float((a * b).sum() / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-6))


def warp(image: Image.Image, scale: float, dx: float, dy: float) -> Image.Image:
    """Масштаб относительно центра кадра + сдвиг (px полного размера)."""
    cx, cy = SIZE[0] / 2, SIZE[1] / 2
    inverse = 1 / scale
    return image.transform(SIZE, Image.AFFINE, (inverse, 0, cx - (cx + dx) * inverse, 0, inverse, cy - (cy + dy) * inverse),
                           Image.BILINEAR)


def global_fit(collage: Image.Image, fused_edges: np.ndarray) -> tuple[float, int, int]:
    """Flare слегка сдвигает и масштабирует весь кадр — находим это по контурам всей сцены (в 1/4)."""
    small = lambda array: array[::4, ::4]  # noqa: E731
    target = small(fused_edges)
    center = np.zeros_like(target, dtype=bool)
    center[target.shape[0] // 6:, target.shape[1] // 6: -target.shape[1] // 6] = True
    best = (1.0, 0, 0, -1.0)
    for scale in np.arange(0.9, 1.101, 0.02):
        for dy in range(-60, 61, 8):
            for dx in range(-60, 61, 8):
                score = correlation(small(edges(warp(collage, scale, dx, dy))), target, center)
                if score > best[3]:
                    best = (float(scale), dx, dy, score)
    scale, dx, dy, _ = best
    for fine_scale in np.arange(scale - 0.015, scale + 0.016, 0.005):
        for fine_dy in range(dy - 6, dy + 7, 2):
            for fine_dx in range(dx - 6, dx + 7, 2):
                score = correlation(small(edges(warp(collage, fine_scale, fine_dx, fine_dy))), target, center)
                if score > best[3]:
                    best = (float(fine_scale), fine_dx, fine_dy, score)
    print(f"кадр: масштаб {best[0]:.3f}, сдвиг ({best[1]:+d},{best[2]:+d}), совпадение {best[3]:.2f}")
    return best[0], best[1], best[2]


def best_placement(fused_edges: np.ndarray, sprite: Image.Image, left: float, top: float) -> tuple[Image.Image, int, int, float]:
    """Точное место здания: перебор масштаба и сдвига вокруг ожидаемой позиции."""
    best = (sprite, round(left), round(top), -1.0)
    for scale in (0.94, 0.97, 1.0, 1.03, 1.06):
        size = (max(1, round(sprite.width * scale)), max(1, round(sprite.height * scale)))
        candidate = sprite.resize(size, Image.LANCZOS)
        alpha = np.asarray(candidate.getchannel("A")) > 128
        template = edges(candidate.convert("RGB"))
        # масштаб — от низа-центра, чтобы основание оставалось на месте
        base_left = left + (sprite.width - size[0]) / 2
        base_top = top + sprite.height - size[1]
        for dy in range(-20, 21, 2):
            for dx in range(-20, 21, 2):
                x0, y0 = round(base_left + dx), round(base_top + dy)
                if y0 < 0 or x0 < 0 or y0 + size[1] > SIZE[1] or x0 + size[0] > SIZE[0]:
                    continue
                score = correlation(fused_edges[y0:y0 + size[1], x0:x0 + size[0]], template, alpha)
                if score > best[3]:
                    best = (candidate, x0, y0, score)
    return best


def refined_region(fused: Image.Image, sprite: Image.Image, left: int, top: int) -> np.ndarray:
    """Силуэт здания на итоговом кадре: альфа спрайта минус то, чего flare не нарисовал.

    Деталь спрайта, которой нет на кадре (деревце, флажок), сильно отличается по цвету от того,
    что там теперь (стена, небо) — такие куски отрезаем, оставляем связную часть с основанием.
    """
    alpha = np.asarray(sprite.getchannel("A")) > 128
    height, width = alpha.shape
    window = np.asarray(fused, dtype=np.float32)[top:top + height, left:left + width]
    colors = np.asarray(sprite.convert("RGB"), dtype=np.float32)
    blur = lambda image: ndimage.gaussian_filter(image, (5, 5, 0))  # noqa: E731
    distance = np.linalg.norm(blur(window) - blur(colors), axis=2)
    keep = alpha & (distance < 70)
    keep = ndimage.binary_opening(keep, iterations=2)
    parts, count = ndimage.label(keep)
    if count:
        sizes = ndimage.sum(keep, parts, range(1, count + 1))
        keep = parts == (int(np.argmax(sizes)) + 1)
    keep = ndimage.binary_fill_holes(ndimage.binary_closing(keep, iterations=4)) & ndimage.binary_dilation(alpha, iterations=3)
    region = np.zeros((SIZE[1], SIZE[0]), dtype=bool)
    region[top:top + height, left:left + width] = ndimage.binary_dilation(keep, iterations=2)
    return region


# Башни, которые flare перерисовал иначе, чем спрайт (до земли, без подставки): их силуэт на
# выбранном кадре обведён вручную (px кадра 1536×864). Относится к fused-6f040bfc622f.png —
# после новой генерации проверить hotspots-preview.png и обвести заново.
MANUAL_SILHOUETTES: dict[str, list[tuple[int, int]]] = {
    "tower-sp3": [(412, 112), (430, 112), (452, 125), (462, 130), (462, 165), (460, 182), (450, 190), (452, 300),
                  (458, 330), (455, 345), (385, 345), (388, 300), (395, 190), (383, 182), (382, 165), (392, 150),
                  (395, 125)],
    "tower-sp4": [(1105, 125), (1115, 125), (1130, 140), (1132, 178), (1140, 165), (1165, 165), (1165, 215),
                  (1152, 222), (1138, 215), (1135, 230), (1140, 245), (1140, 280), (1145, 320), (1152, 345),
                  (1150, 365), (1075, 365), (1080, 320), (1078, 262), (1085, 245), (1090, 180), (1088, 140)],
    "tower-sp2": [(1210, 370), (1222, 372), (1250, 430), (1250, 445), (1245, 480), (1242, 505), (1262, 510),
                  (1275, 545), (1275, 585), (1240, 592), (1190, 592), (1172, 560), (1180, 480), (1175, 445),
                  (1172, 432), (1205, 385)],
}


def polygon_region(points: list[tuple[int, int]]) -> np.ndarray:
    canvas = Image.new("L", SIZE)
    ImageDraw.Draw(canvas).polygon(points, fill=255)
    return np.asarray(canvas) > 128


LABEL_STEP = 20  # индекс здания × 20 в карте зон — переживает любое сглаживание цвета при декодировании


def masks(pick: Path) -> None:
    fused = Image.open(pick).convert("RGB").resize(SIZE, Image.LANCZOS)
    fused_edges = edges(fused)
    layout = json.loads((WORK / "layout.json").read_text())
    scale, shift_x, shift_y = global_fit(Image.open(WORK / "collage.png").convert("RGB"), fused_edges)
    cx, cy = SIZE[0] / 2, SIZE[1] / 2
    labels = np.zeros((SIZE[1], SIZE[0]), dtype=np.uint8)
    for index, entry in enumerate(layout, start=1):
        placed = Image.open(WORK / f"placed-{entry['id']}.png")
        placed = placed.resize((round(placed.width * scale), round(placed.height * scale)), Image.LANCZOS)
        left = cx + (entry["left"] - cx) * scale + shift_x
        top = cy + (entry["top"] - cy) * scale + shift_y
        entry.update(index=index)
        if entry["id"] in MANUAL_SILHOUETTES:
            labels[polygon_region(MANUAL_SILHOUETTES[entry["id"]])] = index
            print(f"{entry['id']:10s} силуэт обведён вручную")
            continue
        sprite, left, top, score = best_placement(fused_edges, placed, left, top)
        region = refined_region(fused, sprite, left, top)
        labels[region] = index  # передние (позже в списке) перекрывают задние
        print(f"{entry['id']:10s} ({left},{top}) {sprite.size} совпадение {score:.2f}")

    (CASTLE / "masks").mkdir(exist_ok=True)
    spots = []
    for entry in layout:
        visible = labels == entry["index"]
        rows, cols = np.where(visible.any(axis=1))[0], np.where(visible.any(axis=0))[0]
        box = (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)
        alpha = Image.fromarray((visible * 255).astype(np.uint8)).crop(box).filter(ImageFilter.GaussianBlur(1.2))
        # CSS mask-image читает альфу: белый слой с прозрачностью вне силуэта
        cutout = Image.new("RGBA", alpha.size, (255, 255, 255, 0))
        cutout.putalpha(alpha)
        cutout.save(CASTLE / "masks" / f"{entry['id']}.png", optimize=True)
        # Подпись — над плотной частью силуэта, а не над тонкими флагштоками/ветками маски.
        counts = visible[box[1]:box[3]].sum(axis=1)
        dense_top = int(np.argmax(counts >= counts.max() * 0.2))
        spots.append({
            "id": entry["id"], "index": entry["index"],
            "labelTop": round(dense_top * 100 / (box[3] - box[1]), 2),
            "area": {name: round(value * 100 / total, 3) for name, value, total in (
                ("left", box[0], SIZE[0]), ("top", box[1], SIZE[1]),
                ("width", box[2] - box[0], SIZE[0]), ("height", box[3] - box[1], SIZE[1]))},
        })

    fused.save(CASTLE / "castle-diorama.webp", "WEBP", quality=90)
    Image.fromarray(labels * LABEL_STEP).resize((SIZE[0] // 4, SIZE[1] // 4), Image.NEAREST).save(
        CASTLE / "castle-hotspots.png", optimize=True)
    (ROOT / "world" / "src" / "castle" / "castle-hotspots.json").write_text(
        json.dumps({"labelStep": LABEL_STEP, "spots": spots}, indent=2) + "\n")
    preview = fused.convert("RGBA")
    tint = np.zeros((SIZE[1], SIZE[0], 4), dtype=np.uint8)
    palette = np.array([[0, 0, 0, 0]] + [[(i * 97) % 255, (i * 57) % 255, (i * 151) % 255, 110] for i in range(1, 13)], dtype=np.uint8)
    tint[:] = palette[labels]
    preview.alpha_composite(Image.fromarray(tint))
    preview.convert("RGB").save(WORK / "hotspots-preview.png")
    print(f"готово: {CASTLE / 'castle-diorama.webp'}, проверка зон: {WORK / 'hotspots-preview.png'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["compose", "fuse", "masks"])
    parser.add_argument("--variants", type=int, default=2)
    parser.add_argument("--pick", type=Path)
    args = parser.parse_args()
    if args.step == "compose":
        compose()
    elif args.step == "fuse":
        fuse(args.variants, args.pick)
    else:
        masks(args.pick)


if __name__ == "__main__":
    main()
