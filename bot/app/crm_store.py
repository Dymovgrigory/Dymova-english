"""Постоянное CRM-хранилище: клиенты, идентичности, диалоги и сообщения.

Живёт рядом с legacy-таблицей `conversations` в той же базе SQLite (DB_PATH):
legacy-таблица остаётся состоянием для AI (memory.py не трогаем), а здесь —
полная история сообщений по всем каналам (MAX / Telegram / веб-виджет),
карточки клиентов, журнал входящих событий и аудит.

Принципы:
- никаких DELETE клиентских данных: архивация вместо удаления;
- все записи идемпотентны (дедуп по внешним id), повторный вебхук не плодит
  дубли сообщений;
- все метки времени — UTC ISO;
- полнотекстовый поиск по сообщениям через FTS5, если доступен (иначе LIKE).
"""
from __future__ import annotations

import contextlib
import hmac
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Маркер однократной миграции legacy-таблицы conversations.
_MIGRATION_KEY = "legacy_migrated"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    child_name TEXT NOT NULL DEFAULT '',
    child_age TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    lead_status TEXT NOT NULL DEFAULT 'new',
    source TEXT NOT NULL DEFAULT '',
    utm_json TEXT NOT NULL DEFAULT '{}',
    notes TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    interests TEXT NOT NULL DEFAULT '',
    manager TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    archived_at TEXT,
    archived_by TEXT,
    archive_reason TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS customer_identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    channel TEXT NOT NULL,
    external_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(channel, external_id)
);
CREATE INDEX IF NOT EXISTS idx_identities_customer ON customer_identities(customer_id);

CREATE TABLE IF NOT EXISTS crm_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    channel TEXT NOT NULL,
    external_user_id TEXT NOT NULL,
    ai_mode TEXT NOT NULL DEFAULT 'active',
    ai_paused_until TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    unread_count INTEGER NOT NULL DEFAULT 0,
    last_message_at TEXT,
    last_message_text TEXT,
    last_sender_type TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(channel, external_user_id)
);
CREATE INDEX IF NOT EXISTS idx_crm_conv_customer ON crm_conversations(customer_id);
CREATE INDEX IF NOT EXISTS idx_crm_conv_last_msg ON crm_conversations(last_message_at);

CREATE TABLE IF NOT EXISTS crm_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES crm_conversations(id),
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    channel TEXT NOT NULL,
    external_message_id TEXT,
    direction TEXT NOT NULL,
    sender_type TEXT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'sent',
    error TEXT,
    reply_to TEXT,
    intent TEXT,
    stage TEXT,
    ai_model TEXT,
    created_at TEXT NOT NULL
);
-- Частичный уникальный индекс: дедуп только по известным внешним id,
-- NULL (миграция, веб) не конфликтует между собой.
CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_messages_ext
    ON crm_messages(channel, external_message_id)
    WHERE external_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_crm_messages_conv ON crm_messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_crm_messages_customer ON crm_messages(customer_id, created_at);
CREATE INDEX IF NOT EXISTS idx_crm_messages_channel ON crm_messages(channel, created_at);
CREATE INDEX IF NOT EXISTS idx_crm_messages_created ON crm_messages(created_at);

