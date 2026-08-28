"""Notification Orchestrator: единая точка отправки сообщений клиентам.

Решения перед отправкой (§50 мандата): канал доступен → не дубликат → не
тихие часы (для маркетинга/сервиса; критические транзакционные идут всегда).
Каждая отправка фиксируется в notification_log с dedup_key — повторное
событие не отправит второе сообщение (§21).

Приоритеты: transactional > service > marketing. Тихие часы применяются
ко всему, кроме transactional.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from app.config import settings

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))

TRANSACTIONAL = "transactional"
SERVICE = "service"
MARKETING = "marketing"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    channel TEXT NOT NULL,
    target TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    error TEXT NOT NULL DEFAULT '',
    sent_at TEXT
);
"""

# Тихие часы (МСК): маркетинговые и сервисные сообщения не шлём ночью.
QUIET_HOURS_START = 21
QUIET_HOURS_END = 9


def _db() -> sqlite3.Connection:
    from app.platform import bb_store
    conn = bb_store._db()
    conn.executescript(_SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def in_quiet_hours(now: datetime | None = None) -> bool:
    now = now or datetime.now(MSK)
    return now.hour >= QUIET_HOURS_START or now.hour < QUIET_HOURS_END


def already_sent(dedup_key: str) -> bool:
    row = _db().execute(
        "SELECT status FROM notification_log WHERE dedup_key=?", (dedup_key,)).fetchone()
    return row is not None and row["status"] == "sent"


async def resolve_targets_by_phone(phone: str) -> list[tuple[str, str]]:
    """Каналы клиента по телефону из CRM-хранилища идентичностей.

    Возвращает [(channel, external_id)]: channel = telegram|max|web.
    """
    from app import crm_store
    norm = "".join(c for c in (phone or "") if c.isdigit())[-10:]
    if not norm:
        return []
    conn = crm_store.get_conn()
    out: list[tuple[str, str]] = []
    for row in conn.execute(
            "SELECT id, phone FROM customers WHERE phone != '' AND status != 'archived'"
    ).fetchall():
        digits = "".join(c for c in (row["phone"] or "") if c.isdigit())[-10:]
        if digits != norm:
            continue
        for ident in conn.execute(
                "SELECT channel, external_id FROM customer_identities WHERE customer_id=?",
                (row["id"],)).fetchall():
            if ident["channel"] in ("telegram", "max"):
                out.append((ident["channel"], ident["external_id"]))
        break
    return out


async def send(kind: str, dedup_key: str, *, phone: str = "",
               targets: list[tuple[str, str]] | None = None,
               text: str) -> dict:
    """Отправка с дедупом и тихими часами. Возвращает статистику."""
    if already_sent(dedup_key):
        return {"sent": 0, "skipped": "duplicate"}
    if kind != TRANSACTIONAL and in_quiet_hours():
        return {"sent": 0, "skipped": "quiet_hours"}

    if targets is None:
        targets = await resolve_targets_by_phone(phone)
    if not targets:
        return {"sent": 0, "skipped": "no_channel"}

    sent, errors = 0, []
    for channel, external_id in targets:
        ok = await _send_channel(channel, external_id, text)
        if ok:
            sent += 1
        else:
            errors.append(channel)

    status = "sent" if sent else "failed"
    try:
        _db().execute(
            "INSERT INTO notification_log (dedup_key, created_at, kind, channel,"
            " target, text, status, error, sent_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (dedup_key, _now(), kind, ",".join(t[0] for t in targets),
             ",".join(t[1] for t in targets), text[:2000], status,
             ",".join(errors), _now() if sent else None))
        _db().commit()
    except sqlite3.IntegrityError:
        return {"sent": 0, "skipped": "duplicate"}
    return {"sent": sent, "failed_channels": errors}


async def _send_channel(channel: str, external_id: str, text: str) -> bool:
    try:
        if channel == "telegram":
            from app.telegram_client import get_telegram
            client = get_telegram()
            if client.configured:
                chat_id = external_id[3:] if external_id.startswith("tg:") else external_id
                return await client.send_message(chat_id, text)
        elif channel == "max":
            from app.max_client import get_max
            client = get_max()
            if client.configured:
                return await client.send_message(external_id, text)
    except Exception:
        logger.exception("notify: сбой канала %s → %s", channel, external_id)
    return False
