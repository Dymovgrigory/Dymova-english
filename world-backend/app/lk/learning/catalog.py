"""Versioned LMS learning catalog, independent from the World content graph."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Level = Literal["pre-a1", "a1", "a2", "b1"]


@dataclass(frozen=True)
class LearningUnit:
    id: str
    level: Level
    topic: str
    title_ru: str
    title_en: str
    skills: tuple[str, ...]
    order: int


_CATALOG = (
    LearningUnit("pre-a1.family", "pre-a1", "family", "Моя семья", "My family", ("vocabulary", "grammar", "listening", "reading", "writing", "speaking"), 10),
    LearningUnit("pre-a1.school", "pre-a1", "school", "В школе", "At school", ("vocabulary", "grammar", "listening", "reading", "writing", "speaking"), 20),
    LearningUnit("a1.family", "a1", "family", "Семья и друзья", "Family and friends", ("vocabulary", "grammar", "reading", "listening", "writing", "speaking"), 30),
    LearningUnit("a1.home", "a1", "home", "Мой дом", "My home", ("vocabulary", "grammar", "reading", "listening", "writing", "speaking"), 40),
    LearningUnit("a2.travel", "a2", "travel", "Путешествия", "Travel", ("vocabulary", "grammar", "reading", "listening", "writing", "speaking"), 50),
    LearningUnit("a2.health", "a2", "health", "Здоровье", "Health", ("vocabulary", "grammar", "reading", "listening", "writing", "speaking"), 60),
    LearningUnit("b1.adventures", "b1", "adventures", "Приключения", "Adventures", ("vocabulary", "grammar", "reading", "listening", "writing", "speaking"), 70),
)


def catalog() -> tuple[LearningUnit, ...]:
    return _CATALOG


def available_units(*, level: str | None = None, topic: str | None = None) -> tuple[LearningUnit, ...]:
    return tuple(item for item in _CATALOG if (level is None or item.level == level) and (topic is None or item.topic == topic))


def unit(unit_id: str) -> LearningUnit:
    for item in _CATALOG:
        if item.id == unit_id:
            return item
    raise KeyError(unit_id)
