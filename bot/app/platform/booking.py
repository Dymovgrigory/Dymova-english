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

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass

from app.config import settings
from app.platform import bb_store
from app.platform.bigben_v2 import BigBenError, get_bigben_v2

logger = logging.getLogger(__name__)


_LEVEL_RE = re.compile(
    r"\b(starters?|movers?|flyers?|ket|pet|fce|a0|a1\+?|a2\+?|b1\+?|b2\+?|c1\+?|c2|ml\d)(?![\w+])",
    re.IGNORECASE)
# Порядок уровней для сортировки расписания (от младшего к старшему).
LEVEL_ORDER = ["pre-a1", "pre-a1+", "starter", "starters", "movers", "flyers",
               "a0", "a1", "a1+", "ket", "a2", "a2+", "pet",
               "b1", "b1+", "b2", "b2+", "fce", "c1", "c1+", "c2"]


def derive_level(caption: str) -> str:
    """Уровень группы из названия (в API BigBen поля уровня нет)."""
    m = _LEVEL_RE.search(caption or "")
    return m.group(1).upper() if m else ""


def level_rank(level: str) -> int:
    try:
        return LEVEL_ORDER.index(level.lower())
    except ValueError:
        return len(LEVEL_ORDER)


def derive_teacher(caption: str) -> str:
    """Педагог из названия группы по списку KNOWN_TEACHERS (фамилия)."""
    cap = (caption or "").lower()
    for full in settings.KNOWN_TEACHERS.split(","):
        full = full.strip()
        if not full:
            continue
        surname = full.split()[-1].lower()
        if surname and surname in cap:
            return full
    return ""


# --- Курс и уровень CEFR по учебнику (линейка My Level + Get Involved) ---
# Источник соответствия: mylevelbook.com (My Level 1-5 — Pre-A1..A1+,
# дети 6-12), Get Involved — подростковая линейка, CEFR в названии группы.
_MY_LEVEL_RE = re.compile(r"(?:my\s*level|\bml)\s*(\d)", re.IGNORECASE)
_GET_INVOLVED_RE = re.compile(
    r"get\s*involved\s*(a1\+?|a2\+?|b1\+?|b2\+?)", re.IGNORECASE)
