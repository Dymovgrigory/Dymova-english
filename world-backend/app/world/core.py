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



def _daily_xp_today(row) -> int:
    if "daily_xp" not in row.keys():
        return 0
    from .engine import _day
    if row["daily_xp_day"] != _day():
        return 0
    return int(row["daily_xp"] or 0)


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
        "level_title_ru": config.LEVEL_TITLES_RU[min(lvl - 1, len(config.LEVEL_TITLES_RU) - 1)],
        "xp_into_level": row["xp"] - cur,
        "xp_to_next": (nxt - row["xp"]) if nxt else None,
        "streak_days": row["streak_days"],
        "hearts": int(row["hearts"]) if "hearts" in row.keys() else 5,
        "streak_freeze": int(row["streak_freeze"]) if "streak_freeze" in row.keys() else 0,
        "daily_xp": _daily_xp_today(row),
        "daily_goal": int(row["daily_goal"]) if "daily_goal" in row.keys() else config.DAILY_XP_GOAL,
    }


_ALLOWED_ROLES = frozenset({"child", "parent", "teacher", "admin"})


def get_or_create_player(external_key: str, display_name: str = "Explorer",
                         role: str = "child") -> dict:
    """Create player if missing. Never upgrades/downgrades an existing role."""
    role = (role or "child").strip().lower()
    if role not in _ALLOWED_ROLES:
        role = "child"
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO players (external_key, display_name, role) VALUES (?,?,?)",
        (external_key, display_name, role),
    )
    # Refresh display_name only — role stays as first-write-wins.
    conn.execute(
        "UPDATE players SET display_name=?, updated_at=datetime('now') WHERE external_key=?",
        (display_name, external_key),
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


def link_guardian(parent_player_id: int, child_player_id: int) -> dict:
    """Family-ready link. Parent/teacher/admin roles only on the parent side."""
    conn = get_conn()
    parent = conn.execute("SELECT * FROM players WHERE id=?", (parent_player_id,)).fetchone()
    child = conn.execute("SELECT * FROM players WHERE id=?", (child_player_id,)).fetchone()
    if parent is None or child is None:
        raise NotFound("parent or child player not found")
    if parent["role"] not in ("parent", "teacher", "admin"):
        raise Conflict("guardian must have parent/teacher/admin role")
    if child["role"] != "child":
        raise Conflict("ward must be a child")
    if parent_player_id == child_player_id:
        raise Conflict("cannot link player to self")
    conn.execute(
        "INSERT OR IGNORE INTO guardianship (parent_player_id, child_player_id) VALUES (?,?)",
        (parent_player_id, child_player_id),
    )
    return {"parent_player_id": parent_player_id, "child_player_id": child_player_id}


def list_wards(parent_player_id: int) -> list[dict]:
    rows = get_conn().execute(
        "SELECT p.* FROM guardianship g"
        " JOIN players p ON p.id = g.child_player_id"
        " WHERE g.parent_player_id=?"
        " ORDER BY p.id",
        (parent_player_id,),
    ).fetchall()
    return [_row_to_player(r) for r in rows]


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
                # Keep daily goal in sync for any award path (lessons, quests, practice).
                from .engine import _day
                today = _day()
                row_d = conn.execute(
                    "SELECT daily_xp, daily_xp_day FROM players WHERE id=?", (pid,)
                ).fetchone()
                cur_d = int(row_d["daily_xp"] or 0) if row_d["daily_xp_day"] == today else 0
                conn.execute(
                    "UPDATE players SET daily_xp=?, daily_xp_day=? WHERE id=?",
                    (cur_d + xp, today, pid),
                )
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


def spend(external_key: str, *, coins: int, source: str, type_: str,
          idempotency_key: str) -> dict:
    if coins <= 0:
        raise Conflict("invalid spend")
    player = get_player(external_key)
    if player["coins"] < coins:
        raise Conflict("not enough coins")
    conn = get_conn()
    pid = player["id"]
    applied = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT coins FROM players WHERE id=?", (pid,)).fetchone()
        if row["coins"] < coins:
            raise Conflict("not enough coins")
        applied = bool(_ledger(conn, "coin_transactions", pid, type_, -coins, source,
                   f"{idempotency_key}:coins", {}))
        if applied:
            conn.execute(
                "UPDATE players SET coins=coins-?, updated_at=datetime('now') WHERE id=?",
                (coins, pid),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {
        "coins_delta": -coins if applied else 0,
        "applied": applied,
        "player": get_player(external_key),
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
    for sid, spec in config.STICKERS.items():
        conn.execute(
            "INSERT OR IGNORE INTO items (id, category, rarity, title_ru, asset_id, unlock_condition)"
            " VALUES (?,?,?,?,?,?)",
            (sid, "stickers", "common", spec["title_ru"], spec["emoji"],
             f"unit:{spec['unit']}" if spec.get("unit") else "earn"),
        )
    from . import catalog
    for uid, unit in catalog.load_units().items():
        sid = f"sticker-{uid}"
        conn.execute(
            "INSERT OR IGNORE INTO items (id, category, rarity, title_ru, asset_id, unlock_condition)"
            " VALUES (?,?,?,?,?,?)",
            (sid, "stickers", "common", unit["place_ru"], "🦊", f"unit:{uid}"),
        )
    extras = (
        ("foxi-cape", "clothes", "uncommon", "Плащ Фокси", "🦊"),
        ("castle-banner", "collectibles", "uncommon", "Знамя замка", "🏳️"),
    )
    for item_id, category, rarity, title, asset in extras:
        conn.execute(
            "INSERT OR IGNORE INTO items (id, category, rarity, title_ru, asset_id, unlock_condition)"
            " VALUES (?,?,?,?,?,?)",
            (item_id, category, rarity, title, asset, "shop"),
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


def advance_quest_step(external_key: str, quest_id: str, action: str,
                       target: str) -> dict:
    """Двигает квест на шаг вперёд, если действие совпало с текущим шагом.

    Порядок шагов проверяет сервер: клиент не может перепрыгнуть шаг (§84).
    """
    player = get_player(external_key)
    quest = get_quest(quest_id)
    steps = quest["config"].get("steps", [])
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status, step FROM quest_progress WHERE player_id=? AND quest_id=?",
            (player["id"], quest_id),
        ).fetchone()
        if row is None:
            raise Conflict("quest not started")
        if row["status"] == "completed":
            raise Conflict("quest already completed")
        step = row["step"]
        if step >= len(steps):
            raise Conflict("all steps already done")
        current = steps[step]
        if current["action"] != action or current["target"] != target:
            raise Conflict(
                f"step mismatch: expected {current['action']}:{current['target']}"
            )
        new_step = step + 1
        conn.execute(
            "UPDATE quest_progress SET step=? WHERE player_id=? AND quest_id=?",
            (new_step, player["id"], quest_id),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {
        "quest_id": quest_id,
        "step": new_step,
        "steps_total": len(steps),
        "all_steps_done": new_step >= len(steps),
    }


def complete_quest(external_key: str, quest_id: str,
                   idempotency_key: str | None = None) -> dict:
    """Завершение квеста → награды из config.quests (server-authoritative).

    `idempotency_key` принимается из тела запроса только для обратной
    совместимости API — на реальный ключ ledger он не влияет и нигде не
    используется. Ledger-запись всегда идёт под ключом, который сервер
    строит сам из player_id и quest_id: иначе клиент мог бы прислать чужой
    предсказуемый ключ (например ключ, который сервер построил бы для
    другого игрока) и сжечь UNIQUE-слот в ledger до того, как настоящий
    адресат квест завершит — тот получил бы нулевую награду при помеченном
    завершённым квесте.
    """
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

    steps = quest["config"].get("steps") or []
    prog = conn.execute(
        "SELECT step FROM quest_progress WHERE player_id=? AND quest_id=?",
        (player["id"], quest_id),
    ).fetchone()
    if steps and int(prog["step"] or 0) < len(steps):
        raise Conflict("quest steps incomplete")

    rewards = quest["config"].get("rewards", {})
    result = award(
        external_key,
        xp=rewards.get("xp", 0),
        coins=rewards.get("coins", 0),
        items=rewards.get("items"),
        unlocks=rewards.get("unlocks"),
        source=quest_id,
        type_="QUEST_REWARD",
        idempotency_key=f"quest-complete:{player['id']}:{quest_id}",
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
