#!/usr/bin/env python3
"""Ассеты «живой миниатюры» (world-pipeline/prompts/ART_DIRECTION.md) через Meshy gpt-image-2-5-flare.

Usage:
  python3 world-pipeline/diorama_art.py sp1.m1          # все ассеты модуля + общие (башня, окна, фактуры)
  python3 world-pipeline/diorama_art.py sp1.m1 --force  # перегенерировать даже существующие
"""
from __future__ import annotations

import argparse
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
PUBLIC = ROOT / "world" / "public" / "content"
RAW = ROOT / "world-pipeline" / "word-art" / "diorama"
MODEL = "gpt-image-2-5-flare"
API = "https://api.meshy.ai/openapi/v1/text-to-image"

CORE = (
    "Ultra-detailed photorealistic miniature diorama, a handcrafted tabletop model photographed with a professional "
    "macro lens, tilt-shift look, shallow depth of field, creamy bokeh. Real handmade materials with rich "
    "micro-texture: hand-carved lavender-grey stone with visible mortar and chipped edges, soft green moss and tiny "
    "ivy, weathered oak wood, aged brass, deep plum roof tiles, hand-painted porcelain. Warm golden glow from windows "
    "and lanterns, soft volumetric dusk light, cinematic colour grading with plum, gold and teal accents. Intricate "
    "details, 8k, award-winning product photography. No text, no letters, no numbers, no watermark. "
)

PEOPLE = {
    "boy": "a smiling schoolboy with a backpack", "girl": "a smiling schoolgirl with a hair ribbon",
    "family": "a happy family of four: mother, father, a boy and a girl standing together",
    "mummy": "a kind young mother in a cosy cardigan", "daddy": "a friendly young father in a knitted sweater",
    "king": "a jolly fairy-tale king with a golden crown and a velvet cloak",
    "queen": "a gentle fairy-tale queen with a small crown and a flowing gown",
    "chimp": "a cheerful little chimpanzee",
    "hello": "a smiling child happily waving hello with one raised hand",
    "goodbye": "a child walking away down a tiny mossy path, looking back and waving goodbye, backpack on",
    "yes": "a happy child nodding and giving a big thumbs up",
    "no": "a child gently shaking the head with crossed arms",
    "like": "a smiling child hugging a big red velvet heart",
}
COLOURS = {"red", "blue", "green", "yellow", "pink", "purple", "orange", "black", "white", "brown"}
OBJECTS = {
    "name": "single blank wooden name tag badge on a purple ribbon with a tiny brass pin, lying alone on the pedestal, nothing written on it, no house, no building, no roof",
    "cup": "simple round white porcelain teacup with a golden rim on a saucer, an ordinary cup shape, no house or roof details", "cake": "layered cake with cream and a strawberry on top",
    "tea": "porcelain teapot pouring steaming tea into a cup", "milk": "glass bottle of milk with a paper cap",
    "jam": "jar of strawberry jam with a gingham cloth lid", "lemon": "fresh lemon with a slice cut open",
}

WINDOW_STATES = {
    "lit": "brightly lit from inside: intense warm golden candlelight glowing through amber leaded glass panes and spilling onto the sill, a tiny flower box with lavender",
    "dark": "dark leaded glass panes with a faint teal magical reflection, no light inside",
    "shutters": "closed weathered wooden shutters with black iron hinges and a small brass padlock",
    "chest": "a small arched stone niche holding an ornate wooden treasure chest with brass fittings, faint golden glow",
    "balcony": "a small stone balcony with a wrought-iron rail and a plum banner with a golden star on a pole",
}
TEXTURES = {
    "parchment": "aged cream parchment paper with subtle fibres and soft stains",
    "stone": "hand-carved lavender-grey castle stone blocks with mortar and tiny patches of moss",
    "wood": "dark weathered oak planks with visible grain and iron nails",
}


def slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def assets_for(module_id: str) -> list[dict]:
    book, key = module_id.split(".")
    module = json.loads((CONTENT / book / f"{key}.json").read_text(encoding="utf-8"))
    items: list[dict] = [{
        "name": f"tower-{book}", "aspect": "9:16", "bg": False, "out": PUBLIC / "towers" / f"{book}.webp", "size": (900, 1600),
        "prompt": "A tall fairy-tale castle tower as a miniature diorama: stacked round floors with glowing arched windows, "
                  "an outer spiral stone staircase, ivy, tiny brass lanterns, a plum tiled conical roof with a golden flag, "
                  "standing on a mossy rock base with a winding stone path to a small wooden door; misty evening forest bokeh.",
    }]
    for name, aspect, size in (("scene-forest-wide", "16:9", (1600, 900)), ("scene-forest-tall", "9:16", (900, 1600))):
        items.append({
            "name": name, "aspect": aspect, "bg": False, "out": PUBLIC / "scenes" / f"{name}.webp", "size": size,
            "prompt": "Pure landscape background plate, nature only: a misty dusk pine forest with mossy rocks at the "
                      "edges, soft warm firefly bokeh lights among the trees, rolling hills and distant blue-plum mountains "
                      "fading into haze, empty calm centre, strongly out of focus. The frame contains ONLY nature. Absolutely "
                      "no houses, cottages, buildings, towers, roofs, windows, lanterns on structures or any man-made objects, "
                      "no people.",
        })
    for state, text in WINDOW_STATES.items():
        items.append({
            "name": f"window-{state}", "aspect": "1:1", "bg": True, "out": PUBLIC / "ui" / f"window-{state}.webp", "size": (512, 512),
            "prompt": f"Front view of a single arched window from a miniature castle diorama, hand-carved stone frame with moss, {text}, isolated object, plain background.",
        })
    for name, text in TEXTURES.items():
        items.append({
            "name": f"tex-{name}", "aspect": "1:1", "bg": False, "out": PUBLIC / "ui" / f"tex-{name}.webp", "size": (768, 768),
            "prompt": f"Orthographic top-down texture photo of {text}, even soft lighting, fills the whole frame edge to edge, seamless look.",
        })
    for word in module["words"]:
        if not word.get("image"):
            continue
        en = word["en"]
        if en in PEOPLE:
            subject = f"A handcrafted miniature figurine of {PEOPLE[en]}, painted resin"
        elif en in COLOURS:
            subject = f"A tiny hand-blown glass jar filled with vivid {en} paint, a little wooden brush beside it"
        else:
            subject = f"A single {OBJECTS.get(en, en)} as a handcrafted miniature"
        items.append({
            "name": f"word-{slug(en)}", "aspect": "1:1", "bg": False, "size": (768, 768),
            "out": PUBLIC / "words" / Path(word["image"]).name,
            "prompt": f"{subject}, centered, standing on a small round mossy stone pedestal, whole object in frame, soft warm dusk bokeh background.",
        })
    return items


def floor_assets(module_ids: list[str]) -> list[dict]:
    """Этажи башни: комната «в разрезе» по теме модуля, как эталонный этаж Spotlight 1 · Module 1."""
    from module_art import SCENES

    return [{
        "name": f"floor-{mid}", "aspect": "16:9", "bg": False, "size": (1536, 864),
        "out": PUBLIC / "modules" / f"{mid.replace('.', '-')}.webp",
        "prompt": f"Cutaway of one cosy round room inside a fairy-tale castle tower: {SCENES[mid]}. Plum tiled roof edge "
                  "above, hand-carved stone wall with ivy around the opening, glowing small arched windows on the outer "
                  "wall, misty dusk forest bokeh behind. No people.",
    } for mid in module_ids]


def generate(asset: dict, key: str) -> str:
    payload = {"ai_model": MODEL, "prompt": CORE + asset["prompt"], "aspect_ratio": asset["aspect"]}
    if asset["bg"]:
        payload["remove_background"] = True
    for attempt in range(3):
        try:
            task = api("POST", API, key, payload)["result"]
            while True:
                status = api("GET", f"{API}/{task}", key)
                if status["status"] == "SUCCEEDED":
                    RAW.mkdir(parents=True, exist_ok=True)
                    raw = RAW / f"{asset['name']}-{task[:8]}.png"
                    urllib.request.urlretrieve(status["image_urls"][0], raw)
                    image = Image.open(raw)
                    image = image.convert("RGBA" if asset["bg"] else "RGB")
                    if asset["bg"] and image.getbbox():
                        image = image.crop(image.getbbox())
                    image.thumbnail(asset["size"], Image.LANCZOS)
                    asset["out"].parent.mkdir(parents=True, exist_ok=True)
                    image.save(asset["out"], "WEBP", quality=88)
                    return f"{asset['name']}: готово {image.size}"
                if status["status"] in ("FAILED", "CANCELED"):
                    raise RuntimeError(status.get("task_error"))
                time.sleep(8)
        except Exception as exc:  # сбой сети или Meshy — повтор
            last = exc
            time.sleep(15)
    return f"{asset['name']}: ОШИБКА {last}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("module")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    if args.module == "floors":
        ids = [json.loads(p.read_text(encoding="utf-8"))["id"] for p in sorted(CONTENT.glob("sp*/*.json"))]
        assets = floor_assets([m for m in ids if m != "sp1.m1"])
    else:
        assets = assets_for(args.module)
    if args.only:
        assets = [a for a in assets if a["name"] in args.only]
    marker = RAW / "done.json"
    done = set(json.loads(marker.read_text())) if marker.exists() and not args.force else set()
    todo = [a for a in assets if a["name"] not in done]
    print(f"ассетов: {len(todo)} (~{len(todo) * 9} кредитов)", flush=True)
    key = load_key()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for asset, line in zip(todo, pool.map(lambda a: generate(a, key), todo)):
            print(line, flush=True)
            if "готово" in line:
                done.add(asset["name"])
                RAW.mkdir(parents=True, exist_ok=True)
                marker.write_text(json.dumps(sorted(done)))


if __name__ == "__main__":
    main()
