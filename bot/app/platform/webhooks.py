"""Приёмник вебхуков BigBen CRM: POST /api/webhooks/bigben.

Поток: raw body → HMAC-SHA256 (заголовок X-BigBen-Signature, timing-safe) →
дедуп (dedup_key UNIQUE) → persist → 200 сразу → обработка в фоне → доменные
события (уведомления админам/клиентам, обновление read-model).

Подписка настраивается в CRM: Настройки → Информация о школе → Интеграции →
Вебхуки. Секрет показывается один раз — храним в BIGBEN_WEBHOOK_SECRET.

События: student.created, lead.created, group.enrolled, lesson.completed,
payment.received. ВНИМАНИЕ: в payment.received суммы в РУБЛЯХ (не копейки!) —
в отличие от GET /payments (amount_kopecks).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.platform import bb_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["bigben-webhooks"])

_KNOWN_EVENTS = {
    "student.created", "lead.created", "group.enrolled",
    "lesson.completed", "payment.received", "webhook.test",
}


def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """Timing-safe проверка HMAC-SHA256 от сырых байт тела."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _dedup_key(event: str, account_id: int | None, payload: dict, ts: str) -> str:
    inner_id = (payload.get("payment_id") or payload.get("lead_id")
                or payload.get("enrollment_id") or payload.get("student_id")
                or payload.get("lesson_id") or "")
    return f"{event}:{account_id}:{inner_id}:{ts}"


@router.post("/bigben")
async def bigben_webhook(request: Request) -> JSONResponse:
    raw = await request.body()
    if not settings.BIGBEN_WEBHOOK_SECRET:
        logger.error("webhook: BIGBEN_WEBHOOK_SECRET не задан — приём невозможен")
        return JSONResponse({"error": "webhook not configured"}, status_code=503)
    signature = request.headers.get("X-BigBen-Signature", "")
    if not verify_signature(raw, signature, settings.BIGBEN_WEBHOOK_SECRET):
        logger.warning("webhook: неверная подпись (remote=%s)", request.client)
        return JSONResponse({"error": "invalid signature"}, status_code=401)
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse({"error": "invalid json"}, status_code=400)

    event = str(body.get("event", ""))
    account_id = body.get("account_id")
    payload = body.get("payload") or {}
    ts = str(body.get("timestamp", ""))
    dedup_key = _dedup_key(event, account_id, payload, ts)

    event_id, is_dup = await asyncio.to_thread(
        bb_store.record_webhook_event, event, account_id, payload, ts, dedup_key)
    if is_dup:
        logger.info("webhook: дубликат %s (%s)", event, dedup_key)
        return JSONResponse({"ok": True, "duplicate": True})

    # Быстрый 200, обработка — в фоне (BigBen ждёт ответ до 10 секунд).
    asyncio.create_task(_process(event_id, event, payload))
    return JSONResponse({"ok": True})


async def _process(event_id: int, event: str, payload: dict) -> None:
    try:
        await _handle(event, payload)
        await asyncio.to_thread(bb_store.mark_webhook_processed, event_id)
    except Exception as exc:
        logger.exception("webhook: ошибка обработки %s", event)
        await asyncio.to_thread(bb_store.mark_webhook_processed, event_id, error=repr(exc))


_LK_INTERNAL_URL = os.environ.get("LK_INTERNAL_URL", "http://world-api:8010").strip()