CREATE TABLE IF NOT EXISTS inbound_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    external_event_id TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    received_at TEXT NOT NULL,
    processed_at TEXT,
    status TEXT NOT NULL DEFAULT 'received',
    error TEXT,
    UNIQUE(channel, external_event_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL DEFAULT '',
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    author TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_customer ON customer_notes(customer_id);

CREATE TABLE IF NOT EXISTS customer_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    title TEXT NOT NULL,
    due_at TEXT,
    assignee TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    done_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_customer ON customer_tasks(customer_id);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS customer_tags (
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    UNIQUE(customer_id, tag_id)
);

CREATE TABLE IF NOT EXISTS ai_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER,
    customer_id INTEGER,
    kind TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_events_kind ON ai_events(kind, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_events_customer ON ai_events(customer_id, created_at);

CREATE TABLE IF NOT EXISTS broadcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    segment_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    total INTEGER NOT NULL DEFAULT 0,
    delivered INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS broadcast_recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broadcast_id INTEGER NOT NULL REFERENCES broadcasts(id),
    customer_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    external_user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    sent_at TEXT,
    UNIQUE(broadcast_id, customer_id, channel)
);

CREATE TABLE IF NOT EXISTS crm_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS crm_messages_fts USING fts5(
    text, content='crm_messages', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS crm_messages_ai AFTER INSERT ON crm_messages BEGIN
    INSERT INTO crm_messages_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS crm_messages_ad AFTER DELETE ON crm_messages BEGIN
    INSERT INTO crm_messages_fts(crm_messages_fts, rowid, text)
        VALUES('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS crm_messages_au AFTER UPDATE OF text ON crm_messages BEGIN
    INSERT INTO crm_messages_fts(crm_messages_fts, rowid, text)
        VALUES('delete', old.id, old.text);
    INSERT INTO crm_messages_fts(rowid, text) VALUES (new.id, new.text);
END;
"""

_conn: sqlite3.Connection | None = None
_lock = threading.RLock()
# Доступность FTS5 определяем пробным созданием таблицы при инициализации.
_fts5_ok = False


@contextlib.contextmanager
def _tx(conn: sqlite3.Connection):
    """Запись в транзакции. Реентерабельно: миграция вызывает upsert/add_message,
    которые сами открывают транзакцию, — вложенный BEGIN был бы ошибкой."""
    with _lock:
        if conn.in_transaction:
            yield
            return
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_db_path() -> str:
    # Тот же источник, что и у memory.MemoryStore: одна база на процесс.
    if settings.STATE_FILE:
        return settings.STATE_FILE
    return settings.DB_PATH or ":memory:"


def _connect(db_path: str) -> sqlite3.Connection:
    uri = db_path.startswith("file:")
    if db_path not in (":memory:",) and not uri:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False, uri=uri, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.Error:
        pass
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def get_conn(db_path: str | None = None) -> sqlite3.Connection:
    """Единственное соединение на процесс (как у MemoryStore)."""
    global _conn
    with _lock:
        if _conn is None:
            _conn = _connect(db_path or _resolve_db_path())
            init_schema(_conn)
        return _conn


def reset() -> None:
    """Закрывает соединение. Нужно тестам и «мягкому перезапуску» store."""
    global _conn, _fts5_ok
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except sqlite3.Error:
                pass
        _conn = None
        _fts5_ok = False


def fts_available() -> bool:
    get_conn()
    return _fts5_ok


def init_schema(conn: sqlite3.Connection) -> None:
    """Идемпотентно создаёт схему (IF NOT EXISTS)."""
    global _fts5_ok
    with _lock:
        conn.executescript(_SCHEMA)
        init_segments_table(conn)
        init_kb_tables(conn)
        init_rbac_tables(conn)
        try:
            conn.executescript(_FTS_SCHEMA)
            _fts5_ok = True
        except sqlite3.Error:
            # Нет FTS5 в этой сборке sqlite3: полнотекстовый поиск ниже
            # прозрачно деградирует до LIKE.
            _fts5_ok = False
            logger.warning("crm_store: FTS5 недоступен, поиск сообщений через LIKE")


def _rows(cur: sqlite3.Cursor) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _norm_phone(phone: str) -> str:
    """Нормализует телефон до последних 10 цифр для сравнения."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def audit(actor: str, action: str, entity_type: str, entity_id: object = "",
          before: dict | None = None, after: dict | None = None) -> None:
    conn = get_conn()
    with _tx(conn):
        conn.execute(
            "INSERT INTO audit_log(actor, action, entity_type, entity_id, before_json, after_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                actor, action, entity_type, str(entity_id),
                json.dumps(before, ensure_ascii=False) if before is not None else None,
                json.dumps(after, ensure_ascii=False) if after is not None else None,
                _now(),
            ),
        )


# --------- Клиенты и идентичности ---------


def upsert_customer_for_identity(
    channel: str,
    external_id: str,
    name: str = "",
    first_name: str = "",
    last_name: str = "",
    username: str = "",
    phone: str = "",
    email: str = "",
    child_name: str = "",
    child_age: str = "",
    source: str = "",
    utm: dict | None = None,
    interests: str = "",
    notes: str = "",
) -> int:
    """Находит или создаёт клиента по паре (канал, внешний id).

    Если идентичности ещё нет, но телефон совпал с уже известным клиентом —
    привязываем новую идентичность к нему (склейка каналов по телефону).
    Непустые новые поля дописываем, но непустые существующие НЕ затираем.
    """
    conn = get_conn()
    now = _now()
    with _tx(conn):
        row = conn.execute(
            "SELECT customer_id FROM customer_identities WHERE channel = ? AND external_id = ?",
            (channel, external_id),
        ).fetchone()
        if row is not None:
            customer_id = int(row["customer_id"])
            conn.execute(
                "UPDATE customers SET last_seen_at = ?, updated_at = ? WHERE id = ?",
                (now, now, customer_id),
            )
            _fill_empty_fields(conn, customer_id, name=name, first_name=first_name,
                               last_name=last_name, username=username, phone=phone,
                               email=email, child_name=child_name, child_age=child_age,
                               interests=interests, notes=notes)
            _merge_utm(conn, customer_id, utm)
            return customer_id

        customer_id = None
        norm = _norm_phone(phone)
        if norm:
            # Склейка каналов по телефону: ищем клиента с тем же номером.
            for cand in conn.execute(
                "SELECT id, phone FROM customers WHERE phone != '' AND status != 'archived'"
            ).fetchall():
                if _norm_phone(cand["phone"]) == norm:
                    customer_id = int(cand["id"])
                    break

        if customer_id is None:
            cur = conn.execute(
                """
                INSERT INTO customers(name, first_name, last_name, username, phone, email,
                    child_name, child_age, status, lead_status, source, utm_json,
                    interests, notes, created_at, updated_at, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 'new', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name, first_name, last_name, username, phone, email,
                    child_name, child_age, source or (utm or {}).get("utm_source", ""),
                    json.dumps(utm or {}, ensure_ascii=False),
                    interests, notes, now, now, now, now,
                ),
            )
            customer_id = int(cur.lastrowid)
        else:
            conn.execute(
                "UPDATE customers SET last_seen_at = ?, updated_at = ? WHERE id = ?",
                (now, now, customer_id),
            )
            _fill_empty_fields(conn, customer_id, name=name, first_name=first_name,
                               last_name=last_name, username=username, phone=phone,
                               email=email, child_name=child_name, child_age=child_age,
                               interests=interests, notes=notes)
            _merge_utm(conn, customer_id, utm)

        conn.execute(
            "INSERT OR IGNORE INTO customer_identities(customer_id, channel, external_id, created_at)"
            " VALUES (?, ?, ?, ?)",
            (customer_id, channel, external_id, now),
        )
        return customer_id


def _fill_empty_fields(conn: sqlite3.Connection, customer_id: int, **fields: str) -> None:
    """Дописывает только те поля, которые сейчас пусты (не затираем данные)."""
    current = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if current is None:
        return
    updates = []
    values = []
    for key, value in fields.items():
        if value and not current[key]:
            updates.append(f"{key} = ?")
            values.append(value)
    if updates:
        updates.append("updated_at = ?")
        values.append(_now())
        values.append(customer_id)
        conn.execute(f"UPDATE customers SET {', '.join(updates)} WHERE id = ?", values)


def _merge_utm(conn: sqlite3.Connection, customer_id: int, utm: dict | None) -> None:
    if not utm:
        return
    row = conn.execute("SELECT utm_json FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if row is None:
        return
    try:
        existing = json.loads(row["utm_json"] or "{}")
    except json.JSONDecodeError:
        existing = {}
    # Первый источник важнее: существующие ключи не перезаписываем.
    merged = {**{k: v for k, v in utm.items() if v}, **existing}
    if merged != existing:
        conn.execute(
            "UPDATE customers SET utm_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(merged, ensure_ascii=False), _now(), customer_id),
        )


def get_or_create_conversation(customer_id: int, channel: str, external_user_id: str) -> int:
    conn = get_conn()
    now = _now()
    with _tx(conn):
        row = conn.execute(
            "SELECT id, customer_id FROM crm_conversations WHERE channel = ? AND external_user_id = ?",
            (channel, external_user_id),
        ).fetchone()
        if row is not None:
            conv_id = int(row["id"])
            # Клиент мог быть склеен по телефону: перевешиваем диалог на
            # актуального клиента, чтобы история не оставалась на дубле.
            if int(row["customer_id"]) != customer_id:
                conn.execute(
                    "UPDATE crm_conversations SET customer_id = ?, updated_at = ? WHERE id = ?",
                    (customer_id, now, conv_id),
                )
                conn.execute(
                    "UPDATE crm_messages SET customer_id = ? WHERE conversation_id = ?",
                    (customer_id, conv_id),
                )
            return conv_id
        cur = conn.execute(
            "INSERT INTO crm_conversations(customer_id, channel, external_user_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (customer_id, channel, external_user_id, now, now),
        )
        return int(cur.lastrowid)


# --------- События и сообщения ---------


def record_inbound_event(channel: str, external_event_id: str, payload: dict) -> tuple[int, bool]:
    """Журнал входящих событий. Возвращает (event_id, is_duplicate)."""
    conn = get_conn()
    with _tx(conn):
        cur = conn.execute(
            "INSERT OR IGNORE INTO inbound_events(channel, external_event_id, payload_json, received_at)"
            " VALUES (?, ?, ?, ?)",
            (channel, external_event_id, json.dumps(payload, ensure_ascii=False, default=str)[:4000], _now()),
        )
        if cur.rowcount == 1:
            return int(cur.lastrowid), False
        conn.execute(
            "UPDATE inbound_events SET status = 'duplicate' WHERE channel = ? AND external_event_id = ?",
            (channel, external_event_id),
        )
        row = conn.execute(
            "SELECT id FROM inbound_events WHERE channel = ? AND external_event_id = ?",
            (channel, external_event_id),
        ).fetchone()
        return int(row["id"]), True


def mark_event_processed(event_id: int, status: str = "processed", error: str | None = None) -> None:
    conn = get_conn()
    with _tx(conn):
        conn.execute(
            "UPDATE inbound_events SET status = ?, processed_at = ?, error = ? WHERE id = ?",
            (status, _now(), error, event_id),
        )


def add_message(
    conversation_id: int,
    customer_id: int,
    channel: str,
    direction: str,
    sender_type: str,
    text: str,
    external_message_id: str | None = None,
    payload: dict | None = None,
    status: str | None = None,
    error: str | None = None,
    reply_to: str | None = None,
    intent: str | None = None,
    stage: str | None = None,
    ai_model: str | None = None,
    created_at: str | None = None,
) -> tuple[int, bool]:
    """Пишет сообщение. Идемпотентно по (channel, external_message_id).

    Возвращает (message_id, is_duplicate). Заодно обновляет агрегаты диалога:
    последнее сообщение и счётчик непрочитанных (для входящих).
    """
    conn = get_conn()
    now = created_at or _now()
    if status is None:
        status = "delivered" if direction == "in" else "sent"
    with _tx(conn):
        if external_message_id:
            row = conn.execute(
                "SELECT id FROM crm_messages WHERE channel = ? AND external_message_id = ?",
                (channel, external_message_id),
            ).fetchone()
            if row is not None:
                return int(row["id"]), True
        cur = conn.execute(
            """
            INSERT INTO crm_messages(conversation_id, customer_id, channel, external_message_id,
                direction, sender_type, text, payload_json, status, error, reply_to,
                intent, stage, ai_model, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id, customer_id, channel, external_message_id,
                direction, sender_type, text or "",
                json.dumps(payload or {}, ensure_ascii=False, default=str),
                status, error, reply_to, intent, stage, ai_model, now,
            ),
        )
        message_id = int(cur.lastrowid)
        unread_inc = 1 if direction == "in" else 0
        conn.execute(
            """
            UPDATE crm_conversations
            SET last_message_at = ?, last_message_text = ?, last_sender_type = ?,
                unread_count = unread_count + ?, updated_at = ?
            WHERE id = ?
            """,
            (now, (text or "")[:200], sender_type, unread_inc, _now(), conversation_id),
        )
        return message_id, False


def mark_conversation_read(conversation_id: int) -> None:
    conn = get_conn()
    with _tx(conn):
        conn.execute(
            "UPDATE crm_conversations SET unread_count = 0, updated_at = ? WHERE id = ?",
            (_now(), conversation_id),
        )


def set_ai_mode(conversation_id: int, mode: str, paused_until: str | None = None,
                actor: str = "system") -> None:
    """Перевод диалога в режим active/paused/manager (AI pause / handoff)."""
    conn = get_conn()
    with _tx(conn):
        before = conn.execute(
            "SELECT ai_mode, ai_paused_until FROM crm_conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        conn.execute(
            "UPDATE crm_conversations SET ai_mode = ?, ai_paused_until = ?, updated_at = ? WHERE id = ?",
            (mode, paused_until, _now(), conversation_id),
        )
    audit(actor, "set_ai_mode", "crm_conversation", conversation_id,
          before=dict(before) if before else None,
          after={"ai_mode": mode, "ai_paused_until": paused_until})


def add_ai_event(kind: str, conversation_id: int | None = None,
                 customer_id: int | None = None, detail: dict | None = None) -> int:
    conn = get_conn()
    with _tx(conn):
        cur = conn.execute(
            "INSERT INTO ai_events(conversation_id, customer_id, kind, detail_json, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (conversation_id, customer_id, kind,
             json.dumps(detail or {}, ensure_ascii=False, default=str), _now()),
        )
        return int(cur.lastrowid)


