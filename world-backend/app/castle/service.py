"""Витрина, покупка и применение облика замка.

Все проверки — на сервере: цена, условие по званию и владение вещью. Клиент только
показывает то, что вернул этот модуль.
"""
from __future__ import annotations

from app.world import core
from app.world.core import Conflict, NotFound
from app.world.db import get_conn

from . import catalog, state, titles

_FIELD_KIND = {"season": "season", "time_of_day": "time", "weather": "weather", "banner_color": "banner"}


def _levels(player_id: int) -> dict[str, int]:
    """Уровни веток игрока: {track: level}."""
    return {row["track"]: int(row["level"]) for row in titles.state(player_id)}


def _unlocked(item: catalog.Item, levels: dict[str, int]) -> bool:
    if item.requires_track is None:
        return True
    return levels.get(item.requires_track, 0) >= item.requires_level


def view(external_key: str) -> dict:
    player = core.get_player(external_key)
    player_id = int(player["id"])
    track_rows = titles.state(player_id)
    levels = {row["track"]: int(row["level"]) for row in track_rows}
    owned = state.owned(player_id)
    items = []
    for item in catalog.ITEMS.values():
        items.append({
            "id": item.id,
            "kind": item.kind,
            "title_ru": item.title_ru,
            "value": item.value,
            "price": item.price,
            "purchasable": item.purchasable,
            "owned": item.id in owned,
            "unlocked": _unlocked(item, levels),
            "requires_track": item.requires_track,
            "requires_level": item.requires_level,
            "anchor": item.anchor,
        })
    return {
        "appearance": state.appearance(player_id),
        "catalog": items,
        "owned": owned,
        "decor": state.decor(player_id),
        "titles": track_rows,
        "coins": int(player["coins"]),
    }


def buy(external_key: str, item_id: str) -> dict:
    item = catalog.ITEMS.get(item_id)
    if item is None:
        raise NotFound(f"item {item_id!r} not found")
    player = core.get_player(external_key)
    player_id = int(player["id"])
    if item_id in state.owned(player_id):
        return view(external_key)          # повторное нажатие не списывает второй раз
    if not item.purchasable:
        raise Conflict("item_not_for_sale")
    levels = _levels(player_id)
    if not _unlocked(item, levels):
        raise Conflict("title_required")

    core.spend(
        external_key, coins=item.price, source=item_id, type_="CASTLE_BUY",
        idempotency_key=f"castle:{player_id}:{item_id}",
    )
    get_conn().execute(
        "INSERT OR IGNORE INTO castle_owned (player_id, item_id, anchor, source) VALUES (?,?,?,?)",
        (player_id, item_id, item.anchor, "shop"),
    )
    return view(external_key)


def apply(external_key: str, **fields) -> dict:
    """Применяет выбранное. Платный вариант должен быть куплен, бесплатный доступен всегда."""
    player = core.get_player(external_key)
    player_id = int(player["id"])
    owned = set(state.owned(player_id))
    levels = _levels(player_id)

    decor_off_ids = set(fields.pop("decor_off", None) or [])
    decor_on_ids = set(fields.pop("decor_on", None) or [])
    for item_id in decor_off_ids | decor_on_ids:
        item = catalog.ITEMS.get(item_id)
        if item is None or item.kind != "decor":
            raise Conflict(f"unknown decor {item_id!r}")
        if item_id not in owned:
            raise Conflict("item_not_owned")
    if decor_off_ids or decor_on_ids:
        off = (set(state.decor_off(player_id)) | decor_off_ids) - decor_on_ids
        state.set_decor_off(player_id, sorted(off))

    for field, value in fields.items():
        kind = _FIELD_KIND.get(field)
        if kind is None or value is None or value == catalog.FREE_VALUES.get(kind):
            continue
        item = next((i for i in catalog.ITEMS.values() if i.kind == kind and i.value == value), None)
        if item is None:
            raise Conflict(f"unknown value for {field}")
        earned = not item.purchasable and _unlocked(item, levels)
        if item.id not in owned and not earned:
            raise Conflict("item_not_owned")

    state.set_appearance(player_id, **fields)
    return view(external_key)
