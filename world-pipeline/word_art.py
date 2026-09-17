#!/usr/bin/env python3
"""Картинки слов тренажёра Spotlight: Meshy text-to-image листами 3×3 → WebP 512 px.

Цифры и цвета рисуются программно (точность важнее стиля). Остальные слова
группируются по модулям в листы по 9 штук, лист генерируется одной задачей Meshy
и нарезается. Прогресс хранится в manifest — повторный запуск продолжает с места.

Usage:
  python3 world-pipeline/word_art.py plan                 # что будет сгенерировано и сколько кредитов
  python3 world-pipeline/word_art.py local                # цифры и цвета
  python3 world-pipeline/word_art.py sheets --limit 1     # пилот: один лист
  python3 world-pipeline/word_art.py sheets               # все оставшиеся листы

Ключ: MESHY_API_KEY из окружения или secrets/meshy.env.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "world-backend" / "content" / "spotlight"
OUT = ROOT / "world" / "public" / "content"
WORK = ROOT / "world-pipeline" / "word-art"
MANIFEST = WORK / "manifest.json"
API = "https://api.meshy.ai/openapi/v1/text-to-image"
MODEL = "nano-banana-pro"
CREDITS_PER_SHEET = 9
TILE = 512

NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}
COLOURS = {
    "red": "#E5484D", "blue": "#3E7BFA", "green": "#35A853", "yellow": "#FFD43B", "pink": "#FF8FC7",
    "purple": "#8E5CD9", "orange": "#FF8A1F", "black": "#1F1A24", "white": "#FFFFFF", "brown": "#8B5A2B",
}

# Как нарисовать слово, если само слово неоднозначно для художника.
DESCRIBE = {
    "family": "a happy family of four (mother, father, boy, girl) standing together",
    "mummy": "a smiling young mother", "daddy": "a smiling young father", "mother": "a smiling mother",
    "father": "a smiling father", "grandma": "a smiling grandmother with glasses", "grandmother": "a smiling grandmother with glasses",
    "grandpa": "a smiling grandfather with grey beard", "grandfather": "a smiling grandfather with grey beard",
    "boy": "a school boy", "girl": "a school girl", "sister": "a little girl, older sister", "brother": "a little boy, brother",
    "children": "three happy children", "friend": "two kids hugging as friends", "aunt": "a friendly woman, aunt",
    "uncle": "a friendly man with moustache, uncle", "cousin": "two kid cousins smiling", "daughter": "a mother with her daughter",
    "son": "a father with his son", "chimp": "a chimpanzee", "king": "a cartoon king with crown", "queen": "a cartoon queen with crown",
    "rubber": "a pink school eraser", "schoolbag": "a school backpack", "school bag": "a school backpack",
    "TV": "a television set", "tortoise": "a tortoise", "biscuit": "a round biscuit cookie",
    "sausage": "a sausage", "plate": "an empty dinner plate", "eat": "a child eating with a spoon",
    "drink": "a child drinking from a glass", "play": "children playing with a ball", "sand": "a pile of sand with a spade",
    "seaside": "a seaside with waves and sand", "ink": "an ink bottle", "jug": "a water jug", "pin": "a safety pin",
    "vest": "a white vest undershirt", "zip": "a zipper", "chick": "a baby chick", "thumb": "a thumbs-up hand",
    "home": "a cosy home with warm windows", "living room": "a living room with sofa", "bath": "a bathtub",
    "floor": "a wooden floor", "birthday": "a birthday cake with candles and gifts", "party": "a party with balloons and confetti",
    "happy": "a happy smiling face", "sad": "a sad face with a tear", "chips": "french fries in a box",
    "chocolate cake": "a chocolate cake slice", "meat": "a piece of meat steak", "animal": "a group of farm animals",
    "swim": "a child swimming", "sing": "a child singing with music notes", "dance": "a child dancing",
    "fly": "a bird flying in the sky", "circus": "a circus tent", "swing": "a playground swing",
    "toy soldier": "a toy soldier", "shelf": "a wall shelf", "toy box": "a wooden toy box full of toys",
    "puppet": "a hand puppet", "jack-in-the-box": "a jack-in-the-box toy", "hair": "long wavy hair",
    "holiday": "a suitcase with beach hat", "shorts": "a pair of shorts", "socks": "a pair of socks", "jeans": "blue jeans",
    "T-shirt": "a t-shirt", "shoes": "a pair of shoes", "summer": "a summer meadow with sun", "autumn": "autumn tree with orange leaves",
    "winter": "a snowy winter landscape", "spring": "spring blossoms and flowers", "sunny": "a bright shining sun",
    "hot": "a thermometer in hot red sun", "cold": "a shivering snowman", "windy": "a tree bending in strong wind",
    "beach": "a sandy beach with palm tree", "English": "an English textbook with the UK flag", "Maths": "numbers and a calculator",
    "Art": "paint brushes and palette", "Music": "music notes and a drum", "PE": "sneakers and a ball, sports lesson",
    "Science": "a microscope and test tube", "History": "an ancient scroll and helmet", "Geography": "a globe",
    "family tree": "a family tree drawing with portraits", "tall": "a very tall giraffe next to a small mouse",
    "vegetables": "a pile of vegetables", "water": "a glass of water", "lunch box": "an open lunch box with sandwich and apple",
    "potatoes": "potatoes", "carrots": "carrots", "menu": "a restaurant menu card", "shopping list": "a paper shopping list with pencil",
    "fruit": "a bowl of fruit", "breakfast": "breakfast plate with eggs and toast", "toast": "a slice of toast",
    "musical box": "a musical box with ballerina", "tea set": "a toy tea set", "rocking horse": "a rocking horse toy",
    "aeroplane": "an aeroplane", "playroom": "a children's playroom with toys", "game": "a board game with dice",
    "present": "a wrapped gift box with ribbon", "fairy tale": "an open fairy tale book with a castle", "shout": "a child shouting",
    "legs": "a pair of legs in shorts", "body": "a child body outline", "neck": "a giraffe neck", "thin": "a thin man",
    "fat": "a chubby cat", "men": "two men", "women": "two women", "teeth": "a smile with white teeth", "feet": "two bare feet",
    "mice": "three little mice", "crawl": "a baby crawling", "sea horse": "a sea horse", "walk": "a child walking",
    "talk": "two kids talking with speech bubbles", "fast": "a running cheetah", "cute": "a cute puppy", "farm": "a farm with red barn",
    "cooker": "a kitchen stove cooker", "dish": "a serving dish", "castle": "a fairy tale castle", "prize": "a golden trophy prize",
    "winner": "a child on a winner podium", "sky": "a blue sky with clouds", "drive": "a person driving a car",
    "sandcastle": "a sandcastle", "watch": "a child watching TV", "paint": "a child painting on an easel", "picture": "a framed picture",
    "sleep": "a child sleeping in bed", "ride": "a child riding a bike", "bike": "a bicycle", "park": "a green city park",
    "picnic": "a picnic blanket with basket", "bell": "a bell", "ring": "a ringing alarm bell", "mac": "a yellow raincoat",
    "cartoon": "a TV screen showing a cartoon", "clock": "a wall clock", "night": "a night sky with moon and stars",
    "shower": "a shower head with water", "lunch": "a lunch plate with soup", "supper": "a dinner table with food",
    "listen": "a child listening with headphones", "CD": "a compact disc", "slim": "a slim woman", "plump": "a plump man",
    "vet": "a veterinarian with a dog", "best friend": "two best friends high-five", "wristwatch": "a wristwatch",
    "hairbrush": "a hairbrush", "roller blades": "roller blades", "gloves": "a pair of gloves", "keys": "a bunch of keys",
    "mobile phone": "a smartphone", "ski": "a child skiing", "sail": "a sailing boat on the sea", "skate": "a child ice skating",
    "surf": "a child surfing a wave", "station": "a train station", "garage": "a car repair garage", "cafe": "a small cafe with tables",
    "theatre": "a theatre stage with red curtains", "baker's": "a bakery shop with bread", "mechanic": "a car mechanic with wrench",
    "postman": "a postman with letters bag", "post office": "a post office building", "waiter": "a waiter with a tray",
    "nurse": "a nurse", "uniform": "a school uniform", "wear": "a child putting on a jacket", "wash": "washing dishes in a sink",
    "sports centre": "a sports centre building", "police officer": "a police officer", "doctor": "a doctor with stethoscope",
    "beans": "a bowl of beans", "butter": "a block of butter", "flour": "a bag of flour", "olive oil": "a bottle of olive oil",
    "sugar": "a bowl of sugar cubes", "salt": "a salt shaker", "pepper": "a pepper grinder", "packet": "a packet of crisps",
    "bar": "a chocolate bar", "kilo": "a one kilogram weight", "loaf": "a loaf of bread", "jar": "a glass jar of jam",
    "carton": "a milk carton", "bottle": "a bottle of water", "tin": "a tin can of food", "dairy": "milk, cheese and yogurt",
    "hungry": "a hungry child holding tummy", "dessert": "a dessert cup with cream", "seal": "a seal animal", "lazy": "a lazy cat sleeping on sofa",
    "clap": "hands clapping", "journey": "a car on a road trip", "ticket": "a ticket", "suitcase": "a suitcase", "feed": "a child feeding a duck",
    "bored": "a bored child face", "angry": "an angry face", "scared": "a scared face", "tired": "a tired yawning face",
    "balloon": "a red balloon", "card": "a greeting card", "hare": "a hare", "slow": "a slow snail", "race": "kids running a race",
    "laugh": "a child laughing", "finish line": "a finish line ribbon", "porridge": "a bowl of porridge", "study": "a child studying at desk",
    "bark": "a dog barking", "kitten": "a kitten", "lamb": "a lamb", "river": "a river", "museum": "a museum building",
    "dinosaur": "a dinosaur skeleton", "concert": "a concert stage with singer", "funfair": "a funfair ferris wheel",
    "fireworks": "fireworks in the night sky", "shy": "a shy child hiding face", "strong": "a strong man lifting weights",
    "loud": "a loud speaker with sound waves", "pancake": "a stack of pancakes", "Greece": "Greek white houses with blue domes",
    "Italy": "the Leaning Tower of Pisa", "Spain": "a flamenco dancer", "Russia": "Saint Basil's Cathedral in Moscow",
    "Turkey": "hot air balloons over Cappadocia", "Mexico": "a sombrero and cactus", "camping": "a campfire and tent",
    "mountains": "mountains", "lake": "a lake", "diary": "a diary notebook", "swimsuit": "a swimsuit", "sunglasses": "sunglasses",
    "boots": "a pair of boots", "tent": "a camping tent", "flippers": "swimming flippers", "sleeping bag": "a sleeping bag",
    "cloudy": "grey clouds", "rainy": "a rain cloud with raindrops", "room": "a child's bedroom", "desk": "a school desk",
    "pet": "a child with a pet dog", "house": "a house", "food": "a plate of food", "basket": "a picnic basket",
    "orange juice": "a glass of orange juice", "hot dog": "a hot dog", "under": "a ball under a chair", "toy": "a toy",
    "ant": "an ant", "flag": "a flag", "glass": "a drinking glass", "nest": "a bird nest with eggs", "box": "a cardboard box",
    "radio": "a radio", "candle": "a candle", "clown": "a clown", "magician": "a magician with a top hat",
    "yacht": "a yacht", "jelly": "a jelly dessert", "chicken": "a roast chicken", "mirror": "a mirror",
    "cupboard": "a cupboard", "armchair": "an armchair", "computer": "a computer", "head": "a child's head",
    "tail": "a fox tail", "cow": "a cow", "spider": "a spider", "parrot": "a parrot", "koala": "a koala", "coconut": "a coconut",
}

STYLE = (
    "A 3x3 grid of nine separate children's vocabulary flashcard illustrations with thick pure white gutters "
    "between cells, pure white background. Each cell shows exactly one centered subject. Style: premium soft "
    "3D cartoon render, rounded friendly shapes, vibrant but gentle colours, soft studio lighting, subtle shadow. "
    "Absolutely no text, letters, numbers or labels anywhere. Left to right, top to bottom: "
)


def load_key() -> str:
    key = os.environ.get("MESHY_API_KEY")
    if not key:
        env = ROOT / "secrets" / "meshy.env"
        for line in env.read_text().splitlines():
            if line.startswith("MESHY_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        raise SystemExit("MESHY_API_KEY не найден")
    return key


def collect() -> list[tuple[str, str]]:
    """(slug картинки, английское слово) в порядке учебников и модулей, без повторов."""
    seen: dict[str, str] = {}
    for path in sorted(CONTENT.glob("sp*/*.json"), key=lambda p: (p.parent.name, int(p.stem[1:]))):
        module = json.loads(path.read_text(encoding="utf-8"))
        for word in module["words"]:
            image = word.get("image")
            if image and image not in seen:
                seen[image] = word["en"]
    return [(Path(image).stem, en) for image, en in seen.items()]


def manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"sheets": {}}


def save_manifest(data: dict) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def ai_words() -> list[tuple[str, str]]:
    return [(slug, en) for slug, en in collect() if en not in NUMBERS and en not in COLOURS]


def plan_sheets() -> list[list[tuple[str, str]]]:
    words = [(s, e) for s, e in ai_words() if not (OUT / "words" / f"{s}.webp").exists()]
    if not words:
        return []
    while len(words) % 9:
        words.append(words[len(words) % 9])  # добиваем лист повтором, дубликат просто перезапишется
    return [words[i:i + 9] for i in range(0, len(words), 9)]


def font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def draw_local() -> int:
    (OUT / "words").mkdir(parents=True, exist_ok=True)
    count = 0
    for slug, en in collect():
        dest = OUT / "words" / f"{slug}.webp"
        if en in NUMBERS:
            img = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((36, 36, TILE - 36, TILE - 36), radius=96, fill="#F5ED75", outline="#D8B72C", width=10)
            text = str(NUMBERS[en])
            f = font(260 if len(text) < 3 else 190)
            box = d.textbbox((0, 0), text, font=f)
            d.text(((TILE - (box[2] - box[0])) / 2 - box[0], (TILE - (box[3] - box[1])) / 2 - box[1]), text, font=f, fill="#3A2953")
        elif en in COLOURS:
            img = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse((76, 76, TILE - 76, TILE - 76), fill=COLOURS[en], outline="#3A2953" if en == "white" else None, width=8)
            d.ellipse((150, 130, 230, 190), fill=(255, 255, 255, 90))
        else:
            continue
        img.save(dest, "WEBP", quality=90)
        count += 1
    return count


def api(method: str, url: str, key: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        url, method=method, data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def generate(prompt: str, key: str) -> Image.Image:
    task = api("POST", API, key, {"ai_model": MODEL, "prompt": prompt, "aspect_ratio": "1:1"})["result"]
    deadline = time.time() + 900
    while time.time() < deadline:
        status = api("GET", f"{API}/{task}", key)
        if status["status"] == "SUCCEEDED":
            dest = WORK / "sheets" / f"{task}.png"
            dest.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(status["image_urls"][0], dest)
            return Image.open(dest).convert("RGB")
        if status["status"] in ("FAILED", "CANCELED"):
            raise RuntimeError(f"Meshy task {task} {status['status']}: {status.get('task_error')}")
        time.sleep(8)
    raise TimeoutError(f"Meshy task {task} timed out")


def slice_sheet(sheet: Image.Image, slugs: list[str], gutter: float = 0.05) -> None:
    (OUT / "words").mkdir(parents=True, exist_ok=True)
    w, h = sheet.size
    for i, slug in enumerate(slugs):
        col, row = i % 3, i // 3
        cw, ch = w / 3, h / 3
        tile = sheet.crop((int(col * cw + cw * gutter), int(row * ch + ch * gutter),
                           int((col + 1) * cw - cw * gutter), int((row + 1) * ch - ch * gutter)))
        side = min(tile.size)
        tile = tile.crop(((tile.width - side) // 2, (tile.height - side) // 2,
                          (tile.width + side) // 2, (tile.height + side) // 2)).resize((TILE, TILE), Image.LANCZOS)
        tile.save(OUT / "words" / f"{slug}.webp", "WEBP", quality=86)


def _make_sheet(number: int, total: int, sheet: list[tuple[str, str]], key: str) -> tuple[list[tuple[str, str]], str] | None:
    described = [DESCRIBE.get(slug) or DESCRIBE.get(en) or f"a {en}" for slug, en in sheet]
    prompt = STYLE + "; ".join(f"{i + 1}) {d}" for i, d in enumerate(described)) + "."
    for attempt in range(3):
        try:
            image = generate(prompt, key)
            slice_sheet(image, [slug for slug, _ in sheet])
            print(f"  лист {number}/{total} готов: {', '.join(en for _, en in sheet)}", flush=True)
            return sheet, prompt
        except Exception as exc:  # сеть или сбой Meshy — повторяем лист
            print(f"  лист {number}: попытка {attempt + 1} не удалась: {exc}", flush=True)
            time.sleep(20)
    print(f"  лист {number}: пропущен", flush=True)
    return None


def run_sheets(limit: int | None, workers: int) -> None:
    from concurrent.futures import ThreadPoolExecutor

    key = load_key()
    data = manifest()
    sheets = plan_sheets()[: limit or None]
    print(f"листов к генерации: {len(sheets)} (~{len(sheets) * CREDITS_PER_SHEET} кредитов)", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_make_sheet, n, len(sheets), sheet, key) for n, sheet in enumerate(sheets, start=1)]
        for future in futures:
            done = future.result()
            if done:
                sheet, prompt = done
                data["sheets"][sheet[0][0]] = {"words": [en for _, en in sheet], "prompt": prompt}
                save_manifest(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["plan", "local", "sheets"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.command == "plan":
        sheets = plan_sheets()
        print(f"всего картинок: {len(collect())}, через Meshy: {len(ai_words())}, листов осталось: {len(sheets)}, "
              f"кредитов: {len(sheets) * CREDITS_PER_SHEET}")
    elif args.command == "local":
        print(f"нарисовано программно: {draw_local()}")
    else:
        run_sheets(args.limit, args.workers)


if __name__ == "__main__":
    main()
