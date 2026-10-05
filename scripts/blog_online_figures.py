#!/usr/bin/env python3
"""Иллюстрации статей блога (онлайн-направление) через Meshy text-to-image.

Модель `gpt-image-2-5-flare`, формат 16:9 → WebP 1280×720 в prototype/article-images/<alias>.webp.
Ключ берётся только из переменной окружения MESHY_API_KEY (в репозиторий не пишется).

Usage:
  MESHY_API_KEY=... python3 scripts/blog_online_figures.py            # все 10
  MESHY_API_KEY=... python3 scripts/blog_online_figures.py --only blog-kak-prohodit-urok-onlajn
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "prototype" / "article-images"
API = "https://api.meshy.ai/openapi/v1/text-to-image"
MODEL = "gpt-image-2-5-flare"
SUFFIX = (
    " Editorial photo-realistic illustration, soft warm evening light, plum and gold colour palette,"
    " shallow depth of field, calm and friendly mood, 16:9 composition."
    " No text, no letters, no numbers, no watermark."
)

PROMPTS: dict[str, str] = {
    "blog-test-gotovnosti-k-shkole-onlajn":
        "A six-year-old child sitting at a small desk with a laptop showing a smiling teacher on a video call, pencils and a school backpack nearby.",
    "blog-onlajn-anglijskij-dlya-vzroslyh":
        "An adult professional at a tidy home desk with a laptop, a notebook and a cup of tea, plants and a window with evening light behind.",
    "blog-kak-prohodit-urok-onlajn":
        "A child in front of a tablet on a desk with colourful flashcards and a small headset, cheerful and focused.",
    "blog-onlajn-bezopasnost-rebenka":
        "A parent and a child at a kitchen table with a laptop, a calm home atmosphere and a soft lamp glowing.",
    "blog-onlajn-letnij-intensiv-dlya-shkolnikov":
        "Two teenagers at a sunny summer desk by an open window, books and a laptop, relaxed summer light.",
    "blog-onlajn-russkij-kak-inostrannyj":
        "A young adult with a laptop and a notebook in a cosy room, a world map on the wall and a window with warm light.",
    "blog-onlajn-nemeckij-dlya-detej":
        "A child with a headset and a laptop, cheerful colourful cushions and a bright, playful desk setup.",
    "blog-onlajn-kitajskij-dlya-shkolnikov":
        "A teenager with an ink brush and a paper scroll on a wooden desk, abstract brush strokes, a calm study corner.",
    "blog-onlajn-podgotovka-k-oge-anglijskij":
        "A focused teenager at a desk with a laptop and a notebook under a warm study lamp in the evening.",
    "blog-onlajn-ekrannoe-vremya":
        "A child with a tablet on a soft blanket, a book beside them and a wall clock, balanced and cosy mood.",
}


def api(method: str, url: str, key: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


def generate(prompt: str, key: str) -> bytes:
    task = api("POST", API, key, {
        "ai_model": MODEL,
        "prompt": prompt + SUFFIX,
        "aspect_ratio": "16:9",
    })["result"]
    for _ in range(120):
        time.sleep(5)
        status = api("GET", f"{API}/{task}", key)
        if status["status"] == "SUCCEEDED":
            with urllib.request.urlopen(status["image_urls"][0], timeout=120) as image:
                return image.read()
        if status["status"] in ("FAILED", "CANCELED"):
            raise RuntimeError(f"Meshy task {task} {status['status']}: {status.get('task_error')}")
    raise TimeoutError(f"Meshy task {task} timed out")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="один alias из списка")
    args = parser.parse_args()

    key = os.environ.get("MESHY_API_KEY")
    if not key:
        sys.exit("Нет MESHY_API_KEY в окружении")

    targets = {args.only: PROMPTS[args.only]} if args.only else PROMPTS
    OUT.mkdir(parents=True, exist_ok=True)
    for alias, prompt in targets.items():
        dest = OUT / f"{alias}.webp"
        if dest.exists():
            print(f"пропуск (уже есть): {dest.name}")
            continue
        raw_path = OUT / f"{alias}.raw.png"
        raw_path.write_bytes(generate(prompt, key))
        with Image.open(raw_path) as image:
            image.convert("RGB").resize((1280, 720), Image.LANCZOS).save(dest, "WEBP", quality=85)
        raw_path.unlink()
        print(f"готово: {dest.name}")


if __name__ == "__main__":
    main()
