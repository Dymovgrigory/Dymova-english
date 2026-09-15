"""Каталог курса: юниты, слова, фразы. Не vocabulary.json."""
from __future__ import annotations

from functools import lru_cache

from .learn_course import COURSE, tokenize_en
from .word_library import image_path, phrase_for, teach_line

LESSONS_PER_UNIT = 6


def _word(row) -> dict:
    if isinstance(row, dict) and "en" in row:
        en = row["en"]
        ru = row["ru"]
        return {
            "en": en,
            "ipa": row.get("ipa", ""),
            "ru": ru,
            "image": row.get("image") or image_path(en),
            "teach_ru": row.get("teach_ru") or teach_line(en, ru),
            "example_en": row.get("example_en") or phrase_for(en, ru)[0],
            "example_ru": row.get("example_ru") or phrase_for(en, ru)[1],
        }
    en, ipa, ru, example_en, example_ru = row
    return {
        "en": en, "ipa": ipa, "ru": ru,
        "example_en": example_en, "example_ru": example_ru,
        "image": image_path(en),
        "teach_ru": teach_line(en, ru),
    }


@lru_cache(maxsize=1)
def load_units() -> dict[str, dict]:
    units = {}
    for raw in COURSE:
        lessons = []
        for ls in raw.get("lessons") or []:
            lesson_words = [_word(w) for w in ls["words"]]
            phrases = []
            for en, ru in ls["phrases"]:
                phrases.append({"en": en, "ru": ru, "tokens": tokenize_en(en)})
            lessons.append({
                **ls,
                "words": lesson_words,
                "phrases": phrases,
            })
        words = [_word(w) for w in raw["words"]]
        phrases = []
        for en, ru in raw["phrases"]:
            phrases.append({"en": en, "ru": ru, "tokens": tokenize_en(en)})
        units[raw["id"]] = {
            "id": raw["id"],
            "book": raw.get("book", "prep"),
            "book_ru": raw.get("book_ru", ""),
            "place_ru": raw["place_ru"],
            "topic_ru": raw["topic_ru"],
            "goal_ru": raw.get("goal_ru", ""),
            "accent": raw["accent"],
            "spots": list(raw["spots"]),
            "has_checkpoint": bool(raw.get("has_checkpoint")),
            "checkpoint_ru": raw.get("checkpoint_ru", ""),
            "grammar": list(raw.get("grammar") or []),
            "theory": list(raw.get("theory") or []),
            "words": words,
            "phrases": phrases,
            "lessons": lessons,
        }
    return units


def unit_order() -> list[str]:
    return [u["id"] for u in COURSE]


def get_unit(unit_id: str) -> dict:
    units = load_units()
    if unit_id not in units:
        raise KeyError(unit_id)
    return units[unit_id]


def get_lesson(unit_id: str, lesson_n: int) -> dict | None:
    unit = get_unit(unit_id)
    lessons = unit.get("lessons") or []
    if 1 <= lesson_n <= len(lessons):
        return lessons[lesson_n - 1]
    return None