# --------- Запросы для админки ---------


def list_conversations(
    channel: str | None = None,
    unread: bool | None = None,
    ai_mode: str | None = None,
    lead_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    cursor: str | None = None,
) -> dict:
    """Inbox-выдача: диалоги с карточкой клиента, свежие сверху.

    cursor — строка "last_message_at|id" с прошлой страницы (keyset-пагинация).
    """
    conn = get_conn()
    where: list[str] = ["c.status != 'archived'"]
    params: list = []
    if channel:
        where.append("c.channel = ?")
        params.append(channel)
    if unread:
        where.append("c.unread_count > 0")
    if ai_mode:
        where.append("c.ai_mode = ?")
        params.append(ai_mode)
    if lead_status:
        where.append("cu.lead_status = ?")
        params.append(lead_status)
    if date_from:
        where.append("c.last_message_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("c.last_message_at <= ?")
        params.append(date_to)
    if search:
        like = f"%{search}%"
        where.append("(cu.name LIKE ? OR cu.phone LIKE ? OR cu.username LIKE ?)")
        params.extend([like, like, like])
    if q:
        where.append(_fts_subquery(q))
        params.extend(_fts_params(q))
    if cursor:
        try:
            cur_ts, cur_id = cursor.rsplit("|", 1)
            where.append("(COALESCE(c.last_message_at, '') < ? OR "
                         "(COALESCE(c.last_message_at, '') = ? AND c.id < ?))")
            params.extend([cur_ts, cur_ts, int(cur_id)])
        except (ValueError, IndexError):
            pass
    sql = (
        "SELECT c.*, cu.name AS customer_name, cu.phone AS customer_phone,"
        " cu.lead_status AS lead_status, cu.status AS customer_status"
        " FROM crm_conversations c JOIN customers cu ON cu.id = c.customer_id"
        f" WHERE {' AND '.join(where)}"
        " ORDER BY COALESCE(c.last_message_at, '') DESC, c.id DESC"
        " LIMIT ? OFFSET ?"
    )
    params.extend([max(1, min(int(limit), 200)), max(0, int(offset))])
    items = _rows(conn.execute(sql, params))
    next_cursor = ""
    if items:
        last = items[-1]
        next_cursor = f"{last.get('last_message_at') or ''}|{last['id']}"
    return {"items": items, "next_cursor": next_cursor}


def _fts_subquery(q: str) -> str:
    if _fts5_ok:
        return ("c.id IN (SELECT m.conversation_id FROM crm_messages m"
                " JOIN crm_messages_fts f ON f.rowid = m.id"
                " WHERE crm_messages_fts MATCH ?)")
    return "c.id IN (SELECT m.conversation_id FROM crm_messages m WHERE m.text LIKE ?)"


def _fts_params(q: str) -> list:
    if _fts5_ok:
        # Экранируем спецсимволы FTS: ищем фразу целиком.
        return [f'"{q.replace(chr(34), " ")}"']
    return [f"%{q}%"]


def get_customer(customer_id: int) -> dict | None:
    """Карточка клиента: поля + идентичности + теги + счётчики."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if row is None:
        return None
    customer = dict(row)
    customer["utm"] = json.loads(customer.pop("utm_json") or "{}")
    customer["metadata"] = json.loads(customer.pop("metadata_json") or "{}")
    customer["identities"] = _rows(conn.execute(
        "SELECT channel, external_id, created_at FROM customer_identities WHERE customer_id = ?",
        (customer_id,),
    ))
    customer["tags"] = _rows(conn.execute(
        "SELECT t.id, t.name, t.color FROM tags t"
        " JOIN customer_tags ct ON ct.tag_id = t.id WHERE ct.customer_id = ?",
        (customer_id,),
    ))
    customer["counts"] = {
        "messages": conn.execute(
            "SELECT COUNT(*) c FROM crm_messages WHERE customer_id = ?", (customer_id,)
        ).fetchone()["c"],
        "conversations": conn.execute(
            "SELECT COUNT(*) c FROM crm_conversations WHERE customer_id = ?", (customer_id,)
        ).fetchone()["c"],
        "notes": conn.execute(
            "SELECT COUNT(*) c FROM customer_notes WHERE customer_id = ?", (customer_id,)
        ).fetchone()["c"],
        "open_tasks": conn.execute(
            "SELECT COUNT(*) c FROM customer_tasks WHERE customer_id = ? AND status = 'open'",
            (customer_id,),
        ).fetchone()["c"],
    }
    return customer


def find_conversation(channel: str, external_user_id: str) -> dict | None:
    row = get_conn().execute(
        "SELECT * FROM crm_conversations WHERE channel = ? AND external_user_id = ?",
        (channel, external_user_id),
    ).fetchone()
    return dict(row) if row else None


def get_messages(conversation_id: int, before_id: int | None = None, limit: int = 50) -> list[dict]:
    """История диалога с курсорной пагинацией назад (before_id — последний
    известный id с предыдущей страницы)."""
    conn = get_conn()
    sql = "SELECT * FROM crm_messages WHERE conversation_id = ?"
    params: list = [conversation_id]
    if before_id:
        sql += " AND id < ?"
        params.append(int(before_id))
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    rows = _rows(conn.execute(sql, params))
    rows.reverse()
    return rows


def search_messages(q: str, channel: str | None = None, customer_id: int | None = None,
                    limit: int = 50) -> list[dict]:
    """Полнотекстовый поиск по сообщениям (FTS5, при отсутствии — LIKE)."""
    conn = get_conn()
    if _fts5_ok:
        sql = ("SELECT m.* FROM crm_messages m"
               " JOIN crm_messages_fts f ON f.rowid = m.id"
               " WHERE crm_messages_fts MATCH ?")
        params: list = [f'"{q.replace(chr(34), " ")}"']
    else:
        sql = "SELECT m.* FROM crm_messages m WHERE m.text LIKE ?"
        params = [f"%{q}%"]
    if channel:
        sql += " AND m.channel = ?"
        params.append(channel)
    if customer_id:
        sql += " AND m.customer_id = ?"
        params.append(customer_id)
    sql += " ORDER BY m.id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 200)))
    return _rows(conn.execute(sql, params))


def customer_timeline(customer_id: int, limit: int = 200) -> list[dict]:
    """Единая лента клиента: сообщения, события AI, заметки и задачи по времени."""
    conn = get_conn()
    events: list[dict] = []
    for m in _rows(conn.execute(
        "SELECT id, direction, sender_type, text, created_at FROM crm_messages"
        " WHERE customer_id = ? ORDER BY id DESC LIMIT ?", (customer_id, limit),
    )):
        events.append({"type": "message", "ts": m["created_at"], **m})
    for e in _rows(conn.execute(
        "SELECT id, kind, detail_json, created_at FROM ai_events"
        " WHERE customer_id = ? ORDER BY id DESC LIMIT ?", (customer_id, limit),
    )):
        events.append({"type": "ai_event", "ts": e["created_at"],
                       "detail": json.loads(e.pop("detail_json") or "{}"), **e})
    for n in _rows(conn.execute(
        "SELECT id, author, text, created_at FROM customer_notes"
        " WHERE customer_id = ? ORDER BY id DESC LIMIT ?", (customer_id, limit),
    )):
        events.append({"type": "note", "ts": n["created_at"], **n})
    for t in _rows(conn.execute(
        "SELECT id, title, due_at, assignee, status, created_at, done_at FROM customer_tasks"
        " WHERE customer_id = ? ORDER BY id DESC LIMIT ?", (customer_id, limit),
    )):
        events.append({"type": "task", "ts": t["created_at"], **t})
    events.sort(key=lambda item: (item["ts"], item.get("id") or 0))
    return events[-limit:]


# --------- Карточка клиента: архив, заметки, задачи, теги, склейка ---------


def archive_customer(customer_id: int, actor: str = "system", reason: str = "") -> None:
    """Мягкое удаление: клиент уходит в архив, данные сохраняются."""
    conn = get_conn()
    now = _now()
    with _tx(conn):
        before = conn.execute(
            "SELECT status FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        conn.execute(
            "UPDATE customers SET status = 'archived', archived_at = ?, archived_by = ?,"
            " archive_reason = ?, updated_at = ? WHERE id = ?",
            (now, actor, reason, now, customer_id),
        )
    audit(actor, "archive", "customer", customer_id,
          before=dict(before) if before else None, after={"status": "archived"})


def add_note(customer_id: int, author: str, text: str) -> int:
    conn = get_conn()
    with _tx(conn):
        cur = conn.execute(
            "INSERT INTO customer_notes(customer_id, author, text, created_at) VALUES (?, ?, ?, ?)",
            (customer_id, author, text, _now()),
        )
        return int(cur.lastrowid)


def add_task(customer_id: int, title: str, due_at: str | None = None,
             assignee: str = "") -> int:
    conn = get_conn()
    with _tx(conn):
        cur = conn.execute(
            "INSERT INTO customer_tasks(customer_id, title, due_at, assignee, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (customer_id, title, due_at, assignee, _now()),
        )
        return int(cur.lastrowid)


def complete_task(task_id: int) -> None:
    conn = get_conn()
    with _tx(conn):
        conn.execute(
            "UPDATE customer_tasks SET status = 'done', done_at = ? WHERE id = ?",
            (_now(), task_id),
        )


def ensure_tag(name: str, color: str = "") -> int:
    conn = get_conn()
    with _tx(conn):
        conn.execute("INSERT OR IGNORE INTO tags(name, color) VALUES (?, ?)", (name, color))
        row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        return int(row["id"])


def assign_tag(customer_id: int, tag: str | int) -> None:
    tag_id = ensure_tag(tag) if isinstance(tag, str) else int(tag)
    conn = get_conn()
    with _tx(conn):
        conn.execute(
            "INSERT OR IGNORE INTO customer_tags(customer_id, tag_id) VALUES (?, ?)",
            (customer_id, tag_id),
        )


def unassign_tag(customer_id: int, tag: str | int) -> None:
    conn = get_conn()
    with _tx(conn):
        if isinstance(tag, str):
            row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
            if row is None:
                return
            tag_id = int(row["id"])
        else:
            tag_id = int(tag)
        # Служебная связка many-to-many: снятие тега не трогает данные клиента.
        conn.execute(
            "DELETE FROM customer_tags WHERE customer_id = ? AND tag_id = ?",
            (customer_id, tag_id),
        )


def merge_customers(primary_id: int, secondary_id: int, actor: str = "system") -> None:
    """Склейка дублей: вся история secondary перевешивается на primary,
    сам secondary архивируется с указанием причины."""
    if primary_id == secondary_id:
        return
    conn = get_conn()
    with _tx(conn):
        for table, column in (
            ("customer_identities", "customer_id"),
            ("crm_conversations", "customer_id"),
            ("crm_messages", "customer_id"),
            ("customer_notes", "customer_id"),
            ("customer_tasks", "customer_id"),
            ("ai_events", "customer_id"),
        ):
            conn.execute(
                f"UPDATE {table} SET {column} = ? WHERE {column} = ?",
                (primary_id, secondary_id),
            )
        # Теги перевешиваем с игнором конфликтов: дубль связки просто
        # останется на архивной карточке.
        conn.execute(
            "UPDATE OR IGNORE customer_tags SET customer_id = ? WHERE customer_id = ?",
            (primary_id, secondary_id),
        )
    archive_customer(secondary_id, actor=actor, reason=f"merged into {primary_id}")
    audit(actor, "merge", "customer", primary_id,
          before={"secondary_id": secondary_id}, after={"merged_into": primary_id})


# --------- Рассылки ---------


def create_broadcast(title: str, text: str, segment: dict | None = None,
                     created_by: str = "") -> int:
    conn = get_conn()
    with _tx(conn):
        cur = conn.execute(
            "INSERT INTO broadcasts(title, text, segment_json, created_by, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (title, text, json.dumps(segment or {}, ensure_ascii=False), created_by, _now()),
        )
        return int(cur.lastrowid)


def add_broadcast_recipient(broadcast_id: int, customer_id: int, channel: str,
                            external_user_id: str) -> tuple[int, bool]:
    conn = get_conn()
    with _tx(conn):
        cur = conn.execute(
            "INSERT OR IGNORE INTO broadcast_recipients(broadcast_id, customer_id, channel, external_user_id)"
            " VALUES (?, ?, ?, ?)",
            (broadcast_id, customer_id, channel, external_user_id),
        )
        if cur.rowcount == 1:
            return int(cur.lastrowid), False
        row = conn.execute(
            "SELECT id FROM broadcast_recipients WHERE broadcast_id = ? AND customer_id = ? AND channel = ?",
            (broadcast_id, customer_id, channel),
        ).fetchone()
        return int(row["id"]), True


def update_recipient_status(recipient_id: int, status: str, error: str | None = None) -> None:
    conn = get_conn()
    with _tx(conn):
        conn.execute(
            "UPDATE broadcast_recipients SET status = ?, error = ?, sent_at = ? WHERE id = ?",
            (status, error, _now() if status in ("sent", "delivered") else None, recipient_id),
        )


def update_broadcast_status(broadcast_id: int, status: str, **counters: int) -> None:
    conn = get_conn()
    sets = ["status = ?"]
    params: list = [status]
    if status == "sending":
        sets.append("started_at = ?")
        params.append(_now())
    if status in ("done", "failed"):
        sets.append("finished_at = ?")
        params.append(_now())
    for key in ("total", "delivered", "failed_count", "skipped"):
        if key in counters:
            sets.append(f"{key} = ?")
            params.append(int(counters[key]))
    params.append(broadcast_id)
    with _tx(conn):
        conn.execute(f"UPDATE broadcasts SET {', '.join(sets)} WHERE id = ?", params)


# --------- Миграция из legacy-таблицы conversations ---------


def migrate_from_legacy(conn: sqlite3.Connection | None = None) -> dict:
    """Однократный перенос истории из legacy `conversations` в CRM-таблицы.

    Идемпотентно: после успешного переноса ставится маркер в crm_meta.
    Legacy-таблица не изменяется — она остаётся состоянием для AI.
    """
    conn = conn or get_conn()
    with _tx(conn):
        marked = conn.execute(
            "SELECT value FROM crm_meta WHERE key = ?", (_MIGRATION_KEY,)
        ).fetchone()
        if marked:
            return {"skipped": True, "reason": "already migrated"}
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'conversations'"
        ).fetchone()
        if table is None:
            conn.execute(
                "INSERT OR REPLACE INTO crm_meta(key, value) VALUES (?, ?)",
                (_MIGRATION_KEY, _now()),
            )
            return {"skipped": True, "reason": "no legacy table"}

        rows = conn.execute("SELECT platform, user_id, payload FROM conversations").fetchall()
        report = {
            "legacy_conversations": len(rows),
            "legacy_messages": 0,
            "customers_before": _count(conn, "customers"),
            "conversations_before": _count(conn, "crm_conversations"),
            "messages_before": _count(conn, "crm_messages"),
            "skipped_existing": 0,
        }
        now = _now()
        for row in rows:
            try:
                data = json.loads(row["payload"])
            except (json.JSONDecodeError, TypeError):
                logger.warning("crm-migrate: битый payload у %s/%s", row["platform"], row["user_id"])
                continue
            _migrate_one(conn, row["platform"], row["user_id"], data, report, now)
        conn.execute(
            "INSERT OR REPLACE INTO crm_meta(key, value) VALUES (?, ?)",
            (_MIGRATION_KEY, now),
        )
        if _fts5_ok:
            # На случай рассинхрона индекса перестраиваем его целиком.
            conn.execute("INSERT INTO crm_messages_fts(crm_messages_fts) VALUES('rebuild')")
        report.update(
            customers_after=_count(conn, "customers"),
            conversations_after=_count(conn, "crm_conversations"),
            messages_after=_count(conn, "crm_messages"),
        )
        return report


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"])


def _migrate_one(conn: sqlite3.Connection, platform: str, user_id: str,
                 data: dict, report: dict, now: str) -> None:
    lead = data.get("lead") or {}
    utm = data.get("utm") or {}
    customer_id = upsert_customer_for_identity(
        platform,
        user_id,
        name=lead.get("fio_parent") or data.get("client_name", ""),
        username=data.get("max_username", ""),
        phone=lead.get("phone", ""),
        email=lead.get("email", ""),
        child_name=lead.get("fio_child", ""),
        child_age=lead.get("age", ""),
        source=utm.get("utm_source", ""),
        utm=utm,
        interests=data.get("selected_course") or lead.get("course", ""),
        notes=lead.get("comment", ""),
    )
    if data.get("lead_submitted"):
        conn.execute(
            "UPDATE customers SET lead_status = 'client' WHERE id = ? AND lead_status = 'new'",
            (customer_id,),
        )
    conv_id = get_or_create_conversation(customer_id, platform, user_id)
    ai_mode = "manager" if data.get("handed_off") else "active"
    conn.execute(
        "UPDATE crm_conversations SET ai_mode = ? WHERE id = ? AND ai_mode = 'active'",
        (ai_mode, conv_id),
    )
    transcript = data.get("transcript") or []
    report["legacy_messages"] += len(transcript)
    if not transcript:
        return
    existing = conn.execute(
        "SELECT COUNT(*) c FROM crm_messages WHERE conversation_id = ?", (conv_id,)
    ).fetchone()["c"]
    if existing:
        # Диалог уже перенесён (например, миграцию запускали вручную):
        # не дублируем сообщения.
        report["skipped_existing"] += len(transcript)
        return
    for item in transcript:
        role = str(item.get("role", "user"))
        if role == "user":
            direction, sender_type = "in", "customer"
        elif role in ("assistant", "bot"):
            direction, sender_type = "out", "ai"
        else:
            direction, sender_type = "out", "system"
        ts = str(item.get("ts") or "")
        try:
            datetime.fromisoformat(ts)
        except ValueError:
            ts = now
        add_message(
            conv_id, customer_id, platform, direction, sender_type,
            str(item.get("content", "")), status="delivered", created_at=ts,
        )


# --------- Запросы для админки (Этапы 5-7) ---------


def get_conversation(conversation_id: int) -> dict | None:
    row = get_conn().execute(
        "SELECT * FROM crm_conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    return dict(row) if row else None


# Поля карточки клиента, которые менеджер может править из админки.
_CUSTOMER_EDITABLE = (
    "name", "first_name", "last_name", "username", "phone", "email",
    "child_name", "child_age", "lead_status", "manager", "notes",
    "interests", "source", "status",
)


def update_customer(customer_id: int, fields: dict, actor: str = "admin") -> bool:
    """Точечное редактирование карточки. Только поля из белого списка."""
    conn = get_conn()
    updates = {k: str(v) for k, v in fields.items() if k in _CUSTOMER_EDITABLE and v is not None}
    if not updates:
        return False
    with _tx(conn):
        before = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if before is None:
            return False
        sets = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE customers SET {sets}, updated_at = ? WHERE id = ?",
            [*updates.values(), _now(), customer_id],
        )
    audit(actor, "update", "customer", customer_id,
          before={k: before[k] for k in updates}, after=updates)
    return True


def unarchive_customer(customer_id: int, actor: str = "admin") -> None:
    conn = get_conn()
    with _tx(conn):
        conn.execute(
            "UPDATE customers SET status = 'active', archived_at = NULL,"
            " archived_by = NULL, archive_reason = NULL, updated_at = ? WHERE id = ?",
            (_now(), customer_id),
        )
    audit(actor, "unarchive", "customer", customer_id, after={"status": "active"})


def list_customers(
    search: str | None = None,
    lead_status: str | None = None,
    status: str | None = None,
    channel: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    conn = get_conn()
    where: list[str] = ["1=1"]
    params: list = []
    if status:
        where.append("c.status = ?")
        params.append(status)
    else:
        where.append("c.status != 'archived'")
    if lead_status:
        where.append("c.lead_status = ?")
        params.append(lead_status)
    if search:
        like = f"%{search}%"
        where.append("(c.name LIKE ? OR c.phone LIKE ? OR c.username LIKE ? OR c.child_name LIKE ?)")
        params.extend([like, like, like, like])
    if channel:
        where.append("c.id IN (SELECT customer_id FROM customer_identities WHERE channel = ?)")
        params.append(channel)
    if date_from:
        where.append("c.last_seen_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("c.last_seen_at <= ?")
        params.append(date_to)
    base = f"FROM customers c WHERE {' AND '.join(where)}"
    total = conn.execute(f"SELECT COUNT(*) c {base}", params).fetchone()["c"]
    items = _rows(conn.execute(
        f"SELECT c.* {base} ORDER BY c.last_seen_at DESC, c.id DESC LIMIT ? OFFSET ?",
        [*params, max(1, min(int(limit), 200)), max(0, int(offset))],
    ))
    for item in items:
        item["channels"] = [r["channel"] for r in conn.execute(
            "SELECT DISTINCT channel FROM customer_identities WHERE customer_id = ?",
            (item["id"],),
        ).fetchall()]
    return {"items": items, "total": total}


def list_notes(customer_id: int) -> list[dict]:
    return _rows(get_conn().execute(
        "SELECT * FROM customer_notes WHERE customer_id = ? ORDER BY id DESC LIMIT 200",
        (customer_id,),
    ))


def list_tasks(customer_id: int, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM customer_tasks WHERE customer_id = ?"
    params: list = [customer_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    return _rows(get_conn().execute(sql + " ORDER BY id DESC LIMIT 200", params))


def list_all_tags() -> list[dict]:
    return _rows(get_conn().execute("SELECT * FROM tags ORDER BY name"))


def list_ai_events(kind: str | None = None, days: int = 7, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM ai_events WHERE created_at >= datetime('now', ?)"
    params: list = [f"-{max(1, int(days))} days"]
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    return _rows(get_conn().execute(sql, params))


def pop_pending_web_messages(session_id: str) -> list[dict]:
    """Недоставленные ответы менеджера для веб-виджета.

    Виджет — request/response, push нет: менеджерские реплики копятся со
    статусом pending и отдаются поллингу, после чего становятся delivered.
    """
    conn = get_conn()
    with _tx(conn):
        conv = conn.execute(
            "SELECT id FROM crm_conversations WHERE channel = 'web' AND external_user_id = ?",
            (f"web:{session_id}",),
        ).fetchone()
        if conv is None:
            return []
        rows = _rows(conn.execute(
            "SELECT id, text, created_at FROM crm_messages"
            " WHERE conversation_id = ? AND sender_type = 'manager' AND status = 'pending'"
            " ORDER BY id",
            (conv["id"],),
        ))
        if rows:
            ids = ",".join(str(r["id"]) for r in rows)
            conn.execute(f"UPDATE crm_messages SET status = 'delivered' WHERE id IN ({ids})")
        return rows


def stats_today() -> dict:
    """Сводка для дашборда: сегодня / 7д / 30д, каналы, события AI."""
    conn = get_conn()

    def _scalar(sql: str, params: tuple = ()) -> int:
        return int(conn.execute(sql, params).fetchone()["c"])

    return {
        "new_customers": {
            "today": _scalar("SELECT COUNT(*) c FROM customers WHERE first_seen_at >= date('now')"),
            "d7": _scalar("SELECT COUNT(*) c FROM customers WHERE first_seen_at >= datetime('now', '-7 days')"),
            "d30": _scalar("SELECT COUNT(*) c FROM customers WHERE first_seen_at >= datetime('now', '-30 days')"),
        },
        "customers_total": _scalar("SELECT COUNT(*) c FROM customers WHERE status != 'archived'"),
        "active_conversations": _scalar(
            "SELECT COUNT(*) c FROM crm_conversations WHERE status = 'active'"),
        "unread_conversations": _scalar(
            "SELECT COUNT(*) c FROM crm_conversations WHERE unread_count > 0 AND status = 'active'"),
        "messages_today": {
            "in": _scalar("SELECT COUNT(*) c FROM crm_messages"
                          " WHERE direction = 'in' AND created_at >= date('now')"),
            "out": _scalar("SELECT COUNT(*) c FROM crm_messages"
                           " WHERE direction = 'out' AND created_at >= date('now')"),
        },
        "by_channel": _rows(conn.execute(
            "SELECT channel, COUNT(*) c FROM crm_messages"
            " WHERE created_at >= date('now') GROUP BY channel")),
        "ai_events_today": {
            "handoff": _scalar("SELECT COUNT(*) c FROM ai_events"
                               " WHERE kind = 'handoff' AND created_at >= date('now')"),
            "no_answer": _scalar("SELECT COUNT(*) c FROM ai_events"
                                 " WHERE kind = 'no_answer' AND created_at >= date('now')"),
        },
    }


def inbound_events_health(hours: int = 24) -> list[dict]:
    """События за сутки по статусам — индикатор здоровья ingestion."""
    return _rows(get_conn().execute(
        "SELECT status, COUNT(*) c FROM inbound_events"
        " WHERE received_at >= datetime('now', ?) GROUP BY status",
        (f"-{max(1, int(hours))} hours",),
    ))


# --------- Этап 8: сегменты и Broadcast Center ---------


def init_segments_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            rules_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        );
        """
    )
    # retry_count дорос позже создания таблицы: старые базы догоняем ALTER'ом.
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(broadcast_recipients)")}
    if "retry_count" not in cols:
        conn.execute(
            "ALTER TABLE broadcast_recipients ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"
        )


