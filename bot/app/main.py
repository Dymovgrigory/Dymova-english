"""FastAPI-приложение бота MAX для языковой школы «Фоксинбург».

Содержит:
- POST /webhook — приём событий MAX (bot_started, message_created, message_callback);
- эндпоинты мини-приложения (/api/miniapp/*);
- статику мини-приложения (личный кабинет / витрина) на /app;
- служебные эндпоинты (/health, POST /admin/set-webhook).
"""
from __future__ import annotations

import asyncio
import base64
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import insights, scheduler
from app import intent as I
from app.conv_report import conversations_digest
from app.convlog import log_turn
from app.dedup import mark_seen
from app.ai_core import handle_message, handle_start, parse_utm
from app.broadcast import audience_counts, get_user_detail, list_users, resolve_recipients, send_broadcast
from app.admin_router import hand_off
from app.bigben import get_bigben
from app.config import settings
from app.course_selector import recommend
from app import group_chat
from app.knowledge.kb import get_kb
from app.llm import get_llm
from app.max_client import callback_button, get_max, link_button
from app.memory import Lead, STAGE_DONE, STAGE_HANDOFF, get_store
from app.telegram_client import get_telegram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"
_TELEGRAM_POLL_TASK: asyncio.Task | None = None

@asynccontextmanager
async def _lifespan(_: FastAPI):
    global _TELEGRAM_POLL_TASK
    scheduler.start()
    if settings.TELEGRAM_POLLING and get_telegram().configured:
        _TELEGRAM_POLL_TASK = asyncio.create_task(_telegram_poll_loop(get_telegram()))
    yield
    task = _TELEGRAM_POLL_TASK
    _TELEGRAM_POLL_TASK = None
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Telegram polling task stopped with error")


app = FastAPI(title="Foxinburg MAX Bot", lifespan=_lifespan)

_MINIAPP_DIR = Path(__file__).with_name("miniapp")
_WIDGET_DIR = Path(__file__).with_name("widget")
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def _parse_web_chat_origins(raw: str) -> tuple[list[str], str | None]:
    origins: list[str] = []
    regex_parts: list[str] = []
    for item in raw.split(","):
        origin = item.strip()
        if not origin:
            continue
        if "*" in origin:
            escaped = re.escape(origin).replace(r"\*", r"\d+")
            regex_parts.append(f"^{escaped}$")
            continue
        origins.append(origin)
    allow_origin_regex = "|".join(f"(?:{part})" for part in regex_parts) if regex_parts else None
    return origins, allow_origin_regex


