"""Слой БД Foxinburg World.

Dev/тесты: SQLite (WORLD_DB_PATH, по умолчанию world-backend/data/world.sqlite).
Prod Postgres (WORLD_DATABASE_URL) — отдельный шаг, не слой бота.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "world.sqlite"


def using_postgres() -> bool:
    return bool(os.environ.get("WORLD_DATABASE_URL"))


def _connect_sqlite(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class _LockedConn:
    """Один SQLite на процесс: FastAPI гоняет хендлеры в тредпуле — execute+fetch без лока ломается."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple | list = ()):
        with _lock:
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall()
            return _Rows(rows, cur.lastrowid, cur.rowcount)

    def executescript(self, sql: str):
        with _lock:
            return self._conn.executescript(sql)

    def close(self) -> None:
        with _lock:
            self._conn.close()


class _Rows:
    def __init__(self, rows: list, lastrowid: int, rowcount: int) -> None:
        self._rows = rows
        self.lastrowid = lastrowid
        self.rowcount = rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


def adapt_sql(sql: str) -> str:
    """Перевод SQLite-идиом движка на Postgres."""
    out = sql.replace("datetime('now')", "CURRENT_TIMESTAMP")
    out = out.replace("BEGIN IMMEDIATE", "BEGIN")
    if out.lstrip().upper().startswith("INSERT OR IGNORE"):
        out = out.replace("INSERT OR IGNORE", "INSERT", 1).replace("insert or ignore", "INSERT", 1)
        if "ON CONFLICT" not in out.upper():
            out = out.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    out = out.replace("?", "%s")
    return out


class _PgLocked:
    def __init__(self, conn) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple | list = ()):
        with _lock:
            cur = self._conn.execute(adapt_sql(sql), params)
            rows = cur.fetchall() if cur.description else []
            return _Rows(rows, getattr(cur, "lastrowid", 0) or 0, cur.rowcount)

    def executescript(self, sql: str):
        with _lock:
            self._conn.execute(sql)
            return self

    def close(self) -> None:
        with _lock:
            self._conn.close()


def _connect_postgres():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "WORLD_DATABASE_URL задан: установите psycopg[binary] "
            "(см. docs/world/DEPLOY.md)."
        ) from exc
    raw = psycopg.connect(os.environ["WORLD_DATABASE_URL"], row_factory=dict_row, autocommit=True)
    migrate_pg(raw)
    return _PgLocked(raw)


def migrate_pg(conn) -> None:
    schema = (
        SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        .replace("DEFAULT (datetime('now'))", "DEFAULT CURRENT_TIMESTAMP")
    )
    for stmt in schema.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    for table, extras in _TABLE_EXTRAS.items():
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
            (table,),
        ).fetchall()
        existing = {r["column_name"] if isinstance(r, dict) else r[0] for r in rows}
        for name, spec in extras.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {spec}")


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                if using_postgres():
                    _conn = _connect_postgres()  # type: ignore[assignment]
                else:
                    path = os.environ.get("WORLD_DB_PATH", str(DEFAULT_PATH))
                    Path(path).parent.mkdir(parents=True, exist_ok=True)
                    raw = _connect_sqlite(path)
                    migrate(raw)
                    _conn = _LockedConn(raw)  # type: ignore[assignment]
    return _conn  # type: ignore[return-value]


def reset_for_tests(path: str) -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
    os.environ["WORLD_DB_PATH"] = path
    os.environ.pop("WORLD_DATABASE_URL", None)
    if os.path.exists(path):
        os.remove(path)


_PLAYER_EXTRAS = {
    "hearts": "INTEGER NOT NULL DEFAULT 5",
    "hearts_at": "TEXT",
    "last_lesson_day": "TEXT",
    "streak_freeze": "INTEGER NOT NULL DEFAULT 0",
    "daily_xp": "INTEGER NOT NULL DEFAULT 0",
    "daily_xp_day": "TEXT",
    "daily_goal": "INTEGER NOT NULL DEFAULT 50",
}


_TABLE_EXTRAS = {
    "players": _PLAYER_EXTRAS,
    "word_stats": {"due_at": "TEXT"},
    "auth_sessions": {"revoked_at": "TEXT"},
    "castle_appearance": {
        "decor_off": "TEXT NOT NULL DEFAULT '[]'",   # JSON-массив снятых украшений
        "scene_set": "TEXT",                         # запечённый набор сцены, NULL = нет набора
        "decor_slots": "TEXT NOT NULL DEFAULT '{}'",  # JSON {item_id: slot_id}
    },
    "atom_mastery": {"learned_at": "TEXT"},  # московский день первого взятия порога силы 2
}


