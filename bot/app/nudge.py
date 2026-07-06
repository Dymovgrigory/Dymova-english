"""Warm nudges: return incomplete leads with a personalized reminder.

Scans all conversations for users who started engaging but dropped off
before submitting a lead (stages: discovery, selection, objection, lead).
After a configurable delay (default 36 h of inactivity), sends a single
warm reminder via the same channel (MAX or Telegram). Web-chat users
are skipped (no push capability).

Runs as a daily scheduled task (default 11:00 MSK) alongside the digest.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.convlog import log_turn
from app.max_client import get_max, link_button
from app.memory import (
    Conversation,
    STAGE_DISCOVERY,
    STAGE_DONE,
    STAGE_GREETING,
    STAGE_HANDOFF,
    STAGE_LEAD,
    STAGE_OBJECTION,
    STAGE_SELECTION,
    get_store,
)
from app.telegram_client import get_telegram

logger = logging.getLogger(__name__)

_NUDGE_ELIGIBLE_STAGES = frozenset({
    STAGE_DISCOVERY, STAGE_SELECTION, STAGE_OBJECTION, STAGE_LEAD,
})


def _channel(user_id: str) -> str:
    if user_id.startswith("tg:"):
        return "telegram"
    if user_id.startswith("web:"):
        return "web"
    return "max"


def is_nudgeable(conv: Conversation, now: datetime | None = None) -> bool:
    """Check whether a conversation qualifies for a warm nudge."""
    if conv.nudge_sent:
        return False
    if conv.lead_submitted:
        return False
    if conv.stage not in _NUDGE_ELIGIBLE_STAGES:
        return False
    if _channel(conv.user_id) == "web":
        return False
    # Must have at least one user message
    if not any(m.get("role") == "user" for m in conv.history):
        return False

    hours = conv.hours_since_update()
    if hours is None:
        return False
    if hours < settings.NUDGE_DELAY_HOURS:
        return False
    if hours > settings.NUDGE_MAX_AGE_HOURS:
        return False
    return True


def find_nudgeable(now: datetime | None = None) -> list[Conversation]:
    """Return all conversations eligible for a warm nudge."""
    return [c for c in get_store().all_conversations() if is_nudgeable(c, now)]


def compose_message(conv: Conversation) -> str:
    """Build a personalized warm reminder for the given conversation."""
    name = conv.lead.fio_parent or ""
    child = conv.child_label()
    course = conv.selected_course or conv.lead.course or ""
    branch = conv.selected_branch or conv.lead.branch or ""

    greeting = f"{name}, " if name else ""
    greeting += "здравствуйте! "

    # Tailor the body based on what we know
    parts: list[str] = [f"{greeting}Это Фокси из Фоксинбурга 🦊"]

    if course:
        parts.append(
            f"Мы недавно общались по поводу «{course}» — "
            "хотел уточнить, остались ли вопросы?"
        )
    elif child:
        parts.append(
            f"Мы недавно обсуждали обучение для {child} — "
            "хотел уточнить, остались ли вопросы?"
        )
    else:
        parts.append(
            "Мы недавно общались — хотел уточнить, "
            "остались ли вопросы?"
        )

    parts.append(
        "У нас есть бесплатная диагностика — поможем определить уровень "
        "и подобрать идеальную программу. Записаться можно прямо здесь, "
        "просто напишите!"
    )

    if branch:
        parts.append(f"Удобный филиал: {branch}.")

    parts.append("Буду рад помочь! 😊")

    return "\n\n".join(parts)


def compose_buttons(conv: Conversation) -> list[list[dict]]:
    """Link buttons for the nudge message (miniapp signup + phones)."""
    rows: list[list[dict]] = []
    miniapp = settings.MINIAPP_BASE_URL.rstrip("/") if settings.MINIAPP_BASE_URL else ""
    if miniapp:
        rows.append([link_button("📋 Записаться онлайн", f"{miniapp}#signup")])
    return rows


async def send_nudge(conv: Conversation) -> bool:
    """Send a warm nudge to a single user. Returns True on success."""
    channel = _channel(conv.user_id)
    text = compose_message(conv)
    buttons = compose_buttons(conv)

    ok = False
    if channel == "max":
        max_client = get_max()
        if max_client.configured:
            try:
                ok = await max_client.send_message(conv.user_id, text, buttons or None)
            except Exception:
                logger.exception("nudge: MAX send failed user=%s", conv.user_id)
    elif channel == "telegram":
        tg = get_telegram()
        if tg.configured:
            chat_id = conv.user_id.removeprefix("tg:")
            try:
                ok = await tg.send_message(int(chat_id), text, buttons or None)
            except Exception:
                logger.exception("nudge: Telegram send failed user=%s", conv.user_id)

    if ok:
        store = get_store()
        conv.nudge_sent = True
        store.save(conv)
        log_turn(conv.user_id, "[nudge]", text, "nudge", conv.stage, "nudge")
        logger.info("nudge: sent to %s (channel=%s)", conv.user_id, channel)

    return ok


async def run_nudges() -> dict:
    """Scan and send nudges to all eligible conversations.

    Returns stats dict: {eligible, sent, failed, skipped_web}.
    """
    candidates = find_nudgeable()
    sent = 0
    failed = 0
    skipped_web = 0

    for conv in candidates:
        ch = _channel(conv.user_id)
        if ch == "web":
            skipped_web += 1
            continue
        try:
            ok = await send_nudge(conv)
            if ok:
                sent += 1
            else:
                failed += 1
        except Exception:
            logger.exception("nudge: error for user=%s", conv.user_id)
            failed += 1
        # Small delay to avoid rate limits
        if sent + failed < len(candidates):
            await asyncio.sleep(0.1)

    stats = {
        "eligible": len(candidates),
        "sent": sent,
        "failed": failed,
        "skipped_web": skipped_web,
    }
    logger.info("nudge: run complete — %s", stats)
    return stats


def preview() -> list[dict]:
    """Return a list of conversations that would receive a nudge (dry run)."""
    rows: list[dict] = []
    for conv in find_nudgeable():
        rows.append({
            "user_id": conv.user_id,
            "channel": _channel(conv.user_id),
            "stage": conv.stage,
            "hours_inactive": round(conv.hours_since_update() or 0, 1),
            "name": conv.lead.fio_parent,
            "child": conv.child_label(),
            "course": conv.selected_course or conv.lead.course,
            "branch": conv.selected_branch or conv.lead.branch,
            "message_preview": compose_message(conv)[:300],
        })
    return rows
