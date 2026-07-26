"""Administrator Router: передача диалога администратору с полным контекстом.

Срабатывает при жалобах, нестандартных вопросах, запросах договора/возврата
или явной просьбе позвать человека. Администратор получает историю диалога,
обсуждавшиеся курсы, собранные данные и текущий этап продаж.
"""
from __future__ import annotations

import logging

from app.config import settings
from app.max_client import MaxClient
from app.memory import Conversation, STAGE_HANDOFF

logger = logging.getLogger(__name__)


def _format_history(conv: Conversation, limit: int = 10) -> str:
    rows = []
    for m in conv.history[-limit:]:
        who = "Клиент" if m["role"] == "user" else "Бот"
        rows.append(f"{who}: {m['content']}")
    return "\n".join(rows)


def _client_contact_block(conv: Conversation) -> str:
    lead = conv.lead
    parts: list[str] = []
    name = lead.fio_parent.strip() or conv.client_name.strip()
    if name:
        parts.append(f"👤 {name}")
    if lead.phone:
        parts.append(f"📱 {lead.phone}")

    user_id = conv.user_id
    if user_id.startswith("tg:"):
        link = f"tg://user?id={user_id.removeprefix('tg:')}"
        platform = "Telegram"
    elif user_id.startswith("web:"):
        link = ""
        platform = "Веб-виджет"
    else:
        link = f"https://max.ru/{conv.max_username}" if conv.max_username else ""
        platform = "MAX"

    parts.append(platform)
    if link:
        parts.append(link)
    if not lead.phone or not link:
        parts.append(f"ID: {user_id}")
    return "\n".join(parts)


async def hand_off(max_client: MaxClient, conv: Conversation, reason: str = "") -> bool:
    """Уведомляет администраторов и помечает диалог как переданный."""
    conv.stage = STAGE_HANDOFF
    conv.handed_off = True

    if not settings.admin_ids:
        logger.warning("ADMIN_MAX_IDS не настроен — некому передать диалог")
        return False

    header = "🔔 Требуется администратор"
    if reason:
        header += f" ({reason})"
    message = (
        f"{header}\n\n"
        f"{_client_contact_block(conv)}\n"
        f"{conv.summary()}\n\n"
        f"История диалога:\n{_format_history(conv)}"
    )
    ok_any = False
    for admin_id in settings.admin_ids:
        ok = await max_client.send_message(admin_id, message)
        ok_any = ok_any or ok
    return ok_any