def _backfill_atom_learned_at(conn: sqlite3.Connection) -> None:
    """Для атомов, выученных до появления колонки, — приблизим день по последнему ответу."""
    conn.execute(
        "UPDATE atom_mastery SET learned_at=substr(updated_at,1,10)"
        " WHERE strength>=2 AND learned_at IS NULL"
    )


def _ensure_columns(conn: sqlite3.Connection) -> None:
    for table, extras in _TABLE_EXTRAS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, spec in extras.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {spec}")
    _backfill_atom_learned_at(conn)


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _ensure_columns(conn)


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
    hearts        INTEGER NOT NULL DEFAULT 5,
    hearts_at     TEXT,
    last_lesson_day TEXT,
    streak_freeze INTEGER NOT NULL DEFAULT 0,
    daily_xp      INTEGER NOT NULL DEFAULT 0,
    daily_xp_day  TEXT,
    daily_goal    INTEGER NOT NULL DEFAULT 50,
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

-- Сессия активности: вопросы и правильные ответы живут на сервере (§84).
CREATE TABLE IF NOT EXISTS activity_sessions (
    id           TEXT PRIMARY KEY,
    player_id    INTEGER NOT NULL REFERENCES players(id),
    activity_id  TEXT NOT NULL,
    payload      TEXT NOT NULL,               -- {questions:[...с correct_index]}
    answers      TEXT NOT NULL DEFAULT '{}',  -- {"0": {"choice":2,"correct":true}}
    status       TEXT NOT NULL DEFAULT 'active',  -- active|completed
    score        INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS lesson_progress (
    player_id   INTEGER NOT NULL REFERENCES players(id),
    lesson_id   TEXT NOT NULL,
    stars       INTEGER NOT NULL DEFAULT 0,
    best_score  INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS word_stats (
    player_id     INTEGER NOT NULL REFERENCES players(id),
    unit_id       TEXT NOT NULL,
    word_en       TEXT NOT NULL,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count   INTEGER NOT NULL DEFAULT 0,
    strength      INTEGER NOT NULL DEFAULT 0,
    due_at        TEXT,                      -- когда слово вернётся на повтор (SRS)
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, unit_id, word_en)
);

CREATE TABLE IF NOT EXISTS mistakes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id  INTEGER NOT NULL REFERENCES players(id),
    unit_id    TEXT NOT NULL,
    item       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    cleared    INTEGER NOT NULL DEFAULT 0
);