_WEB_CHAT_ORIGINS, _WEB_CHAT_ORIGIN_REGEX = _parse_web_chat_origins(settings.WEB_CHAT_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_WEB_CHAT_ORIGINS,
    allow_origin_regex=_WEB_CHAT_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    homework_button = _homework_button()
    if homework_button:
        rows.insert(1 if base else 0, homework_button[0])
    return rows


def _homework_button() -> list[list[dict]]:
    url = _miniapp_url("homework")
    if not url:
        return []
    return [[link_button("📸 Помощь с домашкой (бесплатно)", url)]]


def _response_buttons(rows: list[list[dict]] | None) -> list[dict]:
    buttons: list[dict] = []
    seen_urls: set[str] = set()
    for row in rows or []:
        for button in row:
            if button.get("type") != "link":
                continue
            url = str(button.get("url", "")).strip()
            title = str(button.get("text", "")).strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            buttons.append({"title": title, "url": url})
    return buttons


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

    if I.is_homework_request(question) or I.is_homework_request(reply):
        homework_button = _homework_button()
        if homework_button:
            rows.append(homework_button[0])

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


def _dialogue_result(conv, default: str = "consultation") -> str:
    if conv.lead_submitted or conv.stage == STAGE_DONE:
        return "lead"
    if conv.handed_off or conv.stage == STAGE_HANDOFF:
        return "handoff"
    return default


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


def _branch_by_key(branch_key: str | None) -> dict | None:
    key = (branch_key or "").strip().lower()
    if not key:
        return None
    branches = get_kb().branches
    for branch in branches:
        bid = str(branch.get("id", "")).lower()
        name = str(branch.get("name", "")).lower()
        if key == bid or key == name:
            return branch
    for branch in branches:
        bid = str(branch.get("id", "")).lower()
        name = str(branch.get("name", "")).lower()
        if key in bid or key in name:
            return branch
    return None


def _branch_contact_buttons() -> list[list[dict]]:
    rows: list[list[dict]] = []
    for branch in get_kb().branches:
        branch_id = str(branch.get("id", "")).strip()
        if not branch_id:
            continue
        rows.append([callback_button(str(branch.get("name", branch_id)), f"contact:{branch_id}")])
    return rows


async def _admin_contact_flow(max_client, conv, branch_key: str | None = None) -> tuple[str, list[list[dict]] | None]:
    branch = _branch_by_key(branch_key or conv.selected_branch or conv.lead.branch)
    if not branch:
        return (
            "Подскажите, пожалуйста, какой филиал вам удобнее — и я сразу передам ваш вопрос нужному администратору.",
            _branch_contact_buttons(),
        )

    branch_name = str(branch.get("name", branch.get("id", "филиал"))).strip()
    branch_phone = str(branch.get("phone", "")).strip()
    contact_url = str(branch.get("admin_contact_url", "")).strip()
    conv.selected_branch = branch_name
    await hand_off(max_client, conv, reason=f"контакт с администратором: {branch_name}")
    reply = (
        f"Свяжу вас с администратором {branch_name}.\n"
        f"Телефон филиала: {branch_phone}."
    )
    buttons = [[link_button(f"✍️ Написать администратору ({branch_name})", contact_url)]] if contact_url else None
    return reply, buttons


async def _send_admin_report(max_client, user_id: str) -> None:
    texts = [conversations_digest(days=settings.DIGEST_DAYS), insights.digest(days=settings.DIGEST_DAYS)]
    for text in texts:
        try:
            await max_client.send_message(user_id, text)
        except Exception:
            logger.exception("Не удалось отправить отчёт админу %s", user_id)


@app.get("/health")
async def health() -> dict:
    max_client = get_max()
    llm = get_llm()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "max_configured": max_client.configured,
        "telegram_configured": get_telegram().configured,
        "bigben_configured": get_bigben().configured,
        "kb_documents": len(get_kb().documents),
        "llm_configured": llm.enabled,
        "llm_providers": len(llm.providers),
    }


@app.get("/ready")
async def ready() -> dict:
    llm = get_llm()
    return {"ready": llm.enabled, "llm_configured": llm.enabled}


@app.post("/api/chat")
async def api_chat(data: dict) -> dict:
    raw_text = data.get("text")
    if not isinstance(raw_text, str):
        raise HTTPException(status_code=400, detail="text required")
    text = raw_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="text too long")

    raw_session_id = data.get("session_id")
    session_id = str(raw_session_id).strip() if raw_session_id is not None else ""
    if not session_id:
        session_id = str(uuid4())
    user_id = f"web:{session_id}"

    intent = I.detect_intent(text)
    if intent == I.HOMEWORK:
        conv = get_store().get(user_id)
        reply = (
            "Помощь с домашкой у нас бесплатная 📸 Откройте приложение, "
            "загрузите фото задания — объясню, что нужно сделать и как, на примере. "
            "Решать ребёнок будет сам 🙂"
        )
        buttons = _response_buttons(_homework_button())
        log_turn(user_id, text, reply, intent, conv.stage, "homework")
        return {"session_id": session_id, "reply": reply, "buttons": buttons}

    reply = await handle_message(user_id, text)
    buttons = _response_buttons(_contextual_buttons(text, reply))
    conv = get_store().get(user_id)
    log_turn(user_id, text, reply, intent, conv.stage, _dialogue_result(conv))
    return {"session_id": session_id, "reply": reply, "buttons": buttons}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    if settings.TELEGRAM_WEBHOOK_SECRET:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if header != settings.TELEGRAM_WEBHOOK_SECRET:
            return JSONResponse({"error": "forbidden"}, status_code=403)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "invalid json"}, status_code=400)

    _schedule_telegram_update(payload, get_telegram())
    return {"status": "ok"}


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


def _schedule_telegram_update(update: dict, telegram_client) -> bool:
    event_id = _extract_telegram_event_id(update)
    if event_id and not mark_seen(event_id):
        logger.info("Duplicate Telegram webhook event skipped id=%s", event_id)
        return False
    task = asyncio.create_task(_process_telegram_update_safe(update, telegram_client))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return True


async def _process_telegram_update_safe(update: dict, telegram_client) -> None:
    try:
        await _process_telegram_update(update, telegram_client)
    except Exception:
        logger.exception("Ошибка обработки Telegram update")


