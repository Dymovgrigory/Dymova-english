"""Витрина облика замка. Цены и условия — из спеки, держим кодом ради быстрых правок баланса."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

SEASONS = ("spring", "summer", "autumn", "winter")
TIMES = ("dawn", "day", "dusk", "night")
WEATHERS = ("snow", "rain", "fireflies", "fog", "aurora", "petals")
BANNER_COLORS = ("plum", "emerald", "gold", "azure", "rose")


@dataclass(frozen=True)
class Item:
    id: str
    kind: str              # season|time|weather|banner|decor
    title_ru: str
    price: int
    value: str             # что применяется: имя сезона, времени, погоды, цвета
    requires_track: str | None = None
    requires_level: int = 0
    purchasable: bool = True


def _items() -> dict[str, Item]:
    items: dict[str, Item] = {}
    seasons_ru = {"spring": "Весна", "summer": "Лето", "autumn": "Осень", "winter": "Зима"}
    for season, title in seasons_ru.items():
        items[f"season-{season}"] = Item(
            id=f"season-{season}", kind="season", title_ru=title, price=150, value=season,
            requires_track="lexicon", requires_level=2,
        )
    times_ru = {"dawn": "Рассвет", "day": "День", "dusk": "Закат", "night": "Ночь"}
    for time_of_day, title in times_ru.items():
        items[f"time-{time_of_day}"] = Item(
            id=f"time-{time_of_day}", kind="time", title_ru=title, price=80, value=time_of_day,
        )
    weather_specs = {
        "snow": ("Снегопад", 90, None, 0, True),
        "rain": ("Дождь", 60, None, 0, True),
        "fireflies": ("Светлячки", 120, "yard", 2, True),
        "fog": ("Туман", 60, None, 0, True),
        "petals": ("Лепестки", 90, "stickers", 2, True),
        "aurora": ("Северное сияние", 0, "nest", 5, False),  # только за звание
    }
    for weather, (title, price, track, level, purchasable) in weather_specs.items():
        items[f"weather-{weather}"] = Item(
            id=f"weather-{weather}", kind="weather", title_ru=title, price=price, value=weather,
            requires_track=track, requires_level=level, purchasable=purchasable,
        )
    colors_ru = {"emerald": "Изумрудное", "gold": "Золотое", "azure": "Лазурное", "rose": "Розовое"}
    for color, title in colors_ru.items():
        items[f"banner-{color}"] = Item(
            id=f"banner-{color}", kind="banner", title_ru=f"{title} знамя", price=50, value=color,
        )
    return items


ITEMS: dict[str, Item] = _items()

# Бесплатно и всегда доступно: сезон по календарю, время «как за окном», сливовое знамя.
FREE_VALUES = {"season": None, "time": None, "weather": None, "banner": "plum"}


def season_by_date(moment: datetime) -> str:
    month = moment.month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"