-- Phase 1 Identity: opaque sessions (revocable) + family links.
CREATE TABLE IF NOT EXISTS auth_sessions (
    id          TEXT PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TEXT NOT NULL,
    revoked_at  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS guardianship (
    parent_player_id INTEGER NOT NULL REFERENCES players(id),
    child_player_id  INTEGER NOT NULL REFERENCES players(id),
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (parent_player_id, child_player_id)
);
-- World v2: тренажёр Spotlight (app/learning).
CREATE TABLE IF NOT EXISTS learner_profile (
    player_id     INTEGER PRIMARY KEY REFERENCES players(id),
    book_id       TEXT NOT NULL,
    module_id     TEXT NOT NULL,
    daily_goal_xp INTEGER NOT NULL DEFAULT 20,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS node_progress (
    player_id     INTEGER NOT NULL REFERENCES players(id),
    node_id       TEXT NOT NULL,
    stars         INTEGER NOT NULL DEFAULT 0,
    best_accuracy REAL NOT NULL DEFAULT 0,
    completed_at  TEXT NOT NULL,
    PRIMARY KEY (player_id, node_id)
);

CREATE TABLE IF NOT EXISTS learn_sessions (
    id          TEXT PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    node_id     TEXT NOT NULL,
    kind        TEXT NOT NULL,
    payload     TEXT NOT NULL,
    pending     TEXT NOT NULL,
    state       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    result      TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id      INTEGER NOT NULL REFERENCES players(id),
    session_id     TEXT NOT NULL,
    node_id        TEXT NOT NULL,
    challenge_type TEXT NOT NULL,
    atom_id        TEXT NOT NULL,
    answer         TEXT NOT NULL,
    correct        INTEGER NOT NULL,
    typo           INTEGER NOT NULL DEFAULT 0,
    response_ms    INTEGER,
    attempt_no     INTEGER NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS atom_mastery (
    player_id     INTEGER NOT NULL REFERENCES players(id),
    atom_id       TEXT NOT NULL,
    strength      INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count   INTEGER NOT NULL DEFAULT 0,
    due_at        TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (player_id, atom_id)
);

CREATE TABLE IF NOT EXISTS daily_activity (
    player_id INTEGER NOT NULL REFERENCES players(id),
    day       TEXT NOT NULL,
    xp        INTEGER NOT NULL DEFAULT 0,
    sessions  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, day)
);

CREATE TABLE IF NOT EXISTS castle_appearance (
    player_id     INTEGER PRIMARY KEY REFERENCES players(id),
    season        TEXT,                       -- spring|summer|autumn|winter, NULL = по календарю
    time_of_day   TEXT,                       -- dawn|day|dusk|night, NULL = как за окном
    weather       TEXT,                       -- snow|rain|fireflies|fog|aurora|petals, NULL = без эффекта
    banner_color  TEXT NOT NULL DEFAULT 'plum',
    banner_emblem TEXT NOT NULL DEFAULT 'fox',
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS castle_owned (
    player_id   INTEGER NOT NULL REFERENCES players(id),
    item_id     TEXT NOT NULL,
    anchor      TEXT,                          -- точка на замке для украшений
    source      TEXT NOT NULL,                 -- shop|title|gift
    acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, item_id)
);

CREATE TABLE IF NOT EXISTS titles (
    player_id  INTEGER NOT NULL REFERENCES players(id),
    track      TEXT NOT NULL,                  -- lexicon|yard|nest|glory|stickers
    level      INTEGER NOT NULL DEFAULT 0,
    awarded_at TEXT NOT NULL DEFAULT (datetime('now')),
    worn       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, track)
);

CREATE TABLE IF NOT EXISTS lexicon_chests (
    player_id   INTEGER NOT NULL REFERENCES players(id),
    chest_index INTEGER NOT NULL,              -- 0,1,2... — какой по счёту сундук
    opened_at   TEXT NOT NULL DEFAULT (datetime('now')),
    coins       INTEGER NOT NULL,
    item_id     TEXT,                          -- выпавшее украшение, NULL если всё куплено
    PRIMARY KEY (player_id, chest_index)
);

-- Регистрация: анкета ученика, согласия, верификация телефона.
CREATE TABLE IF NOT EXISTS player_identity (
    player_id       INTEGER PRIMARY KEY REFERENCES players(id),
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    birth_date      TEXT NOT NULL,
    school_number   TEXT NOT NULL,
    class_grade     INTEGER NOT NULL,
    class_letter    TEXT,
    parent_email    TEXT NOT NULL,
    parent_phone    TEXT NOT NULL,
    phone_verified_at TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS consents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    type        TEXT NOT NULL,               -- pd_child|privacy|marketing
    version     TEXT NOT NULL,
    accepted_at TEXT NOT NULL DEFAULT (datetime('now')),
    ip          TEXT,
    user_agent  TEXT
);

CREATE INDEX IF NOT EXISTS idx_consents_player_type ON consents (player_id, type);

CREATE TABLE IF NOT EXISTS phone_verifications (
    id          TEXT PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    phone       TEXT NOT NULL,
    code_hash   TEXT NOT NULL,               -- sha256(salt:code), salt = id записи
    channel     TEXT NOT NULL,               -- sms|call
    attempts    INTEGER NOT NULL DEFAULT 0,
    expires_at  TEXT NOT NULL,
    verified_at TEXT,
    provider_id TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Вход через мессенджеры (Telegram/MAX): привязка внешнего аккаунта к игроку.
CREATE TABLE IF NOT EXISTS external_identities (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    provider         TEXT NOT NULL,              -- telegram|max
    provider_user_id TEXT NOT NULL,
    player_id        INTEGER NOT NULL REFERENCES players(id),
    display_name     TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (provider, provider_user_id)
);

-- Админка: пользователи, сессии, аудит.
CREATE TABLE IF NOT EXISTS admin_users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    login         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,             -- salt_hex$pbkdf2_hex
    role          TEXT NOT NULL DEFAULT 'manager',  -- owner|manager
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admin_sessions (
    id         TEXT PRIMARY KEY,
    admin_id   INTEGER NOT NULL REFERENCES admin_users(id),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admin_audit (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    actor      TEXT NOT NULL,                -- login админа
    action     TEXT NOT NULL,                -- adjust|patch_identity|mastery|items
    entity     TEXT NOT NULL,                -- player:{id}
    payload    TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS league_weeks (
    player_id     INTEGER NOT NULL REFERENCES players(id),
    week_start    TEXT NOT NULL,               -- понедельник недели, YYYY-MM-DD
    rank          INTEGER NOT NULL,
    weekly_xp     INTEGER NOT NULL,
    coins_awarded INTEGER NOT NULL DEFAULT 0,
    closed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, week_start)
);
"""
