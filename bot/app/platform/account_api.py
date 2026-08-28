"""Личный кабинет ученика в мини-аппе: «мои занятия», баланс, группы.

Личность — только подписанный initData (miniapp_auth), никаких user_id из
параметров (IDOR). Связка с BigBen: телефон из регистрационной анкеты
диалога → bb_students (нормализация по последним 10 цифрам). Группы ученика
и его баланс — свежие из API; расписание — из read-model (freshness в ответе).

BigBen v1 не отдаёт «оставшиеся занятия абонемента» — показываем баланс в
рублях как есть, без выдуманных метрик.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import miniapp_auth
from app.config import settings
from app.memory import get_store
from app.platform import bb_store
from app.platform.bigben_v2 import BigBenError, get_bigben_v2

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/miniapp/account", tags=["account"])

_LESSONS_AHEAD_DAYS = 30


# Те же заголовки, что и у остальных ручек мини-аппа (app.main).
INIT_DATA_HEADER = "X-Miniapp-Init-Data"
PLATFORM_HEADER = "X-Miniapp-Platform"


def _verified_identity(request: Request) -> miniapp_auth.MiniAppIdentity | None:
    identity = miniapp_auth.identify(
        init_data=request.headers.get(INIT_DATA_HEADER, ""),
        platform_hint=request.headers.get(PLATFORM_HEADER, ""),
        fallback_user_id="",
    )
    if identity is None or not identity.verified:
        return None
    return identity


@router.get("/overview")
async def overview(request: Request) -> JSONResponse:
    identity = _verified_identity(request)
    if identity is None:
        return JSONResponse(
            {"error": "unauthorized",
             "message": "Откройте приложение внутри Telegram или MAX."},
            status_code=401)

    conv = await asyncio.to_thread(get_store().get, identity.user_id, identity.platform)
    phone = (conv.lead.phone or "").strip() if conv and conv.lead else ""
    if not phone:
        return JSONResponse({
            "linked": False,
            "message": "Мы ещё не знаем ваш номер. Напишите боту свой телефон — "
                       "и здесь появятся ваши занятия и баланс.",
        })

    student = await asyncio.to_thread(bb_store.find_student_by_phone, phone)
    if not student:
        return JSONResponse({
            "linked": False,
            "message": "Не нашли ученика с таким номером в системе школы. "
                       "Если вы уже занимаетесь — напишите нам, поправим.",
        })

    # Свежая карточка ученика (группы + баланс) из API; при недоступности —
    # кэш с пометкой свежести.
    active_groups: list[dict] = []
    balance_kopecks = student.get("balance_kopecks", 0)
    live = True
    try:
        card = await get_bigben_v2().student(student["id"])
        active_groups = card.get("active_groups") or []
        balance_kopecks = card.get("balance_kopecks", balance_kopecks)
    except BigBenError as exc:
        live = False
        logger.warning("account: свежая карточка недоступна (%s), отдаём кэш", exc.code)
    except Exception:
        live = False
        logger.exception("account: неожиданный сбой карточки ученика")

    group_ids = [g.get("id") for g in active_groups if g.get("id")]
    today = date.today()
    lessons: list[dict] = []
    if group_ids:
        all_lessons = await asyncio.to_thread(
            bb_store.list_lessons, today.isoformat(),
            (today + timedelta(days=_LESSONS_AHEAD_DAYS)).isoformat())
        lessons = [l for l in all_lessons if l.get("group_id") in group_ids]

    fresh = await asyncio.to_thread(bb_store.freshness)
    return JSONResponse({
        "linked": True,
        "live": live,
        "student": {"id": student["id"], "fio": student.get("fio", "")},
        "balance_rub": round(balance_kopecks / 100, 2),
        "groups": [{"id": g.get("id"), "caption": g.get("caption", "")}
                   for g in active_groups],
        "upcoming_lessons": [{
            "lesson_id": l["id"], "date": l.get("date"),
            "starts_at": l.get("starts_at"), "ends_at": l.get("ends_at"),
            "group_caption": l.get("group_caption", ""),
            "filial": l.get("filial_caption", ""),
        } for l in lessons[:20]],
        "freshness": {"lessons_synced_at": fresh["lessons"]["last_synced_at"]},
    })
