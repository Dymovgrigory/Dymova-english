"""Логика работы бота в групповых чатах MAX."""
from __future__ import annotations

import logging
import re
from typing import Any

from app import ai_core
from app import intent as I
from app.config import settings
from app.memory import Conversation, STAGE_DISCOVERY

logger = logging.getLogger(__name__)

_PRIVATE_CUES = (
    "запис",
    "пробн",
    "заявк",
    "телефон",
    "номер",
    "перезвон",
    "связаться",
    "оставить заявку",
    "оформ",
    "личн",
    "ребёнк",
    "ребенк",
)


def _node(update_or_message: dict[str, Any]) -> dict[str, Any]:
    if "message" in update_or_message and isinstance(update_or_message["message"], dict):
        return update_or_message["message"]
    return update_or_message


def extract_chat_id(update_or_message: dict[str, Any]) -> int | None:
    node = _node(update_or_message)
    for key in ("chat_id", "chatId"):
        val = node.get(key)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                return None
    recipient = node.get("recipient") or {}
    if isinstance(recipient, dict):
        val = recipient.get("chat_id")
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                return None
    return None


def is_group_message(message: dict[str, Any]) -> bool:
    recipient = message.get("recipient") or {}
    chat_type = str(recipient.get("chat_type") or "").lower()
    if chat_type in {"chat", "channel"}:
        return True
    chat_id = extract_chat_id(message)
    if chat_id is not None and chat_id < 0:
        return True
    return chat_type and chat_type != "dialog"


def _username_matches(text: str, bot_username: str | None) -> bool:
    if not bot_username:
        return False
    return re.search(rf"(?i)@{re.escape(bot_username)}\b", text or "") is not None


def is_addressed_to_bot(message: dict[str, Any], bot_user_id: str | None, bot_username: str | None) -> bool:
    body = message.get("body") or {}
    text = str(body.get("text") or "")
    markup = body.get("markup") or []
    if isinstance(markup, list):
        for element in markup:
            if not isinstance(element, dict):
                continue
            if element.get("type") in {"user_mention", "user_link"}:
                target = element.get("user_id")
                if target is not None and bot_user_id is not None and str(target) == str(bot_user_id):
                    return True
    link = message.get("link") or {}
    if isinstance(link, dict) and str(link.get("type") or "") == "reply":
        linked = link.get("message") or {}
        sender = linked.get("sender") or {}
        if bot_user_id is not None and str(sender.get("user_id")) == str(bot_user_id):
            return True
    return _username_matches(text, bot_username)


def strip_mention(text: str, bot_username: str | None) -> str:
    clean = (text or "").strip()
    if not bot_username:
        return clean
    clean = re.sub(rf"(?i)@\s*{re.escape(bot_username)}\b", " ", clean)
    clean = re.sub(r"\s{2,}", " ", clean)
    return clean.strip(" ,:;!?.\n\t")


def _needs_private_dialog(text: str, intent: str) -> bool:
    low = text.lower()
    if intent in {I.WANT_SIGNUP, I.HANDOFF}:
        return True
    return any(cue in low for cue in _PRIVATE_CUES)


async def _notify_admins(max_client, chat_id: int | None, sender: dict[str, Any], text: str) -> None:
    sender_name = sender.get("name") or sender.get("username") or sender.get("user_id") or "—"
    sender_id = sender.get("user_id") or "—"
    admin_text = (
        "🛎 Жалоба из группового чата\n\n"
        f"chat_id: {chat_id}\n"
        f"От: {sender_name} ({sender_id})\n"
        f"Текст: {text}"
    )
    for admin_id in settings.admin_ids:
        await max_client.send_message(admin_id, admin_text)


async def handle_group_message(message: dict[str, Any], max_client) -> None:
    if not settings.GROUP_MODE_ENABLED:
        return

    chat_id = extract_chat_id(message)
    if chat_id is None:
        return

    whitelist = settings.group_chat_whitelist()
    if whitelist and chat_id not in whitelist:
        return

    if not await max_client.ensure_bot_identity():
        return

    if not is_addressed_to_bot(message, getattr(max_client, "bot_user_id", None), getattr(max_client, "bot_username", None)):
        return

    sender = message.get("sender") or {}
    body = message.get("body") or {}
    text = strip_mention(str(body.get("text") or ""), getattr(max_client, "bot_username", None))
    if not text:
        reply = "Чем помочь? Спросите про цены, расписание, филиалы 🦊"
        await max_client.send_to_chat(chat_id, reply)
        return

    intent = I.detect_intent(text)
    if I.detect_complaint(text):
        reply = "Спасибо, я передал ваше обращение администратору 🙏 — он свяжется с вами."
        await _notify_admins(max_client, chat_id, sender, text)
        await max_client.send_to_chat(chat_id, reply)
        return

    if _needs_private_dialog(text, intent):
        reply = "Запишу с удовольствием! Напишите мне в личные сообщения — там оформим заявку 🦊"
        await max_client.send_to_chat(chat_id, reply)
        return

    conv = Conversation(user_id=f"group:{chat_id}")
    conv.stage = STAGE_DISCOVERY
    reply = await ai_core._consult(conv, text)
    if not reply:
        reply = "Могу подсказать по школе, курсам, филиалам и ценам 🦊"
    await max_client.send_to_chat(chat_id, reply)
