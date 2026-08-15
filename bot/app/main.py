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
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import ai_core
from app.ai_core import handle_message, handle_start
from app import broadcast
from app import cabinet
from app import crm_ingest
from app.bigben import get_bigben
from app.config import settings
from app.course_selector import recommend
from app.email_notify import send_lead_email
from app import intent as I
from app import group_chat
from app import insights
from app import leveltest
from app import nudge
from app import profile
from app import registration
from app import runtime
from app import scheduler
from app import watchdog
from app.knowledge.kb import get_kb
from app.observability import init_sentry
from app.llm import get_llm
from app.llm_gateway import (
    ROLE_CRITIC,
    ROLE_FAST,
    ROLE_REASONING,
    ROLE_VISION,
    get_gateway,
)
from app.max_client import callback_button, get_max, link_button
from app import miniapp_auth
from app.memory import Lead, STAGE_HANDOFF, get_store
from app.slack import notify_slack
from app.telegram_client import get_telegram

logging.basicConfig(level=logging.INFO)
# httpx/httpcore логируют полный URL запроса на уровне INFO, а токены MAX и
# Telegram передаются прямо в пути URL (botTOKEN/...) — на WARNING+ секреты
# в логи не попадают.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"
PLATFORM = "max"

init_sentry()

app = FastAPI(title="Foxinburg MAX Bot", version=APP_VERSION)

# Форма заявки на статическом сайте (миграция с Tilda) шлёт POST с другого
# origin (dymova-english.ru / new.dymova-english.ru) — без этого браузер
# заблокирует запрос.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.site_cors_origins,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

_MINIAPP_DIR = Path(__file__).with_name("miniapp")
_BACKGROUND_TASKS: set[asyncio.Task] = set()


@app.on_event("startup")
async def _start_scheduler() -> None:
    # CRM-хранилище: схема рядом с legacy-таблицами и однократный перенос
    # истории. Сбой здесь не должен мешать запуску бота — логируем и живём.
    try:
        from app import crm_store

        crm_store.get_conn()
        report = crm_store.migrate_from_legacy()
        crm_store.seed_bootstrap_admin()
        if not report.get("skipped"):
            logger.info("crm: миграция legacy-истории: %s", report)
    except Exception:
        logger.exception("crm: ошибка инициализации/миграции")
    for task in scheduler.start():
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
    telegram = get_telegram()
    if settings.TELEGRAM_POLLING and telegram.configured:
        logger.info("telegram: запуск long-polling")
        task = asyncio.create_task(_telegram_poll_loop(telegram))
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)


def _miniapp_open(user_id: str, platform: str = PLATFORM) -> bool:
    """Показывать ли кнопку запуска мини-приложения.

    Личный кабинет открывается только зарегистрированным: незарегистрированный
    человек всё равно упрётся в анкету уже внутри приложения, а кнопка,
    ведущая в тупик, — худший вид кнопки.
    """
    if not user_id:
        return False
    return registration.is_registered(get_store().get(user_id, platform=platform))


def _main_menu(user_id: str = "") -> list[list[dict]]:
    rows = [
        [callback_button("🎓 Подобрать курс", "menu:courses")],
        [callback_button("📅 Записаться на пробное", "menu:signup")],
        [callback_button("💳 Стоимость обучения", "menu:price")],
        [callback_button("🏫 Наши филиалы", "menu:branches")],
        [callback_button("☎ Связаться с администратором", "menu:admin")],
    ]
    if settings.MINIAPP_BASE_URL and _miniapp_open(user_id):
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
        "Ты помогаешь ученику разобраться с домашним заданием. Не давай "
        "готовых ответов и не решай задание за него: объясняй, как к нему "
        "подступиться, давай подсказки, задавай наводящие вопросы и приводи "
        "короткий пример на похожем материале."
    )


def _homework_user_prompt(note: str) -> str:
    extra = f" Дополнительная заметка: {note}." if note else ""
    return (
        "Не давай готовые ответы, не решай за ребёнка и помоги понять, как "
        "это сделать самостоятельно. Покажи короткий пример и объясни шаги."
        f"{extra}"
    )


async def explain_homework_image(
    image_bytes: bytes, content_type: str, note: str = ""
) -> str | None:
    """Разбор фотографии задания. None — модель не смогла помочь.

    Общая точка для мини-приложения и для чата: раньше vision работал только
    в мини-приложении, а на фото в чате бот отвечал «опишите текстом» — то
    есть отказывался от того, что уже умел.
    """
    messages = [
        {"role": "system", "content": _homework_system_prompt()},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _homework_user_prompt(note)},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            f"data:{content_type};base64,"
                            f"{base64.b64encode(image_bytes).decode('ascii')}"
                        )
                    },
                },
            ],
        },
    ]
    return await get_gateway().vision(messages, temperature=0.2, max_tokens=1200)


def _admin_authorized(request: Request) -> bool:
    token = request.headers.get("X-Admin-Token", "")
    if not settings.ADMIN_TOKEN:
        return False
    # Сравнение постоянного времени: обычный == утекает длину общего префикса
    # и позволяет подбирать токен по времени ответа.
    return hmac.compare_digest(token, settings.ADMIN_TOKEN)


def _nudge_authorized(request: Request) -> bool:
    """Рассылка напоминаний — тоже админское действие.

    Раньше при пустом ADMIN_TOKEN эти ручки были открыты всему интернету:
    кто угодно мог инициировать рассылку по всей базе клиентов.
    """
    return _admin_authorized(request)


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


# Заголовок, в котором мини-приложение передаёт подписанный initData.
INIT_DATA_HEADER = "X-Miniapp-Init-Data"
PLATFORM_HEADER = "X-Miniapp-Platform"


def _identity_from_request(
    request: Request | None,
    init_data: str = "",
    fallback_user_id: str = "",
) -> miniapp_auth.MiniAppIdentity | None:
    """Личность пользователя мини-приложения — только из подписанных данных.

    `user_id` из запроса личностью не считается (см. miniapp_auth.identify):
    доверять ему означало бы отдавать чужой профиль любому желающему.
    """
    if request is not None:
        init_data = init_data or request.headers.get(INIT_DATA_HEADER, "")
        platform_hint = request.headers.get(PLATFORM_HEADER, "")
    else:
        platform_hint = ""
    return miniapp_auth.identify(
        init_data=init_data,
        platform_hint=platform_hint,
        fallback_user_id=fallback_user_id,
    )


