"""Админская рассылка по пользователям, которые уже общались с ботом."""
from __future__ import annotations

import asyncio
from collections import Counter

from app.memory import STAGE_DONE, Conversation, get_store
from app.max_client import link_button


def _value_matches(value: str, needle: str | None) -> bool:
    if not needle:
        return False
    return needle.lower() in value.lower()


def _conversation_course(conv: Conversation) -> str:
    return conv.selected_course or conv.lead.course or ""


def _conversation_branch(conv: Conversation) -> str:
    return conv.selected_branch or conv.lead.branch or ""


def audience_counts() -> dict:
    """Возвращает общую аудиторию и доступные значения сегментов."""
    convs = get_store().all_conversations()
    courses = Counter()
    branches = Counter()
    lead_count = 0

    for conv in convs:
        if conv.lead.is_complete() or conv.stage == STAGE_DONE:
            lead_count += 1
        course = _conversation_course(conv).strip()
        branch = _conversation_branch(conv).strip()
        if course:
            courses[course] += 1
        if branch:
            branches[branch] += 1

    def _items(counter: Counter) -> list[dict]:
        return [
            {"value": value, "count": count}
            for value, count in sorted(
                counter.items(), key=lambda item: (-item[1], item[0].lower())
            )
        ]

    total = len(convs)
    return {
        "total": total,
        "segments": {
            "all": total,
            "leads": lead_count,
            "course": sum(1 for conv in convs if _conversation_course(conv).strip()),
            "branch": sum(1 for conv in convs if _conversation_branch(conv).strip()),
        },
        "courses": _items(courses),
        "branches": _items(branches),
    }


def resolve_recipients(
    segment: str,
    course: str | None = None,
    branch: str | None = None,
) -> list[str]:
    """Список user_id для выбранного сегмента."""
    convs = get_store().all_conversations()
    recipients: list[str] = []
    seen: set[str] = set()

    for conv in convs:
        include = False
        if segment == "all":
            include = True
        elif segment == "leads":
            include = conv.lead.is_complete() or conv.stage == STAGE_DONE
        elif segment == "course":
            target = (course or "").strip()
            include = bool(target) and _value_matches(_conversation_course(conv), target)
        elif segment == "branch":
            target = (branch or "").strip()
            include = bool(target) and _value_matches(_conversation_branch(conv), target)
        else:
            include = False

        if include and conv.user_id not in seen:
            seen.add(conv.user_id)
            recipients.append(conv.user_id)

    return recipients


async def send_broadcast(
    max_client,
    user_ids: list[str],
    text: str,
    button_text: str | None = None,
    button_url: str | None = None,
) -> dict:
    """Отправляет рассылку по списку получателей."""
    buttons = None
    if button_text and button_url:
        buttons = [[link_button(button_text, button_url)]]

    delivered = 0
    failed = 0
    total = len(user_ids)

    for index, user_id in enumerate(user_ids):
        try:
            ok = await max_client.send_message(user_id, text, buttons)
            if ok:
                delivered += 1
            else:
                failed += 1
        except Exception:
            failed += 1
        if index + 1 < total:
            await asyncio.sleep(0.05)

    return {"total": total, "delivered": delivered, "failed": failed}
