"""FastAPI-приложение бота MAX для языковой школы «Фоксинбург».

Содержит:
- POST /webhook — приём событий MAX (bot_started, message_created, message_callback);
- эндпоинты мини-приложения (/api/miniapp/*);
- статику мини-приложения (личный кабинет / витрина) на /app;
- служебные эндпоинты (/health, POST /admin/set-webhook).
"""
from __future__ import annotations

import base64
import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.ai_core import handle_message, handle_start
from app import broadcast
from app.bigben import get_bigben
from app.config import settings
from app.course_selector import recommend
from app import intent as I
from app import group_chat
from app import insights
from app import nudge
from app import scheduler
from app.knowledge.kb import get_kb
from app.observability import init_sentry
from app.llm import get_llm
from app.max_client import callback_button, get_max, link_button
from app.memory import Lead, STAGE_HANDOFF, get_store
from app.slack import notify_slack
from app.telegram_client import get_telegram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"
PLATFORM = "max"

init_sentry()

app = FastAPI(title="Foxinburg MAX Bot", version=APP_VERSION)

_MINIAPP_DIR = Path(__file__).with_name("miniapp")
_BACKGROUND_TASKS: set[asyncio.Task] = set()


@app.on_event("startup")
async def _start_scheduler() -> None:
    for task in scheduler.start():
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
    telegram = get_telegram()
    if settings.TELEGRAM_POLLING and telegram.configured:
        logger.info("telegram: запуск long-polling")
        task = asyncio.create_task(_telegram_poll_loop(telegram))
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)


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

_BRANCH_CONTACTS = {
    "contact:lihachevsky": {
        "name": "Филиал на Лихачевском",
        "phone": "8 993 923-23-09",
        "url": "tel:+79939232309",
    },
    "contact:raketostroiteley": {
        "name": "Филиал на Ракетостроителей",
        "phone": "8 916 732-31-69",
        "url": "tel:+79167323169",
    },
}


def _homework_system_prompt() -> str:
    return (
        "Ты помогаешь с домашним заданием, но не давай готовые ответы и не "
        "не выполнять его за ученика и не решай за него. Вместо этого объясняй, как это сделать, "
        "давай подсказки, задавай наводящие вопросы и приводи короткий пример."
    )


def _homework_user_prompt(note: str) -> str:
    extra = f" Дополнительная заметка: {note}." if note else ""
    return (
        "Не давай готовые ответы, не решай за ребёнка и помоги понять, как "
        "это сделать самостоятельно. Покажи короткий пример и объясни шаги."
        f"{extra}"
    )


def _admin_authorized(request: Request) -> bool:
    token = request.headers.get("X-Admin-Token", "")
    return bool(settings.ADMIN_TOKEN) and token == settings.ADMIN_TOKEN


def _nudge_authorized(request: Request) -> bool:
    return not settings.ADMIN_TOKEN or _admin_authorized(request)


def _miniapp_url() -> str:
    return settings.MINIAPP_BASE_URL.rstrip("/")


def _miniapp_user_id(data: dict | None) -> str:
    if not data:
        return ""
    for key in ("user_id", "uid", "session_id"):
        value = data.get(key)
        if value:
            return str(value).strip()
    return ""


def _miniapp_access_state(user_id: str) -> dict:
    has_identity = bool(user_id)
    registered = False
    if has_identity:
        registered = bool(get_store().get(user_id).registered)
    locked = has_identity and settings.MINIAPP_REQUIRE_REGISTRATION and not registered
    message = ""
    if locked:
        message = (
            "Сначала зарегистрируйтесь в чате бота: "
            "напишите «зарегистрироваться», и я проведу вас по шагам."
        )
    elif not has_identity:
        message = "Откройте miniapp внутри MAX, чтобы связать профиль."
    return {
        "user_id": user_id,
        "has_identity": has_identity,
        "registered": registered,
        "locked": locked,
        "message": message,
    }