def _miniapp_access_state(identity: miniapp_auth.MiniAppIdentity | None) -> dict:
    has_identity = identity is not None
    registered = False
    if identity is not None:
        registered = bool(
            get_store().get(identity.user_id, platform=identity.platform).registered
        )
    locked = has_identity and settings.MINIAPP_REQUIRE_REGISTRATION and not registered
    message = ""
    if locked:
        message = (
            "Сначала зарегистрируйтесь в чате бота: "
            "напишите «зарегистрироваться», и я проведу вас по шагам."
        )
    elif not has_identity:
        message = "Откройте приложение внутри Telegram или MAX, чтобы связать профиль."
    return {
        "user_id": identity.user_id if identity else "",
        "platform": identity.platform if identity else "",
        "display_name": identity.display_name if identity else "",
        "has_identity": has_identity,
        "verified": bool(identity and identity.verified),
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
        f"{profile.lead_summary(conv)}"
    )
    for admin_id in settings.admin_ids:
        await admin_client.send_message(admin_id, message)
    await notify_slack(f"MAX handoff ({reason})\n\n{profile.lead_summary(conv)}")


# Публичный чат-эндпоинт ходит в платный LLM, поэтому ограничиваем частоту:
# без этого один скрипт способен сжечь квоту провайдера за минуты.
MAX_CHAT_TEXT_CHARS = 2000
_CHAT_RATE_LIMIT = 20          # сообщений
_CHAT_RATE_WINDOW_SEC = 60.0   # за окно
# Заявка с сайта дороже сообщения: она пишется в CRM, уходит письмом и
# сообщением каждому администратору. Поток таких «заявок» — это спам по всем
# трём каналам сразу, поэтому лимит на порядок строже.
_LEAD_RATE_LIMIT = 5
_LEAD_RATE_WINDOW_SEC = 600.0
_hits: dict[tuple[str, str], list[float]] = {}


def _rate_limited(bucket: str, key: str, limit: int, window: float) -> bool:
    """Скользящее окно на пару «эндпоинт + клиент»."""
    now = time.monotonic()
    slot = (bucket, key)
    hits = [t for t in _hits.get(slot, []) if now - t < window]
    if len(hits) >= limit:
        _hits[slot] = hits
        return True
    hits.append(now)
    _hits[slot] = hits
    if len(_hits) > 10_000:
        # Грубая, но достаточная защита словаря от неограниченного роста.
        stale = [k for k, v in _hits.items() if not v or now - v[-1] > window]
        for stale_key in stale:
            _hits.pop(stale_key, None)
    return False


def _chat_rate_limited(key: str) -> bool:
    return _rate_limited("chat", key, _CHAT_RATE_LIMIT, _CHAT_RATE_WINDOW_SEC)


def _lead_rate_limited(key: str) -> bool:
    return _rate_limited("lead", key, _LEAD_RATE_LIMIT, _LEAD_RATE_WINDOW_SEC)


@app.post("/api/chat")
async def api_chat(request: Request, data: dict) -> dict:
    text = str(data.get("text", "")).strip()
    if not text:
        return JSONResponse({"detail": "text required"}, status_code=400)
    if len(text) > MAX_CHAT_TEXT_CHARS:
        return JSONResponse(
            {"detail": f"Сообщение длиннее {MAX_CHAT_TEXT_CHARS} символов"}, status_code=413
        )
    session_id = str(data.get("session_id") or uuid.uuid4().hex)[:64]
    client_host = request.client.host if request.client else "unknown"
    if _chat_rate_limited(client_host):
        return JSONResponse(
            {"detail": "Слишком много сообщений подряд, попробуйте через минуту"},
            status_code=429,
        )
    # У веб-виджета нет внешнего id события — генерируем свой, чтобы журнал
    # входящих событий был полным по всем каналам.
    crm_ctx = crm_ingest.ingest_inbound(
        "web", f"web:{session_id}", text, external_event_id=f"web:{uuid.uuid4().hex}",
    )
    reply = await handle_message(f"web:{session_id}", text, platform="web")
    if reply:
        crm_ingest.ingest_outbound(crm_ctx, reply, ai_model=settings.LLM_MODEL)
    # Пустой ответ = диалог на паузе/у менеджера: вместо реплики бота виджет
    # получает накопившиеся ответы менеджера.
    pending = crm_ingest.pop_pending_web(session_id)
    return {
        "session_id": session_id,
        "reply": reply,
        "buttons": _contextual_buttons(text, reply),
        "pending_messages": pending,
    }


@app.get("/api/chat/pending")
async def api_chat_pending(session_id: str = "") -> dict:
    """Поллинг виджета: недоставленные ответы менеджера (push у веба нет)."""
    session_id = str(session_id or "")[:64]
    if not session_id:
        return JSONResponse({"detail": "session_id required"}, status_code=400)
    return {"messages": crm_ingest.pop_pending_web(session_id)}


@app.post("/api/miniapp/chat")
async def miniapp_chat(request: Request, data: dict) -> dict:
    """Чат с Фокси внутри мини-приложения — тот же диалог, что и в мессенджере."""
    identity = _identity_from_request(request, fallback_user_id=_miniapp_user_id(data))
    if identity is None:
        return JSONResponse(
            {"ok": False, "error": "Нужна авторизация внутри Telegram или MAX"},
            status_code=401,
        )
    text = str(data.get("text", "")).strip()
    if not text:
        return JSONResponse({"ok": False, "error": "Пустое сообщение"}, status_code=400)
    if len(text) > MAX_CHAT_TEXT_CHARS:
        return JSONResponse({"ok": False, "error": "Слишком длинное сообщение"}, status_code=413)
    if _chat_rate_limited(identity.user_id):
        return JSONResponse(
            {"ok": False, "error": "Слишком много сообщений подряд, попробуйте через минуту"},
            status_code=429,
        )
    reply = await handle_message(identity.user_id, text, platform=identity.platform)
    return {"ok": True, "reply": reply}


# Больше 8 МБ фото задания быть не может, а вот OOM от «загрузки» на 2 ГБ —
# вполне: UploadFile.read() без лимита читает всё тело в память.
MAX_HOMEWORK_IMAGE_BYTES = 8 * 1024 * 1024


