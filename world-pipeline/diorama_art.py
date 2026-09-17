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
    "vest": "white cotton sleeveless vest undershirt neatly laid on the pedestal",
    "fly": "small colourful bird flying with spread wings above the pedestal",
    "plane": "toy aeroplane with a spinning propeller and wings, clearly an aircraft, no animals",
    "run": "child figurine running fast with one leg forward and arms swinging, dust puffs behind",
    "jump": "child figurine jumping high in the air over a small puddle, feet off the ground",
    "climb": "child figurine climbing up a small tree trunk, holding onto a branch",
    "toy": "open wooden toy box with a teddy bear, wooden blocks and a toy train inside",
    "new": "shiny brand-new red school backpack with a gift ribbon and a tiny price-free tag",
    "under": "red ball lying under a small wooden chair",
    "big": "giant oversized red apple towering over a tiny figurine child standing beside it",
    "small": "tiny little kitten sitting inside a porcelain teacup",
    "food": "wooden table full of different tiny foods: bread, cheese, fruit and a pie",
    "love": "child figurine hugging a puppy with little red hearts floating above",
    "can": "strong child figurine proudly lifting a small dumbbell above the head",
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


# Ядро стиля тянет модель к сказочным домикам; предмет-слово должен остаться самим собой.
NOT_A_HOUSE = (
    "The object keeps its own real shape and is NOT turned into a house or building: no windows, no doors, no roofs, "
    "no chimneys, no lanterns attached to it. Only this one object on the pedestal."
)


def word_assets(module_id: str) -> list[dict]:
    """Картинки всех слов модуля в стиле «живой миниатюры» (заменяют старые плоские)."""
    from word_art import DESCRIBE, NUMBERS

    book, key = module_id.split(".")
    module = json.loads((CONTENT / book / f"{key}.json").read_text(encoding="utf-8"))
    items = []
    for word in module["words"]:
        if not word.get("image"):
            continue
        en = word["en"]
        if en in PEOPLE:
            subject = f"A handcrafted miniature figurine of {PEOPLE[en]}, painted resin"
        elif en in COLOURS:
            subject = f"A tiny hand-blown glass jar filled with vivid {en} paint, a little wooden brush beside it"
        elif en in NUMBERS:
            subject = (f"A hand-carved wooden plaque in the shape of the single number {NUMBERS[en]}, painted warm gold "
                       f"(the only allowed characters in the image are the digits {NUMBERS[en]})")
        elif en in OBJECTS:
            subject = f"A single {OBJECTS[en]} as a handcrafted miniature"
        elif en in ABSTRACT:
            subject = f"A handcrafted miniature diorama of {ABSTRACT[en]}"
        elif DESCRIBE.get(en) or DESCRIBE.get(Path(word["image"]).stem):
            subject = f"A handcrafted miniature diorama of {DESCRIBE.get(Path(word['image']).stem) or DESCRIBE[en]}"
        else:
            subject = f"A single {en} as a handcrafted miniature"
        items.append({
            "name": f"word-{Path(word['image']).stem}", "aspect": "1:1", "bg": False, "size": (768, 768), "en": en,
            "out": PUBLIC / "words" / Path(word["image"]).name,
            "prompt": f"{subject}, centered, standing on a small round mossy stone pedestal, whole object in frame, soft warm dusk bokeh background. "
                      f"{NOT_A_HOUSE}",
        })
    return items


TOWER_THEMES = {
    "sp1": "A tall slender fairy-tale castle tower as a miniature diorama: stacked round floors with glowing arched windows, "
           "an outer spiral stone staircase, ivy, tiny brass lanterns, a plum tiled conical roof with a golden flag, "
           "standing on a mossy rock base with a winding stone path to a small wooden door; misty evening forest bokeh.",
    "sp2": "The Masters' Tower of the same fairy-tale kingdom as a miniature diorama: a wide sturdy round stone tower with "
           "a turning wooden waterwheel, a craftsman's workshop with open shutters and tiny tools, a small stone bridge "
           "over a sparkling creek, glowing arched windows, ivy, brass lanterns, a plum tiled roof with a weathervane and "
           "a golden flag, mossy rocks; misty evening forest bokeh.",
    "sp3": "The Stargazers' Tower of the same fairy-tale kingdom as a miniature diorama: a tall round stone observatory tower "
           "with a copper-and-brass dome opened to the sky and a large brass telescope, tiny glowing star lanterns, balconies "
           "with star charts, glowing arched windows, ivy, a plum tiled lower roof with a golden flag, perched on a mossy hill "
           "under a deep twilight sky with the first stars; misty evening forest bokeh.",
    "sp4": "The Travellers' Tower of the same fairy-tale kingdom as a miniature diorama: a lighthouse-like round stone tower "
           "on a mossy sea cliff with a glowing lantern room at the top, a tiny harbour with sailing ships below, a striped "
           "hot-air balloon tethered to a balcony, wooden piers, ivy, brass lanterns, plum tiled roof accents and a golden "
           "flag; misty evening sea and distant mountains bokeh.",
}


