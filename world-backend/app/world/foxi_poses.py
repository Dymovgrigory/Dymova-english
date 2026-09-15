"""Какой Фокси показать: поза и одежда под слово или этап урока."""
from __future__ import annotations

import re

DEFAULT = "wave"

WORD_POSE = {
    "hello": "wave",
    "hi": "wave",
    "foxy": "wave",
    "mum": "sit",
    "dad": "sit",
    "family": "sit",
    "happy": "cheer",
    "play": "cheer",
    "jump": "cheer",
    "apple": "pan",
    "cake": "pan",
    "milk": "pan",
    "bird": "bee",
    "fish": "ship",
    "ball": "cheer",
    "school": "book",
    "pencil": "book",
    "friend": "wave",
    "sit": "sit",
    "sat": "sit",
    "sun": "sun",
    "hot": "sun",
    "rain": "rain",
    "coat": "rain",
    "cat": "cat",
    "hat": "hat",
    "cap": "cap",
    "pan": "pan",
    "pot": "pan",
    "cook": "pan",
    "map": "map",
    "nap": "nap",
    "sleep": "nap",
    "dog": "dog",
    "duck": "duck",
    "bed": "bed",
    "cot": "bed",
    "fan": "fan",
    "ship": "ship",
    "boat": "ship",
    "sail": "ship",
    "night": "night",
    "light": "night",
    "moon": "moon",
    "star": "moon",
    "bee": "bee",
    "tree": "bee",
    "car": "car",
    "bus": "car",
    "train": "car",
    "book": "book",
    "look": "book",
}

STAGE_POSE = {
    "warmup": "wave",
    "theory": "sit",
    "words": "book",
    "listen": "fan",
    "practice": "map",
    "wrap": "cheer",
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z]+", "", (text or "").lower())


def pose_for_item(item: dict) -> str:
    for key in ("en", "speak", "example_en"):
        slug = _slug(str(item.get(key) or ""))
        if slug in WORD_POSE:
            return WORD_POSE[slug]
        for token in re.findall(r"[A-Za-z]+", str(item.get(key) or "")):
            hit = WORD_POSE.get(_slug(token))
            if hit:
                return hit
    for token in list(item.get("left") or []) + list(item.get("bank") or []) + [
        p.get("en", "") for p in (item.get("pairs") or []) if isinstance(p, dict)
    ]:
        hit = WORD_POSE.get(_slug(str(token)))
        if hit:
            return hit
    stage = item.get("stage") or ""
    if stage in STAGE_POSE:
        return STAGE_POSE[stage]
    return DEFAULT