def save_segment(name: str, rules: list[dict]) -> int:
    conn = get_conn()
    with _tx(conn):
        conn.execute(
            "INSERT INTO segments(name, rules_json, created_at) VALUES (?, ?, ?)"
            " ON CONFLICT(name) DO UPDATE SET rules_json = excluded.rules_json",
            (name, json.dumps(rules, ensure_ascii=False), _now()),
        )
        row = conn.execute("SELECT id FROM segments WHERE name = ?", (name,)).fetchone()
        return int(row["id"])


def list_segments() -> list[dict]:
    items = _rows(get_conn().execute("SELECT * FROM segments ORDER BY name"))
    for item in items:
        item["rules"] = json.loads(item.pop("rules_json") or "[]")
    return items


def get_segment(segment_id: int) -> dict | None:
    row = get_conn().execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["rules"] = json.loads(item.pop("rules_json") or "[]")
    return item


def delete_segment(segment_id: int) -> None:
    # Служебный справочник (не клиентские данные): удаление допустимо.
    conn = get_conn()
    with _tx(conn):
        conn.execute("DELETE FROM segments WHERE id = ?", (segment_id,))


def _age_value(raw: str) -> int | None:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    return int(digits) if digits else None


def _rule_matches(rule: dict, customer: sqlite3.Row, tags: set[str], channels: set[str]) -> bool:
    """Одно условие сегмента. Неизвестное поле — не матч (лучше пустая
    выборка, чем рассылка «всем» из-за опечатки в правиле)."""
    field = str(rule.get("field", ""))
    op = str(rule.get("op", "eq"))
    value = rule.get("value")
    if field == "channel":
        return str(value) in channels
    if field == "tag":
        return str(value) in tags
    if field in ("lead_status", "status"):
        return customer[field] == str(value)
    if field == "child_age":
        age = _age_value(customer["child_age"])
        if age is None:
            return False
        if isinstance(value, dict):
            lo = _age_value(str(value.get("from", "")))
            hi = _age_value(str(value.get("to", "")))
            if lo is not None and age < lo:
                return False
            if hi is not None and age > hi:
                return False
            return True
        target = _age_value(str(value))
        if target is None:
            return False
        if op == "gte":
            return age >= target
        if op == "lte":
            return age <= target
        return age == target
    if field in ("date_first_seen", "date_last_seen"):
        actual = customer["first_seen_at" if field == "date_first_seen" else "last_seen_at"]
        if isinstance(value, dict):
            if value.get("from") and actual < str(value["from"]):
                return False
            if value.get("to") and actual > str(value["to"]):
                return False
            return True
        return actual >= str(value)
    if field in ("course", "branch", "source"):
        haystack = " ".join([
            customer["interests"], customer["source"],
            customer["utm_json"], customer["metadata_json"],
        ]).lower()
        return str(value).lower() in haystack
    if field == "search":
        haystack = " ".join([
            customer["name"], customer["phone"], customer["username"],
            customer["child_name"],
        ]).lower()
        return str(value).lower() in haystack
    return False