def tower_asset(book: str) -> dict:
    return {
        "name": f"tower-{book}", "aspect": "9:16", "bg": False, "out": PUBLIC / "towers" / f"{book}.webp", "size": (900, 1600),
        "prompt": TOWER_THEMES[book],
    }


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


# Более дешёвая модель для предметов/животных/отвлечённых слов (одобрено владельцем 2026-09-17);
# уточнение композиции держит её в стиле flare.
BUDGET_MODEL = "nano-banana-2"
BUDGET_TUNE = (" Composition: the object is large and fills about 60 percent of the frame, seen slightly from above; "
               "the background is only a smooth, strongly blurred warm golden-plum dusk bokeh with no room, no furniture, "
               "no shelves, no buildings, no clutter.")
PEOPLE_WORDS = set("""sister brother grandma grandpa children friend mother father grandmother grandfather aunt uncle
cousin vet nurse doctor postman waiter mechanic clown magician ballerina men women slim plump""".split()) | {
    "best friend", "police officer", "family tree", "toy soldier"}


def generate(asset: dict, key: str) -> str:
    model = asset.get("model", MODEL)
    prompt = CORE + asset["prompt"] + (BUDGET_TUNE if model == BUDGET_MODEL else "")
    payload = {"ai_model": model, "prompt": prompt, "aspect_ratio": asset["aspect"]}
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
    parser.add_argument("--budget", action="store_true", help="nano-banana-2 для всех слов, кроме людей")
    args = parser.parse_args()
    if args.module == "castle":
        assets = castle_assets()
    elif args.module == "castle-structure":
        assets = castle_structure_assets()
    elif args.module.startswith("towers:"):
        assets = [tower_asset(b) for b in args.module.split(":", 1)[1].split(",")]
    elif args.module.startswith("words:"):
        wanted = args.module.split(":", 1)[1].split(",")
        # один файл — одна генерация; слова, уже нарисованные для Spotlight 1, не перезаписываем
        sp1 = set() if any(m.startswith("sp1.") for m in wanted) else {
            str(a["out"]) for p in sorted(CONTENT.glob("sp1/*.json")) for a in word_assets(json.loads(p.read_text(encoding="utf-8"))["id"])
        }
        seen: set[str] = set()
        assets = []
        for a in (a for mid in wanted for a in word_assets(mid)):
            if str(a["out"]) in seen or str(a["out"]) in sp1:
                continue
            seen.add(str(a["out"]))
            assets.append(a)
    elif args.module == "floors":
        ids = [json.loads(p.read_text(encoding="utf-8"))["id"] for p in sorted(CONTENT.glob("sp*/*.json"))]
        assets = floor_assets([m for m in ids if m != "sp1.m1"])
    else:
        assets = assets_for(args.module)
    if args.only:
        assets = [a for a in assets if a["name"] in args.only]
    if args.budget:
        for a in assets:
            if a["name"].startswith("word-") and a.get("en") not in PEOPLE_WORDS:
                a["model"] = BUDGET_MODEL
    marker = RAW / "done.json"
    done = set(json.loads(marker.read_text())) if marker.exists() and not args.force else set()
    todo = [a for a in assets if a["name"] not in done]
    cost = sum(6 if a.get("model") == BUDGET_MODEL else 9 for a in todo)
    print(f"ассетов: {len(todo)} (~{cost} кредитов)", flush=True)
    key = load_key()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for asset, line in zip(todo, pool.map(lambda a: generate(a, key), todo)):
            print(line, flush=True)
            if "готово" in line:
                done.add(asset["name"])
                RAW.mkdir(parents=True, exist_ok=True)
                marker.write_text(json.dumps(sorted(done)))



