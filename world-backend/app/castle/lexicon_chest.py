"""Сундук слов в Сокровищнице: каждые 25 выученных слов — монеты и украшение.

Сундук засчитывается по счётчику Словесника (те же таблицы, один источник правды).
Выдача идемпотентна: сундук номера N открывается ровно один раз, повторный вызов
возвращает уже выданное. Украшение выбирается детерминированно по игроку и номеру
сундука, чтобы ответ сервера не зависел от случайности при повторах.
"""
from __future__ import annotations

import hashlib

from app.world import core
from app.world.core import Conflict
from app.world.db import get_conn

from . import catalog, counters

PER_CHEST = 25
COINS_CHEST = 30
COINS_IF_ALL_OWNED = 60


def status(player_id: int) -> dict:
    words = counters.learned_words(player_id)
    opened = int(
        get_conn()
        .execute("SELECT COUNT(*) AS n FROM lexicon_chests WHERE player_id=?", (player_id,))
        .fetchone()["n"]
    )
    earned = words // PER_CHEST
    return {
        "words": words,
        "per_chest": PER_CHEST,
        "opened": opened,
        "ready": max(0, earned - opened),
        "progress": words % PER_CHEST,
    }


def _pick_item(player_id: int, chest_index: int) -> str | None:
    """Некупленное украшение, выбранное детерминированно; None, если всё уже есть."""
    owned = {
        row["item_id"]
        for row in get_conn().execute(
            "SELECT item_id FROM castle_owned WHERE player_id=?", (player_id,)
        ).fetchall()
    }
    candidates = sorted(
        item.id for item in catalog.ITEMS.values() if item.kind == "decor" and item.id not in owned
    )
    if not candidates:
        return None
    digest = hashlib.sha256(f"lexicon-chest:{player_id}:{chest_index}".encode()).hexdigest()
    return candidates[int(digest, 16) % len(candidates)]


def open(external_key: str) -> dict:
    """Открывает следующий готовый сундук. Повтор без готового сундука — 409."""
    player = core.get_player(external_key)
    player_id = int(player["id"])
    current = status(player_id)
    conn = get_conn()
    if current["ready"] <= 0:
        # Идемпотентность двойного нажатия: если сундук только что открыт и новых слов
        # не прибавилось — возвращаем последний выданный, а не ошибку.
        row = conn.execute(
            "SELECT chest_index, coins, item_id FROM lexicon_chests WHERE player_id=?"
            " ORDER BY chest_index DESC LIMIT 1",
            (player_id,),
        ).fetchone()
        if row is None:
            raise Conflict("chest_not_ready")
        return {"chest_index": int(row["chest_index"]), "coins": int(row["coins"]), "item_id": row["item_id"]}

    chest_index = current["opened"]
    existing = conn.execute(
        "SELECT coins, item_id FROM lexicon_chests WHERE player_id=? AND chest_index=?",
        (player_id, chest_index),
    ).fetchone()
    if existing is not None:
        return {"chest_index": chest_index, "coins": int(existing["coins"]), "item_id": existing["item_id"]}

    item_id = _pick_item(player_id, chest_index)
    coins = COINS_CHEST if item_id is not None else COINS_IF_ALL_OWNED
    core.award(
        external_key,
        coins=coins,
        source=f"lexicon-chest:{chest_index}",
        type_="LEXICON_CHEST",
        idempotency_key=f"lexicon-chest:{player_id}:{chest_index}",
    )
    conn.execute(
        "INSERT INTO lexicon_chests (player_id, chest_index, coins, item_id) VALUES (?,?,?,?)",
        (player_id, chest_index, coins, item_id),
    )
    if item_id is not None:
        anchor = catalog.ITEMS[item_id].anchor
        conn.execute(
            "INSERT OR IGNORE INTO castle_owned (player_id, item_id, anchor, source) VALUES (?,?,?,?)",
            (player_id, item_id, anchor, "lexicon-chest"),
        )
    return {"chest_index": chest_index, "coins": coins, "item_id": item_id}