# Каналы с настоящим push. У web-виджета исходящих нет — он не звонит первым.
_PUSH_CHANNELS = ("max", "telegram")


def resolve_segment(rules: list[dict] | None) -> dict:
    """Разворачивает правила сегмента в список получателей.

    На клиента — один лучший канал: приоритет каналу последнего контакта
    (max last_message_at). Клиенты, у которых есть только веб-виджет,
    попадают в skipped_web (push у виджета нет).
    """
    conn = get_conn()
    rules = rules or []
    recipients: list[dict] = []
    skipped_web = 0
    customers = conn.execute("SELECT * FROM customers WHERE status != 'archived'").fetchall()
    for customer in customers:
        cid = int(customer["id"])
        tags = {r["name"] for r in conn.execute(
            "SELECT t.name FROM tags t JOIN customer_tags ct ON ct.tag_id = t.id"
            " WHERE ct.customer_id = ?", (cid,)).fetchall()}
        channels = {r["channel"] for r in conn.execute(
            "SELECT DISTINCT channel FROM customer_identities WHERE customer_id = ?",
            (cid,)).fetchall()}
        if not all(_rule_matches(rule, customer, tags, channels) for rule in rules):
            continue
        # Лучший канал: диалог с самым свежим сообщением среди push-каналов.
        conv = conn.execute(
            "SELECT channel, external_user_id FROM crm_conversations"
            " WHERE customer_id = ? AND channel IN ('max', 'telegram')"
            " ORDER BY COALESCE(last_message_at, '') DESC, id DESC LIMIT 1",
            (cid,),
        ).fetchone()
        if conv is not None:
            recipients.append({
                "customer_id": cid, "name": customer["name"],
                "channel": conv["channel"], "external_user_id": conv["external_user_id"],
            })
            continue
        # Диалога в push-канале нет — пробуем голую идентичность.
        identity = conn.execute(
            "SELECT channel, external_id FROM customer_identities"
            " WHERE customer_id = ? AND channel IN ('max', 'telegram')"
            " ORDER BY id LIMIT 1",
            (cid,),
        ).fetchone()
        if identity is not None:
            recipients.append({
                "customer_id": cid, "name": customer["name"],
                "channel": identity["channel"], "external_user_id": identity["external_id"],
            })
        elif "web" in channels:
            skipped_web += 1
    return {"recipients": recipients, "skipped_web": skipped_web}


