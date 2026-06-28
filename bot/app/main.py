"""FastAPI-приложение бота MAX для языковой школы «Фоксинбург».

Содержит:
- POST /webhook — приём событий MAX (bot_started, message_created, message_callback);
- эндпоинты мини-приложения (/api/miniapp/*);
- статику мини-приложения (личный кабинет / витрина) на /app;
- служебные эндпоинты (/health, POST /admin/set-webhook).
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import insights
from app.ai_core import handle_message, handle_start, parse_utm
from app.bigben import get_bigben
from app.config import settings
from app.course_selector import recommend
from app.knowledge.kb import get_kb
from app.max_client import callback_button, get_max, link_button
from app.memory import Lead, get_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Foxinburg MAX Bot")

_MINIAPP_DIR = Path(__file__).with_name("miniapp")


def _main_menu() -> list[list[dict]]:
    rows = [
        [callback_button("🎓 Подобрать курс", "menu:courses")],
        [callback_button("📅 Записаться на пробное", "menu:signup")],
        [callback_button("💳 Стоимость обучения", "menu:price")],
        [callback_button("🏫 Наши филиалы", "menu:branches")],
        [callback_button("☎ Связаться с администратором", "menu:admin")],
    ]
    if settings.MINIAPP_BASE_URL:
        rows.insert(0, [link_button("📱 Личный кабинет", settings.MINIAPP_BASE_URL)])
    return rows


_CALLBACK_TEXT = {
    "menu:courses": "Какие у вас есть курсы и программы?",
    "menu:signup": "Хочу записаться на пробное занятие",
    "menu:price": "Сколько стоит обучение?",
    "menu:branches": "Где находятся ваши филиалы?",
    "menu:admin": "Соедините меня с администратором",
}


@app.get("/health")
async def health() -> dict:
    max_client = get_max()
    return {
        "status": "ok",
        "max_configured": max_client.configured,
        "bigben_configured": get_bigben().configured,
        "kb_documents": len(get_kb().documents),
    }


@app.post("/webhook")
async def webhook(request: Request):
    if settings.MAX_WEBHOOK_SECRET:
        if request.headers.get("X-Max-Bot-Api-Secret") != settings.MAX_WEBHOOK_SECRET:
            return JSONResponse({"error": "invalid secret"}, status_code=401)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    max_client = get_max()
    updates = payload if isinstance(payload, list) else [payload]

    for update in updates:
        update_type = update.get("type") or update.get("update_type")
        try:
            await _process_update(update, update_type, max_client)
        except Exception:
            logger.exception("Ошибка обработки update_type=%s", update_type)

    return {"status": "ok"}


async def _process_update(update: dict, update_type: str, max_client) -> None:
    if update_type == "bot_started":
        user_id = _extract_user_id(update)
        if user_id:
            reply = await handle_start(user_id, start_param=_extract_start_param(update))
            await max_client.send_message(user_id, reply, buttons=_main_menu())
        return

    if update_type == "message_created":
        message = update.get("message") or update
        sender = message.get("sender") or {}
        if sender.get("is_bot"):
            return
        user_id = str(sender.get("user_id")) if sender.get("user_id") else None
        if not user_id:
            return
        text = (message.get("body") or {}).get("text", "").strip()
        if not text:
            return
        low = text.lower()
        if low.split(maxsplit=1)[0] in ("/start", "start"):
            parts = text.split(maxsplit=1)
            start_param = parts[1].strip() if len(parts) > 1 else ""
            reply = await handle_start(user_id, start_param=start_param)
            await max_client.send_message(user_id, reply, buttons=_main_menu())
        elif low in ("/menu", "меню"):
            await max_client.send_message(user_id, "Чем помочь? 😊", buttons=_main_menu())
        else:
            reply = await handle_message(user_id, text)
            await max_client.send_message(user_id, reply)
        return

    if update_type == "message_callback":
        callback = update.get("callback") or update
        callback_id = callback.get("callback_id") or callback.get("id")
        payload = callback.get("payload", "")
        user_id = _extract_user_id(update) or _extract_user_id(callback)
        if callback_id:
            await max_client.answer_callback(callback_id)
        if user_id and payload in _CALLBACK_TEXT:
            reply = await handle_message(user_id, _CALLBACK_TEXT[payload])
            await max_client.send_message(user_id, reply)
        return


def _extract_start_param(update: dict) -> str:
    """Нагрузка deep-link из события bot_started (MAX: поле payload)."""
    for key in ("payload", "start_payload", "start_param"):
        val = update.get(key)
        if val:
            return str(val)
    return ""


def _extract_user_id(update: dict):
    for key in ("user_id",):
        if update.get(key):
            return str(update[key])
    for key in ("sender", "user", "from"):
        node = update.get(key)
        if isinstance(node, dict):
            uid = node.get("user_id") or node.get("id")
            if uid:
                return str(uid)
    return None


# --------- Мини-приложение: API ---------

@app.get("/api/miniapp/info")
async def miniapp_info() -> dict:
    kb = get_kb()
    return {
        "company": kb.company,
        "branches": kb.branches,
        "formats": kb.formats,
        "age_programs": kb.age_programs,
        "courses": kb.courses,
        "social": kb.social,
    }


@app.get("/api/miniapp/recommend")
async def miniapp_recommend(age: str = "", fmt: str = "") -> dict:
    kb = get_kb()
    items = recommend(kb, age or None, fmt or None)
    return {"recommendations": items}


@app.post("/api/miniapp/lead")
async def miniapp_lead(data: dict) -> dict:
    """Приём заявки из мини-приложения и отправка в BigBen CRM."""
    lead = Lead(
        fio_parent=str(data.get("fio_parent", ""))[:255],
        fio_child=str(data.get("fio_child", ""))[:255],
        phone=str(data.get("phone", ""))[:20],
        birthday=str(data.get("birthday", "")),
        age=str(data.get("age", "")),
        branch=str(data.get("branch", "")),
        course=str(data.get("course", "")),
        comment=str(data.get("comment", ""))[:255],
        email=str(data.get("email", ""))[:255],
        city=str(data.get("city", ""))[:255],
    )
    if not lead.fio_parent or not lead.phone:
        return {"ok": False, "error": "Укажите имя и телефон"}
    course = lead.course or "диагностика"
    source = f"MAX мини-приложение Фоксинбург ({course})"
    utm = parse_utm(str(data.get("start_param", "")))
    raw_utm = data.get("utm")
    if isinstance(raw_utm, dict):
        utm.update({k: str(v)[:300] for k, v in raw_utm.items() if v})
    utm.setdefault("utm_source", "max")
    utm.setdefault("utm_medium", "miniapp")
    ok = await get_bigben().create_lead(lead, source=source, utm=utm)
    return {"ok": ok}


# Статика мини-приложения (если каталог есть).
if _MINIAPP_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(_MINIAPP_DIR), html=True), name="miniapp")


def _check_admin(token: str | None) -> None:
    """Защита служебных эндпоинтов. Если ADMIN_TOKEN задан — требуем его."""
    if settings.ADMIN_TOKEN and token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="admin token required")


@app.post("/admin/set-webhook")
async def admin_set_webhook(
    data: dict, x_admin_token: str | None = Header(default=None)
) -> dict:
    """Регистрирует webhook бота в MAX. Тело: {"url": "https://.../webhook"}."""
    _check_admin(x_admin_token)
    url = data.get("url")
    if not url:
        return {"ok": False, "error": "url required"}
    ok = await get_max().set_webhook(url, settings.MAX_WEBHOOK_SECRET or None)
    return {"ok": ok}


@app.get("/admin/insights")
async def admin_insights(
    days: int = 30, top: int = 20, x_admin_token: str | None = Header(default=None)
) -> dict:
    """Отчёт цикла улучшения: топ вопросов, где бот отвечал неуверенно."""
    _check_admin(x_admin_token)
    return insights.summarize(days=days, top=top)


@app.get("/admin/insights/digest", response_class=PlainTextResponse)
async def admin_insights_digest(
    days: int = 7, top: int = 10, x_admin_token: str | None = Header(default=None)
) -> str:
    """Готовый текст-дайджест «слабых мест» за период."""
    _check_admin(x_admin_token)
    return insights.digest(days=days, top=top)
