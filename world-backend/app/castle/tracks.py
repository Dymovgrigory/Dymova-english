"""Ветки званий: каждое здание замка растит свою.

Пороги и названия держим кодом, а не в базе: баланс правится часто, и миграция
на каждое изменение порога не нужна. Уровень 0 — звания ещё нет.
"""
from __future__ import annotations

from dataclasses import dataclass

LEVEL_REWARDS = (25, 50, 100, 200, 400)


@dataclass(frozen=True)
class Track:
    id: str
    title_ru: str
    building: str          # id здания на карте замка
    unit_ru: str           # что считаем, для подписи прогресса
    thresholds: tuple[int, int, int, int, int]
    level_titles: tuple[str, str, str, str, str]


TRACKS: dict[str, Track] = {
    "lexicon": Track(
        id="lexicon", title_ru="Словесник", building="lexicon", unit_ru="слов выучено",
        thresholds=(10, 50, 150, 300, 600),
        level_titles=("Собиратель слов", "Знаток слов", "Хранитель словаря", "Мастер слова", "Магистр словаря"),
    ),
    "yard": Track(
        id="yard", title_ru="Тренер", building="yard", unit_ru="тренировок",
        thresholds=(5, 20, 60, 150, 300),
        level_titles=("Новичок двора", "Боец двора", "Ветеран двора", "Мастер двора", "Легенда двора"),
    ),
    "nest": Track(
        id="nest", title_ru="Хранитель огня", building="nest", unit_ru="дней подряд",
        thresholds=(3, 7, 21, 60, 150),
        level_titles=("Искра", "Огонёк", "Костёр", "Маяк", "Вечное пламя"),
    ),
    "glory": Track(
        id="glory", title_ru="Чемпион", building="glory", unit_ru="недель в тройке",
        thresholds=(1, 3, 8, 20, 40),
        level_titles=("Призёр", "Финалист", "Чемпион недели", "Чемпион замка", "Легенда лиги"),
    ),
    "stickers": Track(
        id="stickers", title_ru="Собиратель", building="stickers", unit_ru="наклеек",
        thresholds=(3, 8, 14, 20, 22),
        level_titles=("Любитель наклеек", "Коллекционер", "Знаток альбома", "Хранитель альбома", "Полный альбом"),
    ),
}


def level_for(track_id: str, value: int) -> int:
    """Уровень 0..5 по достигнутому значению."""
    thresholds = TRACKS[track_id].thresholds
    return sum(1 for threshold in thresholds if value >= threshold)


def level_reward(level: int) -> int:
    """Монеты за взятый уровень."""
    return LEVEL_REWARDS[level - 1] if 1 <= level <= len(LEVEL_REWARDS) else 0


def track_view(track_id: str, value: int) -> dict:
    """Строка прогресса ветки для интерфейса."""
    track = TRACKS[track_id]
    level = level_for(track_id, value)
    return {
        "track": track.id,
        "track_title_ru": track.title_ru,
        "building": track.building,
        "unit_ru": track.unit_ru,
        "level": level,
        "title_ru": track.level_titles[level - 1] if level else None,
        "value": value,
        "next_threshold": track.thresholds[level] if level < len(track.thresholds) else None,
    }
