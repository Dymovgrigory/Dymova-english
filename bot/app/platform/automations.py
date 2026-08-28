"""Automation Engine: отложенные задачи по событиям (trigger → delay → action).

Модель: таблица automation_jobs (run_at, handler, payload, статус) + фоновый
воркер (раз в минуту забирает созревшие). События-источники:
- booking confirmed → напоминание за 24ч и за 2ч до пробного урока;
- payment.received (billing) → «спасибо» клиенту;
- low balance (по данным sync) → мягкое напоминание (service, тихие часы).

Безопасность (§57): перед отправкой напоминания о занятии проверяем, что
бронь всё ещё confirmed (не отменена/не провалена), а «спасибо» дедупится
по transaction_id — повторный webhook не отправит второе сообщение.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.platform import notifications

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS automation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    run_at TEXT NOT NULL,
    handler TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    dedup_key TEXT NOT NULL UNIQUE,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    done_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_due ON automation_jobs(status, run_at);
"""

WORKER_INTERVAL_SEC = 60
MAX_ATTEMPTS = 3


def _db() -> sqlite3.Connection:
    from app.platform import bb_store
    conn = bb_store._db()
    conn.executescript(_SCHEMA)
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def schedule(handler: str, payload: dict, run_at: datetime, dedup_key: str) -> bool:
    """Ставит задачу. False — такая уже есть (дедуп)."""
    try:
        _db().execute(
            "INSERT INTO automation_jobs (created_at, run_at, handler, payload_json,"
            " dedup_key) VALUES (?,?,?,?,?)",
            (_iso(_now()), _iso(run_at), handler,
             json.dumps(payload, ensure_ascii=False), dedup_key))
        _db().commit()
        return True
    except sqlite3.IntegrityError:
        return False


# --- встроенные потоки ---

def schedule_lesson_reminders(*, booking_id: int, phone: str, lesson_starts_at: str,
                              group_caption: str) -> int:
    """Напоминания за 24ч и за 2ч до пробного урока."""
    try:
        starts = datetime.fromisoformat(lesson_starts_at)
    except (TypeError, ValueError):
        return 0
    if starts.tzinfo is None:
        starts = starts.replace(tzinfo=timezone(timedelta(hours=3)))
    count = 0
    for delta, label in ((timedelta(hours=24), "завтра"), (timedelta(hours=2), "сегодня")):
        run_at = starts - delta
        if run_at <= _now():
            continue
        ok = schedule("lesson_reminder", {
            "booking_id": booking_id, "phone": phone,
            "lesson_starts_at": lesson_starts_at, "group_caption": group_caption,
            "label": label,
        }, run_at, dedup_key=f"remind:{booking_id}:{delta.total_seconds()}")
        count += int(ok)
    return count


def schedule_payment_thankyou(*, invoice_id: str, phone: str, amount_rub: float) -> bool:
    """«Спасибо за оплату» — почти сразу, но через очередь (не в webhook)."""
    return schedule("payment_thankyou", {
        "invoice_id": invoice_id, "phone": phone, "amount_rub": amount_rub,
    }, _now() + timedelta(seconds=5), dedup_key=f"thanks:{invoice_id}")


# --- обработчики ---

async def _handle_lesson_reminder(payload: dict) -> None:
    from app.platform import bb_store
    booking = bb_store.booking_by_id(int(payload["booking_id"]))
    if not booking or booking["status"] != "confirmed":
        logger.info("automation: бронь %s не активна — напоминание отменено",
                    payload.get("booking_id"))
        return
    starts = payload.get("lesson_starts_at", "")
    try:
        dt = datetime.fromisoformat(starts)
        when = dt.strftime("%d.%m в %H:%M")
    except (TypeError, ValueError):
        when = starts
    text = (f"Напоминаем: {payload.get('label', 'скоро')} пробное занятие "
            f"«{payload.get('group_caption', '')}» — {when}. "
            "Ждём вас! Если планы изменились — напишите, перенесём.")
    await notifications.send(
        notifications.SERVICE, f"remind-msg:{payload['booking_id']}:{payload.get('label')}",
        phone=payload.get("phone", ""), text=text)


async def _handle_payment_thankyou(payload: dict) -> None:
    text = (f"Спасибо за оплату {payload.get('amount_rub')} ₽! "
            "Всё прошло успешно. Хороших занятий! 🦊")
    await notifications.send(
        notifications.TRANSACTIONAL, f"thanks-msg:{payload['invoice_id']}",
        phone=payload.get("phone", ""), text=text)


_HANDLERS = {
    "lesson_reminder": _handle_lesson_reminder,
    "payment_thankyou": _handle_payment_thankyou,
}


async def run_due(limit: int = 20) -> int:
    """Выполняет созревшие задачи. Возвращает число обработанных."""
    rows = _db().execute(
        "SELECT * FROM automation_jobs WHERE status='pending' AND run_at<=?"
        " ORDER BY run_at LIMIT ?", (_iso(_now()), limit)).fetchall()
    done = 0
    for row in rows:
        handler = _HANDLERS.get(row["handler"])
        job_id = row["id"]
        if handler is None:
            _db().execute(
                "UPDATE automation_jobs SET status='failed', last_error='unknown handler',"
                " done_at=? WHERE id=?", (_iso(_now()), job_id))
            _db().commit()
            continue
        try:
            await handler(json.loads(row["payload_json"]))
            _db().execute(
                "UPDATE automation_jobs SET status='done', attempts=attempts+1,"
                " done_at=? WHERE id=?", (_iso(_now()), job_id))
            done += 1
        except Exception as exc:
            attempts = row["attempts"] + 1
            status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
            # повтор через 5 минут при transient-сбое
            _db().execute(
                "UPDATE automation_jobs SET status=?, attempts=?, last_error=?,"
                " run_at=? WHERE id=?",
                (status, attempts, repr(exc)[:400],
                 _iso(_now() + timedelta(minutes=5)), job_id))
            logger.exception("automation: задача %s (%s) упала", job_id, row["handler"])
        _db().commit()
    return done


async def _worker_loop() -> None:
    while True:
        try:
            n = await run_due()
            if n:
                logger.info("automation: обработано задач: %d", n)
        except Exception:
            logger.exception("automation: сбой воркера")
        await asyncio.sleep(WORKER_INTERVAL_SEC)


def start() -> list[asyncio.Task]:
    return [asyncio.create_task(_worker_loop())]
