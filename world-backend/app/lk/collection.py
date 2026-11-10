"""Pure collection rules; persistence is intentionally handled by the LK service."""
from __future__ import annotations

from typing import Mapping

STARTER_CARDS = (
    {"id": "first-step", "title": "Первый шаг", "rarity": "common", "condition": "lessons>=1"},
    {"id": "word-scout-25", "title": "Словоискатель", "rarity": "rare", "condition": "learned_words>=25"},
    {"id": "perfect-lesson", "title": "Без ошибок", "rarity": "rare", "condition": "perfect_lessons>=1"},
    {"id": "week-streak", "title": "Неделя практики", "rarity": "epic", "condition": "streak_days>=7"},
)


def unlocked_cards(metrics: Mapping[str, int]) -> list[str]:
    """Return stable card ids unlocked by the current learner metrics."""
    checks = {
        "first-step": metrics.get("lessons", 0) >= 1,
        "word-scout-25": metrics.get("learned_words", 0) >= 25,
        "perfect-lesson": metrics.get("perfect_lessons", 0) >= 1,
        "week-streak": metrics.get("streak_days", 0) >= 7,
    }
    return [card["id"] for card in STARTER_CARDS if checks[card["id"]]]


def card_catalog() -> list[dict]:
    return [dict(card) for card in STARTER_CARDS]
