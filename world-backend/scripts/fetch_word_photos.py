"""Скачать фото слов с Wikipedia / Wikimedia Commons (свободные превью)."""
from __future__ import annotations

import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.world.learn_course import COURSE

ROOT = Path(__file__).resolve().parents[2] / "world" / "public" / "learn" / "words"
CTX = ssl.create_default_context()
UA = {"User-Agent": "FoxinburgWorld/1.0 (educational; dymova-english.ru)"}

# Точные статьи → живые фото, не схемы и не буквы.
PAGES = {
    "cat": "Cat",
    "dog": "Dog",
    "fox": "Red_fox",
    "foxy": "Red_fox",
    "foxi": "Red_fox",
    "sun": "Sun",
    "moon": "Moon",
    "star": "Star",
    "apple": "Apple",
    "banana": "Banana",
    "cake": "Cake",
    "bread": "Bread",
    "egg": "Egg_as_food",
    "milk": "Milk",
    "bed": "Bed",
    "chair": "Chair",
    "lamp": "Lamp",
    "door": "Door",
    "room": "Bedroom",
    "ball": "Ball",
    "doll": "Doll",
    "car": "Automobile",
    "train": "Train",
    "bus": "Bus",
    "book": "Book",
    "pen": "Pen",
    "pencil": "Pencil",
    "bag": "School_bag",
    "fish": "Goldfish",
    "bird": "Bird",
    "duck": "Duck",
    "pig": "Pig",
    "cow": "Cow",
    "hat": "Hat",
    "cap": "Baseball_cap",
    "ship": "Ship",
    "boat": "Boat",
    "tree": "Tree",
    "rain": "Rain",
    "family": "Family",
    "mum": "Mother",
    "dad": "Father",
    "baby": "Infant",
    "sister": "Sister",
    "brother": "Brother",
    "school": "School",
    "desk": "Desk",
    "hello": "Wave_(gesture)",
    "hi": "Wave_(gesture)",
    "happy": "Smile",
    "sad": "Sadness",
    "smile": "Smile",
    "red": "Red",
    "blue": "Blue",
    "green": "Green",
    "yellow": "Yellow",
    "black": "Black",
    "white": "White",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "play": "Play_(activity)",
    "game": "Game",
    "run": "Running",
    "jump": "Jumping",
    "sit": "Sitting",
    "eat": "Eating",
    "drink": "Drinking",
    "pet": "Pet",
    "toy": "Toy",
    "box": "Box",
    "map": "Map",
    "pan": "Frying_pan",
    "cup": "Cup",
    "pot": "Cooking_pot",
    "sock": "Sock",
    "bee": "Bee",
    "night": "Night",
    "fan": "Mechanical_fan",
}


def _words() -> list[str]:
    seen: list[str] = []
    have: set[str] = set()
    for unit in COURSE:
        for lesson in unit["lessons"]:
            for w in lesson["words"]:
                en = w["en"].lower()
                if en not in have:
                    have.add(en)
                    seen.append(en)
    return seen


def _get(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=25) as r:
            return r.read()
    except Exception:
        return None


def wiki_thumb(title: str) -> str | None:
    q = urllib.parse.quote(title)
    raw = _get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{q}")
    if not raw:
        return None
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    img = data.get("originalimage") or data.get("thumbnail") or {}
    src = img.get("source")
    if not src:
        return None
    src = src.replace("/40px-", "/800px-").replace("/320px-", "/800px-")
    return src


def commons_thumb(query: str) -> str | None:
    qs = urllib.parse.urlencode({
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": "5",
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": "800",
        "format": "json",
    })
    raw = _get(f"https://commons.wikimedia.org/w/api.php?{qs}")
    if not raw:
        return None
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("thumburl") or info.get("url")
        if url and not url.lower().endswith(".svg"):
            return url
    return None


def save_jpg(slug: str, src: str) -> bool:
    dest = ROOT / f"{slug}.jpg"
    blob = _get(src)
    if not blob or len(blob) < 4000:
        return False
    dest.write_bytes(blob)
    return dest.stat().st_size > 4000


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for en in _words():
        slug = "".join(ch for ch in en if ch.isalnum())
        dest = ROOT / f"{slug}.jpg"
        if dest.exists() and dest.stat().st_size > 8000:
            ok += 1
            print("have", en)
            continue
        title = PAGES.get(en, en.capitalize())
        src = wiki_thumb(title) or commons_thumb(f"{en} photo")
        if src and save_jpg(slug, src):
            ok += 1
            print("ok", en)
        else:
            print("miss", en)
        time.sleep(0.12)
    print("photos", ok, "→", ROOT)


if __name__ == "__main__":
    main()