# Отвлечённые слова: как показать смысл миниатюрой (для слов, у которых пока нет картинки).
ABSTRACT = {
    "bored": "a cute little child figurine sitting on a tiny stool with chin in hands, looking bored",
    "angry": "a cute little child figurine with arms crossed, stamping one foot, a small cartoon frown and red cheeks, full body",
    "scared": "a cute little child figurine peeking out from behind a small pillow, a little scared, full body",
    "tired": "a cute little child figurine in pyjamas yawning and rubbing one eye, holding a teddy bear, full body",
    "colour": "a wooden artist palette with dabs of many bright paints and a brush",
    "old": "an old grandfather figurine with a walking stick next to a birthday cake with many candles",
    "yummy": "a child figurine licking lips in front of a delicious cupcake",
    "favourite": "a child figurine hugging a favourite teddy bear tightly with a gold star above",
    "funny": "a clown figurine juggling and laughing children around",
    "clever": "an owl wearing tiny glasses sitting on a stack of books",
    "dark": "a child figurine with dark brown hair",
    "fair": "a child figurine with light blond hair",
    "holiday": "a suitcase with a beach hat, sunglasses and a seashell",
    "raining": "a small rain cloud raining over a tiny umbrella",
    "again": "a child figurine rebuilding a toppled tower of blocks one more time",
    "everyone": "a crowd of many different small figurines waving together",
    "today": "a small tear-off calendar with a glowing sun on the top page",
    "think": "a child figurine thinking with a finger on the chin and a glowing thought bubble",
    "day": "a bright sunny day scene with a sun above a meadow",
    "phone number": "an old-fashioned rotary telephone",
    "subject": "a stack of school textbooks of different colours",
    "get": "a child figurine taking a book from a shelf",
    "late": "a child figurine running late holding a big alarm clock",
    "come": "a child figurine running towards open arms of a mother",
    "great": "a child figurine jumping for joy holding a gold trophy",
    "little": "a very little mouse figurine next to a big boot",
    "live": "a cosy little house with a family visible in the window",
    "need": "a child figurine pointing at an empty shopping basket",
    "silly": "a child figurine pulling a silly face with a pot on the head",
    "careful": "a child figurine carefully carrying a full glass of water",
    "whose": "a lost teddy bear sitting alone with a question-mark-shaped ribbon",
    "short": "a short stubby pencil next to a long pencil",
    "long": "a very long snake stretched out across the pedestal",
    "next to": "a cat sitting right next to a dog",
    "in front of": "a small dog standing in front of a doghouse",
    "behind": "a cat hiding behind a flower pot with only its tail visible",
    "famous": "a star figurine on a tiny red carpet with camera flashes",
    "put": "a hand putting an apple into a basket",
    "make": "a child figurine making a clay pot",
    "finish": "a runner figurine crossing a finish ribbon",
    "Monday": "a school backpack by the door on a fresh morning",
    "Tuesday": "a child figurine at a music lesson with a flute",
    "Wednesday": "a child figurine swimming in a small pool",
    "Thursday": "a child figurine painting at an easel",
    "Friday": "a child figurine happily closing a school book",
    "Saturday": "a family picnic on a sunny lawn",
    "Sunday": "a child figurine sleeping in late in a cosy bed with sunlight",
    "quiz": "a small quiz board with a buzzer bell",
    "morning": "a sunrise over hills with a rooster",
    "afternoon": "a bright midday sun above a playground",
    "evening": "a sunset with a lit lantern on a porch",
    "o'clock": "a round wall clock with both hands pointing straight",
    "visit": "a child figurine knocking on grandma's door with flowers",
    "video": "a small video camera on a tripod",
    "join": "children figurines holding hands in a circle",
    "hope": "a child figurine looking up at a shooting star",
    "feel": "a child figurine hugging itself with a warm smile and hearts",
    "remember": "a child figurine looking at an old photo album",
    "surname": "a small brass door plate on a wooden front door, nothing written on it",
    "kind": "a child figurine giving an umbrella to a friend in the rain",
    "friendly": "two child figurines shaking hands and smiling",
    "always": "a sun that is always shining above a small house",
    "usually": "a child figurine brushing teeth at a sink",
    "sometimes": "a sky half sunny half cloudy",
    "never": "a cat avoiding a bath tub full of water",
    "often": "a child figurine watering plants with a watering can",
    "quarter": "a round clock with one quarter of the face highlighted in gold",
    "half": "an apple cut exactly in half",
    "past": "a clock with the minute hand just past twelve",
    "polite": "a child figurine bowing and holding a door open",
    "pass": "one hand passing a salt shaker to another hand",
    "hate": "a child figurine pushing away a plate of broccoli with a frown",
    "tasty": "a steaming delicious pie with a child sniffing it",
    "lunchtime": "a lunch table with a clock showing noon",
    "January": "a snowy winter scene with a snowman",
    "February": "a frosty scene with a sledge on snow",
    "March": "first spring snowdrops melting through snow",
    "April": "a spring rain with blossoming tree",
    "May": "a meadow full of blooming flowers",
    "June": "a sunny beach with a sandcastle",
    "July": "a summer picnic with watermelon",
    "August": "a field of sunflowers under hot sun",
    "September": "a school backpack with autumn leaves",
    "October": "orange pumpkins and falling leaves",
    "November": "bare trees in grey autumn rain",
    "December": "a decorated New Year tree with gifts",
    "amazing": "a child figurine amazed with open mouth at glowing fireworks",
    "journey": "a tiny train travelling across a bridge through mountains",
    "first": "a gold medal on a first-place podium",
    "second": "a silver medal on a second-place podium",
    "third": "a bronze medal on a third-place podium",
    "fourth": "four little ducks in a row with the fourth one highlighted",
    "fifth": "five little ducks in a row with the last one highlighted",
    "delicious": "a beautifully decorated cake with cream and berries",
    "yesterday": "a tear-off calendar with yesterday's page torn off lying beside",
    "ago": "an old dusty hourglass with sand run out",
    "last": "the last cookie left on a plate",
    "interesting": "a child figurine looking through a magnifying glass at a beetle",
    "dream": "a child figurine sleeping with a dream cloud of a castle above",
    "wish": "a child figurine blowing a dandelion",
    "soon": "a child figurine waiting by a window for a train arriving",
    "rest": "a tired traveller figurine resting under a tree",
    "cross": "a child figurine crossing a tiny road on a zebra crossing",
    "busy": "a busy postman figurine carrying many parcels",
    "follow": "ducklings following their mother duck in a line",
    "weekend": "a family figurines relaxing in a garden hammock",
    "pretty": "a pretty princess figurine with flowers in her hair",
    "young": "a baby figurine in a cradle",
    "celebrate": "children figurines celebrating with confetti and balloons",
    "went": "a child figurine walking away along a path to a castle",
    "saw": "a child figurine looking through binoculars at a deer",
    "ate": "an empty plate with crumbs and a happy child figurine",
    "had": "a child figurine holding a puppy",
    "took": "a hand taking a cookie from a jar",
    "made": "a child figurine proudly showing a finished birdhouse",
    "travel": "a suitcase with travel stickers and a globe",
    "relax": "a child figurine lying in a hammock between two trees",
    "tomorrow": "a calendar page turning to the next day with a sunrise",
    "mistake": "a spilled glass of milk on a table",
    "sorry": "a child figurine apologising with a flower to a sad friend",
    "cool": "a light breeze with falling leaves and a child figurine in a light jacket",
    "raining ": "",
}
ABSTRACT.pop("raining ", None)