def _contextual_buttons(question: str, reply: str) -> list[dict]:
    text = f"{question} {reply}".lower()
    base = _miniapp_url()
    if not base:
        return []
    if "домаш" in text or "дз" in text:
        return [{"title": "📸 Помощь с домашкой (бесплатно)", "url": f"{base}#homework"}]
    if "запис" in text or "диагност" in text:
        return [{"title": "📋 Записаться онлайн", "url": f"{base}#signup"}]
    return []


def _branch_admin_buttons() -> list[list[dict]]:
    return [
        [callback_button("Филиал на Лихачевском", "contact:lihachevsky")],
        [callback_button("Филиал на Ракетостроителей", "contact:raketostroiteley")],
    ]


async def _notify_admins_for_telegram(conv, reason: str) -> None:
    admin_client = get_max()
    message = (
        f"🔔 Требуется администратор ({reason})\n\n"
        f"{conv.summary()}"
    )
    for admin_id in settings.admin_ids:
        await admin_client.send_message(admin_id, message)
    await notify_slack(f"MAX handoff ({reason})\n\n{conv.summary()}")


@app.post("/api/chat")
async def api_chat(data: dict) -> dict:
    text = str(data.get("text", "")).strip()
    if not text:
        return JSONResponse({"detail": "text required"}, status_code=400)
    session_id = str(data.get("session_id") or uuid.uuid4().hex)
    reply = await handle_message(session_id, text)
    if not reply.startswith("Привет!"):
        reply = "Привет! " + reply
    return {
        "session_id": session_id,
        "reply": reply,
        "buttons": _contextual_buttons(text, reply),
    }


@app.post("/api/miniapp/homework")
async def api_homework(
    note: str = Form(default=""),
    user_id: str = Form(default=""),
    image: UploadFile | None = File(default=None),
) -> dict:
    access = _miniapp_access_state(user_id)
    if access["locked"]:
        return JSONResponse({"ok": False, "error": access["message"]}, status_code=403)
    if image is None or not image.filename:
        return JSONResponse({"detail": "Нужна фотография задания"}, status_code=400)
    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        return JSONResponse({"detail": "Файл должен быть в формате изображения"}, status_code=400)

    image_bytes = await image.read()
    if not image_bytes:
        return JSONResponse({"detail": "Пустой файл"}, status_code=400)

    llm = get_llm()
    system_prompt = _homework_system_prompt()
    user_prompt = _homework_user_prompt(note)
    explanation = ""

    complete_vision = getattr(llm, "complete_vision", None)
    if callable(complete_vision):
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{base64.b64encode(image_bytes).decode('ascii')}",
                        },
                    },
                ],
            },
        ]
        explanation = await complete_vision(messages, temperature=0.2, max_tokens=1200) or ""
    else:
        explanation = user_prompt

    if not explanation:
        explanation = "Не удалось разобрать фото задания."

    return {
        "ok": True,
        "explanation": explanation,
        "buttons": _contextual_buttons("домашка", explanation),
    }


def _telegram_buttons(text: str, reply: str) -> list[list[dict]]:
    buttons = _contextual_buttons(text, reply)
    return [[button] for button in buttons]


def _link_button_rows(text: str, reply: str) -> list[list[dict]]:
    return [[link_button(button["title"], button["url"])] for button in _contextual_buttons(text, reply)]


async def _process_telegram_update(update: dict, telegram) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = str(message.get("text") or "").strip()
    if chat_id is None or not text:
        return

    user_id = f"tg:{chat_id}"
    low = text.lower()
    if low in ("/start", "start"):
        reply = await handle_start(user_id)
        await telegram.send_message(chat_id, reply, buttons=_telegram_buttons(text, reply) or None)
        return

    if I.detect_complaint(text) or I.detect_intent(text) == I.HANDOFF:
        conv = get_store().get(user_id, platform="telegram")
        branch = conv.selected_branch or conv.lead.branch
        if branch:
            await _notify_admins_for_telegram(conv, "запрос администратора")
            reply = f"Свяжу вас с администратором {branch}. Он скоро ответит."
            await telegram.send_message(chat_id, reply)
        else:
            reply = "Подскажите, пожалуйста, какой филиал вам удобнее?"
            await telegram.send_message(chat_id, reply, buttons=_branch_admin_buttons())
        return

    if "домаш" in low or "дз" in low:
        reply = "Помощь с домашкой у нас бесплатная. Пришлите фото задания, и я подскажу, как его разобрать."
        await telegram.send_message(chat_id, reply, buttons=_telegram_buttons(text, reply) or None)
        return

    reply = await handle_message(user_id, text)
    await telegram.send_message(chat_id, reply, buttons=_telegram_buttons(text, reply) or None)


