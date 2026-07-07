"""Человеческий отчёт по диалогам из JSONL-лога."""
from __future__ import annotations

from collections import defaultdict

from app.convlog import iter_turns
from app.memory import STAGE_DONE, STAGE_HANDOFF, get_store

_MAX_USERS = 30
_MAX_MESSAGES = 5
_MAX_MESSAGE_LEN = 120


def _shorten(text: str, limit: int = _MAX_MESSAGE_LEN) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _classify_result(turns: list[dict], stage: str) -> str:
    results = [str(t.get("result", "")).strip().lower() for t in turns if t.get("result")]
    if "lead" in results:
        return "заявка"
    if "handoff" in results:
        return "передан администратору"
    if "homework" in results:
        return "домашка"
    if stage == STAGE_DONE:
        return "заявка"
    if stage == STAGE_HANDOFF:
        return "передан администратору"
    return "консультация"


def conversations_digest(days: int = 1) -> str:
    turns = iter_turns(days=days)
    if not turns:
        return "🤖 Диалоги за период:\nЗа этот период новых диалогов не было."

    store = get_store()
    name_by_uid = {
        conv.user_id: (conv.lead.fio_parent or "").strip()
        for conv in store.all_conversations()
        if conv.user_id
    }

    grouped: dict[str, list[dict]] = defaultdict(list)
    for turn in turns:
        uid = str(turn.get("user_id", "")).strip()
        if uid:
            grouped[uid].append(turn)

    total_users = len(grouped)
    total_turns = len(turns)
    lead_users = 0
    handoff_users = 0
    homework_users = 0
    lines = [
        "🤖 Диалоги за период",
        f"Всего диалогов: {total_users}",
        f"Сообщений: {total_turns}",
    ]

    summaries: list[tuple[str, str, str, list[str], int]] = []
    for uid, user_turns in grouped.items():
        user_turns.sort(key=lambda item: str(item.get("ts", "")))
        last = user_turns[-1]
        stage = str(last.get("stage", "")).strip()
        result = _classify_result(user_turns, stage)
        if result == "заявка":
            lead_users += 1
        elif result == "передан администратору":
            handoff_users += 1
        elif result == "домашка":
            homework_users += 1

        user_messages = [
            _shorten(str(turn.get("user_text", "")))
            for turn in user_turns
            if str(turn.get("user_text", "")).strip()
        ]
        summary_messages = user_messages[:_MAX_MESSAGES]
        more_count = max(0, len(user_messages) - len(summary_messages))
        summaries.append((uid, name_by_uid.get(uid, ""), result, summary_messages, more_count))

    consultation_users = max(0, total_users - lead_users - handoff_users - homework_users)
    lines.extend(
        [
            f"Заявок: {lead_users}",
            f"Передано администратору: {handoff_users}",
            f"Домашка: {homework_users}",
            f"Консультации: {consultation_users}",
            "",
            "По диалогам:",
        ]
    )

    for idx, (uid, fio_parent, result, messages, more_count) in enumerate(summaries[:_MAX_USERS], start=1):
        who = f"{uid}"
        if fio_parent:
            who += f" / {fio_parent}"
        lines.append(f"{idx}. {who} — {result}.")
        if messages:
            lines.append("   Сообщения: " + " | ".join(messages))
        else:
            lines.append("   Сообщения: нет текста.")
        if more_count:
            lines.append(f"   …и ещё {more_count} сообщений.")

    if total_users > _MAX_USERS:
        lines.append(f"…и ещё {total_users - _MAX_USERS} диалогов.")

    return "\n".join(lines)
