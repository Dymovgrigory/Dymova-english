"""Публичные API платформы: расписание, группы, запись на пробное, health.

Используются сайтом (виджет расписания), ботами и мини-аппом — единый
источник данных, чтобы «3 места» означало одно и то же везде (§211).
Ответы всегда содержат свежесть данных (synced_at) — клиент решает,
показывать ли «обновлено N минут назад».
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Query, Request
from fastapi import Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.platform import analytics, bb_store, booking, sync
from app.platform.bigben_v2 import BigBenError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/platform", tags=["platform"])


def _age_from_caption(caption: str) -> tuple[int | None, int | None]:
    """Грубое извлечение возрастного диапазона из названия группы."""
    import re
    m = re.search(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*лет", caption)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d{1,2})\s*лет", caption)
    if m:
        return int(m.group(1)), int(m.group(1))
    return None, None


def _is_kindergarten(caption: str, filial_caption: str) -> bool:
    """Детский сад исключён из онлайн-расписания (запись через менеджера)."""
    pat = (settings.KINDERGARTEN_EXCLUDE_PATTERN or "").lower()
    if not pat:
        return False
    return pat in (caption or "").lower() or pat in (filial_caption or "").lower()


def _is_individual(caption: str) -> bool:
    return booking.is_individual(caption)


def _group_card(g: dict, duration_min: int | None = None,
                period: tuple[str, str] | None = None,
                meta: dict | None = None) -> dict:
    group_raw = g.get("raw_json")
    import json as _json
    raw = _json.loads(group_raw) if isinstance(group_raw, str) else (group_raw or {})
    free = booking.group_free_slots(raw) if raw else g.get("free_slots")
    caption = ((meta or {}).get("title") or g.get("caption", "")).strip()
    age_from, age_to = _age_from_caption(caption)
    course, cefr = booking.derive_course_level(caption)
    level = cefr or booking.derive_level(caption)
    # Платное пробное — только для учебных групп (распознанный курс/уровень);
    # мероприятия и консультации остаются бесплатной записью.
    is_event = bool((meta or {}).get("for_events"))
    event_price = (meta or {}).get("cost_per_event") if is_event else None
    price = (booking.trial_price_rub(duration_min)
             if settings.TRIAL_PAID and (course or level) and not is_event else None)
    return {
        "id": g["id"],
        "caption": caption,
        "filial": {"id": g.get("filial_id"), "caption": g.get("filial_caption", "")},
        "auditory": g.get("auditory_caption", ""),
        "capacity": g.get("capacity"),
        "occupied": g.get("occupied", 0),
        "free_slots": free,
        "low_availability": free is not None and 0 < free <= settings.LOW_AVAILABILITY_THRESHOLD,
        "age_from": age_from,
        "age_to": age_to,
        "course": course,
        "level": level,
        "level_rank": booking.level_rank(level) if level else 999,
        "teacher": booking.group_teacher(g["id"], caption),
        "duration_min": duration_min,
        "trial_price_rub": price,
        "is_event": is_event,
        "event_price_rub": event_price,
        "period_start": (meta or {}).get("period_start") or (period[0] if period else None),
        "period_end": (meta or {}).get("period_end") or (period[1] if period else None),
        "schedule": _json.loads(g.get("schedule_json") or "[]"),
        "synced_at": g.get("synced_at"),
    }


def _duration_map() -> dict[int, int]:
    today = date.today()
    date_to = today + timedelta(days=settings.BIGBEN_LESSONS_WINDOW_DAYS)
    return bb_store.lesson_duration_map(today.isoformat(), date_to.isoformat())


@router.get("/filials")
async def filials() -> dict:
    items = await asyncio.to_thread(bb_store.list_filials)
    return {"data": [{"id": f["id"], "caption": f["caption"], "city": f["city"],
                      "address": f["address"]} for f in items]}


@router.get("/groups")
async def groups(filial_id: int | None = Query(default=None),
                 all: bool = Query(default=False)) -> dict:
    """Группы. По умолчанию — только активные (с уроками в окне расписания):
    в CRM сотни архивных групп, показывать их клиенту нельзя."""
    items = await asyncio.to_thread(bb_store.list_groups, filial_id)
    items = [g for g in items
             if not _is_kindergarten(g.get("caption", ""), g.get("filial_caption", ""))
             and not _is_individual(g.get("caption", ""))]
    if not all:
        today = date.today()
        date_to = today + timedelta(days=settings.BIGBEN_LESSONS_WINDOW_DAYS)
        lessons = await asyncio.to_thread(
            bb_store.list_lessons, today.isoformat(), date_to.isoformat())
        active_ids = {les.get("group_id") for les in lessons}
        items = [g for g in items if g["id"] in active_ids]
    durations = await asyncio.to_thread(_duration_map)
    periods = await asyncio.to_thread(bb_store.group_period_map)
    metas = await asyncio.to_thread(bb_store.group_meta_map)
    return {"data": [_group_card(g, durations.get(g["id"]),
                                 periods.get(g["id"]),
                                 metas.get(g["id"])) for g in items]}


@router.get("/schedule")
async def schedule(
    filial_id: int | None = Query(default=None),
    days: int = Query(default=14, ge=1, le=92),
    group_id: int | None = Query(default=None),
) -> dict:
    """Расписание занятий на окно дней: уроки + карточки групп с местами."""
    today = date.today()
    date_to = today + timedelta(days=days)
    lessons, groups = await asyncio.gather(
        asyncio.to_thread(bb_store.list_lessons, today.isoformat(), date_to.isoformat(), group_id),
        asyncio.to_thread(bb_store.list_groups, filial_id),
    )
    durations = await asyncio.to_thread(_duration_map)
    periods = await asyncio.to_thread(bb_store.group_period_map)
    metas = await asyncio.to_thread(bb_store.group_meta_map)
    cards = {g["id"]: _group_card(g, durations.get(g["id"]), periods.get(g["id"]),
                                  metas.get(g["id"]))
             for g in groups
             if not _is_kindergarten(g.get("caption", ""), g.get("filial_caption", ""))
             and not _is_individual(g.get("caption", ""))}
    out_lessons = []
    for les in lessons:
        gid = les.get("group_id")
        if filial_id and les.get("filial_id") != filial_id:
            continue
        if gid not in cards:
            continue  # детский сад не показываем
        card = cards.get(gid)
        out_lessons.append({
            "lesson_id": les["id"],
            "date": les.get("date"),
            "starts_at": les.get("starts_at"),
            "ends_at": les.get("ends_at"),
            "group_id": gid,
            "group_caption": les.get("group_caption", ""),
            "filial": {"id": les.get("filial_id"), "caption": les.get("filial_caption", "")},
            "free_slots": card["free_slots"] if card else None,
            "low_availability": card["low_availability"] if card else False,
        })
    fresh = await asyncio.to_thread(bb_store.freshness)
    return {
        "data": out_lessons,
        "groups": list(cards.values()),
        "freshness": {
            "groups_synced_at": fresh["groups"]["last_synced_at"],
            "lessons_synced_at": fresh["lessons"]["last_synced_at"],
        },
    }


class BookingRequest(BaseModel):
    parent_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=7, max_length=50)
    child_name: str = Field(default="", max_length=255)
    child_age: str = Field(default="", max_length=20)
    group_id: int = Field(gt=0)
    lesson_id: int = Field(gt=0)
    comment: str = Field(default="", max_length=800)
    source: str = Field(default="site", max_length=64)
    idempotency_key: str | None = Field(default=None, max_length=64)


@router.post("/booking")
async def create_booking(req: BookingRequest, request: Request) -> JSONResponse:
    analytics.track("booking_started", source=req.source or "site",
                    meta={"group_id": req.group_id})
    if settings.TRIAL_PAID:
        return await _create_paid_booking(req)
    return await _create_free_booking(req)


async def _create_free_booking(req: "BookingRequest") -> JSONResponse:
    result = await booking.book_trial(
        parent_name=req.parent_name, phone=req.phone,
        child_name=req.child_name, child_age=req.child_age,
        group_id=req.group_id, lesson_id=req.lesson_id,
        comment=req.comment, source=req.source,
        idempotency_key=req.idempotency_key)
    if result.status == "confirmed":
        analytics.track("booking_completed", source=req.source or "site",
                        meta={"group_id": req.group_id, "booking_id": result.booking_id})
        analytics.track("lead_created", source=req.source or "site",
                        meta={"lead_id": result.lead_id})
        await _notify_booking(req, result)
        return JSONResponse({
            "ok": True, "status": "confirmed", "booking_id": result.booking_id,
            "message": "Вы записаны на пробное занятие! Мы свяжемся с вами для подтверждения.",
        }, status_code=201)
    if result.status == "duplicate":
        return JSONResponse({
            "ok": True, "status": "duplicate", "booking_id": result.booking_id,
            "message": "Эта запись уже оформлена — мы свяжемся с вами.",
        })
    if result.status == "slot_unavailable":
        return JSONResponse({
            "ok": False, "status": "slot_unavailable",
            "message": "Это место только что заняли. Вот другие варианты:",
            "alternatives": result.alternatives or [],
        }, status_code=409)
    analytics.track("booking_failed", source=req.source or "site",
                    meta={"group_id": req.group_id, "error": (result.error or "")[:200]})
    return JSONResponse({
        "ok": False, "status": "failed",
        "message": result.error or "Не удалось оформить запись. Попробуйте позже.",
    }, status_code=502)


async def _notify_booking(req: BookingRequest, result: booking.BookingResult) -> None:
    from app.max_client import get_max
    client = get_max()
    if not client.configured:
        return
    text = (f"📝 Запись на пробное (#{result.booking_id})\n"
            f"Родитель: {req.parent_name}, {req.phone}\n"
            f"Ребёнок: {req.child_name} {req.child_age}\n"
            f"Группа #{req.group_id}, урок #{req.lesson_id}\n"
            f"Источник: {req.source}")
    for admin_id in settings.admin_ids:
        try:
            await client.send_message(admin_id, text)
        except Exception:
            logger.exception("booking: не удалось уведомить админа %s", admin_id)




async def _create_paid_booking(req: "BookingRequest") -> JSONResponse:
    """Платное пробное: запись в awaiting_payment + параметры виджета CP.

    Длительность урока берём из read-model (мода по окну) — серверная цена.
    """
    from datetime import date as _date, timedelta as _td
    row = await asyncio.to_thread(
        bb_store._rows,
        "SELECT starts_at, ends_at FROM bb_lessons WHERE id=?", (req.lesson_id,))
    duration = None
    if row:
        try:
            from datetime import datetime as _dt
            t0 = _dt.fromisoformat(str(row[0]["starts_at"]).replace("Z", "+00:00"))
            t1 = _dt.fromisoformat(str(row[0]["ends_at"]).replace("Z", "+00:00"))
            duration = int((t1 - t0).total_seconds() // 60)
        except Exception:
            duration = None
    meta = await asyncio.to_thread(bb_store.group_meta_map)
    meta = meta.get(req.group_id) or {}
    is_event = bool(meta.get("for_events"))
    event_price = meta.get("cost_per_event") if is_event else None
    if is_event:
        if not event_price:
            # Бесплатное мероприятие (ДОД, консультации) — простая запись.
            return await _create_free_booking(req)
        result, pay = await booking.start_paid_trial(
            parent_name=req.parent_name, phone=req.phone,
            child_name=req.child_name, child_age=req.child_age,
            group_id=req.group_id, lesson_id=req.lesson_id,
            duration_min=duration, comment=req.comment, source=req.source,
            price_rub=int(event_price),
            description=f"Мероприятие: {(bb_store.get_group(req.group_id) or {}).get('caption', '')}",
            idempotency_key=req.idempotency_key)
    elif booking.trial_price_rub(duration) is None:
        # Цена не определена (консультации/нестандарт) — бесплатная запись.
        return await _create_free_booking(req)
    else:
        result, pay = await booking.start_paid_trial(
            parent_name=req.parent_name, phone=req.phone,
            child_name=req.child_name, child_age=req.child_age,
            group_id=req.group_id, lesson_id=req.lesson_id,
            duration_min=duration, comment=req.comment, source=req.source,
            idempotency_key=req.idempotency_key)
    if result.status == "awaiting_payment" and pay:
        return JSONResponse({
            "ok": True, "status": "awaiting_payment",
            "booking_id": result.booking_id,
            "invoice_id": pay["invoice_id"],
            "widget": pay["widget"], "amount_rub": pay["amount_rub"],
        }, status_code=201)
    if result.status == "duplicate":
        return JSONResponse({
            "ok": True, "status": "duplicate", "booking_id": result.booking_id,
            "message": "Эта запись уже оформлена — мы свяжемся с вами."})
    if result.status == "slot_unavailable":
        return JSONResponse({
            "ok": False, "status": "slot_unavailable",
            "message": "Это место только что заняли. Вот другие варианты:",
            "alternatives": result.alternatives or []}, status_code=409)
    return JSONResponse({
        "ok": False, "status": "failed",
        "message": result.error or "Не удалось оформить запись. Попробуйте позже."},
        status_code=502)


@router.get("/booking/{booking_id}")
async def booking_status(booking_id: int) -> JSONResponse:
    """Статус записи для поллинга после оплаты. PII не отдаём.

    Если запись ждёт оплаты, а вебхук CP ещё не дошёл — спрашиваем статус
    платежа напрямую у CloudPayments API (запасной канал подтверждения).
    """
    row = await asyncio.to_thread(bb_store.booking_by_id, booking_id)
    if row is None:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    status = row.get("status")
    if status == "awaiting_payment" and row.get("invoice_id"):
        status = await _refresh_paid_status(row)
    return {"ok": True, "status": status, "booking_id": row.get("id")}


async def _refresh_paid_status(row: dict) -> str:
    from app.platform import billing
    model = await billing.cp_find_payment(row["invoice_id"])
    if not model:
        return row.get("status")
    st = str(model.get("Status", ""))
    if st in ("Completed", "Authorized"):
        is_new, _pay = billing.mark_paid(
            row["invoice_id"], str(model.get("TransactionId", "")), model)
        if is_new:
            analytics.track("payment_success", source="cloudpayments-poll",
                            meta={"invoice_id": row["invoice_id"]})
            res = await booking.fulfill_paid_booking(row["invoice_id"])
            return res.status if res else row.get("status")
        fresh = await asyncio.to_thread(bb_store.booking_by_id, row["id"])
        return fresh.get("status", row.get("status"))
    if st in ("Declined", "Cancelled"):
        billing.mark_failed(row["invoice_id"], model)
        bb_store.fail_booking(row["id"], f"payment_{st.lower()}")
        return "failed"
    return row.get("status")


class DiagnosticsRequest(BaseModel):
    parent_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=7, max_length=50)
    child_name: str = Field(default="", max_length=255)
    child_age: str = Field(default="", max_length=20)
    filial_id: int | None = Field(default=None)
    slot: str = Field(default="", max_length=120)
    comment: str = Field(default="", max_length=800)
    idempotency_key: str | None = Field(default=None, max_length=64)


@router.get("/diagnostics/slots")
async def diagnostics_slots() -> dict:
    """Слоты диагностики из конфига + филиалы для формы."""
    import json as _json
    raw = (settings.DIAGNOSTIC_SLOTS_JSON or "").strip()
    slots: list[dict] = []
    if raw:
        try:
            parsed = _json.loads(raw)
            if isinstance(parsed, list):
                slots = [x for x in parsed if isinstance(x, dict)]
        except ValueError:
            logger.error("DIAGNOSTIC_SLOTS_JSON: невалидный JSON")
    filials_items = await asyncio.to_thread(bb_store.list_filials)
    filial_map = {f["id"]: f["caption"] for f in filials_items}
    weekdays = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    out = []
    for sl in slots:
        fid = sl.get("filial_id")
        wd = sl.get("weekday")
        out.append({
            "filial_id": fid,
            "filial": filial_map.get(fid, ""),
            "weekday": wd,
            "label": f"{weekdays[wd] if isinstance(wd, int) and 0 <= wd <= 6 else ''} "
                     f"{sl.get('time', '')}".strip(),
        })
    return {"data": out,
            "filials": [{"id": f["id"], "caption": f["caption"]}
                        for f in filials_items]}


@router.post("/diagnostics")
async def create_diagnostics(req: DiagnosticsRequest) -> JSONResponse:
    """Заявка на диагностику: лид в CRM + уведомление методисту и админам."""
    from app.platform.bigben_v2 import BigBenError, get_bigben_v2
    analytics.track("lead_created", source="site-diagnostics",
                    meta={"filial_id": req.filial_id})
    phone = booking.normalize_phone(req.phone)
    if not phone:
        return JSONResponse({"ok": False, "message": "Укажите корректный номер"},
                            status_code=400)
    note = ["Запись на диагностику (сайт)"]
    if req.child_name:
        note.append(f"Ребёнок: {req.child_name}, {req.child_age}")
    if req.slot:
        note.append(f"Выбранное время: {req.slot}")
    if req.comment:
        note.append(req.comment)
    client = get_bigben_v2()
    try:
        lead = await client.create_lead(
            name=req.parent_name, phone=phone, source="site-diagnostics",
            comment=" | ".join(note)[:800],
            idempotency_key=f"diag-{req.idempotency_key or ''}".strip("-") or None)
        lead_id = lead.get("id")
    except BigBenError as exc:
        logger.error("diagnostics: lead failed: %s %s", exc.code, exc.details)
        return JSONResponse(
            {"ok": False,
             "message": "Не удалось отправить заявку. Позвоните нам, пожалуйста."},
            status_code=502)
    await _notify_staff(
        f"🧪 Диагностика (лид #{lead_id})\n"
        f"Родитель: {req.parent_name}, {phone}\n"
        f"Ребёнок: {req.child_name or '—'} {req.child_age}\n"
        f"Время: {req.slot or 'не выбрано'}\n"
        f"Филиал: {req.filial_id or '—'}")
    return JSONResponse({"ok": True, "status": "created", "lead_id": lead_id,
                         "message": "Заявка отправлена! Мы свяжемся с вами "
                                    "для подтверждения времени."}, status_code=201)


async def _notify_staff(text: str) -> None:
    """Методисту в TG + админам в MAX. Сбой канала не ломает заявку."""
    if settings.METHODIST_TG_IDS:
        from app.telegram_client import TelegramClient
        tg = TelegramClient()
        for chat_id in [x.strip() for x in settings.METHODIST_TG_IDS.split(",") if x.strip()]:
            try:
                await tg.send_message(chat_id, text)
            except Exception:
                logger.exception("notify: TG %s недоступен", chat_id)
    from app.max_client import get_max
    client = get_max()
    if client.configured:
        for admin_id in settings.admin_ids:
            try:
                await client.send_message(admin_id, text)
            except Exception:
                logger.exception("notify: MAX %s недоступен", admin_id)


@router.post("/events", status_code=204)
async def collect_event(request: Request) -> Response:
    """Приём клиентских событий аналитики (белый список PUBLIC_EVENTS).

    204 всегда — аналитика fire-and-forget; невалидные события молча
    отбрасываем, чтобы не давать оракул перебору.
    """
    try:
        data = await request.json()
    except Exception:
        return Response(status_code=204)
    event = str(data.get("event", ""))[:60]
    if event in analytics.PUBLIC_EVENTS:
        analytics.track(
            event, source=str(data.get("source", "site"))[:40],
            session_id=str(data.get("session_id", ""))[:80],
            anon_id=str(data.get("anon_id", ""))[:80],
            meta=data.get("meta") if isinstance(data.get("meta"), dict) else None)
    return Response(status_code=204)


@router.get("/health")
async def platform_health() -> dict:
    """Здоровье интеграции BigBen для Alert Center (§139)."""
    fresh = await asyncio.to_thread(bb_store.freshness)
    runs = await asyncio.to_thread(bb_store.last_sync_runs, 10)
    failed = [r for r in runs if r["status"] != "ok"]
    api_ok = None
    if sync.configured():
        try:
            from app.platform.bigben_v2 import get_bigben_v2
            await get_bigben_v2().filials()
            api_ok = True
        except BigBenError:
            api_ok = False
        except Exception:
            api_ok = False
    return {
        "bigben_api_configured": sync.configured(),
        "bigben_api_reachable": api_ok,
        "webhook_secret_configured": bool(settings.BIGBEN_WEBHOOK_SECRET),
        "freshness": fresh,
        "recent_sync_failures": failed[:5],
    }


@router.post("/sync/run")
async def sync_run_now(request: Request) -> JSONResponse:
    """Ручной запуск синхронизации (только с ADMIN_TOKEN)."""
    token = request.headers.get("X-Admin-Token", "")
    if not settings.ADMIN_TOKEN or token != settings.ADMIN_TOKEN:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    results = await sync.run_all("full")
    return JSONResponse({"results": results})
