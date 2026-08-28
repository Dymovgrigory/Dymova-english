"""Продуктовая аналитика: единая шина событий воронки (§105–§108).

События приходят с сайта (виджет расписания, страницы) и от серверных
процессов (booking completed, lead created). Хранилище — та же SQLite,
таблица product_events; схема события: event, timestamp, source, sessionId,
anonymousId, metadata. Никаких PII в metadata: телефоны/имена не пишем.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS product_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    event TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'site',
    session_id TEXT NOT NULL DEFAULT '',
    anon_id TEXT NOT NULL DEFAULT '',
    meta_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_product_events_ts ON product_events(ts);
CREATE INDEX IF NOT EXISTS idx_product_events_event ON product_events(event, ts);
"""

# Открытый приём только для белого списка: иначе таблицу заспамят чем угодно.
PUBLIC_EVENTS = frozenset({
    "page_view", "schedule_open", "filter_used", "group_view",
    "booking_started", "booking_step_completed",
})

# Серверные события (не принимаются извне).
SERVER_EVENTS = frozenset({
    "booking_completed", "booking_failed", "lead_created",
    "payment_started", "payment_success",
})

_MAX_META_BYTES = 2000
_FUNNEL_ORDER = [
    "page_view", "schedule_open", "filter_used", "group_view",
    "booking_started", "booking_completed",
]


def _db() -> sqlite3.Connection:
    from app.platform import bb_store
    conn = bb_store._db()
    conn.executescript(_SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def track(event: str, *, source: str = "site", session_id: str = "",
          anon_id: str = "", meta: dict | None = None) -> bool:
    """Пишет событие. Не бросает исключений наружу — аналитика не должна
    ломать бизнес-операции."""
    if event not in PUBLIC_EVENTS and event not in SERVER_EVENTS:
        return False
    try:
        meta_json = json.dumps(meta or {}, ensure_ascii=False)[:_MAX_META_BYTES]
        _db().execute(
            "INSERT INTO product_events (ts, event, source, session_id, anon_id, meta_json)"
            " VALUES (?,?,?,?,?,?)",
            (_now(), event, source[:40], session_id[:80], anon_id[:80], meta_json))
        _db().commit()
        return True
    except Exception:
        logger.exception("analytics: не удалось записать событие %s", event)
        return False


def funnel(date_from: str | None = None, date_to: str | None = None) -> dict:
    """Количество событий по типам за период + последовательность воронки."""
    sql = "SELECT event, COUNT(*) AS n FROM product_events"
    params: list = []
    clauses = []
    if date_from:
        clauses.append("ts >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("ts <= ?")
        params.append(date_to + "T23:59:59")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " GROUP BY event"
    counts = {row["event"]: row["n"] for row in _db().execute(sql, params).fetchall()}
    steps = [{"event": e, "count": counts.get(e, 0)} for e in _FUNNEL_ORDER]
    return {"counts": counts, "funnel": steps}
