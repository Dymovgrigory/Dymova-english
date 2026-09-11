"""Ночной анализатор: бот учится на слабых местах прошедших суток.

Спека approach-1, раздел 5.1. Каждую ночь (расписание в `scheduler`) модуль:

1. Собирает слабые места за 24 часа: пробелы базы знаний (`insights`,
   вопросы без уверенного ответа) и события качества ответов (`ai_events`).
2. Просит LLM (роль ROLE_CRITIC) предложить конкретные улучшения в виде
   структурированного JSON: дополнения базы знаний и правки промпта.
3. Применяет их автоматически: новые записи в `kb_documents`, новая версия
   промпта в `ai_prompts` + активация; факт применения — в `learning_log`,
   чтобы любое изменение откатывалось одним действием (см. /admin/learning_log).

Ночная задача не имеет права ронять бота: любой сбой (БД, LLM, битый JSON)
— только запись в лог.
"""
from __future__ import annotations

import logging
from datetime import date

from app import crm_store
from app import insights
from app import sales
from app.config import settings
from app.llm_gateway import ROLE_CRITIC, get_gateway

logger = logging.getLogger(__name__)

# Сколько предложений за раз применяем: ночной цикл не должен за одну ночь
# переписать половину базы знаний и промпта.
_MAX_KB_ADDITIONS = 3
_MAX_PROMPT_CHANGES = 2
# Порог «чему учиться»: меньше слабых ответов за сутки — нечего анализировать.
_MIN_WEAK_ANSWERS = 2

_SCHEMA = {
    "type": "object",
    "properties": {
        "kb_additions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["topic", "text"],
                "additionalProperties": False,
            },
        },
        "prompt_changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "change": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["section", "change", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["kb_additions", "prompt_changes"],
}


def _collect_weak_points() -> dict:
    """Слабые места за последние сутки: пробелы БЗ и события качества."""
    gaps = insights.summarize(days=1, top=10)
    try:
        events = crm_store.list_ai_events(days=1, limit=30)
    except Exception:
        logger.exception("learning_loop: не удалось прочитать ai_events")
        events = []
    return {"gaps": gaps, "events": events}


def _proposal_messages(weak: dict, current_prompt: str) -> list[dict]:
    gaps = weak["gaps"]
    lines = [
        "Вопросы родителей за сутки, на которые бот ответил слабо или не знал:"
    ]
    for gap in gaps["gaps"]:
        lines.append(
            f"- «{gap['question']}» — {gap['count']} раз, родителей: {gap['users']}, "
            f"причина: {gap['reason'] or 'не указана'}"
        )
    events_text = "\n".join(
        f"- {event.get('kind', 'event')}: {str(event.get('payload', ''))[:200]}"
        for event in weak["events"][:10]
    )
    if events_text:
        lines.append("\nСобытия качества ответов за сутки:\n" + events_text)
    lines.append(
        "\nВот текущий системный промпт консультанта:\n---\n"
        + current_prompt
        + "\n---\nПредложи конкретные улучшения: что добавить в базу знаний "
        "(kb_additions — готовые фактические тексты о школе, без выдуманных "
        "цен и расписаний) и что уточнить в инструкциях промпта (prompt_changes, "
        "change=add — короткое новое правило). Если улучшать нечего, верни "
        "пустые массивы. Не переписывай существующие правила, только дополняй."
    )
    return [
        {
            "role": "system",
            "content": "Ты — методист языковой школы «Фоксинбург». Улучшаешь "
            "консультанта-бота по журналу его слабых ответов.",
        },
        {"role": "user", "content": "\n".join(lines)},
    ]


def _apply_prompt_changes(current_prompt: str, changes: list[dict]) -> tuple[str, list[dict]]:
    """Дописывает новые правила (change=add) в конец промпта.

    Замены и удаления специально не поддерживаем: автоматическая правка
    существующего текста промпта ночью, без глаз человека, — слишком рискованно.
    """
    additions = []
    applied: list[dict] = []
    for change in changes[:_MAX_PROMPT_CHANGES]:
        text = str(change.get("text", "")).strip()
        if str(change.get("change", "")).strip() != "add" or not text:
            continue
        additions.append(f"- {text}")
        applied.append(change)
    if not additions:
        return current_prompt, []
    new_prompt = (
        current_prompt.rstrip()
        + f"\n\nДополнительные правила (автоулучшение от {date.today().isoformat()}):\n"
        + "\n".join(additions)
    )
    return new_prompt, applied


