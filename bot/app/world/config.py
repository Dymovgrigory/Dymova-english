"""Централизованная конфигурация экономики (бриф §83).

Все числа экономики — только здесь, не хардкодить по коду.
"""

XP_REWARDS = {
    "lesson_complete": 40,
    "quest_complete": 60,
    "vocabulary_challenge": 25,
    "daily_login": 10,
}
COIN_REWARDS = {
    "lesson_complete": 15,
    "quest_complete": 30,
    "vocabulary_challenge": 10,
}
QUEST_REWARDS = {
    "first-day-at-foxinburg": {
        "xp": 60,
        "coins": 30,
        "items": ["fox-badge-first"],
        "unlocks": ["library-courtyard"],
    },
}
LEVEL_THRESHOLDS = [0, 100, 250, 500, 900, 1400, 2000, 2800, 3800, 5000]
LEVEL_TITLES = [
    "Explorer", "Pathfinder", "Linguist", "Adventurer", "Master",
    "World Speaker", "Sage", "Architect", "Legend", "Fox Friend",
]
ITEM_PRICES: dict[str, int] = {}
STREAK_BONUSES = {7: 20, 14: 40, 30: 100, 60: 200, 100: 400, 365: 2000}

# Активности (§68): data-driven описание, связь с шагом квеста.
ACTIVITIES = {
    "vocabulary-challenge-1": {
        "kind": "vocabulary",
        "title_ru": "Первый английский челлендж",
        "theme": "zhivotnye",
        "questions": 5,
        "quest_id": "first-day-at-foxinburg",
    },
}
# Бонус за безошибочное прохождение активности.
PERFECT_BONUS = {"xp": 10, "coins": 5}
