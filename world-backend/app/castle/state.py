"""Что выбрано и что куплено у конкретного игрока."""
from __future__ import annotations

from app.world.core import Conflict
from app.world.db import get_conn

from .catalog import BANNER_COLORS, SEASONS, TIMES, WEATHERS

_ALLOWED = {
    "season": SEASONS,
    "time_of_day": TIMES,
    "weather": WEATHERS,
    "banner_color": BANNER_COLORS,
}


def appearance(player_id: int) -> dict:
    row = get_conn().execute(
        "SELECT season, time_of_day, weather, banner_color, banner_emblem"
        " FROM castle_appearance WHERE player_id=?",
        (player_id,),
    ).fetchone()
    if row is None:
        return {"season": None, "time_of_day": None, "weather": None,
                "banner_color": "plum", "banner_emblem": "fox"}
    return {
        "season": row["season"],
        "time_of_day": row["time_of_day"],
        "weather": row["weather"],
        "banner_color": row["banner_color"],
        "banner_emblem": row["banner_emblem"],
    }


def set_appearance(player_id: int, **fields) -> dict:
    """Сохраняет выбор. None у сезона, времени и погоды означает «бесплатный вариант»."""
    current = appearance(player_id)
    for name, value in fields.items():
        if name not in current:
            raise Conflict(f"unknown field {name!r}")
        if value is not None and name in _ALLOWED and value not in _ALLOWED[name]:
            raise Conflict(f"bad value for {name}")
        current[name] = value
    get_conn().execute(
        "INSERT INTO castle_appearance (player_id, season, time_of_day, weather, banner_color, banner_emblem)"
        " VALUES (?,?,?,?,?,?)"
        " ON CONFLICT(player_id) DO UPDATE SET season=excluded.season, time_of_day=excluded.time_of_day,"
        " weather=excluded.weather, banner_color=excluded.banner_color, banner_emblem=excluded.banner_emblem,"
        " updated_at=datetime('now')",
        (player_id, current["season"], current["time_of_day"], current["weather"],
         current["banner_color"], current["banner_emblem"]),
    )
    return current


def owned(player_id: int) -> list[str]:
    rows = get_conn().execute(
        "SELECT item_id FROM castle_owned WHERE player_id=? ORDER BY acquired_at", (player_id,)
    ).fetchall()
    return [row["item_id"] for row in rows]
