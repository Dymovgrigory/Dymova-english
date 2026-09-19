"""Что выбрано и что куплено у конкретного игрока."""
from __future__ import annotations

import json

from app.world.core import Conflict
from app.world.db import get_conn

from .catalog import BANNER_COLORS, ITEMS, SCENES, SEASONS, TIMES, WEATHERS
from .slots import default_slot

_ALLOWED = {
    "season": SEASONS,
    "time_of_day": TIMES,
    "weather": WEATHERS,
    "banner_color": BANNER_COLORS,
    "scene_set": SCENES,
}


def appearance(player_id: int) -> dict:
    row = get_conn().execute(
        "SELECT season, time_of_day, weather, banner_color, banner_emblem, scene_set"
        " FROM castle_appearance WHERE player_id=?",
        (player_id,),
    ).fetchone()
    if row is None:
        return {"season": None, "time_of_day": None, "weather": None,
                "banner_color": "plum", "banner_emblem": "fox", "scene_set": None}
    return {
        "season": row["season"],
        "time_of_day": row["time_of_day"],
        "weather": row["weather"],
        "banner_color": row["banner_color"],
        "banner_emblem": row["banner_emblem"],
        "scene_set": row["scene_set"],
    }


def set_appearance(player_id: int, **fields) -> dict:
    """Сохраняет выбор. None у сезона, времени, погоды и набора означает «бесплатный вариант»."""
    current = appearance(player_id)
    for name, value in fields.items():
        if name not in current:
            raise Conflict(f"unknown field {name!r}")
        if value is not None and name in _ALLOWED and value not in _ALLOWED[name]:
            raise Conflict(f"bad value for {name}")
        current[name] = value
    get_conn().execute(
        "INSERT INTO castle_appearance (player_id, season, time_of_day, weather, banner_color, banner_emblem, scene_set)"
        " VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(player_id) DO UPDATE SET season=excluded.season, time_of_day=excluded.time_of_day,"
        " weather=excluded.weather, banner_color=excluded.banner_color, banner_emblem=excluded.banner_emblem,"
        " scene_set=excluded.scene_set, updated_at=datetime('now')",
        (player_id, current["season"], current["time_of_day"], current["weather"],
         current["banner_color"], current["banner_emblem"], current["scene_set"]),
    )
    return current


def owned(player_id: int) -> list[str]:
    rows = get_conn().execute(
        "SELECT item_id FROM castle_owned WHERE player_id=? ORDER BY acquired_at", (player_id,)
    ).fetchall()
    return [row["item_id"] for row in rows]


def decor_off(player_id: int) -> list[str]:
    """Снятые украшения (куплены, но не стоят на сцене)."""
    row = get_conn().execute(
        "SELECT decor_off FROM castle_appearance WHERE player_id=?", (player_id,)
    ).fetchone()
    if row is None:
        return []
    return list(json.loads(row["decor_off"] or "[]"))


def set_decor_off(player_id: int, off: list[str]) -> None:
    get_conn().execute(
        "INSERT INTO castle_appearance (player_id, decor_off) VALUES (?,?)"
        " ON CONFLICT(player_id) DO UPDATE SET decor_off=excluded.decor_off, updated_at=datetime('now')",
        (player_id, json.dumps(sorted(off))),
    )


def decor_slots(player_id: int) -> dict[str, str]:
    """Явно выбранные слоты украшений: {item_id: slot_id}."""
    row = get_conn().execute(
        "SELECT decor_slots FROM castle_appearance WHERE player_id=?", (player_id,)
    ).fetchone()
    if row is None:
        return {}
    return dict(json.loads(row["decor_slots"] or "{}"))


def set_decor_slots(player_id: int, slots: dict[str, str]) -> None:
    get_conn().execute(
        "INSERT INTO castle_appearance (player_id, decor_slots) VALUES (?,?)"
        " ON CONFLICT(player_id) DO UPDATE SET decor_slots=excluded.decor_slots, updated_at=datetime('now')",
        (player_id, json.dumps(slots, sort_keys=True)),
    )


def decor(player_id: int) -> list[dict]:
    """Купленные украшения с точкой, признаком «стоит на сцене» и текущим слотом."""
    off = set(decor_off(player_id))
    slots = decor_slots(player_id)
    rows = get_conn().execute(
        "SELECT item_id, anchor FROM castle_owned WHERE player_id=? ORDER BY acquired_at", (player_id,)
    ).fetchall()
    placed = []
    for row in rows:
        item = ITEMS.get(row["item_id"])
        if item is None or item.kind != "decor":
            continue
        active = item.id not in off
        placed.append({
            "item_id": item.id,
            "anchor": row["anchor"] or item.anchor,
            "title_ru": item.title_ru,
            "active": active,
            "slot": (slots.get(item.id) or default_slot(item)) if active else None,
        })
    return placed
