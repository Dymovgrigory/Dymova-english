"""Скачать фото слов с Wikipedia REST (свободные превью)."""
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


def words() -> list[str]:
    seen: list[str] = []
    have = set()
    for unit in COURSE:
        for lesson in unit["lessons"]:
            for w in lesson["words"]:
                en = w["en"].lower()
                if en not in have:
                    have.add(en)
                    seen.append(en)
    return seen


def thumb(title: str) -> str | None:
    q = urllib.parse.quote(title)
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "FoxinburgPhonics/1.0"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=20) as r:
            data = json.loads(r.read().decode())
    except Exception:
        return None
    src = (data.get("thumbnail") or {}).get("source") or (data.get("originalimage") or {}).get("source")
    return src


def save(en: str, src: str) -> bool:
    dest = ROOT / f"{en}.jpg"
    if dest.exists() and dest.stat().st_size > 2000:
        return True
    req = urllib.request.Request(src, headers={"User-Agent": "FoxinburgPhonics/1.0"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
            dest.write_bytes(r.read())
        return dest.stat().st_size > 1000
    except Exception:
        return False


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for en in words():
        src = thumb(en) or thumb(en.capitalize())
        if src and save(en, src):
            ok += 1
            print("ok", en)
        else:
            print("miss", en)
        time.sleep(0.15)
    print("saved", ok)


if __name__ == "__main__":
    main()
