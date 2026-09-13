"""Словарь мира: темы из данных сайта и сборка вопросов челленджа.

Данные — data/vocabulary.json (генерируется scripts/export_world_vocabulary.py).
Правильный ответ (correct_index) остаётся на сервере: в HTTP-ответ он
не попадает (§84).
"""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "vocabulary.json"
OPTIONS_PER_QUESTION = 4


class ThemeNotFound(Exception):
    pass


@lru_cache(maxsize=1)
def load_themes() -> dict[str, dict]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {theme["id"]: theme for theme in raw["themes"]}


def build_questions(theme_id: str, count: int = 5, seed: int | None = None) -> list[dict]:
    """Вопросы «английское слово → 4 варианта перевода», варианты из той же темы."""
    themes = load_themes()
    theme = themes.get(theme_id)
    if theme is None:
        raise ThemeNotFound(f"тема {theme_id!r} не найдена")
    words = theme["words"]
    if len(words) < OPTIONS_PER_QUESTION:
        raise ThemeNotFound(f"в теме {theme_id!r} слишком мало слов")

    rng = random.Random(seed)
    questions = []
    for word in rng.sample(words, min(count, len(words))):
        distractors = [w["ru"] for w in words if w["ru"] != word["ru"]]
        options = rng.sample(distractors, OPTIONS_PER_QUESTION - 1) + [word["ru"]]
        rng.shuffle(options)
        questions.append({
            "en": word["en"],
            "ipa": word["ipa"],
            "example_en": word["example_en"],
            "example_ru": word["example_ru"],
            "options": options,
            "correct_index": options.index(word["ru"]),
        })
    return questions