def list_broadcasts(limit: int = 50, offset: int = 0) -> list[dict]:
    return _rows(get_conn().execute(
        "SELECT * FROM broadcasts ORDER BY id DESC LIMIT ? OFFSET ?",
        (max(1, min(int(limit), 200)), max(0, int(offset))),
    ))


def get_broadcast(broadcast_id: int) -> dict | None:
    row = get_conn().execute("SELECT * FROM broadcasts WHERE id = ?", (broadcast_id,)).fetchone()
    return dict(row) if row else None


def list_recipients(broadcast_id: int, status: str | None = None,
                    limit: int = 100, offset: int = 0) -> list[dict]:
    sql = ("SELECT r.*, c.name AS customer_name FROM broadcast_recipients r"
           " LEFT JOIN customers c ON c.id = r.customer_id WHERE r.broadcast_id = ?")
    params: list = [broadcast_id]
    if status:
        sql += " AND r.status = ?"
        params.append(status)
    sql += " ORDER BY r.id LIMIT ? OFFSET ?"
    params.extend([max(1, min(int(limit), 500)), max(0, int(offset))])
    return _rows(get_conn().execute(sql, params))


def get_recipient(recipient_id: int) -> dict | None:
    row = get_conn().execute(
        "SELECT * FROM broadcast_recipients WHERE id = ?", (recipient_id,)).fetchone()
    return dict(row) if row else None


def fill_recipients(broadcast_id: int, recipients: list[dict]) -> int:
    """Заполняет получателей. UNIQUE(broadcast_id, customer_id, channel)
    защищает от двойного запуска: повторное заполнение вернёт меньше строк."""
    conn = get_conn()
    added = 0
    with _tx(conn):
        for rec in recipients:
            _, is_new = add_broadcast_recipient(
                broadcast_id, rec["customer_id"], rec["channel"], rec["external_user_id"])
            added += 0 if is_new else 1
        conn.execute(
            "UPDATE broadcasts SET total = ? WHERE id = ?", (added, broadcast_id))
    return added


# --------- Этап 9: воронка и экспорт ---------


def pipeline() -> dict:
    """Клиенты, сгруппированные по lead_status (для kanban-доски)."""
    conn = get_conn()
    items = _rows(conn.execute(
        """
        SELECT c.id, c.name, c.phone, c.lead_status, c.interests, c.manager,
               c.last_seen_at,
               (SELECT MAX(cv.last_message_at) FROM crm_conversations cv
                 WHERE cv.customer_id = c.id) AS last_message_at,
               (SELECT cv.channel FROM crm_conversations cv
                 WHERE cv.customer_id = c.id
                 ORDER BY COALESCE(cv.last_message_at, '') DESC LIMIT 1) AS channel
        FROM customers c
        WHERE c.status != 'archived'
        ORDER BY last_message_at DESC NULLS LAST
        """
    ))
    stages = ["new", "contacted", "qualified", "trial", "offer", "payment", "client", "lost"]
    # Нестандартные/пустые статусы уводим в колонку new.
    board: dict[str, list[dict]] = {stage: [] for stage in stages}
    for item in items:
        stage = item["lead_status"] if item["lead_status"] in board else "new"
        board[stage].append(item)
    return {"stages": stages, "board": board}


