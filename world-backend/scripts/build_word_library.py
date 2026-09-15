"""Собрать world/public/learn/words/*.svg — понятные ребёнку картинки."""
from __future__ import annotations

import ssl
import urllib.request
from pathlib import Path
import xml.sax.saxutils as esc

from app.world.learn_course import COURSE
from app.world.word_library import EMOJI, twemoji_url

ROOT = Path(__file__).resolve().parents[2] / "world" / "public" / "learn" / "words"
CTX = ssl.create_default_context()
UA = {"User-Agent": "FoxinburgWordLib/1.0 (educational)"}


def _words() -> dict[str, str]:
    out: dict[str, str] = {}
    for unit in COURSE:
        for lesson in unit["lessons"]:
            for w in lesson["words"]:
                out.setdefault(w["en"].lower(), w["ru"])
    return out


def _sun() -> str:
    rays = ""
    for i, a in enumerate(range(0, 360, 30)):
        rays += (
            f'<rect x="196" y="28" width="16" height="44" rx="8" fill="#f5ed75" '
            f'transform="rotate({a} 204 204)"/>'
        )
    return f"""
  <g>
    {rays}
    <circle cx="204" cy="204" r="88" fill="#ffe14a" stroke="#ee7349" stroke-width="8"/>
    <circle cx="176" cy="188" r="10" fill="#3a2953"/>
    <circle cx="232" cy="188" r="10" fill="#3a2953"/>
    <path d="M168 228 Q204 258 240 228" fill="none" stroke="#ee7349" stroke-width="8" stroke-linecap="round"/>
  </g>"""


def _moon() -> str:
    return """
  <circle cx="210" cy="200" r="90" fill="#f5ed75"/>
  <circle cx="248" cy="176" r="72" fill="#3a2953"/>
  <circle cx="186" cy="186" r="8" fill="#3a2953"/>
  <path d="M170 230 Q200 250 226 228" fill="none" stroke="#f5ed75" stroke-width="6"/>"""


def _cat() -> str:
    return """
  <ellipse cx="204" cy="230" rx="90" ry="70" fill="#ee7349"/>
  <circle cx="204" cy="168" r="62" fill="#ee7349"/>
  <polygon points="150,140 158,88 186,138" fill="#ee7349"/>
  <polygon points="258,140 250,88 222,138" fill="#ee7349"/>
  <circle cx="184" cy="162" r="8" fill="#241a30"/>
  <circle cx="224" cy="162" r="8" fill="#241a30"/>
  <ellipse cx="204" cy="186" rx="10" ry="7" fill="#3a2953"/>
  <path d="M160 200 Q204 220 248 200" fill="none" stroke="#3a2953" stroke-width="5"/>"""


def _dog() -> str:
    return """
  <ellipse cx="210" cy="236" rx="92" ry="64" fill="#c47a3a"/>
  <circle cx="200" cy="168" r="66" fill="#c47a3a"/>
  <ellipse cx="132" cy="176" rx="28" ry="44" fill="#8b5a2b"/>
  <ellipse cx="268" cy="176" rx="22" ry="36" fill="#8b5a2b"/>
  <circle cx="184" cy="160" r="8" fill="#241a30"/>
  <circle cx="228" cy="160" r="8" fill="#241a30"/>
  <ellipse cx="204" cy="188" rx="16" ry="10" fill="#241a30"/>
  <path d="M188 206 Q204 220 222 206" fill="none" stroke="#241a30" stroke-width="5"/>"""


CUSTOM = {"sun": _sun, "moon": _moon, "cat": _cat, "dog": _dog}


def fetch_twemoji(code: str) -> str | None:
    req = urllib.request.Request(twemoji_url(code), headers=UA)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=20) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        if "<svg" in raw:
            inner = raw.split(">", 1)[1].rsplit("</svg>", 1)[0]
            return inner
    except Exception:
        return None
    return None


def card(en: str, ru: str, inner: str) -> str:
    e = esc.escape(en)
    r = esc.escape(ru)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 408 480">
  <rect width="408" height="480" rx="36" fill="#fffaf0"/>
  <rect x="18" y="18" width="372" height="300" rx="28" fill="#3a2953"/>
  <g transform="translate(0,8)">{inner}</g>
  <text x="204" y="360" text-anchor="middle" font-family="Nunito, Trebuchet MS, sans-serif"
        font-size="42" font-weight="800" fill="#3a2953">{e}</text>
  <text x="204" y="408" text-anchor="middle" font-family="Nunito, Trebuchet MS, sans-serif"
        font-size="26" fill="#241a30" opacity="0.55">{r}</text>
</svg>
'''


def letter_badge(en: str) -> str:
    ch = esc.escape(en[:1].upper())
    return f'''
  <circle cx="204" cy="176" r="96" fill="#f5ed75"/>
  <text x="204" y="196" text-anchor="middle" font-size="92" font-weight="800"
        font-family="Nunito, sans-serif" fill="#3a2953">{ch}</text>
  <circle cx="204" cy="268" r="14" fill="#ee7349"/>
'''


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    words = _words()
    ok = 0
    for en, ru in words.items():
        slug = "".join(ch for ch in en if ch.isalnum())
        if en in CUSTOM:
            inner = CUSTOM[en]()
        else:
            code = EMOJI.get(en)
            inner = fetch_twemoji(code) if code else None
            if inner:
                inner = f'<g transform="translate(84,44) scale(2.2)">{inner}</g>'
            else:
                inner = letter_badge(en)
        (ROOT / f"{slug}.svg").write_text(card(en, ru, inner), encoding="utf-8")
        ok += 1
        print(en, "ok")
    print("library", ok, "files →", ROOT)


if __name__ == "__main__":
    main()
