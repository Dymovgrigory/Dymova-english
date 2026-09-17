#!/usr/bin/env python3
"""Иллюстрации этажей башни: комната «в разрезе» по теме модуля Spotlight → WebP 1280×720.

Usage:
  python3 world-pipeline/module_art.py [module_id ...]   # по умолчанию все без готового файла
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from word_art import api, load_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "world-backend" / "content" / "spotlight"
OUT = ROOT / "world" / "public" / "content" / "modules"
WORK = ROOT / "world-pipeline" / "word-art" / "modules"
API = "https://api.meshy.ai/openapi/v1/text-to-image"
MODEL = "nano-banana-pro"

STYLE = (
    "Wide cozy cutaway illustration of one room inside a fairy-tale castle tower, like a dollhouse cross-section, "
    "walls of soft purple stone, warm golden lanterns, teal magical accents, premium soft 3D cartoon render for "
    "children, gentle lighting, rich but calm colours. The room fills the whole frame edge to edge with the "
    "floor visible at the bottom; no empty panels, plaques, frames or blank areas. No people in the foreground, "
    "absolutely no text, letters or numbers. The room is themed: "
)

SCENES = {
    "sp1.m1": "a family living room with family portraits, a tea table with cups and a cake",
    "sp1.m2": "a small classroom with desks, pencils, books and a school bag",
    "sp1.m3": "a child's bedroom with a bed, toys, a kite, a teddy bear and a toy train",
    "sp1.m4": "a pet corner with a cat basket, a dog bed, a rabbit hutch and a bird cage",
    "sp1.m5": "a kitchen with a picnic basket, fruit, sandwiches, ice cream and a window to the seaside",
    "sp2.m0": "a magical library of giant alphabet letter blocks and glowing letters as shapes, no readable text",
    "sp2.m1": "a family room with grandparents' armchairs and colourful paint pots",
    "sp2.m2": "a house cutaway with kitchen, bedroom, bathroom and a garden with a tree house",
    "sp2.m3": "a birthday party room with balloons, candles on a cake, burgers and chocolate",
    "sp2.m4": "a circus ring with a small tent, swing, fish bowl, frog and horse toys",
    "sp2.m5": "a toy room with a toy box, shelf, ballerina, puppet and jack-in-the-box",
    "sp2.m6": "a holiday room with a suitcase, beach hat, sunglasses, and windows showing four seasons",
    "sp3.m0": "a welcoming castle hall with a rainbow of banners and school bags by the door",
    "sp3.m1": "a bright castle school classroom with a globe, paints, music notes and a ruler",
    "sp3.m2": "a cosy family room with a big family tree painting on the wall",
    "sp3.m3": "a castle dining hall with a lunch box, pasta, carrots, lemonade and a menu board",
    "sp3.m4": "a playroom with a rocking horse, tea set, musical box, toy elephant and aeroplane",
    "sp3.m5": "a farm barn inside the castle with a cow, sheep, parrot, spider and a small pond",
    "sp3.m6": "a castle kitchen and living room with fridge, sofa, cooker, mirror and cupboard",
    "sp3.m7": "a castle courtyard park with a picnic, bikes, a kite and a sandcastle",
    "sp3.m8": "a clock tower room with a big clock, a calendar-like wheel of seven coloured days and a cartoon screen",
    "sp4.m0": "a reunion hall with gifts, a CD player and friends' photos on the wall",
    "sp4.m1": "a friends' hangout room with a guitar, camera, roller blades, gloves and keys",
    "sp4.m2": "a small castle town square with a bakery, hospital, post office and cafe fronts",
    "sp4.m3": "a pantry kitchen with jars, bottles, loaves, pineapple, mango and flour bags",
    "sp4.m4": "a castle zoo garden with a giraffe, dolphin pool, seals, hippo and crocodile",
    "sp4.m5": "a tea party room with balloons, birthday cards and a delicious cake",
    "sp4.m6": "a fairy tale reading nook with a big storybook showing a hare and a tortoise race",
    "sp4.m7": "a museum hall with a dinosaur skeleton, a concert stage and fireworks outside the window",
    "sp4.m8": "a travel room with a world map, tent, sleeping bag, flippers and mountain view windows",
}


def module_ids() -> list[str]:
    ids = []
    for path in sorted(CONTENT.glob("sp*/*.json")):
        ids.append(json.loads(path.read_text(encoding="utf-8"))["id"])
    return ids


def make(module_id: str, key: str) -> str:
    dest = OUT / f"{module_id.replace('.', '-')}.webp"
    task = api("POST", API, key, {"ai_model": MODEL, "prompt": STYLE + SCENES[module_id], "aspect_ratio": "16:9"})["result"]
    deadline = time.time() + 900
    while time.time() < deadline:
        status = api("GET", f"{API}/{task}", key)
        if status["status"] == "SUCCEEDED":
            WORK.mkdir(parents=True, exist_ok=True)
            raw = WORK / f"{module_id}-{task[:8]}.png"
            urllib.request.urlretrieve(status["image_urls"][0], raw)
            image = Image.open(raw).convert("RGB")
            image.thumbnail((1280, 720), Image.LANCZOS)
            OUT.mkdir(parents=True, exist_ok=True)
            image.save(dest, "WEBP", quality=82)
            return f"{module_id}: готово"
        if status["status"] in ("FAILED", "CANCELED"):
            return f"{module_id}: {status['status']} {status.get('task_error')}"
        time.sleep(8)
    return f"{module_id}: timeout"


def main() -> None:
    wanted = sys.argv[1:] or [m for m in module_ids() if not (OUT / f"{m.replace('.', '-')}.webp").exists()]
    missing = [m for m in wanted if m not in SCENES]
    if missing:
        raise SystemExit(f"нет описания сцены: {missing}")
    print(f"этажей к генерации: {len(wanted)} (~{len(wanted) * 9} кредитов)", flush=True)
    key = load_key()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for line in pool.map(lambda m: make(m, key), wanted):
            print(line, flush=True)


if __name__ == "__main__":
    main()
