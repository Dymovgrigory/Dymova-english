"""Крупные фото слов: Wikimedia Commons, только jpeg/png, без иконок и без SVG."""
from __future__ import annotations

import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.world.starter_course import COURSE as STARTER
from app.world.learn_course import COURSE

ROOT = Path(__file__).resolve().parents[2] / "world" / "public" / "learn" / "words"
CTX = ssl.create_default_context()
UA = {"User-Agent": "FoxinburgWorld/1.1 (educational; dymova-english.ru)"}

# Поисковые фразы → настоящее фото, не буква и не смайлик.
QUERY = {
    "fox": "red fox wildlife photograph",
    "foxy": "red fox wildlife photograph",
    "cat": "domestic cat photograph",
    "dog": "dog photograph",
    "yes": "person thumbs up photograph",
    "no": "person shaking head no photograph",
    "hello": "child waving hand photograph",
    "hi": "child waving hand photograph",
    "mum": "mother and child photograph",
    "dad": "father and child photograph",
    "family": "family portrait photograph",
    "sister": "sisters children photograph",
    "brother": "brothers children photograph",
    "baby": "baby photograph",
    "happy": "smiling child photograph",
    "sad": "sad child photograph",
    "smile": "child smile photograph",
    "cry": "crying toddler photograph",
    "you": "pointing at camera photograph",
    "i": "child pointing at self photograph",
    "name": "name tag photograph",
    "apple": "red apple fruit photograph",
    "banana": "banana fruit photograph",
    "cake": "birthday cake photograph",
    "bread": "loaf of bread photograph",
    "egg": "chicken egg photograph",
    "milk": "glass of milk photograph",
    "fish": "goldfish aquarium photograph",
    "bird": "songbird photograph",
    "car": "red car photograph",
    "toy": "children toys photograph",
    "ball": "soccer ball photograph",
    "sun": "sun sky photograph",
    "run": "child running photograph",
    "eat": "child eating photograph",
    "drink": "child drinking photograph",
    "friend": "children friends photograph",
    "school": "primary school classroom photograph",
    "book": "open book photograph",
    "pen": "ballpoint pen photograph",
    "pencil": "yellow pencil photograph",
    "bag": "school backpack photograph",
    "bed": "child bedroom bed photograph",
    "chair": "wooden chair photograph",
    "hat": "sun hat photograph",
    "white": "white snow photograph",
    "on": "cup on table photograph",
    "have": "child holding toy photograph",
    "look": "child looking photograph",
    "see": "child looking through window photograph",
    "can": "soda can photograph",
    "like": "child hugging teddy photograph",
    "please": "child praying hands please photograph",
    "thanks": "child saying thank you photograph",
    "thank": "child saying thank you photograph",
    "hungry": "hungry child eating photograph",
    "thirsty": "child drinking water photograph",
    "fun": "children playing outdoors photograph",
    "yum": "child eating ice cream photograph",
    "big": "elephant photograph",
    "small": "kitten photograph",
    "where": "lost looking around photograph",
    "count": "abacus counting photograph",
    "eight": "number 8 balloons photograph",
    "nine": "number 9 photograph",
    "ten": "ten fingers photograph",
    "rubber": "pencil eraser photograph",
    "ruler": "school ruler photograph",
    "case": "pencil case photograph",
}

SKIP = ("svg", "icon", "logo", "flag", "map of", "coat of arms", "diagram", "symbol")


def _words() -> list[str]:
    seen: list[str] = []
    have: set[str] = set()
    for unit in list(STARTER) + list(COURSE):
        for lesson in unit["lessons"]:
            for w in lesson["words"]:
                en = w["en"].lower()
                if en not in have:
                    have.add(en)
                    seen.append(en)
    return seen


def _get(url: str) -> bytes | None:
    req = urllib.request.Request(url.split("?")[0] if "utm_" in url else url, headers=UA)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
            return r.read()
    except Exception:
        return None


def commons_photo(query: str) -> str | None:
    qs = urllib.parse.urlencode({
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": "12",
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": "1280",
        "format": "json",
    })
    raw = _get(f"https://commons.wikimedia.org/w/api.php?{qs}")
    if not raw:
        return None
    pages = (json.loads(raw.decode()).get("query") or {}).get("pages") or {}
    for page in pages.values():
        title = (page.get("title") or "").lower()
        if any(s in title for s in SKIP):
            continue
        info = (page.get("imageinfo") or [{}])[0]
        mime = (info.get("mime") or "").lower()
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            continue
        url = info.get("thumburl") or info.get("url")
        if url and not url.lower().endswith(".svg"):
            return url
    return None


def wiki_photo(title: str) -> str | None:
    raw = _get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}")
    if not raw:
        return None
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    img = data.get("originalimage") or data.get("thumbnail") or {}
    src = img.get("source") or ""
    if not src or src.lower().endswith(".svg"):
        return None
    return src.replace("/320px-", "/1280px-").replace("/40px-", "/1280px-")


def save(slug: str, src: str) -> bool:
    blob = _get(src)
    if not blob or len(blob) < 12000:
        return False
    dest = ROOT / f"{slug}.jpg"
    dest.write_bytes(blob)
    return dest.stat().st_size > 12000


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    ok = 0
    # Сначала устная линия + животные, потом остальное.
    priority = [w["en"].lower() for u in STARTER for ls in u["lessons"] for w in ls["words"]]
    rest = [w for w in _words() if w not in set(priority)]
    order = list(dict.fromkeys(priority + rest))
    for en in order:
        slug = "".join(ch for ch in en if ch.isalnum())
        dest = ROOT / f"{slug}.jpg"
        if dest.exists() and dest.stat().st_size > 20000 and en not in ("fox", "yes", "no", "hello", "hi"):
            ok += 1
            print("have", en)
            continue
        q = QUERY.get(en, f"{en} photograph")
        src = commons_photo(q) or wiki_photo(en.capitalize()) or commons_photo(en)
        if src and save(slug, src):
            ok += 1
            print("ok", en)
        else:
            print("miss", en)
        time.sleep(0.2)
    print("photos", ok)


if __name__ == "__main__":
    main()
