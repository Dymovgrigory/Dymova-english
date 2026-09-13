"""Слой БД Foxinburg World.

Prod: PostgreSQL (WORLD_DATABASE_URL, psycopg). Dev/тесты: SQLite
(WORLD_DB_PATH, по умолчанию bot/data/world.sqlite) — тот же SQL-диалект
(плейсхолдеры ?), компромисс зафиксирован в docs/world/architecture.md.
Переключение только через env (§105).
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "world.sqlite"


def using_postgres() -> bool:
    return bool(os.environ.get("WORLD_DATABASE_URL"))


def _connect_sqlite(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_conn() -> sqlite3.Connection:
    global _conn
    if using_postgres():
        raise RuntimeError(
            "WORLD_DATABASE_URL задан, но psycopg-слой ещё не подключён: "
            "добавьте psycopg[binary] в requirements и реализуйте PgConn "
            "(см. docs/world/architecture.md §3)."
        )
    if _conn is None:
        with _lock:
            if _conn is None:
                path = os.environ.get("WORLD_DB_PATH", str(DEFAULT_PATH))
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                _conn = _connect_sqlite(path)
                migrate(_conn)
    return _conn


def reset_for_tests(path: str) -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
    os.environ["WORLD_DB_PATH"] = path
    if os.path.exists(path):
        os.remove(path)


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    external_key  TEXT NOT NULL UNIQUE,      -- child id из CRM / miniapp auth
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'child',  -- child|parent|teacher|admin (§8)
    xp            INTEGER NOT NULL DEFAULT 0,
    coins         INTEGER NOT NULL DEFAULT 0,
    level         INTEGER NOT NULL DEFAULT 1,
    streak_days   INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Append-only ledger (§85). amount: +начисление / -списание.
CREATE TABLE IF NOT EXISTS xp_transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    type        TEXT NOT NULL,               -- LESSON_REWARD|QUEST_REWARD|...
    amount      INTEGER NOT NULL,
    source      TEXT NOT NULL,               -- quest_id / lesson_id / admin
    idempotency_key TEXT UNIQUE,             -- §160
    metadata    TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS coin_transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    type        TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    source      TEXT NOT NULL,
    idempotency_key TEXT UNIQUE,
    metadata    TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quests (
    id          TEXT PRIMARY KEY,            -- 'first-day-at-foxinburg'
    kind        TEXT NOT NULL DEFAULT 'story',  -- daily|weekly|story|language|event|secret (§19)
    title_ru    TEXT NOT NULL,
    config      TEXT NOT NULL DEFAULT '{}'   -- data-driven: steps, activity, rewards
);

CREATE TABLE IF NOT EXISTS quest_progress (
    player_id   INTEGER NOT NULL REFERENCES players(id),
    quest_id    TEXT NOT NULL REFERENCES quests(id),
    status      TEXT NOT NULL DEFAULT 'active',  -- active|completed
    step        INTEGER NOT NULL DEFAULT 0,
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    PRIMARY KEY (player_id, quest_id)
);

CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,            -- 'fox-badge-first'
    category    TEXT NOT NULL,               -- avatar|clothes|badges|collectibles|... (§16)
    rarity      TEXT NOT NULL DEFAULT 'common',  -- §17
    title_ru    TEXT NOT NULL,
    asset_id    TEXT,                        -- из asset-registry
    unlock_condition TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS inventory (
    player_id   INTEGER NOT NULL REFERENCES players(id),
    item_id     TEXT NOT NULL REFERENCES items(id),
    source      TEXT NOT NULL,               -- quest_id / shop / gift
    acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, item_id)
);

CREATE TABLE IF NOT EXISTS unlocks (
    player_id   INTEGER NOT NULL REFERENCES players(id),
    zone_id     TEXT NOT NULL,
    unlocked_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, zone_id)
);

CREATE TABLE IF NOT EXISTS world_state (
    player_id   INTEGER NOT NULL REFERENCES players(id),
    key         TEXT NOT NULL,
    value       TEXT NOT NULL DEFAULT '{}',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, key)
);
"""
