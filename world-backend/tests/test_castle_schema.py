"""Таблицы мета-игры замка создаются вместе с остальной схемой."""
from __future__ import annotations

import pytest

from app.world.db import get_conn


@pytest.mark.parametrize("table", ["castle_appearance", "castle_owned", "titles", "league_weeks"])
def test_castle_tables_exist(learn_db, table):
    rows = get_conn().execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchall()
    assert len(rows) == 1


def test_owned_item_is_unique_per_player(learn_db):
    conn = get_conn()
    conn.execute("INSERT INTO players (external_key, display_name) VALUES ('kid-1','Маша')")
    pid = conn.execute("SELECT id FROM players WHERE external_key='kid-1'").fetchone()["id"]
    conn.execute("INSERT INTO castle_owned (player_id, item_id, source) VALUES (?,?,?)", (pid, "weather-snow", "shop"))
    conn.execute(
        "INSERT OR IGNORE INTO castle_owned (player_id, item_id, source) VALUES (?,?,?)", (pid, "weather-snow", "shop")
    )
    count = conn.execute("SELECT COUNT(*) AS c FROM castle_owned WHERE player_id=?", (pid,)).fetchone()["c"]
    assert count == 1