@app.post("/api/miniapp/homework")
async def api_homework(
    request: Request,
    note: str = Form(default=""),
    user_id: str = Form(default=""),
    init_data: str = Form(default=""),
    image: UploadFile | None = File(default=None),
) -> dict:
    identity = _identity_from_request(request, init_data=init_data, fallback_user_id=user_id)
    access = _miniapp_access_state(identity)
    if access["locked"]:
        return JSONResponse({"ok": False, "error": access["message"]}, status_code=403)
    if image is None or not image.filename:
        return JSONResponse({"detail": "Нужна фотография задания"}, status_code=400)
    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        return JSONResponse({"detail": "Файл должен быть в формате изображения"}, status_code=400)

    image_bytes = await image.read(MAX_HOMEWORK_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_HOMEWORK_IMAGE_BYTES:
        return JSONResponse(
            {"detail": "Фото слишком большое — пришлите снимок до 8 МБ"}, status_code=413
        )
    if not image_bytes:
        return JSONResponse({"detail": "Пустой файл"}, status_code=400)

    explanation = await explain_homework_image(image_bytes, content_type, note)
    if not explanation:
        explanation = (
            "Не удалось разобрать фото задания. Попробуйте снять его при "
            "хорошем свете — или опишите текстом, что нужно сделать."
        )

    return {
        "ok": True,
        "explanation": explanation,
        "buttons": _contextual_buttons("домашка", explanation),
    }


def _telegram_buttons(text: str, reply: str) -> list[list[dict]]:
    buttons = _contextual_buttons(text, reply)
    return [[button] for button in buttons]


async def _send_tg_logged(telegram, chat_id, text: str, crm_ctx: dict | None,
                          buttons: list | None = None) -> bool:
    """Отправка в Telegram с записью исходящего сообщения в CRM.
    Пустой text — «бот молчит» (AI на паузе/у менеджера)."""
    if not text:
        return True
    ok = await telegram.send_message(chat_id, text, buttons=buttons)
    crm_ingest.ingest_outbound(crm_ctx, text, ai_model=settings.LLM_MODEL, ok=bool(ok))
    return ok


def _telegram_inbound_ctx(update: dict, message: dict, user_id: str, text: str) -> dict | None:
    sender = message.get("from") or {}
    return crm_ingest.ingest_inbound(
        TELEGRAM_PLATFORM, user_id, text,
        external_event_id=str(update.get("update_id") or "") or None,
        external_message_id=str(message.get("message_id") or "") or None,
        first_name=str(sender.get("first_name") or ""),
        last_name=str(sender.get("last_name") or ""),
        username=str(sender.get("username") or ""),
    )


def _telegram_webapp_button(user_id: str = "") -> dict | None:
    """Кнопка открытия Telegram Mini App прямо внутри чата."""
    url = settings.telegram_miniapp_url
    if not url.startswith("https://"):
        return None
    if not _miniapp_open(user_id, platform=TELEGRAM_PLATFORM):
        return None
    return {"type": "web_app", "text": "📱 Личный кабинет", "web_app": url}


def _telegram_menu_buttons(user_id: str = "") -> list[list[dict]]:
    rows: list[list[dict]] = []
    webapp = _telegram_webapp_button(user_id)
    if webapp:
        rows.append([webapp])
    rows.extend(
        [
            [callback_button("🎓 Подобрать курс", "menu:courses")],
            [callback_button("📅 Записаться на пробное", "menu:signup")],
            [callback_button("💳 Стоимость обучения", "menu:price")],
            [callback_button("🏫 Наши филиалы", "menu:branches")],
            [callback_button("☎ Связаться с администратором", "menu:admin")],
        ]
    )
    return rows


def _telegram_start_buttons(text: str, reply: str, user_id: str = "") -> list[list[dict]] | None:
    """На /start показываем меню целиком — иначе новый пользователь видит
    только текст и не знает, что у бота вообще есть кнопки."""
    return _telegram_menu_buttons(user_id) or _telegram_buttons(text, reply) or None


def _link_button_rows(text: str, reply: str) -> list[list[dict]]:
    return [[link_button(button["title"], button["url"])] for button in _contextual_buttons(text, reply)]


_TELEGRAM_MEDIA_FIELDS = ("voice", "photo", "sticker", "video", "document", "audio", "video_note")

TELEGRAM_PLATFORM = "telegram"
# Индикатор «печатает» живёт ~5 секунд, поэтому обновляем его чаще.
TYPING_REFRESH_SEC = 4.0


async def _keep_typing(telegram, chat_id) -> None:
    """Держит индикатор «печатает», пока формируется ответ.

    Молчащий бот и думающий бот выглядят для пользователя одинаково — этот
    цикл делает разницу видимой.
    """
    send_action = getattr(telegram, "send_chat_action", None)
    if not callable(send_action):
        return
    try:
        while True:
            try:
                await send_action(chat_id, "typing")
            except Exception:
                logger.debug("telegram: не удалось отправить typing", exc_info=True)
                return
            await asyncio.sleep(TYPING_REFRESH_SEC)
    except asyncio.CancelledError:
        return


async def _slow_notice(telegram, chat_id) -> None:
    """Промежуточный статус, если ответ готовится дольше обычного."""
    delay = float(getattr(settings, "SLOW_NOTICE_SEC", 12.0) or 0)
    if delay <= 0:
        return
    try:
        await asyncio.sleep(delay)
        await telegram.send_message(
            chat_id, "Секунду, уточняю информацию — сейчас отвечу 🙂"
        )
    except asyncio.CancelledError:
        return
    except Exception:
        logger.debug("telegram: не удалось отправить промежуточный статус", exc_info=True)


async def _reply_while_alive(client, chat_id, produce):
    """Выполняет produce(), показывая пользователю, что бот жив.

    Работает и для Telegram, и для MAX: индикатор «печатает» включается
    только там, где клиент его поддерживает, промежуточный статус —
    везде (у обоих клиентов одинаковая сигнатура send_message).
    """
    typing = asyncio.create_task(_keep_typing(client, chat_id))
    notice = asyncio.create_task(_slow_notice(client, chat_id))
    try:
        return await produce()
    finally:
        for task in (typing, notice):
            task.cancel()
        await asyncio.gather(typing, notice, return_exceptions=True)


async def _telegram_callback(update: dict, telegram) -> None:
    """Обработка нажатия inline-кнопки.

    answerCallbackQuery отправляется ПЕРВЫМ и всегда: пока он не пришёл,
    клиент Telegram крутит спиннер на кнопке до собственного таймаута.
    """
    callback = update.get("callback_query") or {}
    callback_id = callback.get("id")
    payload = str(callback.get("data") or "")
    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    if chat_id is None:
        chat_id = (callback.get("from") or {}).get("id")
    if callback_id:
        try:
            await telegram.answer_callback_query(str(callback_id))
        except Exception:
            logger.exception("telegram: answerCallbackQuery не прошёл")
    if chat_id is None:
        return

    user_id = f"tg:{chat_id}"
    if payload in _BRANCH_CONTACTS:
        info = _BRANCH_CONTACTS[payload]
        conv = get_store().get(user_id, platform=TELEGRAM_PLATFORM)
        conv.selected_branch = info["name"]
        conv.stage = STAGE_HANDOFF
        get_store().save(conv)
        await _notify_admins_for_telegram(conv, "контакт по филиалу")
        await telegram.send_message(
            chat_id,
            f"Свяжу вас с администратором {info['name']}. Телефон: {info['phone']}",
        )
        return
    if payload.startswith("contact:"):
        await telegram.send_message(
            chat_id,
            "Подскажите, пожалуйста, какой филиал вам удобнее?",
            buttons=_branch_admin_buttons(),
        )
        return
    if payload in _CALLBACK_TEXT:
        text = _CALLBACK_TEXT[payload]
        reply = await _reply_while_alive(
            telegram,
            chat_id,
            lambda: handle_message(user_id, text, platform=TELEGRAM_PLATFORM),
        )
        await telegram.send_message(
            chat_id, reply, buttons=_telegram_buttons(text, reply) or None
        )
        return
    logger.info("telegram: неизвестный callback payload=%s", payload[:64])


def parse_start_payload(text: str) -> dict:
    """Разбирает payload команды /start в UTM-метки.

    Deeplink Telegram не допускает `=` и `&`, поэтому источники кодируют
    метки как `utm_source-vk__utm_campaign-avgust`. Всё, что не разобралось
    по этой схеме, сохраняем целиком — это может быть код партнёра или id
    рекламного объявления, и терять его нельзя.
    """
    parts = (text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) > 1 else ""
    if not payload:
        return {}
    utm: dict[str, str] = {}
    for chunk in payload.split("__"):
        key, sep, value = chunk.partition("-")
        if sep and key.startswith("utm_") and value:
            utm[key] = value[:100]
    if not utm:
        utm["deeplink"] = payload[:100]
    return utm


def _remember_deeplink(user_id: str, platform: str, text: str) -> None:
    """Сохраняет источник перехода в диалог — он уйдёт в CRM вместе с заявкой."""
    utm = parse_start_payload(text)
    if not utm:
        return
    store = get_store()
    conv = store.get(user_id, platform=platform)
    # Первый источник важнее последнего: он привёл человека в бота.
    conv.utm = {**utm, **(conv.utm or {})}
    store.save(conv)
    logger.info("deeplink: source=%s user_id=%s", ",".join(utm), user_id)


async def _process_telegram_update(update: dict, telegram) -> None:
    runtime.set_request_id(runtime.new_request_id())
    if update.get("callback_query"):
        try:
            await _telegram_callback(update, telegram)
        except Exception:
            logger.exception("telegram: ошибка обработки callback_query")
        return

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    try:
        # Фото с подписью двусмысленно: «Задание 3» — это комментарий к
        # присланному снимку, а «Сколько стоит?» — самостоятельный вопрос, к
        # которому картинка приложена мимоходом. Решаем по намерению подписи:
        # распознанное намерение (цена, контакты, запись) отвечаем текстом,
        # всё остальное считаем заданием и разбираем фото.
        if message.get("photo"):
            caption = str(message.get("caption") or "").strip()
            caption_intent = I.detect_intent(caption) if caption else I.HOMEWORK
            if caption_intent in (I.QUESTION, I.HOMEWORK):
                await _handle_telegram_photo(message, chat_id, telegram)
                return

        # Подпись к остальным вложениям лежит в caption, не в text.
        text = str(message.get("text") or message.get("caption") or "").strip()
        if not text:
            media_field = next((f for f in _TELEGRAM_MEDIA_FIELDS if message.get(f)), None)
            if media_field is None:
                # Служебные апдейты без текста (new_chat_members,
                # pinned_message и т.п.) — отвечать нечего, не спамим.
                return
            # Голосовые/стикеры/видео бот не читает. Раньше такие апдейты
            # молча отбрасывались (ни ответа, ни лога) — выглядело как
            # зависание бота при любом нетекстовом сообщении.
            await telegram.send_message(
                chat_id,
                "Пока не умею читать голосовые и файлы 🙈 Напишите, "
                "пожалуйста, текстом — обязательно отвечу.",
            )
            return

        user_id = f"tg:{chat_id}"
        crm_ctx = _telegram_inbound_ctx(update, message, user_id, text)
        low = text.lower()
        if low.split(maxsplit=1)[0] in ("/start", "start"):
            # У /start бывает payload: `t.me/bot?start=utm_source-vk` приходит
            # как «/start utm_source-vk». Раньше сравнение шло со всей строкой,
            # поэтому команда с payload не распознавалась как старт, а сам
            # payload (источник перехода) терялся вместе с ней.
            _remember_deeplink(user_id, TELEGRAM_PLATFORM, text)
            reply = await handle_start(user_id, platform=TELEGRAM_PLATFORM)
            await _send_tg_logged(telegram, chat_id, reply, crm_ctx, buttons=_telegram_start_buttons(text, reply, user_id))
            return

        if low in ("/menu", "меню", "/app", "кабинет"):
            await _send_tg_logged(
                telegram, chat_id, "Чем помочь? 😊", crm_ctx, buttons=_telegram_menu_buttons(user_id)
            )
            return

        if I.detect_complaint(text) or I.detect_intent(text) == I.HANDOFF:
            conv = get_store().get(user_id, platform=TELEGRAM_PLATFORM)
            branch = conv.selected_branch or conv.lead.branch
            if branch:
                await _notify_admins_for_telegram(conv, "запрос администратора")
                reply = f"Свяжу вас с администратором {branch}. Он скоро ответит."
                await _send_tg_logged(telegram, chat_id, reply, crm_ctx)
            else:
                reply = "Подскажите, пожалуйста, какой филиал вам удобнее?"
                await _send_tg_logged(telegram, chat_id, reply, crm_ctx, buttons=_branch_admin_buttons())
            return

        if "домаш" in low or "дз" in low:
            reply = "Помощь с домашкой у нас бесплатная. Пришлите фото задания, и я подскажу, как его разобрать."
            await _send_tg_logged(telegram, chat_id, reply, crm_ctx, buttons=_telegram_buttons(text, reply) or None)
            return

        reply = await _reply_while_alive(
            telegram,
            chat_id,
            lambda: handle_message(user_id, text, platform=TELEGRAM_PLATFORM),
        )
        await _send_tg_logged(telegram, chat_id, reply, crm_ctx, buttons=_telegram_buttons(text, reply) or None)
    except Exception:
        # Раньше исключение здесь просто убивало фоновую задачу молча —
        # пользователь не получал вообще ничего, что выглядело как
        # зависший бот. Теперь хотя бы логируем и отвечаем что-то живое.
        logger.exception("telegram: unhandled error processing update %s", update.get("update_id"))
        try:
            await telegram.send_message(
                chat_id,
                "Что-то пошло не так на моей стороне 🙏 Попробуйте, пожалуйста, "
                "написать ещё раз через минуту.",
            )
        except Exception:
            logger.exception("telegram: failed to send fallback error message")


async def _handle_telegram_photo(message: dict, chat_id, telegram) -> None:
    """Фото задания из чата: скачиваем и разбираем тем же vision, что и в кабинете."""
    sizes = message.get("photo") or []
    if not isinstance(sizes, list) or not sizes:
        return
    # Telegram отдаёт несколько размеров по возрастанию — берём самый крупный
    # из тех, что влезают в лимит: мелкий превью нечитаем для модели.
    largest = max(sizes, key=lambda item: item.get("file_size") or item.get("width") or 0)
    file_id = largest.get("file_id")
    if not file_id:
        return

    note = str(message.get("caption") or "").strip()
    download = getattr(telegram, "download_file", None)
    if not callable(download):
        # Клиент без скачивания файлов (старая сборка, урезанный адаптер) —
        # не повод отвечать пользователю ошибкой.
        await telegram.send_message(
            chat_id,
            "Вижу фото 📸 Опишите, пожалуйста, текстом, что за задание — "
            "так смогу помочь точнее.",
        )
        return
    image = await download(file_id, MAX_HOMEWORK_IMAGE_BYTES)
    if not image:
        await telegram.send_message(
            chat_id,
            "Не получилось открыть это фото. Пришлите, пожалуйста, снимок "
            "поменьше — или опишите задание текстом.",
        )
        return

    explanation = await _reply_while_alive(
        telegram, chat_id, lambda: explain_homework_image(image, "image/jpeg", note)
    )
    if not explanation:
        await telegram.send_message(
            chat_id,
            "Не смог разобрать задание по фото. Напишите, пожалуйста, текстом, "
            "что именно нужно сделать — помогу разобраться.",
        )
        return
    await telegram.send_message(chat_id, explanation)


def _schedule_telegram_update(update: dict, telegram) -> bool:
    update_id = update.get("update_id")
    if update_id is not None:
        store = get_store()
        if not store.mark_event_seen(str(update_id), platform=TELEGRAM_PLATFORM, event_type="update"):
            logger.info("telegram: дубликат update_id=%s пропущен", update_id)
            return False
    task = asyncio.create_task(_process_telegram_update(update, telegram))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return True


async def _telegram_poll_loop(telegram) -> None:
    await telegram.delete_webhook()
    offset: int | None = None
    backoff = 3
    while True:
        try:
            updates = await telegram.get_updates(offset=offset, timeout=25)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("telegram: ошибка long-polling")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue
        backoff = 3
        # Отмечаем, что цикл реально прокрутился: сторож по этой метке
        # ловит «getUpdates отвечает, а сообщения не забираются».
        watchdog.record_poll_ok()
        for update in updates:
            # ВАЖНО: offset двигаем ВСЕГДА, даже если апдейт признан
            # дубликатом и обрабатывать его не нужно. Раньше offset
            # обновлялся только для новых апдейтов — и после рестарта
            # (Telegram переотдаёт неподтверждённый апдейт, который уже
            # лежит в processed_events) offset замирал навсегда, getUpdates
            # бесконечно возвращал тот же батч, а бот переставал отвечать
            # вообще всем. Подтверждение доставки и дедупликация — разные
            # вещи, и путать их нельзя.
            update_id = update.get("update_id")
            if update_id is not None:
                try:
                    offset = max(offset or 0, int(update_id) + 1)
                except (TypeError, ValueError):
                    pass
            _schedule_telegram_update(update, telegram)


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
        # Видно, какая модель обслуживает какую роль и как она себя ведёт —
        # без этого деградация быстрой модели незаметна до жалоб клиентов.
        "llm_roles": {
            role: get_gateway().model_for(role) or settings.LLM_MODEL
            for role in (ROLE_REASONING, ROLE_FAST, ROLE_VISION, ROLE_CRITIC)
        },
        "llm_role_stats": get_gateway().stats(),
        "max_configured": max_client.configured,
        "bigben_configured": get_bigben().configured,
        "kb_documents": len(get_kb().documents),
        # Раньше /health отвечал "ok", пока Telegram лежал две недели: он
        # знал только про собственный процесс. Теперь видно и внешний канал.
        "telegram": watchdog.status(),
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
    if not update_id:
        # Апдейт без id: раньше дедупликация просто отключалась, и ретрай
        # вебхука обрабатывался второй раз — клиент получал дубль ответа.
        # Ретрай приходит байт-в-байт таким же, поэтому хэш канонической
        # формы апдейта даёт надёжный ключ; у живого пользователя, написавшего
        # то же слово позже, отличается timestamp, и хэш другой.
        digest = hashlib.sha256(
            json.dumps(update, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        ).hexdigest()
        update_id = f"hash:{digest[:32]}"
    store = get_store()
    if not store.mark_event_seen(update_id, platform=PLATFORM, user_id=user_id or "", event_type=update_type or ""):
        logger.info("Duplicate update skipped id=%s type=%s", update_id, update_type)
        return False

    task = asyncio.create_task(_process_update_safe(update, update_type, max_client))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return True


async def _process_update_safe(update: dict, update_type: str, max_client) -> None:
    runtime.set_request_id(runtime.new_request_id())
    try:
        await _process_update(update, update_type, max_client)
    except Exception:
        logger.exception("Ошибка обработки update_type=%s", update_type)
        # Молчание после исключения выглядит как зависший бот — отвечаем
        # хоть что-то живое, если знаем, кому.
        user_id = _extract_user_id(update) or _extract_user_id(update.get("message") or {})
        if user_id:
            try:
                await max_client.send_message(user_id, ai_core.ERROR_REPLY)
            except Exception:
                logger.exception("MAX: не удалось отправить фолбэк об ошибке")


async def _process_update(update: dict, update_type: str, max_client) -> None:
    if update_type == "bot_started":
        user_id = _extract_user_id(update)
        if user_id:
            crm_ctx = crm_ingest.ingest_inbound(
                PLATFORM, user_id, "/start",
                external_event_id=_extract_update_id(update),
            )
            reply = await handle_start(user_id)
            await _send_max_logged(max_client, user_id, reply, crm_ctx, buttons=_main_menu(user_id))
        return

    if update_type == "message_created":
        message = update.get("message") or update
        sender = message.get("sender") or {}
        if sender.get("is_bot"):
            return

        # Групповые чаты MAX: модуль group_chat был полностью написан и
        # покрыт тестами, но нигде не вызывался — в группах бот молчал на
        # любое обращение, включая прямое упоминание. Приватная ветка ниже
        # для группового сообщения тоже не годится: она отвечает в личку
        # отправителю, а не в чат.
        if settings.GROUP_MODE_ENABLED and group_chat.is_group_message(message):
            await group_chat.handle_group_message(message, max_client)
            return

        user_id = str(sender.get("user_id")) if sender.get("user_id") else None
        if not user_id:
            return
        text = (message.get("body") or {}).get("text", "").strip()
        if not text:
            return
        _remember_sender(user_id, sender)
        crm_ctx = crm_ingest.ingest_inbound(
            PLATFORM, user_id, text,
            external_event_id=_extract_update_id(update),
            external_message_id=_max_message_external_id(message),
            name=str(sender.get("name") or ""),
            username=str(sender.get("username") or ""),
        )
        low = text.lower()
        if low in ("/start", "start"):
            reply = await handle_start(user_id)
            await _send_max_logged(max_client, user_id, reply, crm_ctx, buttons=_main_menu(user_id))
        elif I.detect_intent(text) == I.HANDOFF:
            conv = get_store().get(user_id)
            if conv.selected_branch:
                await _notify_admins_for_telegram(conv, "запрос администратора")
                reply = f"Свяжу вас с администратором {conv.selected_branch}. Он скоро ответит."
                await _send_max_logged(max_client, user_id, reply, crm_ctx, buttons=_main_menu(user_id))
            else:
                await _send_max_logged(
                    max_client,
                    user_id,
                    "Подскажите, пожалуйста, какой филиал вам удобнее?",
                    crm_ctx,
                    buttons=_branch_admin_buttons(),
                )
        elif I.detect_intent(text) == I.HOMEWORK:
            reply = "Помощь с домашкой у нас бесплатная. Пришлите фото задания, и я подскажу, как его разобрать."
            buttons = _link_button_rows(text, reply)
            await _send_max_logged(max_client, user_id, reply, crm_ctx, buttons=buttons or None)
        elif low in ("/menu", "меню"):
            await _send_max_logged(max_client, user_id, "Чем помочь? 😊", crm_ctx, buttons=_main_menu(user_id))
        else:
            reply = await _reply_while_alive(
                max_client,
                user_id,
                lambda: handle_message(user_id, text, platform=PLATFORM),
            )
            await _send_max_logged(max_client, user_id, reply, crm_ctx, buttons=_link_button_rows(text, reply) or None)
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
            if reply:  # пустой ответ — AI на паузе/у менеджера, молчим
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


def _remember_sender(user_id: str, sender: dict) -> None:
    conv = get_store().get(user_id)
    name = str(sender.get("name") or "").strip()
    username = str(sender.get("username") or "").strip()
    if name:
        conv.client_name = name
    if username:
        conv.max_username = username


def _max_message_external_id(message: dict) -> str | None:
    """Внешний id сообщения MAX для дедупликации в CRM."""
    for container in (message, message.get("body") or {}):
        for key in ("id", "mid", "message_id"):
            value = container.get(key)
            if value:
                return str(value)
    return None


async def _send_max_logged(max_client, user_id: str, text: str, crm_ctx: dict | None,
                           buttons: list | None = None) -> bool:
    """Отправка в MAX с записью исходящего сообщения в CRM.

    CRM-запись не влияет на доставку: её сбой глушится внутри crm_ingest.
    Пустой text — сигнал «бот молчит» (AI на паузе/у менеджера): ничего
    не отправляем и не пишем исходящее.
    """
    if not text:
        return True
    ok = await max_client.send_message(user_id, text, buttons=buttons)
    crm_ingest.ingest_outbound(crm_ctx, text, ai_model=settings.LLM_MODEL, ok=bool(ok))
    return ok


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
async def miniapp_access(request: Request, user_id: str = "") -> dict:
    return _miniapp_access_state(_identity_from_request(request, fallback_user_id=user_id))


@app.get("/api/miniapp/info")
async def miniapp_info(request: Request, user_id: str = "") -> dict:
    """Витрина: публичные данные школы + состояние доступа.

    Каталог, форматы и филиалы — публичная информация с сайта, она отдаётся
    и без авторизации, чтобы мини-приложение открывалось мгновенно.
    """
    kb = get_kb()
    access = _miniapp_access_state(_identity_from_request(request, fallback_user_id=user_id))
    return {
        "company": kb.company,
        "branches": kb.branches,
        "formats": kb.formats,
        "age_programs": kb.age_programs,
        "courses": kb.courses,
        "social": kb.social,
        # Преимущества и вопросы-ответы нужны витрине: главный экран
        # рассказывает о школе фактами из базы знаний, а не выдуманным
        # маркетинговым текстом в вёрстке, который разъедется с реальностью.
        "advantages": kb.raw.get("advantages", []),
        "faq": kb.raw.get("faq", []),
        # Педагоги с видеовизитками, шаги зачисления, летняя академия и акции
        # лежали в базе знаний, но в мини-приложение не попадали ни разу.
        # Это самое ценное, что школа может показать: живой педагог на видео
        # убеждает сильнее любого текста о методике.
        "team": kb.raw.get("team", []),
        "enrollment_steps": kb.raw.get("enrollment_steps", []),
        "summer_academy": kb.raw.get("summer_academy", {}),
        "promos": kb.raw.get("promos", []),
        "access": access,
    }


@app.get("/api/miniapp/level-test")
async def miniapp_level_test() -> dict:
    """Задания теста уровня — без правильных ответов.

    Ответы остаются на сервере: тест, который решается открытием исходника
    страницы, не даёт ни пользы человеку, ни данных школе.
    """
    return {"questions": leveltest.public_questions()}


@app.post("/api/miniapp/level-test")
async def miniapp_level_test_result(request: Request, data: dict) -> dict:
    """Проверка ответов теста. Авторизации не требует: это витринный
    инструмент, он работает до регистрации.

    Если личность подписана — попытка сохраняется на сервере (раньше
    результат жил только в localStorage и терялся с чисткой кэша, а без
    истории попыток нет динамики — главной ценности кабинета на старте).
    """
    answers = data.get("answers")
    if not isinstance(answers, dict):
        return JSONResponse({"ok": False, "error": "Нет ответов"}, status_code=400)
    result = leveltest.grade(answers)
    identity = _identity_from_request(request)
    if identity is not None and identity.verified:
        try:
            child_id = data.get("child_id")
            child_id = int(child_id) if child_id is not None else None
        except (TypeError, ValueError):
            child_id = None
        cabinet.record_attempt(
            get_store(), identity.platform, identity.user_id,
            result, answers, child_id=child_id,
        )
    return {"ok": True, "result": result}


@app.get("/api/miniapp/recommend")
async def miniapp_recommend(request: Request, age: str = "", fmt: str = "", user_id: str = "") -> dict:
    identity = _identity_from_request(request, fallback_user_id=user_id)
    access = _miniapp_access_state(identity)
    if access["locked"]:
        return JSONResponse({"ok": False, "error": access["message"]}, status_code=403)
    kb = get_kb()
    items = recommend(kb, age or None, fmt or None)
    return {"recommendations": items}


@app.get("/api/miniapp/profile")
async def miniapp_profile(request: Request) -> dict:
    """Личные данные пользователя. Только по подписанному initData.

    Здесь лежат ФИО, телефон и история заявок — отдавать это по открытому
    `?user_id=` нельзя ни при каких настройках.
    """
    identity = _identity_from_request(request)
    if identity is None or not identity.verified:
        return JSONResponse(
            {"ok": False, "error": "Нужна авторизация внутри Telegram или MAX"},
            status_code=401,
        )
    conv = get_store().get(identity.user_id, platform=identity.platform)
    lead = conv.lead
    return {
        "ok": True,
        "user_id": identity.user_id,
        "platform": identity.platform,
        "display_name": identity.display_name or conv.client_name,
        "registered": bool(conv.registered),
        "stage": conv.stage,
        "lead_submitted": bool(conv.lead_submitted),
        "profile": {
            "fio_parent": lead.fio_parent,
            "fio_child": lead.fio_child,
            "phone": lead.phone,
            "age": lead.age,
            "branch": conv.selected_branch or lead.branch,
            "course": conv.selected_course or lead.course,
            "format": conv.selected_format,
        },
    }


def _verified_identity(request: Request) -> miniapp_auth.MiniAppIdentity | None:
    """Личность для личных данных кабинета: только подписанный initData.

    `user_id` из запроса здесь не передаётся даже как fallback: доверять
    ему — значит отдавать чужой кабинет любому желающему.
    """
    identity = _identity_from_request(request)
    if identity is None or not identity.verified:
        return None
    return identity


@app.get("/api/miniapp/cabinet")
async def miniapp_cabinet(request: Request) -> dict:
    """Личный кабинет: дети, прогресс, заявки, расписание из выгрузки."""
    identity = _verified_identity(request)
    if identity is None:
        return JSONResponse(
            {"ok": False, "error": "Кабинет открывается из чата с ботом"},
            status_code=401,
        )
    store = get_store()
    conv = store.get(identity.user_id, platform=identity.platform)
    payload = cabinet.build_cabinet(store, conv, identity.display_name or "")
    payload["ok"] = True
    return payload


@app.post("/api/miniapp/cabinet/child")
async def miniapp_cabinet_child(request: Request, data: dict) -> dict:
    """Создание/правка карточки ребёнка.

    Правка сразу уходит в профиль, которым пользуется бот в чате, — иначе
    человек поправил возраст в кабинете, а Фокси продолжает называть старый.
    """
    identity = _verified_identity(request)
    if identity is None:
        return JSONResponse(
            {"ok": False, "error": "Кабинет открывается из чата с ботом"},
            status_code=401,
        )
    child_id = data.get("id")
    try:
        child_id = int(child_id) if child_id is not None else None
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "error": "Некорректный id"}, status_code=400)
    store = get_store()
    # Синхронизация в диалог — только для правки существующего ребёнка или
    # самого первого: иначе добавление второго ребёнка затирало бы данные
    # первого в заявке, которой пользуется бот.
    had_children = bool(cabinet.list_children(store, identity.platform, identity.user_id))
    try:
        child = cabinet.upsert_child(
            store, identity.platform, identity.user_id, child_id, data
        )
    except LookupError:
        return JSONResponse({"ok": False, "error": "Ребёнок не найден"}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    if child_id is not None or not had_children:
        conv = store.get(identity.user_id, platform=identity.platform)
        cabinet.sync_child_into_conversation(store, conv, child)
    return {"ok": True, "child": child,
            "children": cabinet.list_children(store, identity.platform, identity.user_id)}


@app.post("/api/miniapp/lead")
async def miniapp_lead(request: Request, data: dict) -> dict:
    """Приём заявки из мини-приложения и отправка в BigBen CRM."""
    identity = _identity_from_request(
        request, fallback_user_id=_miniapp_user_id(data)
    )
    access = _miniapp_access_state(identity)
    if access["locked"]:
        return JSONResponse({"ok": False, "error": access["message"]}, status_code=403)
    client_host = request.client.host if request.client else "unknown"
    if _lead_rate_limited(client_host):
        # Форма открыта всему интернету, а каждая заявка идёт в CRM, на почту
        # и в MAX администраторам. Без ограничения один скрипт заваливает
        # школу так, что настоящую заявку в этом потоке не найти.
        logger.warning("api/lead: превышен лимит заявок с %s", client_host)
        return JSONResponse(
            {"ok": False, "error": "Слишком много заявок подряд, попробуйте позже"},
            status_code=429,
        )
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
    if not lead.phone or not (lead.fio_parent or lead.fio_child):
        return {"ok": False, "error": "Укажите телефон и имя (ваше или ребёнка)"}
    platform_label = {
        "telegram": "Telegram мини-приложение Фоксинбург",
        "max": "MAX мини-приложение Фоксинбург",
    }
    source = platform_label.get(
        identity.platform if identity else "", "Мини-приложение Фоксинбург"
    )
    ok = await get_bigben().create_lead(lead, source=source)
    if ok and identity is not None:
        # Заявка из кабинета — часть того же диалога: сохраняем, чтобы бот
        # в чате не спрашивал заново то, что человек уже заполнил.
        store = get_store()
        conv = store.get(identity.user_id, platform=identity.platform)
        conv.lead = lead
        conv.lead_submitted = True
        conv.lead_submitted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if lead.branch:
            conv.selected_branch = lead.branch
        store.save(conv)
    if ok and settings.admin_ids:
        admin_note = (
            "Новая заявка из мини-приложения\n"
            f"Родитель: {lead.fio_parent}\n"
            f"Ребёнок: {lead.fio_child or '—'}\n"
            f"Дата рождения: {lead.birthday or '—'}\n"
            f"Телефон: {lead.phone}\n"
            f"Филиал: {lead.branch or '—'}\n"
            f"Интерес: {lead.course or data.get('interest_value', '') or data.get('interest_type', '')}\n"
            f"Детали: {lead.comment or '—'}"
        )
        for admin_id in settings.admin_ids:
            await get_max().send_message(admin_id, admin_note)
    return {"ok": ok}


@app.post("/api/lead")
async def site_lead(request: Request, data: dict) -> dict:
    """Приём заявки со статического сайта dymova-english.ru (миграция с Tilda).

    Реплицирует то, что раньше делала форма Tilda через встроенные "сервисы
    приёма данных из форм": BigBen CRM + уведомление админам (тем же
    каналом, что уже получает уведомления от бота — MAX, ADMIN_MAX_IDS) +
    email-дубль на dymovgrigory@gmail.com/kidsfoxclub@yandex.ru.
    """
    client_host = request.client.host if request.client else "unknown"
    if _lead_rate_limited(client_host):
        # Форма открыта всему интернету, а каждая заявка идёт в CRM, на почту
        # и в MAX администраторам. Без ограничения один скрипт заваливает
        # школу так, что настоящую заявку в этом потоке не найти.
        logger.warning("api/lead: превышен лимит заявок с %s", client_host)
        return JSONResponse(
            {"ok": False, "error": "Слишком много заявок подряд, попробуйте позже"},
            status_code=429,
        )
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
    source = str(data.get("source") or "Сайт dymova-english.ru")[:255]
    ok = await get_bigben().create_lead(lead, source=source)
    admin_note = (
        "Новая заявка с сайта\n"
        f"Родитель: {lead.fio_parent}\n"
        f"Ребёнок: {lead.fio_child or '—'}\n"
        f"Дата рождения: {lead.birthday or '—'}\n"
        f"Телефон: {lead.phone}\n"
        f"Филиал: {lead.branch or '—'}\n"
        f"Интерес: {lead.course or '—'}\n"
        f"Детали: {lead.comment or '—'}\n"
        f"Источник: {source}"
    )
    if ok and settings.admin_ids:
        for admin_id in settings.admin_ids:
            await get_max().send_message(admin_id, admin_note)
    await asyncio.to_thread(send_lead_email, "Новая заявка с сайта Фоксинбург", admin_note)
    return {"ok": ok}


# Telegram Mini App: отдельная сборка под гайдлайны Telegram (тема клиента,
# BackButton/MainButton, haptics). Открывается кнопкой web_app в чате бота.
_TGAPP_DIR = Path(__file__).with_name("tgapp")


# Мосты площадок. Оба файла версионируются самими платформами, поэтому
# подключаются по имени, без версии и без SRI.
_BRIDGES = {
    "telegram": '<script src="https://telegram.org/js/telegram-web-app.js"></script>',
    "max": '<script src="https://st.max.ru/js/max-web-app.js"></script>',
}


def _miniapp_page(platform: str) -> HTMLResponse:
    """Одна страница мини-приложения с мостом нужной площадки.

    Оба моста в одной странице держать нельзя: telegram.org из сети MAX
    недоступен, а тег script блокирующий — приложение не открывалось, пока
    запрос не отвалится по таймауту. Разметка при этом остаётся общей:
    именно две отдельные копии привели к тому, что MAX отстал на редизайн.

    Страница собирается на каждый запрос — файл маленький, а перезапуск для
    подхвата правки дороже, чем чтение с диска.
    """
    html = (_TGAPP_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("<!--BRIDGE-->", _BRIDGES.get(platform, ""))
    # Разметку кэшировать нельзя: она уже один раз разъехалась с кодом.
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/app/", include_in_schema=False)
@app.get("/app", include_in_schema=False)
async def miniapp_index_max() -> HTMLResponse:
    """Мини-приложение для MAX. Объявлено до монтирования статики, поэтому
    админка и картинки того же каталога отдаются по-прежнему."""
    return _miniapp_page("max")


@app.get("/tg/", include_in_schema=False)
@app.get("/tg", include_in_schema=False)
async def miniapp_index_telegram() -> HTMLResponse:
    """Мини-приложение для Telegram."""
    return _miniapp_page("telegram")


# Статика мини-приложения MAX: админка и картинки (если каталог есть).
if _MINIAPP_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(_MINIAPP_DIR), html=True), name="miniapp")

