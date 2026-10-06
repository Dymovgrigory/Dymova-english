"""Продуктовая аналитика: единая шина событий воронки (§105–§108).

События приходят с сайта (виджет расписания, страницы) и от серверных
процессов (booking completed, lead created). Хранилище — та же SQLite,
таблица product_events; схема события: event, timestamp, source, sessionId,
anonymousId, metadata. Никаких PII в metadata: телефоны/имена не пишем.
"""
from __future__ import annotations

import json
import re
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

# Действия клиента внутри мини-приложения (MAX/Telegram). Пишутся только с
# подписанной личностью (см. POST /api/miniapp/event), а не с user_id из запроса.
MINIAPP_EVENTS = frozenset({"miniapp_section_view", "miniapp_click"})

# Серверные события (не принимаются извне).
SERVER_EVENTS = frozenset({
    "booking_completed", "booking_failed", "lead_created",
    "payment_started", "payment_success",
    # Воронка бота (TG/MAX): старт → ответ → форма открыта → отправлена.
    "bot_start", "bot_reply", "miniapp_opened", "form_submitted", "form_rejected",
    "chat_phone_lead",
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
    if event not in PUBLIC_EVENTS and event not in SERVER_EVENTS and event not in MINIAPP_EVENTS:
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


_TECHNICAL_LABEL = re.compile(r"WebAppData|https?://|%[0-9A-Fa-f]{2}|=", re.IGNORECASE)


def is_technical_action_label(label: str) -> bool:
    """Служебные строки мессенджера (WebAppData=…, ссылки, query-параметры) —
    не текст кнопки. Такие действия в ленту клиента не попадают."""
    return bool(_TECHNICAL_LABEL.search(label or ""))


def client_activity(identities: list[tuple[str, str]], limit: int = 200) -> list[dict]:
    """Лента действий клиента: старт бота, ответы, открытия и клики в
    мини-приложении. identities — пары (канал, внешний id) из карточки клиента:
    один и тот же числовой id в разных мессенджерах — разные люди, поэтому
    сопоставляем обе части, а не только anon_id."""
    pairs = [(str(src), str(anon)) for src, anon in identities if src and anon]
    if not pairs:
        return []
    clause = " OR ".join("(source = ? AND anon_id = ?)" for _ in pairs)
    params = [part for pair in pairs for part in pair]
    rows = _db().execute(
        "SELECT id, ts, event, source, anon_id, meta_json FROM product_events"
        f" WHERE {clause} ORDER BY id DESC LIMIT ?",
        (*params, max(1, min(int(limit), 500))),
    ).fetchall()
    items = []
    for row in rows:
        try:
            meta = json.loads(row[5] or "{}")
        except ValueError:
            meta = {}
        if row[2] == "miniapp_click" and is_technical_action_label(meta.get("action", "")):
            continue
        items.append({"id": row[0], "ts": row[1], "event": row[2], "source": row[3],
                      "anon_id": row[4], "meta": meta})
    return items
