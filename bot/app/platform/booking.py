"""Booking Engine: запись на пробное занятие.

Поток (anti-race, никакого доверия кэшу перед записью):
1. validate input → 2. свежий запрос группы и урока в BigBen →
3. проверка свободных мест (fresh) → 4. create lead (idempotent) →
5. create demo-lesson (idempotent) → 6. confirm локально → notify.

Если место заняли между показом и записью — НЕ техническая ошибка, а честный
ответ «место только что заняли» + альтернативы из свежих данных.

Если в CRM не задан max_students (capacity=null), вместимость берём из
вместимости аудитории (BIGBEN_CAPACITY_FALLBACK_AUDITORY) — физический лимит
кабинета; если и её нет, запись не блокируем (occupied-лимит неизвестен).
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass

from app.config import settings
from app.platform import bb_store
from app.platform.bigben_v2 import BigBenError, get_bigben_v2

logger = logging.getLogger(__name__)


class SlotUnavailable(Exception):
    """Место занято / группа переполнена по свежим данным."""


@dataclass
class BookingResult:
    booking_id: int
    status: str           # confirmed | duplicate | failed | slot_unavailable
    lead_id: int | None = None
    demo_lesson_id: int | None = None
    error: str = ""
    alternatives: list[dict] | None = None


def filial_capacity(filial_caption: str) -> int | None:
    """Физический лимит группы по правилам филиала (конфиг, не магические числа)."""
    cap = (filial_caption or "").lower()
    if "лихачев" in cap:
        return settings.CAPACITY_LIKHACHEVSKY
    if "ракетостроител" in cap:
        return settings.CAPACITY_RAKETOSTROITELEY
    if "школ" in cap:
        return settings.CAPACITY_SCHOOL
    return None


def effective_capacity(group: dict) -> int | None:
    """Лимит мест группы.

    Приоритет: правило филиала (физическое ограничение школы) как верхняя
    граница для явного max_students CRM; если ни того ни другого нет —
    вместимость аудитории как fallback.
    """
    rule = filial_capacity((group.get("filial") or {}).get("caption", ""))
    explicit = group.get("capacity")
    if explicit and rule:
        return min(explicit, rule)
    if explicit:
        return explicit
    if rule:
        return rule
    if settings.BIGBEN_CAPACITY_FALLBACK_AUDITORY:
        auditory = group.get("auditory") or {}
        cap = auditory.get("capacity")
        if cap and cap > 0:
            return cap
    return None


def group_free_slots(group: dict) -> int | None:
    """Свободные места: из API, либо вычисленные через fallback-вместимость."""
    if group.get("free_slots") is not None:
        return group["free_slots"]
    cap = effective_capacity(group)
    if cap is None:
        return None
    return max(0, cap - int(group.get("occupied", 0)))


async def _fresh_group(group_id: int) -> dict | None:
    """Свежие данные группы напрямую из API (не из кэша)."""
    client = get_bigben_v2()
    try:
        groups = await client.groups()
    except BigBenError:
        raise
    for g in groups:
        if g.get("id") == group_id:
            return g
    return None


async def find_alternatives(filial_id: int | None, exclude_group_id: int,
                            limit: int = 3) -> list[dict]:
    """Альтернативные группы со свободными местами (свежие данные)."""
    client = get_bigben_v2()
    try:
        groups = await client.groups()
    except BigBenError:
        return []
    out = []
    for g in groups:
        if g.get("id") == exclude_group_id:
            continue
        if filial_id and (g.get("filial") or {}).get("id") != filial_id:
            continue
        free = group_free_slots(g)
        if free is None or free > 0:
            out.append({"group_id": g["id"], "caption": g.get("caption", ""),
                        "free_slots": free,
                        "filial": (g.get("filial") or {}).get("caption", "")})
        if len(out) >= limit:
            break
    return out


async def book_trial(*, parent_name: str, phone: str, child_name: str,
                     child_age: str, group_id: int, lesson_id: int,
                     comment: str = "", source: str = "site",
                     idempotency_key: str | None = None) -> BookingResult:
    """Полная запись на пробное занятие с anti-race проверкой."""
    idem = idempotency_key or uuid.uuid4().hex
    phone_norm = normalize_phone(phone)
    if not phone_norm:
        return BookingResult(0, "failed", error="Некорректный номер телефона")

    filial_id = None
    local_group = bb_store.get_group(group_id)
    if local_group:
        filial_id = local_group.get("filial_id")

    booking_id, is_dup = bb_store.create_booking(
        parent_name=parent_name, phone=phone_norm, child_name=child_name,
        child_age=child_age, comment=comment, source=source,
        group_id=group_id, lesson_id=lesson_id, filial_id=filial_id,
        idempotency_key=idem)
    if is_dup:
        existing = bb_store.booking_by_id(booking_id)
        return BookingResult(booking_id, "duplicate",
                             lead_id=existing.get("lead_id"),
                             demo_lesson_id=existing.get("demo_lesson_id"))

    client = get_bigben_v2()
    # --- Anti-race: свежая проверка перед записью ---
    try:
        fresh = await _fresh_group(group_id)
    except BigBenError as exc:
        bb_store.fail_booking(booking_id, f"bigben_unavailable: {exc.code}")
        return BookingResult(booking_id, "failed",
                             error="Не удалось подтвердить свободное место. Попробуйте позже.")
    if fresh is None:
        bb_store.fail_booking(booking_id, "group_not_found")
        return BookingResult(booking_id, "failed", error="Группа не найдена в CRM")
    free = group_free_slots(fresh)
    if free is not None and free <= 0:
        bb_store.fail_booking(booking_id, "slot_unavailable")
        alternatives = await find_alternatives(filial_id, group_id)
        return BookingResult(booking_id, "slot_unavailable", alternatives=alternatives)

    # --- Лид в CRM (идемпотентно) ---
    note_parts = [f"Запись на пробное: {fresh.get('caption', group_id)}"]
    if child_name:
        note_parts.append(f"Ребёнок: {child_name}, {child_age}")
    if comment:
        note_parts.append(comment)
    try:
        lead = await client.create_lead(
            name=parent_name or child_name, phone=phone_norm,
            source=source or "site-booking",
            comment=" | ".join(note_parts),
            idempotency_key=f"lead-{idem}")
        lead_id = lead.get("id")
    except BigBenError as exc:
        bb_store.fail_booking(booking_id, f"lead_failed: {exc.code} {exc.details}")
        return BookingResult(booking_id, "failed",
                             error="Не удалось передать заявку в CRM")

    # --- Демо-урок ---
    try:
        demo = await client.create_demo_lesson(
            group_id=group_id, lesson_id=lesson_id, lead_id=lead_id,
            idempotency_key=f"demo-{idem}")
        demo_id = demo.get("id")
    except BigBenError as exc:
        bb_store.fail_booking(booking_id, f"demo_failed: {exc.code} {exc.details}")
        logger.error("booking %s: лид %s создан, демо не создано: %s",
                     booking_id, lead_id, exc)
        return BookingResult(booking_id, "failed", lead_id=lead_id,
                             error="Заявка принята, но запись на занятие требует подтверждения менеджером")

    bb_store.confirm_booking(booking_id, lead_id=lead_id, demo_lesson_id=demo_id)
    # Оптимистично сдвигаем занятость в read-model до следующей синхронизации.
    _bump_occupied(group_id)
    _schedule_reminders(booking_id, phone_norm, lesson_id, fresh.get("caption", ""))
    return BookingResult(booking_id, "confirmed", lead_id=lead_id, demo_lesson_id=demo_id)


def _schedule_reminders(booking_id: int, phone: str, lesson_id: int, group_caption: str) -> None:
    """Напоминания о пробном через automation engine. Сбой не ломает запись."""
    try:
        from app.platform import automations
        lessons = bb_store._rows("SELECT starts_at FROM bb_lessons WHERE id=?", (lesson_id,))
        starts_at = lessons[0]["starts_at"] if lessons else None
        if starts_at:
            n = automations.schedule_lesson_reminders(
                booking_id=booking_id, phone=phone,
                lesson_starts_at=starts_at, group_caption=group_caption)
            logger.info("booking %s: напоминаний запланировано: %d", booking_id, n)
    except Exception:
        logger.exception("booking %s: не удалось запланировать напоминания", booking_id)


def _bump_occupied(group_id: int) -> None:
    try:
        db = bb_store._db()
        db.execute("UPDATE bb_groups SET occupied=occupied+1 WHERE id=?", (group_id,))
        db.commit()
    except Exception:
        logger.exception("booking: не удалось сдвинуть occupied группы %s", group_id)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits.startswith("7"):
        return "+" + digits
    return ""