async def _relay_attendance(payload: dict) -> None:
    """Переслать отметку посещаемости (lesson.completed) в ЛК.

    Подпись HMAC(WORLD_BRIDGE_SECRET) по контракту world-backend
    (app/lk/service.py ingest_attendance). Любая ошибка — только в лог:
    ретраев нет, источник истины — следующие вебхуки и полная синхронизация.
    """
    import hashlib
    import hmac
    import time

    import httpx

    from app.config import settings

    secret = settings.WORLD_BRIDGE_SECRET
    student_id = payload.get("student_id")
    lesson_id = payload.get("lesson_id") or payload.get("lesson")
    visit_status = payload.get("visit_status")
    if not secret or not student_id or not lesson_id:
        return
    status = "visited" if visit_status == 1 else "missed"
    ts = int(time.time())
    msg = f"{student_id}\n{lesson_id}\n{status}\n{ts}".encode()
    sign = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    body = {
        "student_id": int(student_id),
        "lesson_id": int(lesson_id),
        "status": status,
        "ts": ts,
        "sign": sign,
        "raw": payload,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{_LK_INTERNAL_URL}/api/lk/attendance", json=body)
        if r.status_code != 200:
            logger.warning("lk-relay: status=%s body=%s", r.status_code, r.text[:200])
    except Exception as exc:  # noqa: BLE001 — relay не критичен
        logger.warning("lk-relay: не удалось переслать в ЛК: %s", exc)


async def _relay_membership(payload: dict) -> None:
    """Переслать зачисление (group.enrolled) в ЛК: привязка ученик↔группа.

    Подпись HMAC(WORLD_BRIDGE_SECRET) по контракту world-backend
    (app/lk/service.py ingest_membership). Ошибки — только в лог.
    """
    import hashlib
    import hmac
    import time

    import httpx

    from app.config import settings

    secret = settings.WORLD_BRIDGE_SECRET
    student_id = payload.get("student_id")
    group = payload.get("group") if isinstance(payload.get("group"), dict) else {}
    group_id = payload.get("group_id") or group.get("id")
    caption = payload.get("group_name") or group.get("caption") or ""
    if not secret or not student_id or not group_id:
        return
    status = "active"
    ts = int(time.time())
    msg = f"{student_id}\n{group_id}\n{status}\n{ts}".encode()
    sign = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    body = {
        "student_id": int(student_id),
        "group_id": int(group_id),
        "group_caption": str(caption),
        "status": status,
        "ts": ts,
        "sign": sign,
        "raw": payload,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{_LK_INTERNAL_URL}/api/lk/group-members",
                                  json=body)
        if r.status_code != 200:
            logger.warning("lk-relay(members): status=%s body=%s",
                           r.status_code, r.text[:200])
    except Exception as exc:  # noqa: BLE001 — relay не критичен
        logger.warning("lk-relay(members): не удалось переслать в ЛК: %s", exc)


async def _handle(event: str, payload: dict) -> None:
    """Доменные реакции на события BigBen."""
    from app.max_client import get_max

    if event == "webhook.test":
        logger.info("webhook: тестовое событие от BigBen")
        return

    if event == "lead.created":
        name = payload.get("name", "")
        source = payload.get("source", "")
        await _notify_admins(f"🆕 Новый лид в BigBen: {name} (источник: {source})")
        return

    if event == "student.created":
        await _notify_admins(
            f"👋 Новый ученик в CRM: {payload.get('student_name', '')}")
        return

    if event == "group.enrolled":
        await _notify_admins(
            f"✅ Зачисление: {payload.get('student_id')} → {payload.get('group_name', '')}")
        # Relay в ЛК (Этап 2): публичный API BigBen не отдаёт составы групп,
        # кабинет копит привязки ученик↔группа из вебхуков.
        asyncio.create_task(_relay_membership(payload))
        return

    if event == "payment.received":
        # Суммы здесь в рублях (см. предупреждение в docstring модуля).
        amount = payload.get("payment_amount") or payload.get("amount") or 0
        await _notify_admins(
            f"💰 Оплата: {amount} ₽ от ученика #{payload.get('student_id')}"
            f" ({payload.get('payment_type', '')})")
        return

    if event == "lesson.completed":
        # visit_status: 1 = был. Остальные статусы (пропуск) — сигнал для
        # будущих автоматизаций; пока только логируем.
        logger.info("webhook: lesson.completed student=%s status=%s",
                    payload.get("student_id"), payload.get("visit_status"))
        # Relay в ЛК (Этап 2): отметка посещаемости уходит в world-backend.
        # Fire-and-forget: сбой relay не должен ронять обработку вебхука.
        asyncio.create_task(_relay_attendance(payload))
        return

    logger.info("webhook: неизвестное событие %s", event)


async def _notify_admins(text: str) -> None:
    from app.max_client import get_max
    client = get_max()
    if not client.configured:
        return
    for admin_id in settings.admin_ids:
        try:
            await client.send_message(admin_id, text)
        except Exception:
            logger.exception("webhook: не удалось уведомить админа %s", admin_id)


@router.get("/bigben/health")
async def webhook_health() -> dict:
    """Состояние приёмника: последние события и ошибки (для админки)."""
    failed = await asyncio.to_thread(bb_store.failed_webhooks, 10)
    return {
        "configured": bool(settings.BIGBEN_WEBHOOK_SECRET),
        "failed_count": len(failed),
        "recent_failures": failed[:5],
    }
