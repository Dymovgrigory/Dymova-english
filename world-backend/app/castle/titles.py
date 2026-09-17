"""Звания игрока: пересчёт уровней веток, выдача монет и носимое звание."""
from __future__ import annotations

from app.world import core
from app.world.db import get_conn

from . import counters, tracks


def _levels(player_id: int) -> dict[str, int]:
    rows = get_conn().execute("SELECT track, level FROM titles WHERE player_id=?", (player_id,)).fetchall()
    return {row["track"]: int(row["level"]) for row in rows}


def sync(external_key: str) -> list[dict]:
    """Догоняет уровни веток до текущих значений. Возвращает только новые уровни.

    Монеты за каждый уровень выдаются через core.award с ключом уровня — повторный
    вызов после сбоя сети не начислит дважды.
    """
    player = core.get_player(external_key)
    player_id = int(player["id"])
    values = counters.counters(player_id)
    known = _levels(player_id)
    conn = get_conn()
    gained: list[dict] = []

    for track_id, track in tracks.TRACKS.items():
        old = known.get(track_id, 0)
        new = tracks.level_for(track_id, values[track_id])
        if new <= old:
            continue
        coins = sum(tracks.level_reward(level) for level in range(old + 1, new + 1))
        core.award(
            external_key, coins=coins, source=f"title:{track_id}:{new}", type_="TITLE_REWARD",
            idempotency_key=f"title:{player_id}:{track_id}:{new}",
        )
        conn.execute(
            "INSERT INTO titles (player_id, track, level) VALUES (?,?,?)"
            " ON CONFLICT(player_id, track) DO UPDATE SET level=excluded.level,"
            " awarded_at=datetime('now')",
            (player_id, track_id, new),
        )
        gained.append({
            "track": track_id,
            "level": new,
            "title_ru": track.level_titles[new - 1],
            "coins": coins,
        })
    return gained


def state(player_id: int) -> list[dict]:
    """Прогресс всех веток: уровень, значение, следующая цель, носимое звание."""
    values = counters.counters(player_id)
    levels = _levels(player_id)
    worn = get_conn().execute(
        "SELECT track FROM titles WHERE player_id=? AND worn=1", (player_id,)
    ).fetchone()
    worn_track = worn["track"] if worn else None
    rows = []
    for track_id in tracks.TRACKS:
        view = tracks.track_view(track_id, values[track_id])
        view["level"] = levels.get(track_id, view["level"])
        view["title_ru"] = (
            tracks.TRACKS[track_id].level_titles[view["level"] - 1] if view["level"] else None
        )
        view["worn"] = track_id == worn_track
        rows.append(view)
    return rows


def wear(player_id: int, track_id: str) -> list[dict]:
    """Надеть звание ветки. Носится ровно одно."""
    if track_id not in tracks.TRACKS:
        raise core.NotFound(f"track {track_id!r} not found")
    if _levels(player_id).get(track_id, 0) < 1:
        raise core.Conflict("title_not_earned")
    conn = get_conn()
    conn.execute("UPDATE titles SET worn=0 WHERE player_id=?", (player_id,))
    conn.execute("UPDATE titles SET worn=1 WHERE player_id=? AND track=?", (player_id, track_id))
    return state(player_id)