_PRESCHOOL_RE = re.compile(
    r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*лет|baby", re.IGNORECASE)

MY_LEVEL_CEFR = {"1": "Pre-A1", "2": "Pre-A1", "3": "A1", "4": "A1", "5": "A1+"}


def derive_course_level(caption: str) -> tuple[str, str]:
    """(курс, уровень CEFR) из названия группы. Пусто, если не распознано."""
    cap = caption or ""
    m = _GET_INVOLVED_RE.search(cap)
    if m:
        return "Get Involved", m.group(1).upper()
    m = _MY_LEVEL_RE.search(cap)
    if m:
        n = m.group(1)
        return f"My Level {n}", MY_LEVEL_CEFR.get(n, "")
    if _PRESCHOOL_RE.search(cap):
        return "Дошкольная программа", "Pre-A1"
    return "", ""


def is_individual(caption: str) -> bool:
    """Индивидуальные занятия — не группы, в онлайн-расписании им не место.

    Признаки: «индивидуальн…» в названии или название = ФИО педагога
    (в CRM индивидуальные карточки часто названы именем педагога).
    """
    cap = (caption or "").strip().lower()
    if "индивидуальн" in cap:
        return True
    for full in settings.KNOWN_TEACHERS.split(","):
        if full.strip() and full.strip().lower() == cap:
            return True
    return False


def short_teacher_name(fio: str) -> str:
    """«Дымова Вероника Александровна» → «Вероника Дымова»."""
    parts = (fio or "").split()
    if len(parts) >= 2:
        return f"{parts[1]} {parts[0]}"
    return fio or ""


def group_teacher(group_id: int, caption: str) -> str:
    """Педагог: bb_group_meta (внутренний API, источник истины) →
    таблица соответствия (GROUP_TEACHER_MAP_JSON) → фамилия в названии."""
    from app.platform import bb_store as _st
    meta = _st.group_meta_map().get(group_id)
    if meta and meta.get("teacher"):
        return short_teacher_name(meta["teacher"])
    import json as _json
    raw = (settings.GROUP_TEACHER_MAP_JSON or "").strip()
    if raw:
        try:
            table = _json.loads(raw)
        except ValueError:
            logger.error("GROUP_TEACHER_MAP_JSON: невалидный JSON")
            table = {}
        hit = table.get(str(group_id))
        if hit:
            return str(hit)
    return derive_teacher(caption)


def trial_price_rub(duration_min: int | None) -> int | None:
    """Цена платного пробного по длительности урока (конфиг, не магия).

    120 мин (сдвоенные) — 2250 ₽; 55–89 мин — 1125 ₽; 40–54 — 875 ₽.
    """
    if duration_min is None:
        return None
    if duration_min >= 90:
        return settings.TRIAL_PRICE_120_RUB
    if 55 <= duration_min < 90:
        return settings.TRIAL_PRICE_60_RUB
    if 40 <= duration_min < 55:
        return settings.TRIAL_PRICE_45_RUB
    return None


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

    return await fulfill_trial(booking_id, idem=idem, fresh=fresh)


async def fulfill_trial(booking_id: int, *, idem: str, fresh: dict) -> BookingResult:
    """CRM-регистрация подтверждённой записи: лид + демо-урок + напоминания.

    Вызывается сразу (бесплатное пробное) или из webhook об оплате
    (платное пробное). Идемпотентно: повтор по уже confirmed-записи
    возвращает duplicate, ключи lead-/demo- не дают дублей в CRM.
    """
    row = bb_store.booking_by_id(booking_id)
    if row is None:
        return BookingResult(booking_id, "failed", error="Запись не найдена")
    if row.get("status") == "confirmed":
        return BookingResult(booking_id, "duplicate",
                             lead_id=row.get("lead_id"),
                             demo_lesson_id=row.get("demo_lesson_id"))
    group_id = row["group_id"]
    lesson_id = row["lesson_id"]
    client = get_bigben_v2()

    # --- Лид в CRM (идемпотентно) ---
    note_parts = [f"Запись на пробное: {fresh.get('caption', group_id)}"]
    if row.get("child_name"):
        note_parts.append(f"Ребёнок: {row['child_name']}, {row.get('child_age', '')}")
    if row.get("comment"):
        note_parts.append(row["comment"])
    try:
        lead = await client.create_lead(
            name=row.get("parent_name") or row.get("child_name") or "",
            phone=row.get("phone", ""),
            source=row.get("source") or "site-booking",
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
    _schedule_reminders(booking_id, row.get("phone", ""), lesson_id,
                        fresh.get("caption", ""))
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


# --- Платное пробное (TRIAL_PAID): запись подтверждается оплатой ---

async def start_paid_trial(*, parent_name: str, phone: str, child_name: str,
                           child_age: str, group_id: int, lesson_id: int,
                           duration_min: int | None, comment: str = "",
                           source: str = "site",
                           price_rub: int | None = None,
                           description: str = "",
                           idempotency_key: str | None = None) -> tuple[BookingResult, dict | None]:
    """Создаёт запись в ожидании оплаты + инвойс CloudPayments.

    Цена — только серверная (по длительности урока). CRM не трогаем до
    подтверждённого webhook pay: не подтвердилось — место не занято.
    """
    from app.platform import billing
    idem = idempotency_key or uuid.uuid4().hex
    phone_norm = normalize_phone(phone)
    if not phone_norm:
        return BookingResult(0, "failed", error="Некорректный номер телефона"), None

    price = price_rub if price_rub is not None else trial_price_rub(duration_min)
    if price is None:
        return BookingResult(0, "failed",
                             error="Цена для этой группы не настроена"), None

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
        inv = existing.get("invoice_id")
        if existing.get("status") == "awaiting_payment" and inv:
            pay_row = billing.get_payment(inv)
            if pay_row and pay_row.get("status") == "created":
                provider = billing.get_provider()
                pay: dict = {"invoice_id": inv, "amount_rub": price,
                             "provider": provider.name}
                if provider.name == "tbank":
                    import json as _json
                    try:
                        raw = _json.loads(pay_row.get("raw_json") or "{}")
                    except ValueError:
                        raw = {}
                    pay.update({"payment_url": raw.get("payment_url", ""),
                                "sbp_url": raw.get("sbp_url", ""),
                                "sbp_qr_svg": raw.get("sbp_qr_svg", "")})
                else:
                    pay["widget"] = _widget_params(inv, price, phone_norm)
                return BookingResult(booking_id, "awaiting_payment"), pay
        return BookingResult(booking_id, "duplicate",
                             lead_id=existing.get("lead_id"),
                             demo_lesson_id=existing.get("demo_lesson_id")), None

    # Anti-race: свежая проверка мест до выставления счёта
    try:
        fresh = await _fresh_group(group_id)
    except BigBenError:
        bb_store.fail_booking(booking_id, "bigben_unavailable")
        return BookingResult(booking_id, "failed",
                             error="Не удалось подтвердить свободное место. Попробуйте позже."), None
    if fresh is None:
        bb_store.fail_booking(booking_id, "group_not_found")
        return BookingResult(booking_id, "failed", error="Группа не найдена в CRM"), None
    free = group_free_slots(fresh)
    if free is not None and free <= 0:
        bb_store.fail_booking(booking_id, "slot_unavailable")
        alternatives = await find_alternatives(filial_id, group_id)
        return BookingResult(booking_id, "slot_unavailable",
                             alternatives=alternatives), None

    provider = billing.get_provider()
    desc = (description or f"Пробное занятие: {fresh.get('caption', '')}")[:120]
    try:
        inv = provider.create_invoice(
            amount_kopecks=price * 100, phone=phone_norm, description=desc)
        # Т-Банк делает вызов Init (async), CloudPayments — локальный инвойс
        if asyncio.iscoroutine(inv):
            inv = await inv
    except billing.BillingError as exc:
        bb_store.fail_booking(booking_id, f"invoice_failed: {exc}")
        return BookingResult(booking_id, "failed", error=str(exc)), None
    bb_store.set_booking_awaiting_payment(booking_id, inv["invoice_id"],
                                          amount_kopecks=price * 100)
    pay: dict = {"invoice_id": inv["invoice_id"], "amount_rub": price,
                 "provider": provider.name}
    if provider.name == "tbank":
        pay.update({"payment_url": inv.get("payment_url", ""),
                    "sbp_url": inv.get("sbp_url", ""),
                    "sbp_qr_svg": inv.get("sbp_qr_svg", "")})
    else:
        widget = dict(inv["widget"])
        widget["description"] = desc
        pay["widget"] = widget
    return BookingResult(booking_id, "awaiting_payment"), pay


async def handle_payment_confirmed(invoice_id: str, *, source: str) -> None:
    """Единая реакция на подтверждённую оплату — из вебхука или из polling.

    Вызывать только когда billing.mark_paid вернул is_new=True: повторные
    вебхуки/опросы сюда не доходят, дублей уведомлений нет.
    Порядок: аналитика → thankyou клиенту → CRM-регистрация записи →
    уведомления админам и методисту.
    """
    from app.platform import analytics, automations, billing
    row = billing.get_payment(invoice_id)
    if row is None:
        return
    amount_rub = round(row["amount_kopecks"] / 100, 2)
    analytics.track("payment_success", source=source,
                    meta={"invoice_id": invoice_id})
    try:
        automations.schedule_payment_thankyou(
            invoice_id=invoice_id, phone=row["phone"], amount_rub=amount_rub)
    except Exception:
        logger.exception("billing: не удалось запланировать thankyou")
    res = await fulfill_paid_booking(invoice_id)
    try:
        from app.platform.billing_api import _notify_admins
        await _notify_admins(
            f"💳 Онлайн-оплата: {amount_rub} ₽\n"
            f"Телефон: {row['phone'] or '—'}, ученик: {row['student_id'] or '—'}\n"
            f"Инвойс: {invoice_id}")
    except Exception:
        logger.exception("billing: не удалось уведомить админов (инвойс %s)",
                         invoice_id)
    if res is not None:
        status_line = ("запись подтверждена в CRM"
                       if res.status in ("confirmed", "duplicate")
                       else f"ВНИМАНИЕ: запись НЕ подтверждена ({res.error})")
        try:
            from app.platform.public_api import _notify_staff
            await _notify_staff(
                f"✅ Оплаченное пробное #{res.booking_id}: {amount_rub} ₽\n"
                f"{status_line}")
        except Exception:
            logger.exception("billing: не удалось уведомить методиста (инвойс %s)",
                             invoice_id)


def _widget_params(invoice_id: str, price_rub: int, phone: str) -> dict:
    from app.config import settings as st
    return {"publicId": st.CLOUDPAYMENTS_PUBLIC_ID,
            "amount": float(price_rub), "currency": "RUB",
            "invoiceId": invoice_id, "accountId": phone,
            "description": st.CLOUDPAYMENTS_DESCRIPTION}


async def fulfill_paid_booking(invoice_id: str) -> BookingResult | None:
    """Вызывается из webhook об оплате: подтверждает запись в CRM.

    Повторный webhook безопасен: fulfill_trial идемпотентен.
    """
    row = bb_store.booking_by_invoice(invoice_id)
    if row is None:
        return None
    idem = row.get("idempotency_key") or uuid.uuid4().hex
    try:
        fresh = await _fresh_group(row["group_id"])
    except BigBenError:
        fresh = None
    if fresh is None:
        # Деньги получены, но CRM недоступна — не теряем: помечаем и
        # уведомляем; повторная обработка — через replay/ручной запуск.
        bb_store.mark_booking_paid_unfulfilled(row["id"])
        logger.error("booking %s оплачен (инвойс %s), но CRM недоступна",
                     row["id"], invoice_id)
        return BookingResult(row["id"], "failed",
                             error="Оплата получена, запись подтвердит менеджер")
    return await fulfill_trial(row["id"], idem=idem, fresh=fresh)
