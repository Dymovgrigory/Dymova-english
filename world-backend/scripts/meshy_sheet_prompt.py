#!/usr/bin/env python3
"""Генерация промптов для Meshy-листов из word_sheets.py (без вызова API)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.world.word_sheets import SHEETS

PROMPTS = {
    "pilot-thumbs": "school bag, cozy bed, yellow school bus, orange tabby cat, friendly brown dog, ceramic mug, blue pen, striped sock, shopping tote",
    "school-kit": "closed book, yellow pencil, pink eraser, wooden ruler, pencil case, school desk, wooden chair, table lamp, cardboard box",
    "home": "window, wooden door, floor mat, teacup, sun hat, baseball cap, metal bell, stone well, grassy hill",
    "pets": "small bird, goldfish, pink pig, brown rat, owl, kitten, orange fox, yellow duck, hen",
    "food": "apple, banana, milk carton, cake, loaf of bread, egg, ham slice, jam jar, ear of corn",
    "travel": "red car, train, sailing ship, van, park bench tree, country road, town houses, small boat, football",
    "nature": "bright sun, crescent moon, green tree, wood logs, starry night, glowing lamp, rain cloud, yellow star, farm barn",
}


def sheet_prompt(sheet_id: str, objects: str | None = None) -> str:
    words = None
    for s in SHEETS:
        if s["id"] == sheet_id:
            words = s["words"]
            break
    if not words:
        raise KeyError(sheet_id)
    objects = objects or ", ".join(words)
    return (
        "A 3x3 grid of nine children's flashcard illustrations, thick white gutters, "
        "white background, no text. Premium cartoon 3D, warm light. Left to right, "
        f"top to bottom: {objects}. One object per cell."
    )


if __name__ == "__main__":
    sid = sys.argv[1] if len(sys.argv) > 1 else "pilot-thumbs"
    print(sheet_prompt(sid, PROMPTS.get(sid)))