if _TGAPP_DIR.exists():
    app.mount("/tg", StaticFiles(directory=str(_TGAPP_DIR), html=True), name="tgapp")

# Веб-виджет чата Фокси для статического сайта dymova-english.ru:
# страницы подключают <script src="https://bot.dymova-english.ru/widget/foxi.js">.
_WIDGET_DIR = Path(__file__).with_name("widget")
if _WIDGET_DIR.exists():
    app.mount("/widget", StaticFiles(directory=str(_WIDGET_DIR)), name="widget")


@app.post("/admin/set-webhook")
async def admin_set_webhook(request: Request, data: dict) -> dict:
    """Регистрирует webhook бота в MAX. Тело: {"url": "https://.../webhook"}.

    Ручка была полностью открытой: любой мог переподписать бота на свой URL и
    перехватывать все входящие сообщения клиентов.
    """
    if not _admin_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    url = data.get("url")
    if not url:
        return {"ok": False, "error": "url required"}
    ok = await get_max().set_webhook(url, settings.MAX_WEBHOOK_SECRET or None)
    return {"ok": ok}


# Админка: список клиентов, переписка, заявки, рассылки.
#
# CRM Admin API регистрируется ДО StaticFiles: монтирование перехватывает всё
# под /admin, что не совпало с уже объявленными маршрутами.
from app import admin_api

app.include_router(admin_api.router)

# Монтируется В САМОМ КОНЦЕ файла осознанно: StaticFiles на "/admin"
# перехватывает всё, что не совпало с уже объявленными маршрутами, поэтому
# любая ручка /admin/* должна быть зарегистрирована выше этой строки.
# Страница публична, но пустая: данные отдаются только по X-Admin-Token.
_ADMINAPP_DIR = Path(__file__).with_name("adminapp")
if _ADMINAPP_DIR.exists():
    app.mount("/admin", StaticFiles(directory=str(_ADMINAPP_DIR), html=True), name="adminapp")
