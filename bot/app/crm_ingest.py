"""Ingestion-слой: запись всех сообщений всех каналов в CRM-хранилище.

Тонкая прослойка между обработчиками (MAX webhook, Telegram polling,
веб-виджет) и crm_store. Главное правило: сбой CRM-записи НИКОГДА не должен
ломать ответ клиенту, поэтому каждая функция глушит и логирует исключения.
"""
from __future__ import annotations

import logging

from app import crm_store

logger = logging.getLogger(__name__)


def _channel_for_user(user_id: str) -> str:
    """Канал по префиксу user_id: tg:... — telegram, web:... — виджет, иначе MAX."""
    if user_id.startswith("tg:"):
        return "telegram"
    if user_id.startswith("web:"):
        return "web"
    return "max"


def ingest_inbound(
    channel: str,
    external_user_id: str,
    text: str,
    external_event_id: str | None = None,
    external_message_id: str | None = None,
    name: str = "",
    first_name: str = "",
    last_name: str = "",
    username: str = "",
    phone: str = "",
) -> dict | None:
    """Входящее сообщение: событие, клиент, диалог, сообщение.

    Возвращает контекст для ingest_outbound или None (дубликат события или
    сбой записи — в обоих случаях исходящее логировать не привязываясь).
    """
    try:
        event_id = None
        if external_event_id:
            event_id, is_dup = crm_store.record_inbound_event(
                channel, str(external_event_id),
                {"user": external_user_id, "text": (text or "")[:500]},
            )
            if is_dup:
                # Дедуп выше по стеку (processed_events) обычно отсекает ретрай
                # раньше, но если событие всё же дошло повторно — не плодим
                # дубли сообщений.
                logger.info("crm: дубликат события %s/%s", channel, external_event_id)
                return None
        customer_id = crm_store.upsert_customer_for_identity(
            channel, external_user_id,
            name=name, first_name=first_name, last_name=last_name,
            username=username, phone=phone,
        )
        conversation_id = crm_store.get_or_create_conversation(customer_id, channel, external_user_id)
        message_id, _ = crm_store.add_message(
            conversation_id, customer_id, channel, "in", "customer", text,
            external_message_id=external_message_id,
        )
        return {
            "event_id": event_id,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "channel": channel,
        }
    except Exception:
        logger.exception("crm: ошибка записи входящего %s/%s", channel, external_user_id)
        return None


def ingest_outbound(
    ctx: dict | None,
    text: str,
    sender_type: str = "ai",
    ai_model: str | None = None,
    ok: bool = True,
    error: str | None = None,
) -> None:
    """Исходящее сообщение + закрытие события. Ошибки отправки фиксируем
    статусом failed, чтобы в админке было видно недоставленное."""
    if not ctx:
        return
    try:
        crm_store.add_message(
            ctx["conversation_id"], ctx["customer_id"], ctx["channel"],
            "out", sender_type, text,
            status="sent" if ok else "failed",
            error=None if ok else (error or "send failed"),
            ai_model=ai_model if sender_type == "ai" else None,
        )
        if ctx.get("event_id"):
            crm_store.mark_event_processed(
                ctx["event_id"],
                status="processed" if ok else "failed",
                error=None if ok else (error or "send failed"),
            )
    except Exception:
        logger.exception("crm: ошибка записи исходящего")


def ingest_ai_event(kind: str, platform: str, user_id: str, detail: dict | None = None) -> None:
    """Произвольное событие AI (error/fallback/tool_call...) с привязкой к диалогу."""
    try:
        channel = platform or _channel_for_user(user_id)
        conv = crm_store.find_conversation(channel, user_id)
        crm_store.add_ai_event(
            kind,
            conversation_id=conv["id"] if conv else None,
            customer_id=conv["customer_id"] if conv else None,
            detail=detail or {},
        )
    except Exception:
        logger.exception("crm: ошибка записи ai_event %s", kind)


def pop_pending_web(session_id: str) -> list[dict]:
    """Недоставленные ответы менеджера для виджета (сбой — пустой список)."""
    try:
        return crm_store.pop_pending_web_messages(session_id)
    except Exception:
        logger.exception("crm: ошибка выборки pending-сообщений")
        return []


def ingest_handoff(platform: str, user_id: str, reason: str = "") -> None:
    """Фиксирует передачу диалога администратору."""
    try:
        channel = platform or _channel_for_user(user_id)
        conv = crm_store.find_conversation(channel, user_id)
        crm_store.add_ai_event(
            "handoff",
            conversation_id=conv["id"] if conv else None,
            customer_id=conv["customer_id"] if conv else None,
            detail={"reason": reason, "user_id": user_id},
        )
        if conv:
            crm_store.set_ai_mode(conv["id"], "manager", actor="bot")
    except Exception:
        logger.exception("crm: ошибка записи handoff")


def ingest_no_answer(user_id: str, question: str, reason: str = "") -> None:
    """Дубль «пробела» базы знаний в ai_events (основной журнал — insights)."""
    if not user_id or not question:
        return
    try:
        channel = _channel_for_user(user_id)
        conv = crm_store.find_conversation(channel, user_id)
        crm_store.add_ai_event(
            "no_answer",
            conversation_id=conv["id"] if conv else None,
            customer_id=conv["customer_id"] if conv else None,
            detail={"question": question[:500], "reason": reason},
        )
    except Exception:
        logger.exception("crm: ошибка записи no_answer")
