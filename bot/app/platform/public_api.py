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
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.platform import bb_store, booking, sync
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


def _group_card(g: dict) -> dict:
    group_raw = g.get("raw_json")
    import json as _json
    raw = _json.loads(group_raw) if isinstance(group_raw, str) else (group_raw or {})
    free = booking.group_free_slots(raw) if raw else g.get("free_slots")
    age_from, age_to = _age_from_caption(g.get("caption", ""))
    return {
        "id": g["id"],
        "caption": g.get("caption", ""),
        "filial": {"id": g.get("filial_id"), "caption": g.get("filial_caption", "")},
        "auditory": g.get("auditory_caption", ""),
        "capacity": g.get("capacity"),
        "occupied": g.get("occupied", 0),
        "free_slots": free,
        "low_availability": free is not None and 0 < free <= settings.LOW_AVAILABILITY_THRESHOLD,
        "age_from": age_from,
        "age_to": age_to,
        "schedule": _json.loads(g.get("schedule_json") or "[]"),
        "synced_at": g.get("synced_at"),
    }


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
    if not all:
        today = date.today()
        date_to = today + timedelta(days=settings.BIGBEN_LESSONS_WINDOW_DAYS)
        lessons = await asyncio.to_thread(
            bb_store.list_lessons, today.isoformat(), date_to.isoformat())
        active_ids = {les.get("group_id") for les in lessons}
        items = [g for g in items if g["id"] in active_ids]
    return {"data": [_group_card(g) for g in items]}


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
    cards = {g["id"]: _group_card(g) for g in groups}
    out_lessons = []
    for les in lessons:
        gid = les.get("group_id")
        if filial_id and les.get("filial_id") != filial_id:
            continue
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
    result = await booking.book_trial(
        parent_name=req.parent_name, phone=req.phone,
        child_name=req.child_name, child_age=req.child_age,
        group_id=req.group_id, lesson_id=req.lesson_id,
        comment=req.comment, source=req.source,
        idempotency_key=req.idempotency_key)
    if result.status == "confirmed":
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