async def run_nightly_learning() -> dict:
    """Один цикл ночного анализа. Возвращает статистику применения."""
    stats = {
        "insights_analyzed": 0,
        "kb_added": 0,
        "prompt_changed": False,
        "skipped": False,
    }
    try:
        weak = _collect_weak_points()
        gaps = weak["gaps"]
        stats["insights_analyzed"] = gaps["total_weak_answers"]
        if gaps["total_weak_answers"] < _MIN_WEAK_ANSWERS:
            logger.info(
                "learning_loop: слабых ответов %s < %s — пропускаю цикл",
                gaps["total_weak_answers"], _MIN_WEAK_ANSWERS,
            )
            stats["skipped"] = True
            return stats

        current_prompt = sales.base_prompt()
        active = crm_store.prompt_active()
        version_before = int(active["version"]) if active else 0

        suggestion = await get_gateway().structured(
            ROLE_CRITIC,
            _proposal_messages(weak, current_prompt),
            _SCHEMA,
            name="learning_loop_proposal",
        )
        if suggestion is None:
            logger.warning("learning_loop: LLM не вернул разборный JSON — цикл пропущен")
            return stats

        kb_ids = []
        for addition in suggestion.get("kb_additions", [])[:_MAX_KB_ADDITIONS]:
            topic = str(addition.get("topic", "")).strip()
            text = str(addition.get("text", "")).strip()
            if not topic or not text:
                continue
            kb_ids.append(crm_store.kb_add(topic[:200], text, category="learning_loop"))
        stats["kb_added"] = len(kb_ids)

        new_prompt, applied_changes = _apply_prompt_changes(
            current_prompt, suggestion.get("prompt_changes", []))
        version_after = version_before
        if applied_changes:
            new_id = crm_store.prompt_add(new_prompt, created_by="learning_loop")
            if crm_store.prompt_activate(new_id, actor="learning_loop"):
                sales.reset_prompt_cache()
                version_after = int(crm_store.prompt_get(new_id)["version"])
                stats["prompt_changed"] = True
            else:
                logger.error("learning_loop: не удалось активировать промпт %s", new_id)

        if kb_ids or applied_changes:
            crm_store.learning_log_add(
                prompt_version_before=version_before,
                prompt_version_after=version_after,
                changes={
                    "kb_additions": suggestion.get("kb_additions", [])[:_MAX_KB_ADDITIONS],
                    "prompt_changes": applied_changes,
                    "kb_document_ids": kb_ids,
                },
                insights_analyzed=stats["insights_analyzed"],
            )
        logger.info(
            "learning_loop: цикл завершён — БЗ +%s, промпт изменён: %s",
            stats["kb_added"], stats["prompt_changed"],
        )
    except Exception:
        logger.exception("learning_loop: ошибка ночного цикла — изменения не применены")
    return stats


async def notify_admins(stats: dict) -> None:
    """Короткий отчёт администраторам в MAX (approach-1, р. 5.1, п. 4)."""
    if stats.get("skipped") or (not stats.get("kb_added") and not stats.get("prompt_changed")):
        return
    admins = settings.admin_ids
    if not admins:
        return
    try:
        from app.max_client import get_max

        max_client = get_max()
        if not max_client.configured:
            return
        text = (
            "🌙 Ночной анализ завершён: проанализировано слабых ответов "
            f"{stats['insights_analyzed']}, добавлено знаний в базу: "
            f"{stats['kb_added']}, промпт уточнён: "
            f"{'да' if stats['prompt_changed'] else 'нет'}. "
            "Подробности и откат: /admin/learning_log"
        )
        for admin_id in admins:
            try:
                await max_client.send_message(admin_id, text)
            except Exception:
                logger.exception("learning_loop: не удалось уведомить администратора %s", admin_id)
    except Exception:
        logger.exception("learning_loop: не удалось отправить отчёт администраторам")