def _schedule_telegram_update(update: dict, telegram) -> bool:
    update_id = update.get("update_id")
    if update_id is not None:
        store = get_store()
        if not store.mark_event_seen(str(update_id), platform="telegram", event_type="update"):
            return False
    task = asyncio.create_task(_process_telegram_update(update, telegram))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return True


async def _telegram_poll_loop(telegram) -> None:
    await telegram.delete_webhook()
    offset: int | None = None
    while True:
        try:
            updates = await telegram.get_updates(offset=offset, timeout=25)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("telegram: ошибка long-polling")
            await asyncio.sleep(3)
            continue
        for update in updates:
            if _schedule_telegram_update(update, telegram):
                update_id = update.get("update_id")
                if update_id is not None:
                    try:
                        offset = int(update_id) + 1
                    except (TypeError, ValueError):
                        pass


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> dict:
    if settings.TELEGRAM_WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != settings.TELEGRAM_WEBHOOK_SECRET:
            return JSONResponse({"error": "invalid secret"}, status_code=403)
    payload = await request.json()
    updates = payload if isinstance(payload, list) else [payload]
    telegram = get_telegram()
    for update in updates:
        _schedule_telegram_update(update, telegram)
    return {"ok": True}


@app.post("/admin/telegram/set-webhook")
async def admin_telegram_set_webhook(request: Request) -> dict:
    if not _admin_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    telegram = get_telegram()
    ok = await telegram.set_webhook(settings.TELEGRAM_WEBHOOK_URL, settings.TELEGRAM_WEBHOOK_SECRET or None)
    return {"ok": ok}


@app.get("/admin/broadcast/audience")
async def admin_broadcast_audience(request: Request) -> dict:
    if not _admin_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return broadcast.audience_counts()


@app.get("/admin/nudge/preview")
async def admin_nudge_preview(request: Request) -> dict:
    if not _nudge_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    rows = nudge.preview()
    return {"eligible": len(rows), "rows": rows}


@app.post("/admin/nudge/send")
async def admin_nudge_send(request: Request) -> dict:
    if not _nudge_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await nudge.run_nudges()


@app.post("/admin/broadcast/test")
async def admin_broadcast_test(request: Request, data: dict) -> dict:
    if not _admin_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await broadcast.send_broadcast(
        get_max(),
        settings.admin_ids,
        str(data.get("text", "")),
        str(data.get("button_text", "")) or None,
        str(data.get("button_url", "")) or None,
    )


@app.post("/admin/broadcast/send")
async def admin_broadcast_send(request: Request, data: dict) -> dict:
    if not _admin_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    recipients = broadcast.resolve_recipients(
        str(data.get("segment", "all")),
        course=str(data.get("course", "")) or None,
        branch=str(data.get("branch", "")) or None,
    )
    return await broadcast.send_broadcast(get_max(), recipients, str(data.get("text", "")))


@app.get("/admin/insights")
async def admin_insights(request: Request, days: int = 7, top: int = 20) -> dict:
    if not _admin_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return insights.summarize(days=days, top=top)


@app.post("/admin/digest/send")
async def admin_digest_send(request: Request) -> dict:
    if not _admin_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return {"sent": await scheduler.send_digest_now()}


@app.get("/admin/users")
async def admin_users(request: Request) -> dict:
    if not _admin_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return {"rows": broadcast.list_users()}


