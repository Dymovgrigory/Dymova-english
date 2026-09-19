#!/usr/bin/env python3
"""Праздничные «запечённые» наборы сцены замка: flare img2img от базовой диорамы.

Украшения рисуются прямо в сцене (не наклейки): промпт требует сохранить камеру
и каждое здание (LAYOUT_LOCK), а из вариантов выбираем тот, чьи контуры лучше
совпадают с референсом (`castle_compose.correlation/edges`, порог 0.80). Если
лучший вариант ниже порога — генерируем ещё, до MAX_VARIANTS на набор.

Usage:
  python3 world-pipeline/scene_set_art.py                 # все наборы, по 2 варианта
  python3 world-pipeline/scene_set_art.py --only garland --variants 3
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
WORK = ROOT / "world-pipeline" / "word-art" / "castle" / "sets"
API = "https://api.meshy.ai/openapi/v1/image-to-image"
BALANCE_API = "https://api.meshy.ai/openapi/v1/balance"
SIZE = (1536, 864)
REFERENCE = CASTLE / "castle-diorama.webp"
MIN_SCORE = 0.80
MAX_VARIANTS = 4
MAX_BYTES = 300 * 1024

LAYOUT_LOCK = (
    "Edit this miniature diorama photo. Keep EXACTLY the same camera, framing, layout and composition: "
    "the castle walls, gate, bridge, stream, every tower and every building stay precisely where they are, "
    "same size, same silhouette, same character. Only the decorations and lighting change. "
    "No new buildings, no removed buildings, no text, no people. "
)

SET_PROMPTS = {
    "garland": (
        "Add warm golden garland lights strung along the castle walls, over the gate and above the bridge, "
        "tiny glowing bulbs, cozy evening fairy-tale mood, soft dusk light."
    ),
    "lanterns": (
        "Add paper festival lanterns floating and hanging above the courtyard and over the stream, "
        "warm orange glow, twilight, gentle reflections in the stream."
    ),
    "pumpkins": (
        "Make it an autumn harvest festival: carved pumpkins with warm candlelight by the gate and on the wall "
        "parapets, colorful fall leaves on trees and ground, golden afternoon light."
    ),
}


def balance(key: str) -> int | None:
    try:
        return api("GET", BALANCE_API, key).get("balance")
    except Exception:
        return None


def data_uri(path: Path) -> str:
    import base64

    buffer = io.BytesIO()
    Image.open(path).convert("RGB").save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def generate_once(key: str, reference: str, name: str, index: int) -> Path | None:
    payload = {
        "ai_model": MODEL,
        "prompt": CORE + LAYOUT_LOCK + SET_PROMPTS[name],
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
            out = WORK / f"{name}-{index}-{task[-8:]}.png"
            for _ in range(4):
                try:
                    urllib.request.urlretrieve(status["image_urls"][0], out)
                    return out
                except OSError:
                    time.sleep(10)
            return None
        if status["status"] in ("FAILED", "CANCELED"):
            print(f"{name} вариант {index}: ОШИБКА {status.get('task_error')}")
            return None
        time.sleep(8)


def match_score(reference_edges: np.ndarray, candidate: Path) -> float:
    image = Image.open(candidate).convert("RGB").resize(SIZE, Image.LANCZOS)
    center = np.zeros((SIZE[1] // 4, SIZE[0] // 4), dtype=bool)
    center[SIZE[1] // 24 :, SIZE[0] // 24 : -SIZE[0] // 24] = True
    return correlation(edges(image)[::4, ::4], reference_edges, center)


def save_webp(source: Path, out: Path) -> int:
    image = Image.open(source).convert("RGB").resize(SIZE, Image.LANCZOS)
    quality = 85
    while True:
        image.save(out, "WEBP", quality=quality)
        size = out.stat().st_size
        if size <= MAX_BYTES or quality <= 60:
            return size
        quality -= 5


def run_set(key: str, reference: str, reference_edges: np.ndarray, name: str, variants: int) -> None:
    scored: list[tuple[float, Path]] = []
    attempted = 0
    while attempted < MAX_VARIANTS:
        batch = min(variants, MAX_VARIANTS - attempted)
        attempted += batch
        with ThreadPoolExecutor(max_workers=batch) as pool:
            paths = list(pool.map(lambda i: generate_once(key, reference, name, attempted - batch + i + 1), range(batch)))
        scored += [(match_score(reference_edges, p), p) for p in paths if p]
        if not scored:
            print(f"{name}: все варианты провалились, пробуем ещё" if attempted < MAX_VARIANTS else f"{name}: все варианты провалились")
            continue
        if max(s for s, _ in scored) >= MIN_SCORE:
            break
        print(f"{name}: лучшее совпадение {max(s for s, _ in scored):.3f} < {MIN_SCORE}, генерирую ещё")
    if not scored:
        print(f"{name}: набор пропущен, вариантов нет")
        return
    scored.sort(reverse=True)
    best_score, best = scored[0]
    for score, path in scored:
        print(f"{name}: {path.name} совпадение {score:.3f}{' ← выбран' if path == best else ''}")
    if best_score < MIN_SCORE:
        print(f"{name}: ВНИМАНИЕ — лучший вариант ниже порога ({best_score:.3f} < {MIN_SCORE}) после {attempted} попыток")
    out = CASTLE / "sets" / f"{name}.webp"
    out.parent.mkdir(exist_ok=True)
    size = save_webp(best, out)
    print(f"{name}: сохранено {out} ({size / 1024:.0f} КБ, совпадение {best_score:.3f})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=sorted(SET_PROMPTS))
    parser.add_argument("--variants", type=int, default=2)
    args = parser.parse_args()

    key = load_key()
    before = balance(key)
    print(f"Баланс Meshy до: {before}")
    WORK.mkdir(parents=True, exist_ok=True)
    reference = data_uri(REFERENCE)
    reference_edges = edges(Image.open(REFERENCE).convert("RGB").resize(SIZE, Image.LANCZOS))[::4, ::4]
    names = [args.only] if args.only else list(SET_PROMPTS)
    for name in names:
        run_set(key, reference, reference_edges, name, args.variants)
    after = balance(key)
    print(f"Баланс Meshy после: {after}" + (f" (потрачено {before - after})" if before is not None and after is not None else ""))


if __name__ == "__main__":
    main()
