"""Доменное ядро World: игроки, экономика, прогрессия, квесты, инвентарь.

Все операции наград — транзакционно и идемпотентно (§84, §160):
одна запись в ledger с уникальным idempotency_key + атомарное обновление
баланса игрока. Клиент никогда не присылает суммы — только действие.
"""
from __future__ import annotations

import json
import sqlite3
import uuid

from . import config
from .db import get_conn


class WorldError(Exception):
    pass


class NotFound(WorldError):
    pass


class Conflict(WorldError):
    pass


def _row_to_player(row: sqlite3.Row) -> dict:
    thresholds = config.LEVEL_THRESHOLDS
    lvl = row["level"]
    cur = thresholds[lvl - 1]
    nxt = thresholds[lvl] if lvl < len(thresholds) else None
    return {
        "id": row["id"],
        "external_key": row["external_key"],
        "display_name": row["display_name"],
        "role": row["role"],
        "xp": row["xp"],
        "coins": row["coins"],
        "level": lvl,
        "level_title": config.LEVEL_TITLES[lvl - 1],
        "xp_into_level": row["xp"] - cur,
        "xp_to_next": (nxt - row["xp"]) if nxt else None,
        "streak_days": row["streak_days"],
    }


def get_or_create_player(external_key: str, display_name: str = "Explorer",
                         role: str = "child") -> dict:
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO players (external_key, display_name, role) VALUES (?,?,?)",
        (external_key, display_name, role),
    )
    row = conn.execute("SELECT * FROM players WHERE external_key=?", (external_key,)).fetchone()
    return _row_to_player(row)


def get_player(external_key: str) -> dict:
    row = get_conn().execute(
        "SELECT * FROM players WHERE external_key=?", (external_key,)
    ).fetchone()
    if row is None:
        raise NotFound(f"player {external_key!r} not found")
    return _row_to_player(row)


def _level_for_xp(xp: int) -> int:
    lvl = 1
    for i, threshold in enumerate(config.LEVEL_THRESHOLDS):
        if xp >= threshold:
            lvl = i + 1
    return lvl


def _ledger(conn: sqlite3.Connection, table: str, player_id: int, type_: str,
            amount: int, source: str, idem: str, metadata: dict) -> bool:
    """Пишет в ledger идемпотентно. True = запись добавлена, False = дубликат."""
    try:
        conn.execute(
            f"INSERT INTO {table} (player_id, type, amount, source, idempotency_key, metadata)"
            " VALUES (?,?,?,?,?,?)",
            (player_id, type_, amount, source, idem, json.dumps(metadata, ensure_ascii=False)),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def award(external_key: str, *, xp: int = 0, coins: int = 0, source: str,
          type_: str, idempotency_key: str | None = None,
          items: list[str] | None = None, unlocks: list[str] | None = None) -> dict:
    """Единая точка выдачи наград. Возвращает дельту + новый снапшот игрока.

    Повторный вызов с тем же idempotency_key — no-op с тем же ответом (§160).
    """
    idem = idempotency_key or str(uuid.uuid4())
    conn = get_conn()
    player = get_player(external_key)
    pid = player["id"]
    old_level = player["level"]

    try:
        conn.execute("BEGIN IMMEDIATE")
        xp_added = coins_added = 0
        if xp:
            if _ledger(conn, "xp_transactions", pid, type_, xp, source, f"{idem}:xp", {}):
                conn.execute("UPDATE players SET xp=xp+?, updated_at=datetime('now') WHERE id=?", (xp, pid))
                xp_added = xp
        if coins:
            if _ledger(conn, "coin_transactions", pid, type_, coins, source, f"{idem}:coins", {}):
                conn.execute("UPDATE players SET coins=coins+?, updated_at=datetime('now') WHERE id=?", (coins, pid))
                coins_added = coins
        granted_items: list[str] = []
        for item_id in items or []:
            cur = conn.execute(
                "INSERT OR IGNORE INTO inventory (player_id, item_id, source) VALUES (?,?,?)",
                (pid, item_id, source),
            )
            if cur.rowcount:
                granted_items.append(item_id)
        granted_unlocks: list[str] = []
        for zone in unlocks or []:
            cur = conn.execute(
                "INSERT OR IGNORE INTO unlocks (player_id, zone_id) VALUES (?,?)", (pid, zone)
            )
            if cur.rowcount:
                granted_unlocks.append(zone)

        row = conn.execute("SELECT xp FROM players WHERE id=?", (pid,)).fetchone()
        new_level = _level_for_xp(row["xp"])
        level_up = new_level > old_level
        if level_up:
            conn.execute("UPDATE players SET level=? WHERE id=?", (new_level, pid))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    fresh = get_player(external_key)
    return {
        "idempotency_key": idem,
        "xp_delta": xp_added,
        "coins_delta": coins_added,
        "items_granted": granted_items,
        "unlocks_granted": granted_unlocks,
        "level_up": level_up,
        "new_level": fresh["level"],
        "new_title": fresh["level_title"],
        "player": fresh,
    }


# --- Quests (§19, §168 data-driven) ---

def seed_quests() -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO quests (id, kind, title_ru, config) VALUES (?,?,?,?)",
        (
            "first-day-at-foxinburg",
            "story",
            "Первый день в Фоксинбурге",
            json.dumps({
                "steps": [
                    {"action": "visit", "target": "school-hub", "label_ru": "Найди школу Фоксинбурга"},
                    {"action": "talk", "target": "foxi", "label_ru": "Поговори с Фокси"},
                    {"action": "activity", "target": "vocabulary-challenge-1",
                     "label_ru": "Пройди первый английский челлендж"},
                ],
                "rewards": config.QUEST_REWARDS["first-day-at-foxinburg"],
            }, ensure_ascii=False),
        ),
    )
    conn.execute(
        "INSERT OR IGNORE INTO items (id, category, rarity, title_ru, asset_id, unlock_condition)"
        " VALUES (?,?,?,?,?,?)",
        ("fox-badge-first", "badges", "rare", "Первая значка Фокси", None,
         "quest:first-day-at-foxinburg"),
    )


