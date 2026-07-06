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
    """Формирует блок контактной информации клиента для админа.

    Показывает телефон, имя и ссылку на чат (в зависимости от канала).
    """
    lines: list[str] = []
    user_id = conv.user_id

    # Имя родителя
    if conv.lead.fio_parent:
        lines.append(f"👤 {conv.lead.fio_parent}")

    # Телефон
    if conv.lead.phone:
        lines.append(f"📱 {conv.lead.phone}")

    # Ссылка на чат в зависимости от канала
    if user_id.startswith("tg:"):
        chat_id = user_id.removeprefix("tg:")
        lines.append(f"💬 Telegram: tg://user?id={chat_id}")
    elif user_id.startswith("web:"):
        lines.append("🌐 Веб-виджет (ответить по телефону)")
    else:
        # MAX — прямая ссылка на чат
        lines.append(f"💬 MAX: https://max.ru/chat/{user_id}")

    # Fallback: если телефона нет, показываем user_id
    if not conv.lead.phone:
        lines.append(f"ID: {user_id}")

    return "\n".join(lines)


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
    contact = _client_contact_block(conv)
    message = (
        f"{header}\n\n"
        f"{contact}\n\n"
        f"{conv.summary()}\n\n"
        f"История диалога:\n{_format_history(conv)}"
    )
    ok_any = False
    for admin_id in settings.admin_ids:
        ok = await max_client.send_message(admin_id, message)
        ok_any = ok_any or ok
    return ok_any
