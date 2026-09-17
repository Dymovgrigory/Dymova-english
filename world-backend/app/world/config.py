"""Централизованная конфигурация экономики (бриф §83).

Все числа экономики — только здесь, не хардкодить по коду.
"""
import os

XP_REWARDS = {
    "lesson_complete": 40,
    "lesson_perfect": 10,
    "practice_complete": 10,
    "daily_quest": 15,
    "quest_complete": 60,
    "vocabulary_challenge": 25,
    "daily_login": 10,
}
COIN_REWARDS = {
    "lesson_complete": 15,
    "lesson_perfect": 5,
    "practice_complete": 5,
    "quest_complete": 30,
    "vocabulary_challenge": 10,
}
# Повторять должно быть выгодно, но фарм монет в «Дворе тренировки» — нет.
PRACTICE_COINS_DAILY_CAP = 15
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
LEVEL_TITLES_RU = [
    "Следопыт", "Искатель", "Словечко", "Искатель приключений", "Мастер",
    "Голос мира", "Мудрец", "Зодчий", "Легенда", "Друг Фокси",
]
STICKERS = {
    "sticker-family": {"title_ru": "Семья", "emoji": "👨‍👩‍👧", "unit": "family"},
    "sticker-school": {"title_ru": "Школа", "emoji": "🎒", "unit": "school"},
    "sticker-room": {"title_ru": "Комната", "emoji": "🛏️", "unit": "room"},
    "sticker-pets": {"title_ru": "Питомцы", "emoji": "🐾", "unit": "pets"},
    "sticker-food": {"title_ru": "Еда", "emoji": "🍎", "unit": "food"},
    "sticker-play": {"title_ru": "Игра", "emoji": "🎮", "unit": "play"},
    "sticker-satp": {"title_ru": "Звуки SATP", "emoji": "🔤", "unit": "satp"},
    "sticker-hello": {"title_ru": "Первый урок", "emoji": "👋", "unit": None},
    "sticker-perfect": {"title_ru": "Без ошибок", "emoji": "⭐", "unit": None},
    "sticker-streak": {"title_ru": "Серия дней", "emoji": "🔥", "unit": None},
    "sticker-rainbow": {"title_ru": "Радуга Фокси", "emoji": "🌈", "unit": None},
}
ITEM_PRICES: dict[str, int] = {
    "hearts_refill": 350,
    "streak_freeze": 200,
}
STREAK_BONUSES = {7: 20, 14: 40, 30: 100, 60: 200, 100: 400, 365: 2000}
HEARTS_MAX = 5
# Экзамен юнита: сколько заданий и сколько звёзд открывает следующий юнит.
# Одна звезда = экзамен сдан; требовать три (безошибочно) для семилетки жестоко.
CHECKPOINT_ITEMS = 12
CHECKPOINT_STARS_TO_UNLOCK = 1
# Сколько заданий собираем во «Дворе тренировки».
PRACTICE_ITEMS = 12
PRACTICE_ITEMS_MIN = 6
HEART_REGEN_SEC = 4 * 60 * 60
DAILY_XP_GOAL = 50
# Prod default: linear locks. Local/dev can set WORLD_UNLOCK_ALL=1.
UNLOCK_ALL = os.environ.get("WORLD_UNLOCK_ALL", "0").strip().lower() not in {"0", "false", "no"}
SHOP = {
    "hearts_refill": {"coins": 350, "title_ru": "Полные сердца"},
    "streak_freeze": {"coins": 200, "title_ru": "Заморозка серии"},
    "sticker_rainbow": {"coins": 80, "title_ru": "Стикер «Радуга»", "item": "sticker-rainbow"},
    "foxi_cape": {"coins": 120, "title_ru": "Плащ Фокси", "item": "foxi-cape"},
    "castle_banner": {"coins": 90, "title_ru": "Знамя замка", "item": "castle-banner"},
}

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