def get_quest(quest_id: str) -> dict:
    row = get_conn().execute("SELECT * FROM quests WHERE id=?", (quest_id,)).fetchone()
    if row is None:
        raise NotFound(f"quest {quest_id!r} not found")
    return {
        "id": row["id"],
        "kind": row["kind"],
        "title_ru": row["title_ru"],
        "config": json.loads(row["config"]),
    }


def list_quests(external_key: str) -> list[dict]:
    player = get_player(external_key)
    rows = get_conn().execute(
        "SELECT q.*, p.status, p.step FROM quests q"
        " LEFT JOIN quest_progress p ON p.quest_id=q.id AND p.player_id=?",
        (player["id"],),
    ).fetchall()
    return [
        {**get_quest(r["id"]), "status": r["status"] or "available", "step": r["step"] or 0}
        for r in rows
    ]


def start_quest(external_key: str, quest_id: str) -> dict:
    player = get_player(external_key)
    get_quest(quest_id)
    get_conn().execute(
        "INSERT OR IGNORE INTO quest_progress (player_id, quest_id) VALUES (?,?)",
        (player["id"], quest_id),
    )
    return {"quest_id": quest_id, "status": "active"}


def complete_quest(external_key: str, quest_id: str,
                   idempotency_key: str | None = None) -> dict:
    """Завершение квеста → награды из config.quests (server-authoritative)."""
    player = get_player(external_key)
    quest = get_quest(quest_id)
    conn = get_conn()
    row = conn.execute(
        "SELECT status FROM quest_progress WHERE player_id=? AND quest_id=?",
        (player["id"], quest_id),
    ).fetchone()
    if row is None:
        raise Conflict("quest not started")
    if row["status"] == "completed":
        raise Conflict("quest already completed")

    rewards = quest["config"].get("rewards", {})
    result = award(
        external_key,
        xp=rewards.get("xp", 0),
        coins=rewards.get("coins", 0),
        items=rewards.get("items"),
        unlocks=rewards.get("unlocks"),
        source=quest_id,
        type_="QUEST_REWARD",
        idempotency_key=idempotency_key or f"quest-complete:{player['id']}:{quest_id}",
    )
    conn.execute(
        "UPDATE quest_progress SET status='completed', completed_at=datetime('now')"
        " WHERE player_id=? AND quest_id=?",
        (player["id"], quest_id),
    )
    return {"quest_id": quest_id, "status": "completed", **result}


# --- Inventory / world state ---

def get_inventory(external_key: str) -> list[dict]:
    player = get_player(external_key)
    rows = get_conn().execute(
        "SELECT i.*, inv.source, inv.acquired_at FROM inventory inv"
        " JOIN items i ON i.id=inv.item_id WHERE inv.player_id=?"
        " ORDER BY inv.acquired_at DESC",
        (player["id"],),
    ).fetchall()
    return [
        {
            "id": r["id"], "category": r["category"], "rarity": r["rarity"],
            "title_ru": r["title_ru"], "asset_id": r["asset_id"],
            "source": r["source"], "acquired_at": r["acquired_at"],
        }
        for r in rows
    ]


def get_unlocks(external_key: str) -> list[str]:
    player = get_player(external_key)
    rows = get_conn().execute(
        "SELECT zone_id FROM unlocks WHERE player_id=?", (player["id"],)
    ).fetchall()
    return [r["zone_id"] for r in rows]