async def _process_telegram_update(update: dict, telegram_client) -> None:
    message = update.get("message")
    if not isinstance(message, dict):
        return
    sender = message.get("from") or {}
    if sender.get("is_bot"):
        return

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    text = message.get("text")
    if not isinstance(text, str):
        return
    text = text.strip()
    if not text:
        return

    user_id = f"tg:{chat_id}"
    low = text.lower()
    if low.startswith("/start") or low.startswith("start"):
        parts = text.split(maxsplit=1)
        start_param = parts[1].strip() if len(parts) > 1 else ""
        reply = await handle_start(user_id, start_param=start_param)
        await telegram_client.send_message(chat_id, reply)
        conv = get_store().get(user_id)
        log_turn(user_id, text, reply, I.GREETING, conv.stage, _dialogue_result(conv))
        return

    intent = I.detect_intent(text)
    if intent == I.HOMEWORK:
        conv = get_store().get(user_id)
        reply = (
            "Помощь с домашкой у нас бесплатная 📸 Откройте приложение, "
            "загрузите фото задания — объясню, что нужно сделать и как, на примере. "
            "Решать ребёнок будет сам 🙂"
        )
        buttons = _homework_button()
        await telegram_client.send_message(chat_id, reply, buttons=buttons or None)
        log_turn(user_id, text, reply, intent, conv.stage, "homework")
        return

    if intent == I.HANDOFF:
        store = get_store()
        conv = store.get(user_id)
        conv.add("user", text)
        reply, buttons = await _admin_contact_flow(get_max(), conv)
        conv.add("assistant", reply)
        store.save(conv)
        await telegram_client.send_message(chat_id, reply, buttons=buttons)
        log_turn(user_id, text, reply, intent, conv.stage, "handoff")
        return

    reply = await handle_message(user_id, text)
    btns = _contextual_buttons(text, reply)
    await telegram_client.send_message(chat_id, reply, buttons=btns or None)
    conv = get_store().get(user_id)
    log_turn(user_id, text, reply, intent, conv.stage, _dialogue_result(conv))


async def _telegram_poll_loop(telegram_client) -> None:
    offset: int | None = None
    while True:
        try:
            await telegram_client.delete_webhook()
            while True:
                updates = await telegram_client.get_updates(offset, timeout=25)
                for update in updates:
                    if not isinstance(update, dict):
                        continue
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        offset = update_id + 1
                    else:
                        try:
                            offset = int(update_id) + 1
                        except Exception:
                            pass
                    _schedule_telegram_update(update, telegram_client)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка Telegram polling")
            await asyncio.sleep(3)


def _schedule_update(update: dict, update_type: str, max_client) -> bool:
    event_id = _extract_event_id(update)
    if event_id and not mark_seen(event_id):
        logger.info("Duplicate webhook event skipped id=%s type=%s", event_id, update_type)
        return False
    task = asyncio.create_task(_process_update_safe(update, update_type, max_client))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return True


def _extract_telegram_event_id(update: dict) -> str | None:
    update_id = update.get("update_id")
    if update_id is not None:
        return f"tg:{update_id}"
    return None


async def _process_update_safe(update: dict, update_type: str, max_client) -> None:
    try:
        await _process_update(update, update_type, max_client)
    except Exception:
        logger.exception("Ошибка обработки update_type=%s", update_type)


