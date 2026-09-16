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
    return _mcq(theme_id, count, seed, prompt="en", options="ru")


def _theme_words(theme_id: str) -> list[dict]:
    themes = load_themes()
    theme = themes.get(theme_id)
    if theme is None:
        raise ThemeNotFound(f"тема {theme_id!r} не найдена")
    words = theme["words"]
    if len(words) < OPTIONS_PER_QUESTION:
        raise ThemeNotFound(f"в теме {theme_id!r} слишком мало слов")
    return words


def _mcq(theme_id: str, count: int, seed: int | None, *, prompt: str, options: str) -> list[dict]:
    words = _theme_words(theme_id)
    rng = random.Random(seed)
    questions = []
    for word in rng.sample(words, min(count, len(words))):
        distractors = [w[options] for w in words if w[options] != word[options]]
        opts = rng.sample(distractors, OPTIONS_PER_QUESTION - 1) + [word[options]]
        rng.shuffle(opts)
        questions.append({
            "en": word["en"],
            "ru": word["ru"],
            "ipa": word["ipa"],
            "example_en": word["example_en"],
            "example_ru": word["example_ru"],
            "prompt": word[prompt],
            "options": opts,
            "correct_index": opts.index(word[options]),
            "correct_text": word["en"] if options == "en" else word["ru"],
        })
    return questions


def build_mcq_ru_en(theme_id: str, count: int = 2, seed: int | None = None) -> list[dict]:
    return _mcq(theme_id, count, seed, prompt="ru", options="en")


def build_type_en(theme_id: str, count: int = 2, seed: int | None = None) -> list[dict]:
    words = _theme_words(theme_id)
    rng = random.Random(seed)
    picked = rng.sample(words, min(count, len(words)))
    return [{
        "en": w["en"],
        "ru": w["ru"],
        "ipa": w["ipa"],
        "example_en": w["example_en"],
        "example_ru": w["example_ru"],
        "prompt": w["ru"],
        "correct_text": w["en"],
    } for w in picked]


def build_match(theme_id: str, count: int = 4, seed: int | None = None) -> dict:
    words = _theme_words(theme_id)
    rng = random.Random(seed)
    picked = rng.sample(words, min(count, len(words)))
    left = [w["en"] for w in picked]
    right = [w["ru"] for w in picked]
    rng.shuffle(left)
    rng.shuffle(right)
    return {
        "left": left,
        "right": right,
        "pairs": [{"en": w["en"], "ru": w["ru"]} for w in picked],
    }


def lesson_slice(theme_id: str, lesson_n: int) -> list[dict]:
    """Слова урока: порции по 8 из темы (цикл, если слов меньше)."""
    words = _theme_words(theme_id)
    size = 8
    start = ((lesson_n - 1) * size) % len(words)
    sliced = (words + words)[start:start + size]
    return sliced[:size] if len(sliced) >= OPTIONS_PER_QUESTION else words[:size]
