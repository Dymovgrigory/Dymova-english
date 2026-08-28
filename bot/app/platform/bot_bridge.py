"""Мост бот ↔ платформа: детерминированные ответы из живых данных CRM.

LLM не участвует в формировании фактов о расписании и местах — только
read-model BigBen. Это реализация правила «бот не выдумывает расписание,
группы, места» (§38 мандата): если данных нет — честно говорим об этом и
предлагаем менеджера, а не фантазируем.
"""
from __future__ import annotations

import logging
import re

from app.config import settings
from app.platform import bb_store, booking

logger = logging.getLogger(__name__)

# Возраст из свободного текста: «дочке 8 лет», «сын 7», «нам 10».
_AGE_RE = re.compile(r"(\d{1,2})\s*(?:лет|год(?:а|ик)?\b|г\.?)", re.IGNORECASE)


_BARE_AGE_RE = re.compile(
    r"(?:сыну|сын|дочке|дочь|дочери|ребёнку|ребенку|нам)\s+(\d{1,2})\b",
    re.IGNORECASE)


def extract_age(text: str) -> int | None:
    m = _AGE_RE.search(text or "")
    if not m:
        m = _BARE_AGE_RE.search(text or "")
    if not m:
        return None
    age = int(m.group(1))
    return age if 3 <= age <= 18 else None


def _match_filial(text: str) -> dict | None:
    """Филиал по упоминанию в тексте (по названиям из CRM, не хардкод)."""
    lowered = (text or "").lower()
    if not lowered:
        return None
    for f in bb_store.list_filials():
        caption = (f.get("caption") or "").lower()
        # значимые слова из названия филиала (улица/район), длиннее 4 букв
        for word in re.findall(r"[а-яёa-z]{5,}", caption):
            if word in lowered:
                return f
    return None


def _age_fits(group_caption: str, age: int) -> bool | None:
    """Подходит ли группа по возрасту. None — в названии возраста нет."""
    m = re.search(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*лет", group_caption)
    if m:
        return int(m.group(1)) <= age <= int(m.group(2))
    m = re.search(r"(\d{1,2})\s*лет", group_caption)
    if m:
        return abs(int(m.group(1)) - age) <= 1
    m = re.search(r"\b(\d{1,2})\s*[-–—]\s*(\d{1,2})\b", group_caption)
    if m and 3 <= int(m.group(1)) <= 18:
        return int(m.group(1)) <= age <= int(m.group(2))
    return None


def active_groups(filial_id: int | None = None) -> list[dict]:
    """Активные группы (с уроками впереди) + вычисленные свободные места."""
    import json as _json
    from datetime import date, timedelta
    today = date.today()
    lessons = bb_store.list_lessons(today.isoformat(),
                                    (today + timedelta(days=60)).isoformat())
    active_ids = {l.get("group_id") for l in lessons}
    out = []
    for g in bb_store.list_groups(filial_id):
        if g["id"] not in active_ids:
            continue
        raw = _json.loads(g.get("raw_json") or "{}")
        g = dict(g)
        g["free_calc"] = booking.group_free_slots(raw)
        out.append(g)
    return out


def schedule_reply(text: str) -> str:
    """Ответ на «какое у вас расписание / есть ли места» из живых данных."""
    age = extract_age(text)
    filial = _match_filial(text)
    groups = active_groups(filial["id"] if filial else None)

    if not groups:
        if filial:
            return (f"По филиалу «{filial['caption']}» я не вижу актуального "
                    "расписания — данные могли ещё не синхронизироваться. "
                    "Передам вопрос администратору, он подскажет точно.")
        return ("Я не вижу актуального расписания в системе — передам вопрос "
                "администратору, он подскажет точно. А пока могу рассказать "
                "о направлениях и ценах.")

    scored: list[tuple[int, dict]] = []
    for g in groups:
        score = 0
        fits = _age_fits(g.get("caption", ""), age) if age else None
        if fits is True:
            score += 2
        elif fits is False:
            continue  # возраст явно не подходит — не показываем
        if filial and g.get("filial_id") == filial["id"]:
            score += 1
        free = g.get("free_calc")
        if free is not None and free <= 0:
            continue  # мест нет — не рекламируем
        scored.append((score, g))
    scored.sort(key=lambda t: (-t[0], t[1].get("caption", "")))
    top = [g for _, g in scored[:5]] or [g for _, g in scored[:0]]

    if not top:
        extra = f" для возраста {age} лет" if age else ""
        return (f"Свободных групп{extra} по живым данным сейчас не вижу. "
                "Передам администратору — возможно, откроется новая группа "
                "или есть место вне расписания.")

    lines = []
    for g in top:
        free = g.get("free_calc")
        if free is None:
            slots = "места уточняем"
        elif free <= settings.LOW_AVAILABILITY_THRESHOLD:
            slots = f"осталось {free} м." if free == 1 else f"осталось {free} м."
        else:
            slots = f"свободно {free} м."
        filial_name = g.get("filial_caption") or ""
        lines.append(f"• {g['caption']} — {filial_name}, {slots}")

    header = "Вот актуальные группы"
    if age:
        header += f" для {age} лет"
    if filial:
        header += f" ({filial['caption']})"
    footer = ("\n\nДанные живые, из системы записи. Хотите на пробное занятие? "
              "Могу оформить заявку прямо здесь — скажите, какая группа подходит.")
    return f"{header}:\n" + "\n".join(lines) + footer