def assign_missing_images(module_ids: list[str]) -> int:
    """Проставляет пути картинок словам, у которых их нет и есть описание в ABSTRACT."""
    import re as _re

    changed = 0
    for mid in module_ids:
        book, key = mid.split(".")
        path = CONTENT / book / f"{key}.json"
        module = json.loads(path.read_text(encoding="utf-8"))
        for word in module["words"]:
            if not word.get("image") and word["en"] in ABSTRACT:
                word["image"] = "words/" + _re.sub(r"[^a-z0-9]+", "-", word["en"].lower()).strip("-") + ".webp"
                changed += 1
        path.write_text(json.dumps(module, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed



# ---------------------------------------------------------------- Замок ---------------------------------------------
CASTLE_BUILDINGS = {
    "school": "Foxy's School: a cosy two-storey stone schoolhouse with a small bell tower, arched glowing windows, a tiny "
              "chalkboard sign without letters and satchels by the door",
    "shop": "Foxy's Shop: a crooked little merchant shop with a striped plum awning, shelves of tiny goods, baskets of apples, "
            "a brass shop bell and glowing lantern",
    "glory": "The Tower of Glory: a slender stone tower crowned with a golden trophy, banners with stars and laurel wreaths",
    "lexicon": "The Treasury of Words: a round stone vault with an open iron-bound door, glowing treasure chests full of "
               "floating paper scrolls and books",
    "stickers": "The Sticker Tower: a whimsical tower covered in colourful round sticker-like badges and emblems without "
                "letters, a winding staircase",
    "yard": "The Training Yard: a fenced wooden paddock with archery targets, a practice dummy, wooden training swords and hay bales",
    "quests": "The Quest Gazebo: an open wooden gazebo with a plum roof, a notice board pinned with blank parchment scrolls and a map",
    "nest": "Foxy's Nest: a cosy round burrow home built into a mossy hill with a round wooden door, a chimney and a fox-shaped weathervane",
}


# Конструктив замка — отдельные спрайты в том же стиле, что school/shop (изолированный объект + мшистая база).
CASTLE_STRUCTURE = {
    "gate": (
        "Front view of a fairy-tale castle main gate as a miniature diorama piece: twin round stone gatehouses with plum "
        "conical roofs, wooden drawbridge slightly lowered, warm lanterns, ivy on lavender-grey stone, small mossy oval base. "
        "Isolated object on a plain background, the whole gate in frame, no other buildings."
    ),
    "wall-front": (
        "Front view of a long miniature castle curtain wall segment: lavender-grey battlements, ivy and moss, two tiny "
        "glowing arched windows in the wall, plum-tiled walkway edge, standing on a narrow mossy base. Isolated object on a "
        "plain background, whole wall segment in frame, no towers, no gate, no houses."
    ),
    "wall-corner": (
        "Three-quarter view of a miniature castle wall corner with a short round corner turret, plum conical roof, "
        "battlements continuing both ways a short distance, ivy, mossy base. Isolated object on a plain background, "
        "whole piece in frame, no other buildings."
    ),
    "cottage-a": (
        "Tiny filler cottage for a miniature kingdom: small one-storey stone house with plum roof, glowing window, ivy, "
        "mossy round base. Isolated object on a plain background, whole building in frame, deliberately smaller and simpler "
        "than landmark buildings."
    ),
    "cottage-b": (
        "Tiny filler stable shed for a miniature kingdom: weathered wood and stone shed with plum roof, hay bale beside it, "
        "mossy round base. Isolated object on a plain background, whole building in frame, simple non-landmark prop."
    ),
    "bridge": (
        "Small arched stone bridge for a miniature kingdom diorama, moss and tiny flowers on the sides, short cobblestone "
        "path on both ends on a mossy base. Isolated object on a plain background, whole bridge in frame, no buildings."
    ),
}


def castle_structure_assets() -> list[dict]:
    items = []
    for key, prompt in CASTLE_STRUCTURE.items():
        items.append({
            "name": f"castle-struct-{key}",
            "aspect": "1:1",
            "bg": True,
            "size": (900, 900),
            "out": PUBLIC / "castle" / f"{key}.webp",
            "prompt": prompt,
        })
    # Плашка замка: стены/ворота/тропы/площадки ВПЕЧЕНЫ; landmark-здания — пустые мшистые холмики.
    # Цвет мха/земли = тот же, что у баз school/shop (soft green moss, brown earth).
    items.append({
        "name": "castle-grounds",
        "aspect": "16:9",
        "bg": False,
        "size": (1536, 864),
        "out": PUBLIC / "castle" / "castle-grounds.webp",
        "prompt": (
            "ONE continuous handcrafted miniature diorama of Foxinburg Castle fortress grounds filling the frame edge to edge, "
            "elevated three-quarter view, single unbroken tabletop model — NOT separate floating props. "
            "A complete lavender-grey stone curtain wall with battlements encloses a rectangular courtyard; "
            "twin-tower main gate with lowered wooden drawbridge at the BOTTOM-CENTER; a small stone bridge on the approach in front of the gate; "
            "a tiny teal stream with mossy banks curves to the right of the bridge. "
            "Cobblestone paths connect empty building pads. "
            "EMPTY round mossy earth pads only (no houses, no shops, no landmark towers on the pads) — soft green moss and brown soil "
            "identical in colour and texture to miniature building bases, tiny purple flowers, ready for figurines to sit on: "
            "four corner pads on the wall perimeter (back-left, back-right, front-left, front-right); "
            "five courtyard pads (back-center against the wall, left, center-left, center-right, right); "
            "three outside pads (far front-left hillock, front-left of the gate approach, far front-right paddock clearing). "
            "A few tiny non-landmark filler cottages and sheds baked into the walls and courtyard corners for density only. "
            "Warm dusk light, misty plum mountains behind, continuous shared grass and earth everywhere — same moss green, same soil brown, "
            "no colour breaks, no collage, no grey void between parts, no cutout buildings, no people, no text, no letters, no logos."
        ),
    })
    return items


# Цельный замок — один кадр, без склейки спрайтов. Композиция зафиксирована для хитбоксов.
CASTLE_REALM_PROMPT = (
    "ONE single continuous handcrafted miniature diorama of Foxinburg Castle as one solid tabletop fortress model, "
    "photographed as one unbroken object filling the frame edge to edge, elevated three-quarter view. "
    "Lavender-grey stone curtain walls with battlements enclose a busy courtyard; a grand front gate with twin gatehouses "
    "and a raised wooden drawbridge sits at the bottom-center. "
    "Four distinctive corner towers on the wall perimeter only: "
    "front-left ivy-clad round tower with spiral stair; front-right workshop tower with a tiny water wheel; "
    "back-left observatory tower with a brass telescope dome; back-right coastal lighthouse tower with a warm lantern crown. "
    "Inside the walls, smaller and neat: left a two-storey schoolhouse with bell and satchels; "
    "center-left a plum-awning merchant shop; back-center a slim glory tower with a golden trophy and star banners; "
    "center-right a round word-treasury vault with an open iron door and glowing scrolls; "
    "right a whimsical tower dotted with colourful blank badge-medals. "
    "Outside the walls for mass and life: left-front a fox burrow-home in a mossy hill with round door and fox weathervane; "
    "right-front a fenced training paddock with targets and hay; just outside the gate a plum-roof quest gazebo with a notice board; "
    "plus several small non-landmark cottages, stables and sheds built into the walls for density. "
    "Shared mossy ground, continuous cobblestone paths, one tiny river under a bridge near the right wall, "
    "warm dusk light and misty plum mountains behind. "
    "CRITICAL: everything is fused into one diorama — no separate cutout buildings, no floating pieces, no grey void between props, "
    "no collage, no plain studio background. No text, letters, numbers, logos or people."
)


def castle_assets() -> list[dict]:
    items: list[dict] = [{
        "name": "castle-realm", "aspect": "16:9", "bg": False, "size": (1920, 1080),
        "out": PUBLIC / "castle" / "castle-realm.webp",
        "prompt": CASTLE_REALM_PROMPT,
    }, {
        "name": "castle-realm-tall", "aspect": "9:16", "bg": False, "size": (1080, 1920),
        "out": PUBLIC / "castle" / "castle-realm-tall.webp",
        "prompt": CASTLE_REALM_PROMPT + " Vertical portrait crop of the same fortress, gate near the bottom, walls filling height.",
    }]
    for name, aspect, size in (("castle-plate-wide", "16:9", (1600, 900)), ("castle-plate-tall", "9:16", (900, 1600))):
        items.append({
            "name": name, "aspect": aspect, "bg": False, "size": size, "out": PUBLIC / "castle" / f"{name}.webp",
            "prompt": "Empty landscape plate for a miniature kingdom diorama seen from a slightly elevated angle: a wide green "
                      "mossy valley with winding cobblestone paths, a small sparkling river with a stone bridge, flower "
                      "meadows, a few pine trees at the edges, distant misty blue-plum mountains and a warm dusk sky. Open "
                      "empty ground spots for buildings. No buildings, no towers, no houses, no people.",
        })
    for book, theme in TOWER_THEMES.items():
        items.append({
            "name": f"castle-tower-{book}", "aspect": "9:16", "bg": True, "size": (700, 1244),
            "out": PUBLIC / "castle" / f"tower-{book}.webp",
            "prompt": theme.split(";")[0] + ". Isolated object on a plain background, the whole building with its small "
                      "mossy base in frame.",
        })
    for key, text in CASTLE_BUILDINGS.items():
        items.append({
            "name": f"castle-{key}", "aspect": "1:1", "bg": True, "size": (720, 720),
            "out": PUBLIC / "castle" / f"{key}.webp",
            "prompt": f"{text}, as a miniature diorama building on a small round mossy base. Isolated object on a plain "
                      "background, the whole building in frame.",
        })
        items.append({
            "name": f"castle-room-{key}", "aspect": "16:9", "bg": False, "size": (1536, 864),
            "out": PUBLIC / "castle" / f"room-{key}.webp",
            "prompt": f"Cutaway interior of {text.split(':')[0]} inside the miniature kingdom: {text.split(':', 1)[1]}, seen "
                      "from inside as a cosy detailed room with warm lanterns, misty dusk forest bokeh through the windows. "
                      "No people.",
        })
    return items


if __name__ == "__main__":
    main()
