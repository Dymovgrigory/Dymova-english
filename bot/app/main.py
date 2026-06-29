"""FastAPI-приложение бота MAX для языковой школы «Фоксинбург».

Содержит:
- POST /webhook — приём событий MAX (bot_started, message_created, message_callback);
- эндпоинты мини-приложения (/api/miniapp/*);
- статику мини-приложения (личный кабинет / витрина) на /app;
- служебные эндпоинты (/health, POST /admin/set-webhook).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import insights, scheduler
from app.ai_core import handle_message, handle_start, parse_utm
from app.broadcast import audience_counts, resolve_recipients, send_broadcast
from app.bigben import get_bigben
from app.config import settings
from app.course_selector import recommend
from app.knowledge.kb import get_kb
from app.max_client import callback_button, get_max, link_button
from app.memory import Lead, get_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def _lifespan(_: FastAPI):
    scheduler.start()
    yield


app = FastAPI(title="Foxinburg MAX Bot", lifespan=_lifespan)

_MINIAPP_DIR = Path(__file__).with_name("miniapp")


def _miniapp_url(section: str = "") -> str:
    base = settings.MINIAPP_BASE_URL.rstrip("/") if settings.MINIAPP_BASE_URL else ""
    if not base:
        return ""
    if section:
        return f"{base}#{section}"
    return base


def _main_menu() -> list[list[dict]]:
    rows = [
        [callback_button("🎓 Подобрать курс", "menu:courses")],
        [callback_button("📅 Записаться на пробное", "menu:signup")],
        [callback_button("💳 Стоимость обучения", "menu:price")],
        [callback_button("🏫 Наши филиалы", "menu:branches")],
        [callback_button("☎ Связаться с администратором", "menu:admin")],
    ]
    base = _miniapp_url()
    if base:
        rows.insert(0, [link_button("📱 Открыть приложение", base)])
    return rows


def _contextual_buttons(question: str, reply: str) -> list[list[dict]]:
    """Добавляет кнопку мини-приложения в зависимости от контекста вопроса/ответа."""
    base = _miniapp_url()
    if not base:
        return []
    low_q = question.lower()
    low_r = reply.lower()
    rows = []

    # Course-related
    if any(w in low_q for w in ("курс", "программ", "обучен", "язык", "стоимость",
                                  "цен", "прайс", "сколько стоит")):
        rows.append([link_button("📚 Каталог курсов", _miniapp_url("courses"))])

    # Summer academy
    if any(w in low_q for w in ("лет", "академи", "смен", "каникул")):
        rows.append([link_button("☀️ Летняя Академия", _miniapp_url("summer"))])

    # Branches
    if any(w in low_q for w in ("филиал", "адрес", "добрат", "где вы", "офлайн",
                                  "ракетостр", "лихачев")):
        rows.append([link_button("📍 Филиалы", _miniapp_url("branches"))])

    # Signup
    if any(w in low_q for w in ("запис", "пробн", "диагност")):
        rows.append([link_button("📋 Записаться онлайн", _miniapp_url("signup"))])

    # If nothing matched from question, check reply
    if not rows:
        if any(w in low_r for w in ("курс", "программ")):
            rows.append([link_button("📚 Подробнее о курсах", _miniapp_url("courses"))])

    # If bot offers signup in reply — add button
    if not any("Записаться" in str(r) for r in rows):
        if any(w in low_r for w in ("записать", "диагностик", "пробн",
                                      "запишу", "записаться", "заявк")):
            rows.append([link_button("📋 Записаться онлайн", _miniapp_url("signup"))])

    return rows


_ADMIN_REPORT_CMDS = {"/админ", "/admin", "админ", "/отчет", "/отчёт", "отчет",
                      "отчёт", "/report", "report", "/insights", "статистика",
                      "/статистика", "дайджест", "/дайджест"}
_MYID_CMDS = {"/myid", "myid", "мой id", "/id"}


def _admin_command(low: str, user_id: str) -> str | None:
    """Команды администратора в чате. Возвращает текст ответа или None."""
    if low in _MYID_CMDS:
        role = "администратор" if settings.is_admin(user_id) else "обычный пользователь"
        return f"Ваш MAX ID: {user_id}\nСтатус: {role}."
    if low in _ADMIN_REPORT_CMDS:
        if not settings.is_admin(user_id):
            return None  # для не-админов это обычный вопрос → обрабатывается ботом
        report = insights.digest(days=settings.DIGEST_DAYS)
        return ("🛠 Админ-панель\n\n" + report +
                "\n\nКоманды: /отчёт — дайджест за день, /myid — ваш ID.")
    return None


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
        admin_reply = _admin_command(low, user_id)
        if admin_reply is not None:
            await max_client.send_message(user_id, admin_reply)
        elif low.split(maxsplit=1)[0] in ("/start", "start"):
            parts = text.split(maxsplit=1)
            start_param = parts[1].strip() if len(parts) > 1 else ""
            reply = await handle_start(user_id, start_param=start_param)
            await max_client.send_message(user_id, reply, buttons=_main_menu())
        elif low in ("/menu", "меню"):
            await max_client.send_message(user_id, "Чем помочь? 😊", buttons=_main_menu())
        else:
            reply = await handle_message(user_id, text)
            btns = _contextual_buttons(text, reply)
            await max_client.send_message(user_id, reply, buttons=btns or None)
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
            btns = _contextual_buttons(_CALLBACK_TEXT[payload], reply)
            await max_client.send_message(user_id, reply, buttons=btns or None)
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
        "faq": kb.faq,
        "promos": kb.promos,
        "summer_academy": kb.summer_academy,
        "enrollment_steps": kb.enrollment_steps,
        "advantages": kb.advantages,
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


def _require_admin_token(token: str | None) -> None:
    """Жёсткая защита для рассылок: токен обязателен всегда."""
    if not settings.ADMIN_TOKEN or token != settings.ADMIN_TOKEN:
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


@app.post("/admin/digest/send")
async def admin_digest_send(x_admin_token: str | None = Header(default=None)) -> dict:
    """Немедленно разослать дайджест администраторам (для проверки расписания)."""
    _check_admin(x_admin_token)
    sent = await scheduler.send_digest_now()
    return {"ok": True, "sent": sent, "admins": len(settings.admin_ids)}


@app.get("/admin/broadcast/audience")
async def admin_broadcast_audience(
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _require_admin_token(x_admin_token)
    return audience_counts()


@app.post("/admin/broadcast/test")
async def admin_broadcast_test(
    data: dict,
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _require_admin_token(x_admin_token)
    text = str(data.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    button_text = str(data.get("button_text", "")).strip()
    button_url = str(data.get("button_url", "")).strip()
    if bool(button_text) != bool(button_url):
        raise HTTPException(status_code=400, detail="button_text and button_url must be provided together")
    return await send_broadcast(
        get_max(),
        settings.admin_ids,
        text,
        button_text=button_text or None,
        button_url=button_url or None,
    )


@app.post("/admin/broadcast/send")
async def admin_broadcast_send(
    data: dict,
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _require_admin_token(x_admin_token)
    text = str(data.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    segment = str(data.get("segment", "")).strip()
    course = str(data.get("course", "")).strip() or None
    branch = str(data.get("branch", "")).strip() or None
    button_text = str(data.get("button_text", "")).strip()
    button_url = str(data.get("button_url", "")).strip()
    if bool(button_text) != bool(button_url):
        raise HTTPException(status_code=400, detail="button_text and button_url must be provided together")
    if segment not in {"all", "leads", "course", "branch"}:
        raise HTTPException(status_code=400, detail="segment required")
    if segment == "course" and not course:
        raise HTTPException(status_code=400, detail="course required")
    if segment == "branch" and not branch:
        raise HTTPException(status_code=400, detail="branch required")
    recipients = resolve_recipients(segment, course=course, branch=branch)
    return await send_broadcast(
        get_max(),
        recipients,
        text,
        button_text=button_text or None,
        button_url=button_url or None,
    )