async def _process_update(update: dict, update_type: str, max_client) -> None:
    if update_type == "bot_added":
        chat_id = group_chat.extract_chat_id(update)
        logger.info("BOT ADDED: chat_id=%s", chat_id)
        return

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
        if group_chat.is_group_message(message):
            await group_chat.handle_group_message(message, max_client)
            return
        user_id = str(sender.get("user_id")) if sender.get("user_id") else None
        if not user_id:
            return
        text = (message.get("body") or {}).get("text", "").strip()
        if not text:
            return
        low = text.lower()
        intent = I.detect_intent(text)
        if low in _ADMIN_REPORT_CMDS and settings.is_admin(user_id):
            await _send_admin_report(max_client, user_id)
        else:
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
            elif intent == I.HOMEWORK:
                store = get_store()
                conv = store.get(user_id)
                reply = (
                    "Помощь с домашкой у нас бесплатная 📸 Откройте приложение, "
                    "загрузите фото задания — объясню, что нужно сделать и как, на примере. "
                    "Решать ребёнок будет сам 🙂"
                )
                buttons = _homework_button()
                await max_client.send_message(user_id, reply, buttons=buttons or None)
                log_turn(user_id, text, reply, intent, conv.stage, "homework")
            elif intent == I.HANDOFF:
                store = get_store()
                conv = store.get(user_id)
                conv.add("user", text)
                reply, buttons = await _admin_contact_flow(max_client, conv)
                conv.add("assistant", reply)
                store.save(conv)
                await max_client.send_message(user_id, reply, buttons=buttons)
                log_turn(user_id, text, reply, intent, conv.stage, "handoff")
            else:
                reply = await handle_message(user_id, text)
                btns = _contextual_buttons(text, reply)
                await max_client.send_message(user_id, reply, buttons=btns or None)
                conv = get_store().get(user_id)
                log_turn(user_id, text, reply, intent, conv.stage, _dialogue_result(conv))
        return

    if update_type == "message_callback":
        callback = update.get("callback") or update
        callback_id = callback.get("callback_id") or callback.get("id")
        payload = callback.get("payload", "")
        user_id = _extract_user_id(update) or _extract_user_id(callback)
        if callback_id:
            await max_client.answer_callback(callback_id)
        if user_id and payload == "menu:admin":
            store = get_store()
            conv = store.get(user_id)
            conv.add("user", _CALLBACK_TEXT[payload])
            reply, buttons = await _admin_contact_flow(max_client, conv)
            conv.add("assistant", reply)
            store.save(conv)
            await max_client.send_message(user_id, reply, buttons=buttons)
        elif user_id and payload in _CALLBACK_TEXT:
            reply = await handle_message(user_id, _CALLBACK_TEXT[payload])
            btns = _contextual_buttons(_CALLBACK_TEXT[payload], reply)
            await max_client.send_message(user_id, reply, buttons=btns or None)
        elif user_id and str(payload).startswith("contact:"):
            branch_key = str(payload).split(":", 1)[1].strip()
            store = get_store()
            conv = store.get(user_id)
            reply, buttons = await _admin_contact_flow(max_client, conv, branch_key=branch_key)
            conv.add("assistant", reply)
            store.save(conv)
            await max_client.send_message(user_id, reply, buttons=buttons)
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


def _extract_event_id(update: dict) -> str | None:
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


_HOMEWORK_MAX_BYTES = 5 * 1024 * 1024
_HOMEWORK_ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}


def _homework_fallback(note: str = "") -> str:
    extra = " Пришлите, пожалуйста, более чёткое фото, если это не помогло."
    if note.strip():
        return (
            "Пока я не смогла уверенно разобрать фото домашки. "
            "Попробуйте прислать снимок покрупнее и без размытия."
            + extra
        )
    return (
        "Сейчас я не смогла разобрать фото домашки. "
        "Пришлите, пожалуйста, более чёткое изображение, и я попробую ещё раз."
        + extra
    )


def _homework_system_prompt() -> str:
    return (
        "Ты — добрый AI-репетитор по английскому. Помогаешь родителю и ребёнку, "
        "которые не знают английский. Твоя ГЛАВНАЯ задача — НАУЧИТЬ и ОБЪЯСНИТЬ, "
        "как выполнить задание, но НЕ выполнять его за ученика и НЕ давать готовые ответы. "
        "Отвечай только по-русски, понятно и доброжелательно, без markdown-разметки. "
        "На фото может быть НЕСКОЛЬКО заданий. Найди ВСЕ задания и разбери КАЖДОЕ по очереди, "
        "ничего не пропуская. Нумеруй так же, как на фото (Задание 1, Задание 2 и т. д.). "
        "По каждому заданию дай ровно три части: "
        "1) «Что нужно сделать» — простыми словами объясни, что просит задание; "
        "2) «Как это сделать» — короткое правило/подсказка и пошаговый план действий; "
        "3) «Пример» — покажи ОБРАЗЕЦ на ДРУГОМ, ПОХОЖЕМ слове или предложении (не из самого "
        "задания ребёнка), чтобы было наглядно, КАК выполнять. "
        "СТРОГО ЗАПРЕЩЕНО: давать готовые ответы на конкретные пункты задания, переводить или "
        "заполнять пропуски именно из задания ребёнка, решать за него. Ответы ребёнок вписывает сам. "
        "В самом конце добавь один короткий тёплый совет и напоминание проверить работу с учителем. "
        "Если фото неразборчиво, прямо скажи об этом и попроси прислать более чёткое фото. "
        "Не выдумывай то, чего не видно на изображении."
    )


