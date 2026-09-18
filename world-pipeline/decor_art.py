#!/usr/bin/env python3
"""Украшения замка: 14 предметов с альфой для сцены (Meshy text-to-image flare).

Модель не отдаёт прозрачность, поэтому предмет рисуется на чистом белом фоне,
альфа выделяется флуд-филлом от краёв кадра (предмет не касается краёв — это в промпте).

Usage:
  python3 world-pipeline/decor_art.py              # все предметы
  python3 world-pipeline/decor_art.py --only decor-gate-lantern
"""
from __future__ import annotations

import argparse
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
WORK = ROOT / "world-pipeline" / "word-art" / "castle" / "decor"
API = "https://api.meshy.ai/openapi/v1/text-to-image"

STYLE = (
    "ONE single small handcrafted miniature prop for a castle diorama, photographed alone on a plain pure "
    "white background, centered, not touching the frame edges, soft contact shadow under the prop, "
    "three-quarter view matching a miniature castle scene. No text, no people, no scenery, no ground plane "
    "beyond the prop's own small base. Prop: "
)

PROPS: dict[str, str] = {
    "decor-gate-lantern": "a wrought-iron lantern on a short wooden post, warm glowing glass, mossy base",
    "decor-gate-pots": "a pair of terracotta flower pots with bright petunias on a small stone step",
    "decor-gate-pumpkins": "three cheerful orange pumpkins of different sizes with a tiny straw basket",
    "decor-bridge-garland": "a short festive garland of colourful pennant flags strung between two wooden posts",
    "decor-stream-boat": "a tiny wooden toy sailboat with a red sail, floating base",
    "decor-yard-swing": "a wooden swing with a dark oak plank seat and rope handles hanging from a sturdy oak branch with a small mossy stump base",
    "decor-yard-firepit": "a round stone fire pit bowl with gentle warm flames and two small logs beside it",
    "decor-roof-weathervane": "a brass rooster weathervane on a small spindle with a tiled roof-ridge base",
    "decor-meadow-sundial": "a small stone sundial with a brass gnomon on a mossy round base",
    "decor-meadow-beehive": "a striped straw skep beehive on a wooden stand with tiny bees",
    "decor-meadow-apple-tree": "a small apple tree with red apples in a round grassy mound",
    "decor-wall-gargoyle": "a friendly small stone gargoyle sitting on a crenellated wall pedestal",
    "decor-wall-bell": "a bronze bell in a small wooden belfry frame on a stone base",
    "decor-gate-fox-statue": "a proud sitting red fox statue carved from warm wood on a stone pedestal",
}

WHITE_THRESHOLD = 238

# Предметы, где белый фон оказался заперт между частями (гирлянда): снимаем весь белый,
# а не только достижимый от края. Не применять к предметам с белыми деталями (парус лодочки).
AGGRESSIVE_CUTOUT = {"decor-bridge-garland"}


def cutout(source: Path, out: Path, aggressive: bool = False) -> None:
    """Альфа: не-белое связное пятно предмета; белый фон уходит флуд-филлом от краёв."""
    image = Image.open(source).convert("RGB")
    pixels = np.asarray(image, dtype=np.int16)
    white = (pixels > WHITE_THRESHOLD).all(axis=2)
    if aggressive:
        background = white
    else:
        # Фон — белые пиксели, достижимые от края кадра: предмет может содержать белые блики.
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


def recut(prop_id: str) -> None:
    """Пересчитать альфу из уже скачанного сырого кадра (без обращения к API)."""
    raws = sorted(WORK.glob(f"{prop_id}-*.png"))
    if not raws:
        raise SystemExit(f"нет сырого кадра для {prop_id}")
    out = OUT / f"{prop_id}.webp"
    cutout(raws[-1], out, aggressive=prop_id in AGGRESSIVE_CUTOUT)
    print(f"{prop_id}: альфа пересчитана → {out}")


def generate(key: str, prop_id: str, prompt: str, recut_only: bool = False) -> None:
    out = OUT / f"{prop_id}.webp"
    if recut_only:
        recut(prop_id)
        return
    if out.exists():
        print(f"{prop_id}: уже есть, пропуск")
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
            print(f"{prop_id}: {out}")
            return
        if status["status"] in ("FAILED", "CANCELED"):
            print(f"{prop_id}: ОШИБКА {status.get('task_error')}")
            return
        time.sleep(8)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=sorted(PROPS))
    parser.add_argument("--recut", action="store_true", help="пересчитать альфу из сырого кадра без API")
    args = parser.parse_args()
    key = "" if args.recut else load_key()
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    items = [(args.only, PROPS[args.only])] if args.only else sorted(PROPS.items())
    for prop_id, prompt in items:
        generate(key, prop_id, prompt, recut_only=args.recut)


if __name__ == "__main__":
    main()
