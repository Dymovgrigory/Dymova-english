#!/usr/bin/env python3
"""Сезонные диорамы замка Фоксинбург: img2img от базовой диорамы через flare.

Раскладку держим двумя способами: промпт требует сохранить камеру и каждое здание,
а из вариантов выбираем тот, чьи контуры лучше совпадают с референсом (тот же приём,
что `castle_compose.global_fit`). После генерации каждый сезон проходит
`castle_compose.py season-masks`, потому что flare может сместить здания на пару пикселей.

Usage:
  python3 world-pipeline/season_art.py                 # все 4 сезона, по 2 варианта
  python3 world-pipeline/season_art.py --only winter --variants 3
"""
from __future__ import annotations

import argparse
import io
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from castle_compose import correlation, edges  # noqa: E402
from diorama_art import CORE, MODEL  # noqa: E402
from word_art import api, load_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CASTLE = ROOT / "world" / "public" / "content" / "castle"
WORK = ROOT / "world-pipeline" / "word-art" / "castle" / "seasons"
API = "https://api.meshy.ai/openapi/v1/image-to-image"
SIZE = (1536, 864)
REFERENCE = CASTLE / "castle-diorama.webp"

LAYOUT_LOCK = (
    "Edit this miniature diorama photo. Keep EXACTLY the same camera, framing, layout and composition: "
    "the castle walls, gate, bridge, stream, every tower and every building stay precisely where they are, "
    "same size, same silhouette, same character. Only the season changes. "
    "No new buildings, no removed buildings, no text, no people. "
)

SEASON_PROMPTS = {
    "spring": (
        "It is now early spring: fresh young green grass, pink and white cherry and apple blossom on the trees, "
        "puddles reflecting the sky, soft morning light, a few petals drifting in the air. "
        "The stream runs fuller. Roofs and walls keep their colours."
    ),
    "summer": (
        "It is now a warm summer evening: lush deep green meadows and foliage, bright wildflowers in the grass, "
        "golden low sunlight, long soft shadows, clear warm sky. The stream sparkles. "
        "Roofs and walls keep their colours."
    ),
    "autumn": (
        "It is now golden autumn: trees in amber, rust and copper, fallen leaves on the roofs, paths and bridge, "
        "mist over the stream, warm low sun, a few leaves drifting in the air. "
        "Roofs and walls keep their colours under the leaves."
    ),
    "winter": (
        "It is now a snowy winter day: snow on every roof, wall, bridge and branch, the stream partly frozen, "
        "soft falling snowflakes, cool blue-pink light, warm golden windows glowing. "
        "Silhouettes and rooflines stay readable under the snow."
    ),
}


def data_uri(path: Path) -> str:
    import base64

    buffer = io.BytesIO()
    Image.open(path).convert("RGB").save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def generate_once(key: str, reference: str, season: str, index: int) -> Path | None:
    payload = {
        "ai_model": MODEL,
        "prompt": CORE + LAYOUT_LOCK + SEASON_PROMPTS[season],
        "reference_image_urls": [reference],
        "aspect_ratio": "16:9",
    }
    task = api("POST", API, key, payload)["result"]
    while True:
        try:
            status = api("GET", f"{API}/{task}", key)
        except OSError:
            time.sleep(10)
            continue
        if status["status"] == "SUCCEEDED":
            out = WORK / f"{season}-{index}-{task[-8:]}.png"
            for _ in range(4):
                try:
                    urllib.request.urlretrieve(status["image_urls"][0], out)
                    return out
                except OSError:
                    time.sleep(10)
            return None
        if status["status"] in ("FAILED", "CANCELED"):
            print(f"{season} вариант {index}: ОШИБКА {status.get('task_error')}")
            return None
        time.sleep(8)


def match_score(reference_edges: np.ndarray, candidate: Path) -> float:
    image = Image.open(candidate).convert("RGB").resize(SIZE, Image.LANCZOS)
    center = np.zeros((SIZE[1] // 4, SIZE[0] // 4), dtype=bool)
    center[SIZE[1] // 24 :, SIZE[0] // 24 : -SIZE[0] // 24] = True
    return correlation(edges(image)[::4, ::4], reference_edges, center)


def run_season(key: str, reference: str, reference_edges: np.ndarray, season: str, variants: int) -> None:
    with ThreadPoolExecutor(max_workers=variants) as pool:
        paths = list(pool.map(lambda i: generate_once(key, reference, season, i + 1), range(variants)))
    candidates = [p for p in paths if p]
    if not candidates:
        print(f"{season}: все варианты провалились, сезон пропущен")
        return
    scored = [(match_score(reference_edges, p), p) for p in candidates]
    scored.sort(reverse=True)
    best_score, best = scored[0]
    for score, path in scored:
        print(f"{season}: {path.name} совпадение {score:.3f}{' ← выбран' if path == best else ''}")
    out = CASTLE / "seasons" / f"{season}.webp"
    out.parent.mkdir(exist_ok=True)
    Image.open(best).convert("RGB").resize(SIZE, Image.LANCZOS).save(out, "WEBP", quality=90)
    print(f"{season}: сохранено {out} (совпадение {best_score:.3f})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=sorted(SEASON_PROMPTS))
    parser.add_argument("--variants", type=int, default=2)
    args = parser.parse_args()

    key = load_key()
    WORK.mkdir(parents=True, exist_ok=True)
    reference = data_uri(REFERENCE)
    reference_edges = edges(Image.open(REFERENCE).convert("RGB").resize(SIZE, Image.LANCZOS))[::4, ::4]
    seasons = [args.only] if args.only else list(SEASON_PROMPTS)
    for season in seasons:
        run_season(key, reference, reference_edges, season, args.variants)


if __name__ == "__main__":
    main()
