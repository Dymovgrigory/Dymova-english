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
from PIL import Image, ImageFilter
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
# Плашка уменьшена и опущена: сверху нужно небо, иначе задние башни классов не влезают в кадр.
PLATE_SCALE = 0.8
PLATE_OFFSET = (154, 172)

# Площадки измерены по castle-grounds.webp (px): центр основания и ширина мшистой базы здания.
# Порядок = порядок отрисовки (сзади вперёд).
SLOTS: list[tuple[str, int, int, int]] = [
    ("tower-sp3", 295, 112, 118),   # угловая башня сзади слева
    ("tower-sp4", 1238, 108, 118),  # угловая башня сзади справа
    ("glory", 650, 222, 120),       # у задней стены, левее купола Сокровищницы
    ("shop", 985, 250, 150),        # трава во дворе справа сзади
    ("school", 445, 342, 190),      # левая площадка
    ("lexicon", 790, 358, 195),     # центральная площадка
    ("stickers", 1108, 344, 150),   # правая площадка
    ("tower-sp1", 145, 385, 125),   # угловая башня спереди слева
    ("tower-sp2", 1373, 385, 125),  # угловая башня спереди справа
    ("nest", 220, 660, 185),        # холм снаружи слева
    ("quests", 530, 712, 190),      # площадка у подхода к воротам
    ("yard", 1348, 752, 250),       # загон за ручьём справа
]


def sprite_base(alpha: np.ndarray) -> tuple[float, int, int]:
    """Центр X, низ Y и ширина мшистой базы спрайта — по непрозрачным пикселям."""
    solid = alpha > 128
    rows = np.where(solid.any(axis=1))[0]
    bottom = int(rows[-1])
    height = bottom - int(rows[0])
    band = solid[bottom - int(height * 0.12): bottom + 1]
    cols = np.where(band.any(axis=0))[0]
    return (cols[0] + cols[-1]) / 2, bottom, int(cols[-1] - cols[0])


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
        left, top = round(cx - sx * scale), round(by - sy * scale)
        items.append({"id": spot, "image": sprite, "left": left, "top": top})
    return items


def compose() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    plate = Image.open(PLATE).convert("RGBA").resize(SIZE, Image.LANCZOS)
    collage = plate.filter(ImageFilter.GaussianBlur(24))
    small = plate.resize((round(SIZE[0] * PLATE_SCALE), round(SIZE[1] * PLATE_SCALE)), Image.LANCZOS)
    feather = Image.new("L", small.size, 0)
    feather.paste(255, (24, 24, small.width - 24, small.height))
    small.putalpha(feather.filter(ImageFilter.GaussianBlur(14)))
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
    "Re-photograph this exact layout as ONE single continuous handcrafted miniature diorama of Foxinburg Castle. "
    "Keep the camera, the framing, the castle walls, the gate, the bridge, the stream and the mountains exactly as in "
    "the reference. Keep EVERY building exactly where it stands in the reference, with the same size, silhouette, "
    "roof colours and character: the observatory tower on the back-left corner, the lighthouse tower with a balloon "
    "on the back-right corner, the ivy tower on the front-left corner, the water-wheel workshop tower on the "
    "front-right corner, the slim trophy tower at the back wall, the shop with a striped awning, the schoolhouse "
    "with a bell on the left pad, the round treasury vault with an open round door in the center, the tower covered "
    "in colourful badges on the right pad, the fox burrow in a mossy hill outside on the left, the gazebo with a "
    "notice board in front of the wall, the fenced training paddock beyond the stream. "
    "Re-light and re-seat every building so it is truly built into the model: the same elevated three-quarter "
    "perspective as the walls, bases merged into the moss and cobblestones, contact shadows, no floating cutouts, "
    "no halos, no pasted edges, no collage look. Do not add new big buildings, do not remove any building. "
    "No text, no letters, no people."
)


def data_uri(path: Path) -> str:
    buffer = io.BytesIO()
    Image.open(path).convert("RGB").save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def fuse_once(key: str, reference: str, index: int) -> str:
    payload = {"ai_model": MODEL, "prompt": CORE + FUSE_PROMPT, "reference_image_urls": [reference], "aspect_ratio": "16:9"}
    task = api("POST", API, key, payload)["result"]
    while True:
        status = api("GET", f"{API}/{task}", key)
        if status["status"] == "SUCCEEDED":
            out = WORK / f"fused-{task[-12:]}.png"
            urllib.request.urlretrieve(status["image_urls"][0], out)
            return f"вариант {index}: {out}"
        if status["status"] in ("FAILED", "CANCELED"):
            return f"вариант {index}: ОШИБКА {status.get('task_error')}"
        time.sleep(8)


def fuse(variants: int) -> None:
    key = load_key()
    reference = data_uri(WORK / "collage.png")
    with ThreadPoolExecutor(max_workers=variants) as pool:
        for line in pool.map(lambda i: fuse_once(key, reference, i), range(1, variants + 1)):
            print(line)


def edges(image: Image.Image) -> np.ndarray:
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    magnitude = np.hypot(ndimage.sobel(gray, 0), ndimage.sobel(gray, 1))
    return ndimage.gaussian_filter(magnitude, 2)


def best_offset(fused_edges: np.ndarray, sprite: Image.Image, left: int, top: int, reach: int = 28) -> tuple[int, int, float]:
    """Сдвиг здания на итоговом кадре: максимум корреляции контуров внутри маски спрайта."""
    alpha = np.asarray(sprite.getchannel("A")) > 128
    template = edges(sprite.convert("RGB"))
    template = np.where(alpha, template - template[alpha].mean(), 0)
    best = (0, 0, -1.0)
    height, width = alpha.shape
    for dy in range(-reach, reach + 1, 2):
        for dx in range(-reach, reach + 1, 2):
            y0, x0 = top + dy, left + dx
            if y0 < 0 or x0 < 0 or y0 + height > SIZE[1] or x0 + width > SIZE[0]:
                continue
            window = fused_edges[y0:y0 + height, x0:x0 + width]
            window = np.where(alpha, window - window[alpha].mean(), 0)
            score = float((window * template).sum() / (np.linalg.norm(window) * np.linalg.norm(template) + 1e-6))
            if score > best[2]:
                best = (dx, dy, score)
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


LABEL_STEP = 20  # индекс здания × 20 в карте зон — переживает любое сглаживание цвета при декодировании


def masks(pick: Path) -> None:
    fused = Image.open(pick).convert("RGB").resize(SIZE, Image.LANCZOS)
    fused_edges = edges(fused)
    layout = json.loads((WORK / "layout.json").read_text())
    labels = np.zeros((SIZE[1], SIZE[0]), dtype=np.uint8)
    for index, entry in enumerate(layout, start=1):
        sprite = Image.open(WORK / f"placed-{entry['id']}.png")
        dx, dy, score = best_offset(fused_edges, sprite, entry["left"], entry["top"])
        entry.update(left=entry["left"] + dx, top=entry["top"] + dy, index=index)
        region = refined_region(fused, sprite, entry["left"], entry["top"])
        labels[region] = index  # передние (позже в списке) перекрывают задние
        print(f"{entry['id']:10s} сдвиг ({dx:+d},{dy:+d}) совпадение {score:.2f}")

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
        fuse(args.variants)
    else:
        masks(args.pick)


if __name__ == "__main__":
    main()
