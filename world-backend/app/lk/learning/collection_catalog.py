"""LMS collection catalog: 10 collections, 10 cards each."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CollectionCard:
    id: str
    collection_id: str
    collection_title_ru: str
    title_ru: str
    title_en: str
    rarity: str
    unlock_kind: str
    unlock_value: int
    asset: str


_COLLECTIONS = (
    ("first-steps", "Первые шаги", "First steps", "words", "common"),
    ("school-life", "Школьная жизнь", "School life", "unit", "common"),
    ("family-friends", "Семья и друзья", "Family & friends", "unit", "rare"),
    ("animal-kingdom", "Царство животных", "Animal kingdom", "unit", "rare"),
    ("story-makers", "Создатели историй", "Story makers", "reading", "epic"),
    ("grammar-guild", "Гильдия грамматики", "Grammar guild", "grammar", "epic"),
    ("sound-hunters", "Охотники за звуками", "Sound hunters", "listening", "rare"),
    ("word-crafters", "Мастера слов", "Word crafters", "writing", "epic"),
    ("brave-speakers", "Смелые ораторы", "Brave speakers", "speaking", "legendary"),
    ("foxinburg-legends", "Легенды Фоксинбурга", "Foxinburg legends", "points", "legendary"),
)


def _build() -> tuple[CollectionCard, ...]:
    cards: list[CollectionCard] = []
    for collection_id, title_ru, title_en, unlock_kind, rarity in _COLLECTIONS:
        for number in range(1, 11):
            card_id = f"{collection_id}-{number:02d}"
            cards.append(CollectionCard(
                id=card_id,
                collection_id=collection_id,
                collection_title_ru=title_ru,
                title_ru=f"{title_ru} · карта {number}",
                title_en=f"{title_en} · card {number}",
                rarity=rarity,
                unlock_kind=unlock_kind,
                unlock_value=number,
                asset=f"/collection/{collection_id}/{card_id}.webp",
            ))
    return tuple(cards)


CARDS = _build()


def catalog() -> list[dict]:
    return [asdict(card) for card in CARDS]


def unlocked(*, words: int = 0, units: int = 0, reading: int = 0, grammar: int = 0,
             listening: int = 0, writing: int = 0, speaking: int = 0, points: int = 0) -> list[str]:
    metrics = {"words": words, "unit": units, "reading": reading, "grammar": grammar,
               "listening": listening, "writing": writing, "speaking": speaking, "points": points}
    return [card.id for card in CARDS if metrics[card.unlock_kind] >= card.unlock_value]
