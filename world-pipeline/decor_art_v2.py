#!/usr/bin/env python3
"""Украшения замка v2: те же 14 предметов, но БЕЗ запечённой подложки/подиума.

Отличия от decor_art.py:
  - из описаний предметов убраны слова base/pedestal/step/mound — именно они
    провоцировали генератор рисовать эллипс-подиум;
  - промпт явно запрещает подложку, тень и ground patch;
  - после выреза альфы проверяется, что внизу кадра не осталось светлого «блина»;
  - итог складывается в word-art/castle/decor-v2 (в public копирует deploy-команда).

Usage:
  python3 world-pipeline/decor_art_v2.py                # все 14 предметов
  python3 world-pipeline/decor_art_v2.py --only decor-gate-lantern
  python3 world-pipeline/decor_art_v2.py --deploy       # бэкап старых + замена в public
  python3 world-pipeline/decor_art_v2.py --contact      # контакт-лист /tmp/decor-contact.png
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diorama_art import CORE, MODEL  # noqa: E402
from word_art import api, load_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "world" / "public" / "content" / "castle" / "decor"
WORK = ROOT / "world-pipeline" / "word-art" / "castle" / "decor-v2"
BACKUP = ROOT / "world-pipeline" / "word-art" / "castle" / "decor-v1-backup"
API = "https://api.meshy.ai/openapi/v1/text-to-image"

STYLE = (
    "ONE single small handcrafted miniature prop for a castle diorama, photographed alone, isolated on a plain "
    "pure white background, centered, not touching the left, right and top frame edges. No base, no podium, no "
    "pedestal, no shadow, no ground patch, no platform — the prop stands directly on its own bottom contact line "
    "at the lower edge of the frame. Three-quarter view matching a miniature castle scene. "
    "No text, no people, no scenery. Prop: "
)

# Описания без base/pedestal/step/mound (см. docstring).
PROPS: dict[str, str] = {
    "decor-gate-lantern": "a wrought-iron lantern on a short wooden post, warm glowing glass",
    "decor-gate-pots": "a pair of terracotta flower pots with bright petunias",
    "decor-gate-pumpkins": "three cheerful orange pumpkins of different sizes with a tiny straw basket",
    "decor-bridge-garland": "a short festive garland of colourful pennant flags strung between two wooden posts",
    "decor-stream-boat": "a tiny wooden toy sailboat with a red sail",
    "decor-yard-swing": "a wooden swing with a dark oak plank seat and rope handles hanging from a horizontal oak branch segment",
    "decor-yard-firepit": "a round stone fire pit bowl with gentle warm flames and two small logs beside it",
    "decor-roof-weathervane": "a brass rooster weathervane on a small spindle",
    "decor-meadow-sundial": "a small stone sundial with a brass gnomon",
    "decor-meadow-beehive": "a striped straw skep beehive on a wooden stand with tiny bees",
    "decor-meadow-apple-tree": "a small apple tree with red apples",
    "decor-wall-gargoyle": "a friendly small stone gargoyle sitting upright, carved stone texture",
    "decor-wall-bell": "a bronze bell in a small wooden belfry frame",
    "decor-gate-fox-statue": "a proud sitting red fox statue carved from warm wood",
}

WHITE_THRESHOLD = 238
AGGRESSIVE_CUTOUT = {"decor-bridge-garland"}


def cutout(source: Path, out: Path, aggressive: bool = False) -> None:
    """Альфа: белый фон уходит флуд-филлом от краёв; кроп по альфе; ≤512 px."""
    image = Image.open(source).convert("RGB")
    pixels = np.asarray(image, dtype=np.int16)
    white = (pixels > WHITE_THRESHOLD).all(axis=2)
    if aggressive:
        background = white
    else:
        labels, _count = ndimage.label(white)
        border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
        background = np.isin(labels, list(border))
    alpha = np.where(background, 0, 255).astype(np.uint8)
    alpha = np.asarray(Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(1.2)))
    rgba = np.dstack([pixels.clip(0, 255).astype(np.uint8), alpha])
    sprite = Image.fromarray(rgba, "RGBA")
    box = sprite.getchannel("A").getbbox()
    if box:
        sprite = sprite.crop(box)
    sprite.thumbnail((512, 512), Image.LANCZOS)
    sprite.save(out, "WEBP", quality=90)


def has_base_artifact(path: Path) -> bool:
    """Эвристика «блина»: в нижней полосе кадра широкий светлый непрозрачный регион."""
    image = Image.open(path).convert("RGBA")
    arr = np.asarray(image)
    rgb = arr[..., :3].astype(np.int16)
    alpha = arr[..., 3] > 32
    h, w = alpha.shape
    band = alpha[int(h * 0.92):, :]
    if not band.any():
        return True  # пустой низ — тоже плохо
    band_rgb = rgb[int(h * 0.92):, :]
    luma = band_rgb @ np.array([0.299, 0.587, 0.114])
    light = (luma > 210) & band
    if band.sum() > 0 and (light.sum() / band.sum()) > 0.5 and (band.sum() / band.size) > 0.5:
        return True
    # нижний центр кадра не должен быть белым
    cx = w // 2
    window = alpha[max(0, h - 6):, max(0, cx - 12): cx + 12]
    if window.any():
        patch = rgb[max(0, h - 6):, max(0, cx - 12): cx + 12][window]
        if (patch > 235).all(axis=1).mean() > 0.6:
            return True
    return False


def generate(key: str, prop_id: str, prompt: str) -> None:
    out = WORK / f"{prop_id}.webp"
    if out.exists():
        print(f"{prop_id}: уже есть, пропуск", flush=True)
        return
    task = api("POST", API, key, {"ai_model": MODEL, "prompt": CORE + STYLE + prompt, "aspect_ratio": "1:1"})["result"]
    while True:
        try:
            status = api("GET", f"{API}/{task}", key)
        except OSError:
            time.sleep(10)
            continue
        if status["status"] == "SUCCEEDED":
            raw = WORK / f"{prop_id}-{task[-8:]}.png"
            for _ in range(4):
                try:
                    urllib.request.urlretrieve(status["image_urls"][0], raw)
                    break
                except OSError:
                    time.sleep(10)
            cutout(raw, out, aggressive=prop_id in AGGRESSIVE_CUTOUT)
            flag = "БЛИН?" if has_base_artifact(out) else "ok"
            print(f"{prop_id}: {out.name} [{flag}]", flush=True)
            return
        if status["status"] in ("FAILED", "CANCELED"):
            print(f"{prop_id}: ОШИБКА {status.get('task_error')}", flush=True)
            return
        time.sleep(8)


def deploy() -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    for prop_id in PROPS:
        new = WORK / f"{prop_id}.webp"
        old = OUT / f"{prop_id}.webp"
        if not new.exists():
            raise SystemExit(f"нет нового файла {new}")
        if old.exists() and not (BACKUP / old.name).exists():
            shutil.copy2(old, BACKUP / old.name)
        shutil.copy2(new, old)
        print(f"{prop_id}: обновлён в public")


def contact() -> None:
    tiles = []
    for prop_id in sorted(PROPS):
        image = Image.open(WORK / f"{prop_id}.webp").convert("RGBA")
        image.thumbnail((256, 256), Image.LANCZOS)
        tiles.append((prop_id, image))
    cols, size, label = 4, 256, 22
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * size, rows * (size + label)), (128, 128, 128, 255))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(sheet)
    for i, (name, image) in enumerate(tiles):
        x, y = (i % cols) * size, (i // cols) * (size + label)
        sheet.alpha_composite(image, (x + (size - image.width) // 2, y + (size - image.height) // 2))
        draw.text((x + 6, y + size + 4), name, fill=(255, 255, 255, 255))
    sheet.convert("RGB").save("/tmp/decor-contact.png")
    print("/tmp/decor-contact.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=sorted(PROPS))
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument("--contact", action="store_true")
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if args.deploy:
        deploy()
        return
    if args.contact:
        contact()
        return
    key = load_key()
    items = [(args.only, PROPS[args.only])] if args.only else sorted(PROPS.items())
    for prop_id, prompt in items:
        generate(key, prop_id, prompt)


if __name__ == "__main__":
    main()
