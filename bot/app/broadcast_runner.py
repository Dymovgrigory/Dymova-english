"""Broadcast runner: фоновая отправка рассылки по получателям.

Последовательная отправка с паузой (как у старого broadcast.send_broadcast),
но с записью каждого результата в broadcast_recipients и каждого исходящего
сообщения в crm_messages — история рассылки видна в карточке клиента.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app import crm_store

logger = logging.getLogger(__name__)

# Пауза между отправками: не душним API мессенджеров.
SEND_DELAY_SEC = 0.05
# Сколько раз можно переотправить одному получателю (защита от спам-кликов).
MAX_RETRIES = 3

_SENDABLE = ("pending",)


async def _deliver(channel: str, external_user_id: str, text: str,
                   max_client=None, telegram_client=None) -> tuple[bool, str | None]:
    """Одна отправка в канал. Возвращает (ok, error)."""
    try:
        if channel == "max":
            client = max_client
            if client is None:
                from app.max_client import get_max
                client = get_max()
            ok = await client.send_message(external_user_id, text)
        elif channel == "telegram":
            client = telegram_client
            if client is None:
                from app.telegram_client import get_telegram
                client = get_telegram()
            ok = await client.send_message(external_user_id.removeprefix("tg:"), text)
        else:
            return False, f"канал {channel} не поддерживает исходящие"
        return (True, None) if ok else (False, "send failed")
    except Exception as exc:
        logger.exception("broadcast: ошибка отправки %s/%s", channel, external_user_id)
        return False, str(exc)[:300]


def _log_outgoing(recipient: dict, text: str, ok: bool, error: str | None) -> None:
    """Исходящее рассылки — в историю диалога клиента."""
    try:
        conv_id = crm_store.get_or_create_conversation(
            recipient["customer_id"], recipient["channel"], recipient["external_user_id"])
        crm_store.add_message(
            conv_id, recipient["customer_id"], recipient["channel"],
            "out", "system", text,
            status="sent" if ok else "failed", error=error,
        )
    except Exception:
        logger.exception("broadcast: не удалось записать исходящее в CRM")


async def run_broadcast(broadcast_id: int, max_client=None, telegram_client=None) -> dict:
    """Отправляет всем получателям со статусом pending. Идемпотентно:
    повторный запуск дойдёт только недоставленных."""
    broadcast = crm_store.get_broadcast(broadcast_id)
    if broadcast is None:
        return {"ok": False, "error": "broadcast not found"}
    # Маркетинг в тихие часы не уходит: возвращаем в черновик, запуск
    # повторяют утром. Транзакционных сообщений здесь нет — только кампании.
    from app.config import settings
    from app.platform import notifications
    if settings.MARKETING_RESPECT_QUIET_HOURS and notifications.in_quiet_hours():
        crm_store.update_broadcast_status(broadcast_id, "draft")
        logger.info("broadcast %s: тихие часы — запуск отложен", broadcast_id)
        return {"ok": False, "error": "quiet_hours"}
    text = broadcast["text"]
    crm_store.update_broadcast_status(broadcast_id, "sending")
    delivered = failed = skipped = 0
    recipients = crm_store.list_recipients(broadcast_id, limit=100000)
    for recipient in recipients:
        if recipient["status"] not in _SENDABLE:
            # Уже sent/failed/skipped при прошлом запуске — не трогаем.
            if recipient["status"] == "sent":
                delivered += 1
            elif recipient["status"] == "failed":
                failed += 1
            else:
                skipped += 1
            continue
        # Frequency cap: если клиент уже получал рассылку недавно — пропускаем,
        # чтобы не превращать маркетинг в спам (§103).
        last = crm_store.last_broadcast_sent_at(
            recipient["customer_id"], exclude_broadcast_id=broadcast_id)
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - last_dt < timedelta(
                        hours=settings.MARKETING_FREQ_CAP_HOURS):
                    crm_store.update_recipient_status(
                        recipient["id"], "skipped", error="frequency_cap")
                    skipped += 1
                    continue
            except ValueError:
                pass  # битая дата — не повод блокировать отправку
        ok, error = await _deliver(
            recipient["channel"], recipient["external_user_id"], text,
            max_client=max_client, telegram_client=telegram_client)
        crm_store.update_recipient_status(
            recipient["id"], "sent" if ok else "failed", error=error)
        _log_outgoing(recipient, text, ok, error)
        delivered += 1 if ok else 0
        failed += 0 if ok else 1
        await asyncio.sleep(SEND_DELAY_SEC)
    crm_store.update_broadcast_status(
        broadcast_id, "done", delivered=delivered, failed_count=failed, skipped=skipped)
    logger.info("broadcast %s: delivered=%s failed=%s skipped=%s",
                broadcast_id, delivered, failed, skipped)
    return {"ok": True, "delivered": delivered, "failed": failed, "skipped": skipped}


async def retry_recipient(recipient_id: int, max_client=None,
                          telegram_client=None) -> dict:
    """Повторная отправка одному получателю (не более MAX_RETRIES раз)."""
    recipient = crm_store.get_recipient(recipient_id)
    if recipient is None:
        return {"ok": False, "error": "recipient not found"}
    if recipient["status"] != "failed":
        return {"ok": False, "error": "retry только для failed"}
    if recipient["retry_count"] >= MAX_RETRIES:
        return {"ok": False, "error": f"лимит повторов ({MAX_RETRIES}) исчерпан"}
    broadcast = crm_store.get_broadcast(recipient["broadcast_id"])
    if broadcast is None:
        return {"ok": False, "error": "broadcast not found"}
    ok, error = await _deliver(
        recipient["channel"], recipient["external_user_id"], broadcast["text"],
        max_client=max_client, telegram_client=telegram_client)
    conn = crm_store.get_conn()
    with conn:
        conn.execute(
            "UPDATE broadcast_recipients SET retry_count = retry_count + 1 WHERE id = ?",
            (recipient_id,),
        )
    crm_store.update_recipient_status(recipient_id, "sent" if ok else "failed", error=error)
    _log_outgoing(recipient, broadcast["text"], ok, error)
    # Счётчики рассылки пересчитываем по факту.
    rows = crm_store.list_recipients(recipient["broadcast_id"], limit=100000)
    crm_store.update_broadcast_status(
        recipient["broadcast_id"], broadcast["status"],
        delivered=sum(1 for r in rows if r["status"] == "sent"),
        failed_count=sum(1 for r in rows if r["status"] == "failed"),
        skipped=sum(1 for r in rows if r["status"] == "skipped"),
    )
    return {"ok": ok, "error": error}