def export_customers_rows(limit: int = 50000) -> list[dict]:
    return _rows(get_conn().execute(
        """
        SELECT c.id, c.name, c.phone, c.email, c.child_name, c.child_age,
               c.lead_status, c.status, c.source, c.manager, c.interests,
               c.first_seen_at, c.last_seen_at,
               (SELECT GROUP_CONCAT(DISTINCT i.channel) FROM customer_identities i
                 WHERE i.customer_id = c.id) AS channels
        FROM customers c ORDER BY c.id LIMIT ?
        """,
        (int(limit),),
    ))


def export_messages_rows(date_from: str | None = None, date_to: str | None = None,
                         limit: int = 50000) -> list[dict]:
    sql = ("SELECT m.id, m.created_at, m.channel, m.direction, m.sender_type,"
           " m.status, m.customer_id, m.conversation_id, m.text"
           " FROM crm_messages m WHERE 1=1")
    params: list = []
    if date_from:
        sql += " AND m.created_at >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND m.created_at <= ?"
        params.append(date_to)
    sql += " ORDER BY m.id LIMIT ?"
    params.append(int(limit))
    return _rows(get_conn().execute(sql, params))


# --------- Этапы 10-12: база знаний, промпты, аналитика, ошибки ---------


def init_kb_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS kb_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '',
            text TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'custom',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ai_prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'system',
            content TEXT NOT NULL,
            version INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 0,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        """
    )


def kb_add(title: str, text: str, category: str = "custom") -> int:
    conn = get_conn()
    with _tx(conn):
        cur = conn.execute(
            "INSERT INTO kb_documents(title, text, category, enabled, created_at, updated_at)"
            " VALUES (?, ?, ?, 1, ?, ?)",
            (title, text, category, _now(), _now()),
        )
        return int(cur.lastrowid)


def kb_update(doc_id: int, fields: dict) -> bool:
    conn = get_conn()
    allowed = {k: v for k, v in fields.items()
               if k in ("title", "text", "category", "enabled") and v is not None}
    if not allowed:
        return False
    if "enabled" in allowed:
        allowed["enabled"] = 1 if allowed["enabled"] else 0
    with _tx(conn):
        sets = ", ".join(f"{key} = ?" for key in allowed)
        cur = conn.execute(
            f"UPDATE kb_documents SET {sets}, updated_at = ? WHERE id = ?",
            [*allowed.values(), _now(), doc_id],
        )
        return cur.rowcount == 1


def kb_list(enabled_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM kb_documents"
    if enabled_only:
        sql += " WHERE enabled = 1"
    return _rows(get_conn().execute(sql + " ORDER BY id DESC"))


def prompt_active() -> dict | None:
    return (lambda r: dict(r) if r else None)(get_conn().execute(
        "SELECT * FROM ai_prompts WHERE active = 1 ORDER BY version DESC LIMIT 1"
    ).fetchone())


def prompt_seed(content: str, name: str = "system") -> int:
    """Первая версия промпта из кода — чтобы откат всегда был на что."""
    conn = get_conn()
    with _tx(conn):
        row = conn.execute("SELECT COUNT(*) c FROM ai_prompts").fetchone()
        if row["c"]:
            existing = prompt_active()
            return int(existing["id"]) if existing else 0
        cur = conn.execute(
            "INSERT INTO ai_prompts(name, content, version, active, created_by, created_at)"
            " VALUES (?, ?, 1, 1, 'seed', ?)",
            (name, content, _now()),
        )
        return int(cur.lastrowid)


def prompt_add(content: str, name: str = "system", created_by: str = "admin") -> int:
    conn = get_conn()
    with _tx(conn):
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) v FROM ai_prompts WHERE name = ?", (name,)
        ).fetchone()
        cur = conn.execute(
            "INSERT INTO ai_prompts(name, content, version, active, created_by, created_at)"
            " VALUES (?, ?, ?, 0, ?, ?)",
            (name, content, int(row["v"]) + 1, created_by, _now()),
        )
        return int(cur.lastrowid)


def prompt_activate(prompt_id: int, actor: str = "admin") -> bool:
    conn = get_conn()
    with _tx(conn):
        target = conn.execute("SELECT * FROM ai_prompts WHERE id = ?", (prompt_id,)).fetchone()
        if target is None:
            return False
        conn.execute("UPDATE ai_prompts SET active = 0 WHERE name = ?", (target["name"],))
        conn.execute("UPDATE ai_prompts SET active = 1 WHERE id = ?", (prompt_id,))
    audit(actor, "activate", "ai_prompt", prompt_id,
          after={"version": target["version"], "name": target["name"]})
    return True


def prompt_list(name: str = "system") -> list[dict]:
    return _rows(get_conn().execute(
        "SELECT id, name, version, active, created_by, created_at,"
        " substr(content, 1, 120) AS preview, length(content) AS chars"
        " FROM ai_prompts WHERE name = ? ORDER BY version DESC", (name,)))


def prompt_get(prompt_id: int) -> dict | None:
    row = get_conn().execute("SELECT * FROM ai_prompts WHERE id = ?", (prompt_id,)).fetchone()
    return dict(row) if row else None


def analytics(days: int = 30) -> dict:
    """Агрегаты для раздела «Аналитика»: ряды по дням, каналы, лиды, AI,
    рассылки. Всё из crm_* таблиц за выбранный период."""
    conn = get_conn()
    days = max(1, min(int(days), 365))
    since = f"-{days} days"

    daily_customers = _rows(conn.execute(
        "SELECT substr(first_seen_at, 1, 10) AS day, COUNT(*) c FROM customers"
        " WHERE first_seen_at >= datetime('now', ?) GROUP BY day ORDER BY day", (since,)))
    daily_messages = _rows(conn.execute(
        "SELECT substr(created_at, 1, 10) AS day, direction, sender_type, COUNT(*) c"
        " FROM crm_messages WHERE created_at >= datetime('now', ?)"
        " GROUP BY day, direction, sender_type ORDER BY day", (since,)))
    daily_conversations = _rows(conn.execute(
        "SELECT substr(created_at, 1, 10) AS day, COUNT(*) c FROM crm_conversations"
        " WHERE created_at >= datetime('now', ?) GROUP BY day ORDER BY day", (since,)))

    by_channel = _rows(conn.execute(
        "SELECT channel, COUNT(*) messages FROM crm_messages"
        " WHERE created_at >= datetime('now', ?) GROUP BY channel", (since,)))
    convs_by_channel = _rows(conn.execute(
        "SELECT channel, COUNT(*) c FROM crm_conversations GROUP BY channel"))
    customers_by_channel = _rows(conn.execute(
        "SELECT channel, COUNT(DISTINCT customer_id) c FROM customer_identities"
        " GROUP BY channel"))

    leads = _rows(conn.execute(
        "SELECT lead_status, COUNT(*) c FROM customers WHERE status != 'archived'"
        " GROUP BY lead_status"))
    new_leads = conn.execute(
        "SELECT COUNT(*) c FROM customers WHERE first_seen_at >= datetime('now', ?)",
        (since,)).fetchone()["c"]

    ai_out = conn.execute(
        "SELECT COUNT(*) c FROM crm_messages WHERE direction = 'out'"
        " AND sender_type = 'ai' AND created_at >= datetime('now', ?)", (since,)).fetchone()["c"]
    manager_out = conn.execute(
        "SELECT COUNT(*) c FROM crm_messages WHERE direction = 'out'"
        " AND sender_type = 'manager' AND created_at >= datetime('now', ?)", (since,)).fetchone()["c"]
    events = {r["kind"]: r["c"] for r in conn.execute(
        "SELECT kind, COUNT(*) c FROM ai_events WHERE created_at >= datetime('now', ?)"
        " GROUP BY kind", (since,)).fetchall()}
    avg_len = conn.execute(
        "SELECT AVG(cnt) a FROM (SELECT COUNT(*) cnt FROM crm_messages"
        " WHERE created_at >= datetime('now', ?) GROUP BY conversation_id)",
        (since,)).fetchone()["a"]
    repeat = conn.execute(
        "SELECT COUNT(*) c FROM (SELECT customer_id FROM crm_messages"
        " WHERE created_at >= datetime('now', ?) AND direction = 'in'"
        " GROUP BY customer_id HAVING COUNT(DISTINCT substr(created_at, 1, 10)) > 1)",
        (since,)).fetchone()["c"]

    broadcasts = conn.execute(
        "SELECT COUNT(*) c, COALESCE(SUM(delivered), 0) d,"
        " COALESCE(SUM(failed_count), 0) f, COALESCE(SUM(total), 0) t"
        " FROM broadcasts WHERE created_at >= datetime('now', ?)", (since,)).fetchone()

    return {
        "days": days,
        "daily": {
            "customers": daily_customers,
            "messages": daily_messages,
            "conversations": daily_conversations,
        },
        "channels": {
            "messages": by_channel,
            "conversations": convs_by_channel,
            "customers": customers_by_channel,
        },
        "leads": {"by_status": leads, "new_in_period": new_leads},
        "ai": {
            "ai_messages": ai_out,
            "manager_messages": manager_out,
            "ai_share": round(ai_out / (ai_out + manager_out), 3) if ai_out + manager_out else None,
            "handoff": events.get("handoff", 0),
            "no_answer": events.get("no_answer", 0),
            "errors": events.get("error", 0),
            "avg_conversation_length": round(float(avg_len), 1) if avg_len else 0,
            "repeat_customers": repeat,
        },
        "broadcasts": {
            "count": broadcasts["c"], "total": broadcasts["t"],
            "delivered": broadcasts["d"], "failed": broadcasts["f"],
        },
    }


def errors_feed(days: int = 7, category: str | None = None, limit: int = 100) -> list[dict]:
    """Единая лента ошибок: AI-события, ingestion, рассылки, недоставленные
    исходящие. category фильтрует: ai / ingestion / broadcast / channel."""
    conn = get_conn()
    since = f"-{max(1, int(days))} days"
    items: list[dict] = []
    if category in (None, "ai"):
        for r in conn.execute(
            "SELECT id, kind, detail_json, created_at, customer_id, conversation_id"
            " FROM ai_events WHERE kind IN ('error', 'no_answer', 'fallback')"
            " AND created_at >= datetime('now', ?) ORDER BY id DESC LIMIT ?",
            (since, limit),
        ).fetchall():
            items.append({"category": "ai", "kind": r["kind"], "id": r["id"],
                          "ts": r["created_at"], "customer_id": r["customer_id"],
                          "conversation_id": r["conversation_id"],
                          "detail": json.loads(r["detail_json"] or "{}")})
    if category in (None, "ingestion"):
        for r in conn.execute(
            "SELECT id, channel, external_event_id, error, received_at"
            " FROM inbound_events WHERE status = 'failed'"
            " AND received_at >= datetime('now', ?) ORDER BY id DESC LIMIT ?",
            (since, limit),
        ).fetchall():
            items.append({"category": "ingestion", "kind": "inbound_failed", "id": r["id"],
                          "ts": r["received_at"], "channel": r["channel"],
                          "detail": {"event": r["external_event_id"], "error": r["error"]}})
    if category in (None, "broadcast"):
        for r in conn.execute(
            "SELECT id, broadcast_id, customer_id, channel, error, retry_count"
            " FROM broadcast_recipients WHERE status = 'failed' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall():
            items.append({"category": "broadcast", "kind": "recipient_failed", "id": r["id"],
                          "broadcast_id": r["broadcast_id"], "customer_id": r["customer_id"],
                          "channel": r["channel"], "retry_count": r["retry_count"],
                          "ts": "", "detail": {"error": r["error"]}})
    if category in (None, "channel"):
        for r in conn.execute(
            "SELECT id, conversation_id, customer_id, channel, error, created_at"
            " FROM crm_messages WHERE direction = 'out' AND status = 'failed'"
            " AND created_at >= datetime('now', ?) ORDER BY id DESC LIMIT ?",
            (since, limit),
        ).fetchall():
            items.append({"category": "channel", "kind": "message_failed", "id": r["id"],
                          "ts": r["created_at"], "channel": r["channel"],
                          "conversation_id": r["conversation_id"],
                          "customer_id": r["customer_id"],
                          "detail": {"error": r["error"]}})
    items.sort(key=lambda item: item.get("ts") or "", reverse=True)
    return items[:limit]


# --------- Этап 13: RBAC (пользователи админки и сессии) ---------


def init_rbac_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'manager',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS admin_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES admin_users(id),
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        """
    )