def _homework_user_prompt(note: str) -> str:
    note = note.strip()
    lines = [
        "Помоги разобраться с домашним заданием по английскому на фото — научи, как его сделать.",
    ]
    if note:
        lines.append(f"Заметка родителя: {note}")
    lines.extend(
        [
            "Разбери ВСЕ задания, которые видишь на фото, по очереди — не только первое.",
            "По каждому заданию: 1) что нужно сделать, 2) как это сделать (правило + шаги), "
            "3) пример на ДРУГОМ похожем слове/предложении для наглядности.",
            "НЕ давай готовые ответы на пункты задания и не решай за ребёнка — только объясни и покажи метод.",
            "В конце добавь один короткий тёплый совет для родителя и ребёнка.",
        ]
    )
    return "\n".join(lines)

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
        interest_type=str(data.get("interest_type", "")),
        interest_value=str(data.get("interest_value", "")),
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
    await _notify_admins_new_lead(lead, crm_ok=ok)
    return {"ok": ok}


async def _notify_admins_new_lead(lead: Lead, crm_ok: bool) -> None:
    """Дублирует новую заявку из мини-приложения администраторам в личку."""
    if not settings.admin_ids:
        return
    lines = ["🆕 Новая заявка из мини-приложения"]
    if lead.fio_parent:
        lines.append(f"Родитель: {lead.fio_parent}")
    if lead.fio_child:
        lines.append(f"Ребёнок: {lead.fio_child}")
    if lead.birthday:
        lines.append(f"Дата рождения: {lead.birthday}")
    if lead.phone:
        lines.append(f"Телефон: {lead.phone}")
    if lead.branch:
        lines.append(f"Филиал: {lead.branch}")
    interest = lead.interest_label() or lead.course
    if interest:
        lines.append(f"Интерес: {interest}")
    if lead.comment:
        lines.append(f"Комментарий: {lead.comment}")
    if not crm_ok:
        lines.append("⚠️ В CRM заявка не ушла — свяжитесь с клиентом вручную.")
    text = "\n".join(lines)
    max_client = get_max()
    for admin_id in settings.admin_ids:
        try:
            await max_client.send_message(admin_id, text)
        except Exception:
            logger.exception("Не удалось уведомить администратора %s о заявке", admin_id)


@app.post("/api/miniapp/homework")
async def miniapp_homework(
    image: UploadFile | None = File(default=None),
    note: str = Form(default=""),
) -> dict:
    if image is None:
        raise HTTPException(status_code=400, detail="Прикрепите фото домашнего задания")
    content_type = (image.content_type or "").lower().strip()
    if content_type not in _HOMEWORK_ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Разрешены только фото в формате JPEG, PNG, WEBP, HEIC или HEIF",
        )
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Файл пустой")
    if len(image_bytes) > _HOMEWORK_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Файл слишком большой. Максимум 5 МБ")

    data_uri = f"data:{content_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    llm = get_llm()
    system_prompt = _homework_system_prompt()
    user_prompt = _homework_user_prompt(note)
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        },
    ]
    explanation = await llm.complete_vision(messages, temperature=0.2, max_tokens=1800)
    if not explanation:
        explanation = _homework_fallback(note)
    return {"explanation": explanation}


# Статика мини-приложения (если каталог есть).
if _MINIAPP_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(_MINIAPP_DIR), html=True), name="miniapp")

# Статика веб-виджета (если каталог есть).
if _WIDGET_DIR.exists():
    app.mount("/widget", StaticFiles(directory=str(_WIDGET_DIR), html=True), name="widget")


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


@app.post("/admin/telegram/set-webhook")
async def admin_telegram_set_webhook(
    x_admin_token: str | None = Header(default=None),
) -> dict:
    """Регистрирует webhook Telegram-бота на публичном URL из настроек."""
    _check_admin(x_admin_token)
    if not settings.TELEGRAM_WEBHOOK_URL:
        return {"ok": False, "error": "telegram webhook url required"}
    ok = await get_telegram().set_webhook(
        settings.TELEGRAM_WEBHOOK_URL,
        settings.TELEGRAM_WEBHOOK_SECRET or None,
    )
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


@app.get("/admin/users")
async def admin_users(
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _require_admin_token(x_admin_token)
    return {"rows": list_users()}


@app.get("/admin/users/{user_id}")
async def admin_user_detail(
    user_id: str,
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _require_admin_token(x_admin_token)
    detail = get_user_detail(user_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="user not found")
    return detail


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