@app.get("/admin/users/{user_id}")
async def admin_user_detail(user_id: str, request: Request) -> dict:
    if not _admin_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    detail = broadcast.get_user_detail(user_id)
    if detail is None:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return detail


@app.get("/health")
async def health() -> dict:
    store = get_store()
    llm = get_llm()
    max_client = get_max()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "db_ok": store.ping(),
        "db_path": getattr(store, "_db_path", ""),
        "llm_configured": llm.enabled,
        "llm_providers": len(llm.providers),
        "max_configured": max_client.configured,
        "bigben_configured": get_bigben().configured,
        "kb_documents": len(get_kb().documents),
    }


@app.get("/ready")
async def ready() -> dict:
    store = get_store()
    llm = get_llm()
    db_ok = store.ping()
    llm_ok = llm.enabled
    return {
        "ready": db_ok and llm_ok,
        "version": APP_VERSION,
        "db_ok": db_ok,
        "llm_configured": llm_ok,
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
        _schedule_update(update, update_type, max_client)

    return {"status": "ok"}


def _schedule_update(update: dict, update_type: str, max_client) -> bool:
    update_id = _extract_update_id(update)
    user_id = _extract_user_id(update) or _extract_user_id(update.get("message") or {}) or _extract_user_id(update.get("callback") or {})
    if update_id:
        store = get_store()
        if not store.mark_event_seen(update_id, platform=PLATFORM, user_id=user_id or "", event_type=update_type or ""):
            logger.info("Duplicate update skipped id=%s type=%s", update_id, update_type)
            return False

    task = asyncio.create_task(_process_update_safe(update, update_type, max_client))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return True


async def _process_update_safe(update: dict, update_type: str, max_client) -> None:
    try:
        await _process_update(update, update_type, max_client)
    except Exception:
        logger.exception("Ошибка обработки update_type=%s", update_type)


async def _process_update(update: dict, update_type: str, max_client) -> None:
    if update_type == "bot_started":
        user_id = _extract_user_id(update)
        if user_id:
            reply = await handle_start(user_id)
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
        if low in ("/start", "start"):
            reply = await handle_start(user_id)
            await max_client.send_message(user_id, reply, buttons=_main_menu())
        elif I.detect_intent(text) == I.HANDOFF:
            conv = get_store().get(user_id)
            if conv.selected_branch:
                await _notify_admins_for_telegram(conv, "запрос администратора")
                reply = f"Свяжу вас с администратором {conv.selected_branch}. Он скоро ответит."
                await max_client.send_message(user_id, reply, buttons=_main_menu())
            else:
                await max_client.send_message(
                    user_id,
                    "Подскажите, пожалуйста, какой филиал вам удобнее?",
                    buttons=_branch_admin_buttons(),
                )
        elif I.detect_intent(text) == I.HOMEWORK:
            reply = "Помощь с домашкой у нас бесплатная. Пришлите фото задания, и я подскажу, как его разобрать."
            buttons = _link_button_rows(text, reply)
            await max_client.send_message(user_id, reply, buttons=buttons or None)
        elif low in ("/menu", "меню"):
            await max_client.send_message(user_id, "Чем помочь? 😊", buttons=_main_menu())
        else:
            reply = await handle_message(user_id, text)
            await max_client.send_message(user_id, reply, buttons=_link_button_rows(text, reply) or None)
        return

    if update_type == "message_callback":
        callback = update.get("callback") or update
        callback_id = callback.get("callback_id") or callback.get("id")
        payload = callback.get("payload", "")
        user_id = _extract_user_id(update) or _extract_user_id(callback)
        if callback_id:
            await max_client.answer_callback(callback_id)
        if user_id and payload in _BRANCH_CONTACTS:
            conv = get_store().get(user_id)
            info = _BRANCH_CONTACTS[payload]
            conv.selected_branch = info["name"]
            conv.stage = STAGE_HANDOFF
            await _notify_admins_for_telegram(conv, "контакт по филиалу")
            await max_client.send_message(
                user_id,
                f"Свяжу вас с администратором {info['name']}.",
                buttons=[[link_button(info["name"], info["url"])]],
            )
        elif user_id and str(payload).startswith("contact:"):
            await max_client.send_message(
                user_id,
                "Подскажите, пожалуйста, какой филиал вам удобнее?",
                buttons=_branch_admin_buttons(),
            )
        elif user_id and payload in _CALLBACK_TEXT:
            reply = await handle_message(user_id, _CALLBACK_TEXT[payload])
            await max_client.send_message(user_id, reply)
        return


def _extract_update_id(update: dict):
    for key in ("id", "update_id", "event_id"):
        value = update.get(key)
        if value:
            return str(value)
    message = update.get("message") or {}
    for key in ("id", "message_id"):
        value = message.get(key)
        if value:
            return str(value)
    callback = update.get("callback") or {}
    for key in ("callback_id", "id"):
        value = callback.get(key)
        if value:
            return str(value)
    return None


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

@app.get("/api/miniapp/access")
async def miniapp_access(user_id: str = "") -> dict:
    return _miniapp_access_state(user_id)


@app.get("/api/miniapp/info")
async def miniapp_info(user_id: str = "") -> dict:
    kb = get_kb()
    access = _miniapp_access_state(user_id)
    return {
        "company": kb.company,
        "branches": kb.branches,
        "formats": kb.formats,
        "age_programs": kb.age_programs,
        "courses": kb.courses,
        "social": kb.social,
        "access": access,
    }


@app.get("/api/miniapp/recommend")
async def miniapp_recommend(age: str = "", fmt: str = "", user_id: str = "") -> dict:
    access = _miniapp_access_state(user_id)
    if access["locked"]:
        return JSONResponse({"ok": False, "error": access["message"]}, status_code=403)
    kb = get_kb()
    items = recommend(kb, age or None, fmt or None)
    return {"recommendations": items}


@app.post("/api/miniapp/lead")
async def miniapp_lead(data: dict) -> dict:
    """Приём заявки из мини-приложения и отправка в BigBen CRM."""
    user_id = _miniapp_user_id(data)
    access = _miniapp_access_state(user_id)
    if access["locked"]:
        return JSONResponse({"ok": False, "error": access["message"]}, status_code=403)
    lead = Lead(
        fio_parent=str(data.get("fio_parent", ""))[:255],
        fio_child=str(data.get("fio_child", ""))[:255],
        phone=str(data.get("phone", ""))[:20],
        birthday=str(data.get("birthday", "")),
        age=str(data.get("age", "")),
        branch=str(data.get("branch", "")),
        course=str(data.get("course", "")),
        comment=str(data.get("comment", ""))[:255],
    )
    if not lead.fio_parent or not lead.phone:
        return {"ok": False, "error": "Укажите имя и телефон"}
    source = "MAX мини-приложение Фоксинбург"
    ok = await get_bigben().create_lead(lead, source=source)
    if ok and settings.admin_ids:
        admin_note = (
            "Новая заявка из мини-приложения\n"
            f"Родитель: {lead.fio_parent}\n"
            f"Ребёнок: {lead.fio_child or '—'}\n"
            f"Телефон: {lead.phone}\n"
            f"Филиал: {lead.branch or '—'}\n"
            f"Интерес: {lead.course or data.get('interest_value', '') or data.get('interest_type', '')}"
        )
        for admin_id in settings.admin_ids:
            await get_max().send_message(admin_id, admin_note)
    return {"ok": ok}


# Статика мини-приложения (если каталог есть).
if _MINIAPP_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(_MINIAPP_DIR), html=True), name="miniapp")


@app.post("/admin/set-webhook")
async def admin_set_webhook(data: dict) -> dict:
    """Регистрирует webhook бота в MAX. Тело: {"url": "https://.../webhook"}."""
    url = data.get("url")
    if not url:
        return {"ok": False, "error": "url required"}
    ok = await get_max().set_webhook(url, settings.MAX_WEBHOOK_SECRET or None)
    return {"ok": ok}
