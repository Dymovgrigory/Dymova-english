"""Админская рассылка по пользователям, которые уже общались с ботом."""
from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone

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


def _lead_status(conv: Conversation) -> str:
    if conv.lead.is_complete() or conv.stage == STAGE_DONE:
        return "complete"
    if any(
        getattr(conv.lead, field)
        for field in ("fio_parent", "phone", "fio_child", "birthday", "age", "course", "branch", "comment", "email", "city")
    ):
        return "partial"
    return "none"


def _format_source(utm: dict) -> str:
    if not utm:
        return ""
    source = str(utm.get("source", "")).strip()
    if source:
        return source
    parts = []
    for key in sorted(utm):
        value = utm.get(key)
        if value in ("", None):
            continue
        parts.append(f"{key}={value}")
    return " | ".join(parts)


def _truncate(text: str, limit: int = 140) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _parse_iso(value: str):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _conversation_transcript(conv: Conversation) -> list[dict]:
    if conv.transcript:
        return conv.transcript
    ts = conv.created_at or conv.updated_at or ""
    return [
        {
            "role": item.get("role", ""),
            "content": item.get("content", ""),
            "ts": ts,
        }
        for item in conv.history
    ]


def _first_user_message(conv: Conversation) -> tuple[str, str]:
    for item in _conversation_transcript(conv):
        if item.get("role") == "user":
            return _truncate(str(item.get("content", ""))), str(item.get("ts", "")) or conv.created_at
    return "", conv.created_at or ""


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


def list_users() -> list[dict]:
    rows = []
    for conv in get_store().all_conversations():
        last_message = ""
        if conv.history:
            last_message = _truncate(str(conv.history[-1].get("content", "")))
        first_question, first_at = _first_user_message(conv)
        rows.append(
            {
                "user_id": conv.user_id,
                "stage": conv.stage,
                "course": _conversation_course(conv),
                "branch": _conversation_branch(conv),
                "format": conv.selected_format,
                "lead_status": _lead_status(conv),
                "fio_parent": conv.lead.fio_parent,
                "fio_child": conv.lead.fio_child,
                "birthday": conv.lead.birthday,
                "age": conv.lead.age,
                "phone": conv.lead.phone,
                "first_question": first_question,
                "first_at": first_at,
                "last_message": last_message,
                "msg_count": len(conv.history),
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
                "source": _format_source(conv.utm),
            }
        )
    rows.sort(
        key=lambda row: (
            1 if not row["updated_at"] else 0,
            -_parse_iso(row["updated_at"]).timestamp() if row["updated_at"] else 0,
            -_parse_iso(row["created_at"]).timestamp() if row["created_at"] else 0,
        )
    )
    return rows


def get_user_detail(user_id: str) -> dict | None:
    for conv in get_store().all_conversations():
        if conv.user_id != user_id:
            continue
        lead_fields = {}
        for field in (
            "fio_parent",
            "phone",
            "fio_child",
            "birthday",
            "age",
            "course",
            "branch",
            "comment",
            "email",
            "city",
        ):
            value = getattr(conv.lead, field)
            if value:
                lead_fields[field] = value
        return {
            "header": {
                "user_id": conv.user_id,
                "stage": conv.stage,
                "course": _conversation_course(conv),
                "branch": _conversation_branch(conv),
                "format": conv.selected_format,
                "lead_status": _lead_status(conv),
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
                "lead": lead_fields,
            },
            "transcript": _conversation_transcript(conv),
        }
    return None


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