def _hash_password(password: str, salt: bytes | None = None) -> str:
    """scrypt из stdlib hashlib — без новых зависимостей. Формат:
    scrypt$n$r$p$salt_hex$hash_hex."""
    import hashlib

    salt = salt or os.urandom(16)
    n, r, p = 16384, 8, 1
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p)
    return f"scrypt${n}${r}${p}${salt.hex()}${digest.hex()}"


def _check_password(password: str, stored: str) -> bool:
    import hashlib

    try:
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def admin_user_create(username: str, password: str, role: str = "manager") -> int:
    conn = get_conn()
    with _tx(conn):
        cur = conn.execute(
            "INSERT INTO admin_users(username, password_hash, role, created_at)"
            " VALUES (?, ?, ?, ?)",
            (username.strip(), _hash_password(password), role, _now()),
        )
        return int(cur.lastrowid)


def admin_user_verify(username: str, password: str) -> dict | None:
    """Проверка логина/пароля. Возвращает {id, username, role} или None."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM admin_users WHERE username = ? AND active = 1",
        (username.strip(),),
    ).fetchone()
    if row is None or not _check_password(password, row["password_hash"]):
        return None
    with _tx(conn):
        conn.execute(
            "UPDATE admin_users SET last_login_at = ? WHERE id = ?",
            (_now(), row["id"]),
        )
    return {"id": int(row["id"]), "username": row["username"], "role": row["role"]}


def admin_user_list() -> list[dict]:
    return _rows(get_conn().execute(
        "SELECT id, username, role, active, created_at, last_login_at"
        " FROM admin_users ORDER BY username"))


def admin_user_update(user_id: int, fields: dict) -> bool:
    """role/active/сброс пароля. Пароль приходит открытым — хранится хэш."""
    conn = get_conn()
    updates: dict = {}
    if fields.get("role"):
        updates["role"] = str(fields["role"])
    if fields.get("active") is not None:
        updates["active"] = 1 if fields["active"] else 0
    if fields.get("password"):
        updates["password_hash"] = _hash_password(str(fields["password"]))
    if not updates:
        return False
    with _tx(conn):
        sets = ", ".join(f"{key} = ?" for key in updates)
        cur = conn.execute(
            f"UPDATE admin_users SET {sets} WHERE id = ?", [*updates.values(), user_id])
        return cur.rowcount == 1


def session_create(user_id: int, hours: int = 24 * 7) -> str:
    import secrets

    token = secrets.token_hex(32)
    conn = get_conn()
    with _tx(conn):
        conn.execute(
            "INSERT INTO admin_sessions(token, user_id, created_at, expires_at)"
            " VALUES (?, ?, ?, datetime('now', ?))",
            (token, user_id, _now(), f"+{hours} hours"),
        )
    return token


def session_get(token: str) -> dict | None:
    """Сессия с пользователем, если не истекла и пользователь активен."""
    if not token:
        return None
    row = get_conn().execute(
        "SELECT s.token, u.id AS user_id, u.username, u.role FROM admin_sessions s"
        " JOIN admin_users u ON u.id = s.user_id"
        " WHERE s.token = ? AND s.expires_at > datetime('now') AND u.active = 1",
        (token,),
    ).fetchone()
    return dict(row) if row else None


def session_delete(token: str) -> None:
    conn = get_conn()
    with _tx(conn):
        conn.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))


def seed_bootstrap_admin() -> None:
    """Первый пользователь админки: admin / ADMIN_BOOTSTRAP_PASSWORD или
    случайный пароль (печатается в лог ОДИН раз с требованием сменить)."""
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) c FROM admin_users").fetchone()
    if row["c"]:
        return
    import secrets

    from app.config import settings as _settings

    password = getattr(_settings, "ADMIN_BOOTSTRAP_PASSWORD", "") or secrets.token_urlsafe(12)
    admin_user_create("admin", password, role="super_admin")
    logger.warning(
        "Создан первый пользователь админки: логин admin, пароль %s — "
        "смените его после первого входа (или задайте ADMIN_BOOTSTRAP_PASSWORD)",
        password,
    )
