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
import re
import time
import uuid
from urllib.parse import urlsplit
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


class RevalidatingStaticFiles(StaticFiles):
    """Статика админки и мини-приложения: браузер каждый раз проверяет свежесть.

    Без Cache-Control браузер хранит app.js по эвристике (по Last-Modified),
    и правки интерфейса не видны до истечения этого срока.
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response

from app import ai_core
from app.ai_core import handle_message, handle_start
from app import broadcast
from app import cabinet
from app import consents
from app import crm_ingest
from app import crm_store
from app.bigben import get_bigben
from app.platform import analytics
from app.config import settings
from app.course_selector import recommend
from app.email_notify import send_lead_email
from app import intent as I
from app import group_chat
from app import homework
from app import identify
from app import insights
from app import leveltest
from app import nudge
from app import profile
from app import registration
from app import registration_form
from app import runtime
from app import sales
from app import scheduler
from app import speech
from app import watchdog
from app.homework import (
    HOMEWORK_IMAGE_DIR,
    HOMEWORK_INVITE,
    HOMEWORK_TEXT_FALLBACK,
    _homework_task_text,
    _homework_text_user_prompt,
    _strip_markdown,
    check_homework_image,
    explain_homework_image,
    explain_homework_text,
    save_homework_image,
)
from app.knowledge import team_sync
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
from app.max_client import (
    callback_button,
    contact_belongs_to,
    contact_button,
    get_max,
    link_button,
    phone_from_contact_attachment,
)
from app import customer_sync, miniapp_auth
from app.memory import (
    Lead,
    STAGE_HANDOFF,
    active_homework_context,
    get_store,
    remember_homework_image,
    set_active_homework_context,
)
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

# Форма заявки на статическом сайте шлёт POST с другого
# origin (dymova-english.ru / new.dymova-english.ru) — без этого браузер
# заблокирует запрос. Игровой мир живёт в отдельном процессе world-backend.
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
    # Платформа: фоновая синхронизация BigBen → read-model.
    from app.platform import automations as platform_automations
    for task in platform_automations.start():
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
    from app.platform import sync as platform_sync
    for task in platform_sync.start():
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
    telegram = get_telegram()
    miniapp_url = settings.telegram_miniapp_url
    if telegram.configured and miniapp_url.startswith("https://"):
        # Menu Button чата (слева от поля ввода) — вход в школьное
        # мини-приложение. «Мир Фоксинбурга» живёт кнопкой внутри него.
        try:
            ok = await telegram.set_menu_button("📱 Кабинет", miniapp_url)
            if ok:
                logger.info("telegram: menu button «Кабинет» установлена")
            else:
                logger.warning("telegram: setChatMenuButton не удался")
        except Exception:
            logger.exception("telegram: ошибка установки menu button")
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
    rows: list[list[dict]] = []
    # «Мир Фоксинбурга» — только внутри мини-приложения. В меню чата —
    # кабинет школы (в MAX это обычная link-кнопка, web_app там нет).
    if settings.MINIAPP_BASE_URL and _miniapp_open(user_id):
        rows.append([link_button("📱 Личный кабинет", settings.MINIAPP_BASE_URL)])
    rows.extend(
        [
            [callback_button("🎓 Подобрать курс", "menu:courses")],
            [callback_button("📅 Записаться на пробное", "menu:signup")],
            [callback_button("💳 Стоимость обучения", "menu:price")],
            [callback_button("🏫 Наши филиалы", "menu:branches")],
            [callback_button("🙋 Позвать менеджера", "menu:admin")],
        ]
    )
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
    return homework._homework_system_prompt()


def _homework_user_prompt(note: str) -> str:
    return homework._homework_user_prompt(note)


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


def _admin_base_url() -> str:
    """Публичный URL админки: MINIAPP_BASE_URL ведёт на /app/ (мини-приложение
    MAX), а админка живёт в корне хоста — берём только схему и хост. Иначе
    ссылки «Открыть заявку» вели на несуществующий /app/admin/."""
    base = settings.MINIAPP_BASE_URL.strip()
    if not base:
        return ""
    parts = urlsplit(base if "://" in base else f"https://{base}")
    if not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}/admin/"


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
    needs_consents = False
    prefill: dict = {}
    if identity is not None:
        conv = get_store().get(identity.user_id, platform=identity.platform)
        registered = bool(conv.registered)
        # Старые пользователи (анкета в переписке до этой задачи) уже
        # зарегистрированы, но согласий в журнале у них ещё нет — им нужно
        # отдельно предложить принять согласия, а не всю анкету заново.
        needs_consents = registered and not consents.has_required(
            identity.platform, identity.user_id
        )
        lead = conv.lead
        prefill = {
            "fio_parent": lead.fio_parent or identity.display_name or "",
            "fio_child": lead.fio_child,
            "child_birth": lead.birthday or lead.age,
            "phone": lead.phone,
            "phone_confirmed": bool(lead.phone_confirmed),
        }
    locked = has_identity and settings.MINIAPP_REQUIRE_REGISTRATION and not registered
    message = ""
    if locked:
        message = "Заполните короткую анкету — и всё откроется."
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
        "needs_consents": needs_consents,
        "prefill": prefill,
        "legal": {
            "version": consents.LEGAL_VERSION,
            "labels": consents.CONSENT_LABELS,
            "links": consents.CONSENT_LINKS,
        },
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
    """Эскалация администраторам: заявка в CRM + уведомление в MAX/Slack.

    Вызывается из веток «запрос администратора» вместо admin_router.hand_off,
    поэтому заявку (callback_request) создаём здесь — иначе у эскалации не
    было бы сущности, на которую админка могла бы сослаться.
    """
    # Дедупликация внутри create_callback_request не даст повторной эскалации
    # плодить заявки: открытая заявка диалога просто обновится.
    request_id = crm_ingest.ingest_handoff(conv.platform, conv.user_id, reason)
    crm_conv = None
    try:
        crm_conv = crm_store.find_conversation(conv.platform, conv.user_id)
    except Exception:
        logger.exception("crm: не удалось найти диалог для уведомления админов")
    lines = [f"🔔 Требуется администратор ({reason})", ""]
    if request_id:
        lines.append(f"Заявка: #{request_id}")
    if crm_conv:
        lines.append(f"Клиент: #{crm_conv['customer_id']}")
        lines.append(f"Диалог: #{crm_conv['id']}")
    lines.extend(["", profile.lead_summary(conv)])
    message = "\n".join(lines)
    buttons = None
    admin_base = _admin_base_url()
    if request_id and admin_base:
        buttons = [[link_button("Открыть заявку", f"{admin_base}#/requests/{request_id}")]]
    admin_client = get_max()
    for admin_id in settings.admin_ids:
        await admin_client.send_message(admin_id, message, buttons=buttons)
    await notify_slack(f"MAX handoff ({reason})\n\n{profile.lead_summary(conv)}")


async def _request_manager(user_id: str, platform: str) -> str:
    """Кнопка «Позвать менеджера»: заявка + уведомление админов + режим менеджера.

    Повторное нажатие не спамит админов: диалог уже у менеджера — клиенту
    отвечаем подтверждением без новой эскалации. Режим менеджера сам
    снимется через MANAGER_AUTO_RESUME_MIN минут тишины (см. ai_core).
    """
    crm_conv = crm_store.find_conversation(platform, user_id)
    if crm_conv and crm_conv.get("ai_mode") == "manager":
        return "Менеджер уже подключён к диалогу и скоро ответит 🙌"
    conv = get_store().get(user_id, platform=platform)
    conv.stage = STAGE_HANDOFF
    conv.handed_off = True
    get_store().save(conv)
    await _notify_admins_for_telegram(conv, "кнопка «Позвать менеджера»")
    return (
        "Передаю диалог менеджеру 🙌 Он скоро ответит вам прямо здесь. "
        "Если передумаете — просто продолжайте писать, я на связи."
    )


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
    # Переписка мини-приложения — полноценный канал CRM: раньше она шла мимо
    # хранилища, и админка не видела ни вопросов, ни ответов. Пишем входящее
    # ДО ответа: handoff внутри handle_message привяжется к диалогу.
    crm_ctx = crm_ingest.ingest_inbound(
        identity.platform, identity.user_id, text,
        external_event_id=f"miniapp:{uuid.uuid4().hex}",
        name=str(getattr(identity, "display_name", "") or ""),
        first_name=str(getattr(identity, "first_name", "") or ""),
        last_name=str(getattr(identity, "last_name", "") or ""),
        username=str(getattr(identity, "username", "") or ""),
    )
    reply = await handle_message(identity.user_id, text, platform=identity.platform)
    if reply:
        # Пустой ответ = AI на паузе/у менеджера: исходящее не пишем.
        crm_ingest.ingest_outbound(crm_ctx, reply, ai_model=settings.LLM_MODEL)
    return {"ok": True, "reply": reply}


@app.get("/api/miniapp/messages")
async def miniapp_messages(request: Request, after_id: int = 0, limit: int = 50) -> dict:
    """Новые исходящие сообщения диалога для чата мини-приложения.

    Ответ менеджера из админки уходит клиенту в нативный чат мессенджера,
    но если человек общается внутри мини-аппа, нативное сообщение он может
    не заметить. Мини-апп поллит эту ручку и показывает реплики менеджера
    (и бота) прямо в своём чате. Курсор — id последнего показанного
    сообщения, поэтому дублей нет.
    """
    identity = _identity_from_request(request)
    if identity is None:
        return JSONResponse(
            {"ok": False, "error": "Нужна авторизация внутри Telegram или MAX"},
            status_code=401,
        )
    conv = crm_store.find_conversation(identity.platform, identity.user_id)
    if conv is None:
        return {"ok": True, "messages": []}
    limit = max(1, min(int(limit), 100))
    rows = [
        m for m in crm_store.get_messages(conv["id"], limit=200)
        if m["direction"] == "out" and int(m["id"]) > int(after_id or 0)
    ][-limit:]
    return {
        "ok": True,
        "messages": [
            {
                "id": m["id"],
                "role": "manager" if m["sender_type"] == "manager" else "bot",
                "text": m["text"],
                "created_at": m["created_at"],
            }
            for m in rows
        ],
    }


@app.post("/api/miniapp/manager-call")
async def miniapp_manager_call(request: Request) -> dict:
    """Кнопка «Позвать менеджера» в чате мини-приложения.

    Та же логика, что у кнопки меню в мессенджерах: заявка админам (MAX +
    ссылка на админку), диалог переходит в режим менеджера, клиент видит
    подтверждение. Режим сам снимется через MANAGER_AUTO_RESUME_MIN минут
    тишины.
    """
    identity = _identity_from_request(request)
    if identity is None:
        return JSONResponse(
            {"ok": False, "error": "Нужна авторизация внутри Telegram или MAX"},
            status_code=401,
        )
    if _chat_rate_limited(identity.user_id):
        return JSONResponse(
            {"ok": False, "error": "Слишком много сообщений подряд, попробуйте через минуту"},
            status_code=429,
        )
    crm_ctx = crm_ingest.ingest_inbound(
        identity.platform, identity.user_id, "[кнопка: Позвать менеджера]",
        external_event_id=f"miniapp:{uuid.uuid4().hex}",
        name=str(getattr(identity, "display_name", "") or ""),
    )
    reply = await _request_manager(identity.user_id, identity.platform)
    crm_ingest.ingest_outbound(crm_ctx, reply, ai_model=settings.LLM_MODEL)
    return {"ok": True, "reply": reply}


# Больше 8 МБ фото задания быть не может, а вот OOM от «загрузки» на 2 ГБ —
# вполне: UploadFile.read() без лимита читает всё тело в память.
MAX_HOMEWORK_IMAGE_BYTES = 8 * 1024 * 1024

# Голосовое до 5 минут — примерно 20 МБ в ogg/opus с запасом.
MAX_HOMEWORK_AUDIO_BYTES = 20 * 1024 * 1024

# Стем "провер" + один из этих символов покрывает реальные формы слова
# «проверить/проверять/проверка» (проверь, проверьте, проверить, проверю,
# проверит, проверял, проверяй, проверка, проверен...), но не «провернуть» —
# там за стемом сразу идёт «н», которого в этом наборе нет.
_CHECK_STEM_RE = re.compile(r"\bпровер[ьияюек]", re.IGNORECASE)


def _looks_like_check_request(text: str) -> bool:
    """«Проверь», «проверка», «провери(ть)» — просьба проверить решение, а
    не объяснить задание заново. Не должно ловить постороннее «провернуть»."""
    return bool(_CHECK_STEM_RE.search(text or ""))


# Финальное ревью, важное #8а: homework_check_context раньше не истекал
# никогда — случайное фото без подписи спустя дни после разбора уходило в
# режим проверки решения вместо обычного разбора нового задания. Похожего
# готового TTL-параметра под эту задачу в проекте нет (MANAGER_AUTO_RESUME_MIN
# в crm_store — про другое: авто-возврат диалога боту после паузы менеджера).
# 30 минут — с запасом больше обычной паузы «получил разбор → сфотографировал
# тетрадь», но достаточно мало, чтобы не путать с фото по совсем другому
# поводу через день-два.
HOMEWORK_CHECK_CONTEXT_TTL_MIN = 30


def _homework_check_context_active(conv) -> bool:
    """Актуален ли ещё контекст «жду решение на проверку» — с учётом TTL."""
    if not conv.homework_check_context:
        return False
    at_raw = conv.homework_check_context_at
    if not at_raw:
        # Запись до этого фикса, метки времени ещё нет — не терять молча
        # уже выставленный на проде контекст, считаем актуальным один раз.
        return True
    try:
        at = datetime.fromisoformat(at_raw)
    except ValueError:
        return True
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - at <= timedelta(minutes=HOMEWORK_CHECK_CONTEXT_TTL_MIN)


def _mark_homework_check_context(conv) -> None:
    conv.homework_check_context = True
    conv.homework_check_context_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clear_homework_check_context(conv) -> None:
    conv.homework_check_context = False
    conv.homework_check_context_at = ""


def _record_text_homework_request(
    platform: str, user_id: str, crm_ctx: dict | None, task_text: str, reply: str
) -> None:
    """Заявка на ДЗ текстом — в тот же журнал homework_requests, что и у
    голосовых/фото-обработчиков (финальное ревью, важное #5: явные текстовые
    ветки «домашка»/«дз» и «жду задание после приглашения» никогда не писали
    ни в homework_requests, ни homework_check_context)."""
    if not crm_ctx:
        return
    crm_store.record_homework_request(
        platform=platform, user_id=user_id,
        customer_id=crm_ctx.get("customer_id"),
        conversation_id=crm_ctx.get("conversation_id"), channel=platform,
        mode="explain", input_type="text", task_text=task_text, reply=reply,
    )


# Финальное ревью (регресс из #8б): голосовые обработчики раньше просто
# проверяли `I.detect_intent(text) not in (None, I.QUESTION, I.HOMEWORK)` —
# это deny-list, который разворачивал в обычный чат ВСЁ, кроме явной
# домашки/вопроса. Но `detect_intent` матчит ключевые слова COURSES
# («английск», «грамматик», «уровень», «группа») РАНЬШЕ QUESTION/HOMEWORK —
# а «задание по английскому: вставь is или are» это самая обычная
# формулировка голосового задания в школе английского языка. Deny-list
# уводил такие сообщения в консультацию по курсам вместо разбора задания —
# хуже, чем вообще не фильтровать (что и было проблемой #8б). Поэтому
# список сделан ОБРАТНЫМ: allow-list тем, которые ОДНОЗНАЧНО не домашка —
# при любом сомнении (включая COURSES и GREETING) уходим в тьютора.
_VOICE_DIVERT_INTENTS = frozenset(
    {I.PRICE, I.SCHEDULE, I.WANT_SIGNUP, I.HANDOFF, I.REGISTER, I.OBJECTION}
)
# CONTACTS/ABOUT разворачиваем в чат, только если в тексте вообще нет
# похожего на задание содержимого — «а как к вам добраться» не должно
# уйти в тьютора, а «отметь is или are, кстати как к вам добраться» — с
# заданием внутри — всё равно должно разбираться.
_VOICE_DIVERT_IF_NO_TASK_INTENTS = frozenset({I.CONTACTS, I.ABOUT})


def _voice_diverts_to_chat(text: str) -> bool:
    """Голосовое явно НЕ про домашку — тогда обычный чат, а не тьютор."""
    intent = I.detect_intent(text)
    if intent in _VOICE_DIVERT_INTENTS:
        return True
    if intent in _VOICE_DIVERT_IF_NO_TASK_INTENTS:
        return not homework._homework_task_text(text)
    return False


def _load_prior_homework_images(conv) -> list[tuple[bytes, str]]:
    """Байты последних фото активного задания (пути — см.
    memory.remember_homework_image) — чтобы «вот ещё страница» ушла в
    vision вместе с уже показанными фото того же задания, а не как
    отдельный вопрос с нуля. Файл мог не сохраниться или потеряться —
    тогда просто пропускаем его, а не роняем текущий запрос."""
    images: list[tuple[bytes, str]] = []
    for rel_path in conv.active_homework_image_paths:
        full_path = Path(HOMEWORK_IMAGE_DIR).parent / rel_path
        try:
            images.append((full_path.read_bytes(), "image/jpeg"))
        except OSError:
            continue
    return images


@app.post("/api/miniapp/homework")
async def api_homework(
    request: Request,
    note: str = Form(default=""),
    user_id: str = Form(default=""),
    init_data: str = Form(default=""),
    image: UploadFile | None = File(default=None),
) -> dict:
    identity = _identity_from_request(request, init_data=init_data, fallback_user_id=user_id)
    # См. тот же комментарий в api_homework_check/api_homework_voice: без
    # явной проверки анонимный вызов доходил до платного vision и до
    # сохранения файла на диск ещё до какой-либо идентификации (финальное
    # ревью, важное #7 — эта, самая старая из трёх ручек ДЗ мини-приложения,
    # осталась незакрытой в первом проходе фикса).
    if identity is None:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
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

    # Если ученик уже обсуждает задание, новое фото может быть его
    # продолжением (следующая страница/пункт) — подсказываем это модели
    # текстом И прикладываем предыдущие фото ЭТОГО задания (например,
    # вопросы на одной странице и опорный текст на другой), а не заставляем
    # модель считать каждое фото отдельным вопросом с нуля.
    conv = get_store().get(identity.user_id, platform=identity.platform)
    active_ctx = active_homework_context(conv)
    note_with_hint = homework.with_continuation_hint(*(active_ctx or ("", "")), note)
    prior_images = _load_prior_homework_images(conv) if active_ctx is not None else []
    explanation = await homework.explain_homework_image(
        image_bytes, content_type, note_with_hint, prior_images=prior_images
    )
    if not explanation:
        explanation = (
            "Не удалось разобрать фото задания. Попробуйте снять его при "
            "хорошем свете — или опишите текстом, что нужно сделать."
        )

    # Заявка должна попадать в CRM и в отдельный журнал ДЗ так же, как это
    # уже делают /homework/check и /homework/voice — иначе самый частый путь
    # («разбери задание» по фото) не виден ни в переписке, ни в админке.
    if identity is not None:
        image_path = homework.save_homework_image(image_bytes, ext="jpg")
        crm_ctx = crm_ingest.ingest_inbound(
            identity.platform, identity.user_id, f"[фото задания] {note}".strip(),
            external_event_id=f"miniapp-hw-explain:{uuid.uuid4().hex}",
            payload={"image_path": image_path},
        )
        crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL)
        crm_store.record_homework_request(
            platform=identity.platform, user_id=identity.user_id,
            customer_id=crm_ctx.get("customer_id") if crm_ctx else None,
            conversation_id=crm_ctx.get("conversation_id") if crm_ctx else None,
            channel=identity.platform, mode="explain", input_type="image",
            image_path=image_path, task_text=note, reply=explanation,
        )
        # Чтобы «Разбери задание» → следом обычный текстовый вопрос в чате
        # продолжал разговор об ЭТОМ задании, а не терялся в консультации.
        set_active_homework_context(conv, note, explanation)
        remember_homework_image(conv, image_path)
        get_store().save(conv)

    return {
        "ok": True,
        "explanation": explanation,
        "buttons": _contextual_buttons("домашка", explanation),
    }


@app.get("/api/miniapp/chat/history")
async def miniapp_chat_history(request: Request, limit: int = 50) -> dict:
    """История диалога для чата мини-приложения: подгружается при открытии,
    в отличие от поллинга новых исходящих (см. /api/miniapp/messages)."""
    identity = _identity_from_request(request)
    if identity is None:
        return JSONResponse(
            {"ok": False, "error": "Нужна авторизация внутри Telegram или MAX"},
            status_code=401,
        )
    conv = crm_store.find_conversation(identity.platform, identity.user_id)
    if conv is None:
        return {"ok": True, "messages": []}
    limit = max(1, min(int(limit), 100))
    rows = crm_store.get_messages(conv["id"], limit=limit)
    messages = []
    for m in rows:
        image_url = None
        try:
            payload = json.loads(m.get("payload_json") or "{}")
            if payload.get("image_path"):
                image_url = f"/api/miniapp/homework/image/{payload['image_path'].split('/', 1)[1]}"
        except Exception:
            pass
        role = "me" if m["direction"] == "in" else ("manager" if m["sender_type"] == "manager" else "bot")
        messages.append({
            "id": m["id"], "role": role, "text": m["text"],
            "image_url": image_url, "created_at": m["created_at"],
        })
    return {"ok": True, "messages": messages}


@app.get("/api/miniapp/homework/image/{filename}")
async def miniapp_homework_image(request: Request, filename: str) -> FileResponse:
    """Миниатюры фото задания в истории чата. Только по подписанному
    initData — на фото могут быть личные данные ребёнка.

    Подписанной личности мало: она доказывает, что это какой-то
    зарегистрированный человек, а не то, что фото — его. Без проверки
    владения (по заявке в homework_requests) один ученик мог бы открыть
    фото домашки чужого ребёнка, зная только имя файла."""
    identity = _identity_from_request(request)
    if identity is None:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    safe_name = Path(filename).name  # без произвольных путей вроде "../.."
    owner = crm_store.find_homework_request_by_image(f"homework/{safe_name}")
    # "Не найдено" и "чужое" отвечаем одинаково: подтверждать существование
    # файла человеку, которому он не принадлежит, не нужно.
    if owner is None or owner.get("platform") != identity.platform or owner.get("user_id") != identity.user_id:
        return JSONResponse({"detail": "not found"}, status_code=404)
    path = Path(HOMEWORK_IMAGE_DIR) / safe_name
    if not path.exists():
        return JSONResponse({"detail": "not found"}, status_code=404)
    return FileResponse(str(path))


@app.post("/api/miniapp/homework/check")
async def api_homework_check(
    request: Request,
    note: str = Form(default=""),
    init_data: str = Form(default=""),
    image: UploadFile | None = File(default=None),
) -> dict:
    identity = _identity_from_request(request, init_data=init_data)
    # _miniapp_access_state гейтит "locked" только для УЖЕ распознанной
    # личности (has_identity=True) — анонимный вызов (identity=None) её
    # условие вообще не задевает и проходит дальше. Без этой явной проверки
    # анонимный запрос доходил до сохранения файла на диск и до платного
    # vision-вызова ДО какой-либо идентификации (финальное ревью, важное #7).
    if identity is None:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    access = _miniapp_access_state(identity)
    if access["locked"]:
        return JSONResponse({"ok": False, "error": access["message"]}, status_code=403)
    if image is None or not image.filename:
        return JSONResponse({"detail": "Нужна фотография решения"}, status_code=400)
    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        return JSONResponse({"detail": "Файл должен быть в формате изображения"}, status_code=400)
    image_bytes = await image.read(MAX_HOMEWORK_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_HOMEWORK_IMAGE_BYTES:
        return JSONResponse({"detail": "Фото слишком большое — пришлите снимок до 8 МБ"}, status_code=413)
    if not image_bytes:
        return JSONResponse({"detail": "Пустой файл"}, status_code=400)
    active_ctx = active_homework_context(get_store().get(identity.user_id, platform=identity.platform))
    note_with_hint = homework.with_continuation_hint(*(active_ctx or ("", "")), note)
    explanation = await homework.check_homework_image(image_bytes, content_type, note_with_hint)
    if not explanation:
        explanation = "Не удалось разобрать фото. Попробуйте снять его при хорошем свете."
    image_path = homework.save_homework_image(image_bytes, ext="jpg")
    crm_ctx = None
    if identity is not None:
        crm_ctx = crm_ingest.ingest_inbound(
            identity.platform, identity.user_id, f"[фото решения] {note}".strip(),
            external_event_id=f"miniapp-hw-check:{uuid.uuid4().hex}",
            payload={"image_path": image_path},
        )
        crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL)
        crm_store.record_homework_request(
            platform=identity.platform, user_id=identity.user_id,
            customer_id=crm_ctx.get("customer_id") if crm_ctx else None,
            conversation_id=crm_ctx.get("conversation_id") if crm_ctx else None,
            channel=identity.platform, mode="check", input_type="image",
            image_path=image_path, task_text=note, reply=explanation,
        )
        conv = get_store().get(identity.user_id, platform=identity.platform)
        set_active_homework_context(conv, note, explanation)
        get_store().save(conv)
    return {"ok": True, "explanation": explanation}


@app.post("/api/miniapp/homework/voice")
async def api_homework_voice(
    request: Request,
    mode: str = Form(default="explain"),
    init_data: str = Form(default=""),
    audio: UploadFile | None = File(default=None),
) -> dict:
    identity = _identity_from_request(request, init_data=init_data)
    # См. тот же комментарий в api_homework_check: без явной проверки
    # анонимный вызов доходил до платного STT и до explain_homework_text ещё
    # до какой-либо идентификации (финальное ревью, важное #7).
    if identity is None:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    access = _miniapp_access_state(identity)
    if access["locked"]:
        return JSONResponse({"ok": False, "error": access["message"]}, status_code=403)
    if audio is None or not audio.filename:
        return JSONResponse({"detail": "Нужна голосовая запись"}, status_code=400)
    audio_bytes = await audio.read(MAX_HOMEWORK_AUDIO_BYTES + 1)
    if len(audio_bytes) > MAX_HOMEWORK_AUDIO_BYTES:
        return JSONResponse({"detail": "Запись слишком большая — до 20 МБ"}, status_code=413)
    if not audio_bytes:
        return JSONResponse({"detail": "Пустая запись"}, status_code=400)
    text = await speech.transcribe(audio_bytes, audio.filename or "voice.webm",
                                   (audio.content_type or "audio/webm"))
    if not text:
        return {"ok": False, "error": "Не расслышала запись. Попробуйте ещё раз или напишите текстом."}
    explanation = await homework.explain_homework_text(text)
    if not explanation:
        explanation = HOMEWORK_TEXT_FALLBACK
    crm_ctx = None
    if identity is not None:
        crm_ctx = crm_ingest.ingest_inbound(
            identity.platform, identity.user_id, f"[голосовое] {text}",
            external_event_id=f"miniapp-hw-voice:{uuid.uuid4().hex}",
        )
        crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL)
        crm_store.record_homework_request(
            platform=identity.platform, user_id=identity.user_id,
            customer_id=crm_ctx.get("customer_id") if crm_ctx else None,
            conversation_id=crm_ctx.get("conversation_id") if crm_ctx else None,
            channel=identity.platform, mode="explain", input_type="voice",
            audio_transcript=text, task_text=text, reply=explanation,
        )
        conv = get_store().get(identity.user_id, platform=identity.platform)
        set_active_homework_context(conv, text, explanation)
        get_store().save(conv)
    return {"ok": True, "transcript": text, "explanation": explanation}


def _register_button_rows(platform: str) -> list[list[dict]]:
    """Кнопка анкеты. В Telegram — web_app: только так мини-приложение
    получает подписанный initData и может принять форму."""
    if platform == TELEGRAM_PLATFORM:
        url = settings.telegram_miniapp_url
        if not url.startswith("https://"):
            return []
        return [[{"type": "web_app", "text": registration.FORM_INVITE_MARK,
                  "web_app": f"{url.split('#', 1)[0]}#register"}]]
    base = _miniapp_url()
    return [[link_button(registration.FORM_INVITE_MARK, f"{base}/#register")]] if base else []


def _telegram_buttons(text: str, reply: str) -> list[list[dict]]:
    if registration.FORM_INVITE_MARK in (reply or ""):
        return _register_button_rows(TELEGRAM_PLATFORM)
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
    # «Мир Фоксинбурга» открывается баннером внутри мини-приложения, а не
    # отдельной кнопкой чата — иначе Menu Button / клавиатура вытесняют кабинет.
    webapp = _telegram_webapp_button(user_id)
    if webapp:
        rows.append([webapp])
    rows.extend(
        [
            [callback_button("🎓 Подобрать курс", "menu:courses")],
            [callback_button("📅 Записаться на пробное", "menu:signup")],
            [callback_button("💳 Стоимость обучения", "menu:price")],
            [callback_button("🏫 Наши филиалы", "menu:branches")],
            [callback_button("🙋 Позвать менеджера", "menu:admin")],
        ]
    )
    return rows


def _telegram_start_buttons(text: str, reply: str, user_id: str = "") -> list[list[dict]] | None:
    """На /start показываем меню целиком — иначе новый пользователь видит
    только текст и не знает, что у бота вообще есть кнопки."""
    if registration.FORM_INVITE_MARK in (reply or ""):
        return _register_button_rows(TELEGRAM_PLATFORM)
    return _telegram_menu_buttons(user_id) or _telegram_buttons(text, reply) or None


def _start_buttons(user_id: str, platform: str) -> list[list[dict]]:
    """Стартовое меню. Если включена идентификация и номер ещё не известен,
    первой строкой идёт «📞 Поделиться номером» (в MAX это callback —
    нативного request_contact у MAX Bot API нет, номер просим текстом)."""
    menu = _main_menu(user_id)
    if identify.needs_gate(get_store().get(user_id, platform=platform)):
        return [[callback_button(identify.SHARE_BUTTON_TEXT, identify.SHARE_BUTTON_PAYLOAD)]] + menu
    conv = get_store().get(user_id, platform=platform)
    if not registration.is_registered(conv) and registration.uses_form(platform):
        rows = _register_button_rows(platform)
        if platform != TELEGRAM_PLATFORM and not conv.lead.phone:
            # В MAX номер можно отдать одним нажатием (у Telegram своя
            # клавиатура запроса контакта).
            rows = [[contact_button(identify.SHARE_BUTTON_TEXT)]] + rows
        return rows
    return menu


async def _maybe_send_tg_contact_request(telegram, chat_id, user_id: str) -> None:
    """Reply-клавиатура «Поделиться номером», если диалог ещё под гейтом."""
    conv = get_store().get(user_id, platform=TELEGRAM_PLATFORM)
    wants_phone = (
        not conv.lead.phone
        and not registration.is_registered(conv)
        and registration.uses_form(TELEGRAM_PLATFORM)
    )
    if not (identify.needs_gate(conv) or wants_phone):
        return
    try:
        await telegram.send_contact_request(
            chat_id, "Нажмите кнопку ниже 👇", button_text=identify.SHARE_BUTTON_TEXT
        )
    except Exception:
        logger.exception("telegram: не удалось отправить кнопку запроса контакта")


def _link_button_rows(text: str, reply: str) -> list[list[dict]]:
    if registration.FORM_INVITE_MARK in (reply or ""):
        return _register_button_rows(PLATFORM)
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
    if payload == "menu:admin":
        # Кнопка «Позвать менеджера»: заявка админам + режим менеджера.
        crm_ctx = crm_ingest.ingest_inbound(
            TELEGRAM_PLATFORM, user_id, "[кнопка: menu:admin]",
            external_event_id=str(update.get("update_id") or "") or None,
        )
        reply = await _request_manager(user_id, TELEGRAM_PLATFORM)
        await _send_tg_logged(telegram, chat_id, reply, crm_ctx,
                              buttons=_telegram_menu_buttons(user_id) or None)
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
            # «Проверь» в подписи — явная просьба проверить решение. Пустая
            # подпись сразу после разбора задания (homework_check_context) —
            # тоже решение, которое прислали в ответ, а не новое задание.
            # Пустая подпись без такого контекста — обычное фото задания.
            # Но стем-совпадение не должно перебивать подпись, у которой
            # намерение уже ЯВНО распознано как другая тема (цена, контакты
            # и т.п.) — иначе «Проверьте, сколько стоит абонемент?» вместо
            # ответа про цену улетает в vision-проверку фото.
            conv_for_photo = get_store().get(f"tg:{chat_id}", platform=TELEGRAM_PLATFORM)
            caption_is_clearly_other = caption_intent not in (None, I.QUESTION, I.HOMEWORK)
            wants_check = not caption_is_clearly_other and (
                _looks_like_check_request(caption)
                or (not caption and _homework_check_context_active(conv_for_photo))
            )
            if caption_intent in (I.QUESTION, I.HOMEWORK) or wants_check:
                await _handle_telegram_photo(
                    message, chat_id, telegram, check_mode=wants_check, update=update
                )
                return

        if message.get("voice") or message.get("audio"):
            await _handle_telegram_voice(message, chat_id, telegram, update)
            return

        # Контакт (кнопка «Поделиться номером») — не медиа и не текст:
        # обрабатываем до ветки «голосовые и файлы», иначе он в неё провалится.
        contact = message.get("contact")
        if isinstance(contact, dict) and contact.get("phone_number"):
            user_id = f"tg:{chat_id}"
            crm_ctx = _telegram_inbound_ctx(update, message, user_id, "[контакт]")
            conv = get_store().get(user_id, platform=TELEGRAM_PLATFORM)
            conv.add("user", "[поделился номером телефона]")
            # Подтверждённым считаем только СОБСТВЕННЫЙ контакт отправителя
            # (contact.user_id == from.id) — чужую визитку из адресной книги
            # Telegram прислать тоже можно, но она номер не удостоверяет.
            from_id = (message.get("from") or {}).get("id")
            confirmed = contact.get("user_id") is not None and contact.get("user_id") == from_id
            reply = identify.handle_contact(conv, str(contact["phone_number"]), confirmed=confirmed)
            try:
                customer_sync.sync_conversation(conv)
            except Exception:
                logger.exception("customer_sync: сбой после контакта Telegram user=%s", user_id)
            if not identify.needs_gate(conv) and not registration.is_registered(conv):
                # Шаринг контакта может прийти, пока человек ещё заполняет
                # анкету в мини-приложении (Telegram шлёт requestContact
                # независимо от формы) — не подсовываем старый опрос
                # вопрос-за-вопросом там, где анкета уже есть в виде формы.
                if registration.uses_form(TELEGRAM_PLATFORM):
                    reply = f"{reply}\n\n{registration.FORM_INVITE}"
                else:
                    reply = f"{reply}\n\n{registration.start_registration(conv)}"
            conv.add("assistant", reply)
            get_store().save(conv)
            await _send_tg_logged(telegram, chat_id, reply, crm_ctx,
                                  buttons=_telegram_buttons("", reply) or None)
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
            await _maybe_send_tg_contact_request(telegram, chat_id, user_id)
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

        # Продолжение уже активного задания — ПЕРЕД классификацией «новое
        # задание» по словам «домаш»/«дз» ниже: иначе сообщение вроде «а в
        # этом дз точно они?» про уже обсуждаемое задание запускало разбор
        # с нуля вместо продолжения (владелец, 2026-09-29, прод-лог
        # tg:749445545: «бот не понял что мы обсуждаем задание которое я
        # уже прислал а не новое задание»). intent тем же безопасным
        # подмножеством, что и ниже — явную смену темы не перехватываем.
        if I.detect_intent(text) in (None, "", I.QUESTION, I.HOMEWORK):
            conv = get_store().get(user_id, platform=TELEGRAM_PLATFORM)
            followup_reply = await ai_core.try_continue_active_homework(conv, text)
            if followup_reply is not None:
                get_store().save(conv)
                await _send_tg_logged(telegram, chat_id, followup_reply, crm_ctx)
                return

        if "домаш" in low or "дз" in low:
            conv = get_store().get(user_id, platform=TELEGRAM_PLATFORM)
            task_text = _homework_task_text(text)
            if task_text:
                conv.awaiting_homework = False
                get_store().save(conv)
                reply = await _reply_while_alive(
                    telegram, chat_id, lambda: explain_homework_text(task_text)
                ) or HOMEWORK_TEXT_FALLBACK
                # Финальное ревью, важное #5: текстовая домашка никогда не
                # попадала ни в homework_requests, ни в контекст ожидания
                # проверки — тот же учёт, что уже есть у голоса/фото.
                _record_text_homework_request(TELEGRAM_PLATFORM, user_id, crm_ctx, task_text, reply)
                _mark_homework_check_context(conv)
                set_active_homework_context(conv, task_text, reply)
                get_store().save(conv)
            else:
                conv.awaiting_homework = True
                get_store().save(conv)
                reply = HOMEWORK_INVITE
            await _send_tg_logged(telegram, chat_id, reply, crm_ctx, buttons=_telegram_buttons(text, reply) or None)
            return

        # После приглашения «пришлите задание» следующий текст — это и есть
        # задание, даже без слов «домашка»: сразу разбираем в режиме тьютора.
        conv = get_store().get(user_id, platform=TELEGRAM_PLATFORM)
        if conv.awaiting_homework and I.detect_intent(text) in (None, I.QUESTION, I.HOMEWORK):
            conv.awaiting_homework = False
            get_store().save(conv)
            reply = await _reply_while_alive(
                telegram, chat_id, lambda: explain_homework_text(text)
            ) or HOMEWORK_TEXT_FALLBACK
            _record_text_homework_request(TELEGRAM_PLATFORM, user_id, crm_ctx, text, reply)
            _mark_homework_check_context(conv)
            set_active_homework_context(conv, text, reply)
            get_store().save(conv)
            await _send_tg_logged(telegram, chat_id, reply, crm_ctx, buttons=_telegram_buttons(text, reply) or None)
            return

        reply = await _reply_while_alive(
            telegram,
            chat_id,
            lambda: handle_message(user_id, text, platform=TELEGRAM_PLATFORM),
        )
        await _send_tg_logged(telegram, chat_id, reply, crm_ctx, buttons=_telegram_buttons(text, reply) or None)
        # Если идентификация ещё не пройдена, рядом с ответом-просьбой должна
        # быть и сама кнопка — иначе клиенту нечем поделиться номером.
        await _maybe_send_tg_contact_request(telegram, chat_id, user_id)
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


async def _handle_telegram_voice(message: dict, chat_id, telegram, update: dict | None = None) -> None:
    """Голосовое/аудио: скачиваем, распознаём и либо разбираем тем же
    тьютором, что и текст (если это похоже на домашку), либо отвечаем
    обычным чатом (финальное ревью, важное #8б — раньше ЛЮБОЕ голосовое
    безусловно улетало в разбор задания, даже «когда пробное занятие»)."""
    media = message.get("voice") or message.get("audio") or {}
    file_id = media.get("file_id")
    if not file_id:
        return
    mime_type = str(media.get("mime_type") or "audio/ogg")
    user_id = f"tg:{chat_id}"
    voice_message_id = str(message.get("message_id") or "") or None
    # message_id уникален только ВНУТРИ одного чата Telegram — как ключ
    # дедупликации (UNIQUE(channel, external_event_id) в inbound_events) он
    # сталкивал голосовые разных пользователей с одинаковым (маленьким,
    # последовательным) message_id: второй вызов ingest_inbound тихо считался
    # дублем, и CRM/homework_requests теряли запись (финальное ревью, важное
    # #6). update_id уникален глобально — тот же приём уже используют
    # текстовые обработчики этого файла (см. _telegram_inbound_ctx).
    update_id = str((update or {}).get("update_id") or "") or None
    sender = message.get("from") or {}
    crm_ctx = crm_ingest.ingest_inbound(
        TELEGRAM_PLATFORM, user_id, "[голосовое]",
        external_event_id=update_id,
        external_message_id=voice_message_id,
        first_name=str(sender.get("first_name") or ""),
        last_name=str(sender.get("last_name") or ""),
        username=str(sender.get("username") or ""),
    )
    download = getattr(telegram, "download_file", None)
    if not callable(download):
        # Клиент без скачивания файлов — не повод отвечать пользователю ошибкой.
        await telegram.send_message(
            chat_id, "Пока не могу скачать голосовое здесь. Напишите, пожалуйста, текстом."
        )
        return
    audio = await download(file_id, MAX_HOMEWORK_AUDIO_BYTES)
    if not audio:
        await telegram.send_message(
            chat_id, "Не получилось скачать голосовое. Попробуйте ещё раз или напишите текстом."
        )
        return
    text = await _reply_while_alive(
        telegram, chat_id, lambda: speech.transcribe(audio, "voice.ogg", mime_type)
    )
    if not text:
        await telegram.send_message(
            chat_id,
            "Не расслышала голосовое 🙏 Попробуйте ещё раз при тишине — или "
            "напишите задание текстом.",
        )
        return
    await telegram.send_message(chat_id, f"Услышал: «{text}»")

    # Голосовое явно НЕ про домашку (см. _voice_diverts_to_chat) — уходит в
    # обычный чат, а не в разбор задания. При любом сомнении (в том числе
    # COURSES/GREETING) остаёмся в тьюторе — deny-list здесь уводил обычные
    # формулировки задания («по английскому», «грамматика») в консультацию
    # по курсам (финальное ревью, регресс из #8б).
    if _voice_diverts_to_chat(text):
        reply = await _reply_while_alive(
            telegram, chat_id, lambda: handle_message(user_id, text, platform=TELEGRAM_PLATFORM)
        )
        # _send_tg_logged (а не голый send_message) — пустой reply (AI на
        # паузе/у менеджера) не должен уйти пустым сообщением в Telegram API
        # и пустой записью в CRM (финальное ревью, Minor #2).
        await _send_tg_logged(telegram, chat_id, reply, crm_ctx)
        return

    explanation = await _reply_while_alive(
        telegram, chat_id, lambda: homework.explain_homework_text(text)
    )
    explanation = explanation or HOMEWORK_TEXT_FALLBACK
    ok = await telegram.send_message(chat_id, explanation)
    crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL, ok=bool(ok))
    if crm_ctx:
        crm_store.record_homework_request(
            platform=TELEGRAM_PLATFORM, user_id=user_id,
            customer_id=crm_ctx.get("customer_id"),
            conversation_id=crm_ctx.get("conversation_id"), channel=TELEGRAM_PLATFORM,
            mode="explain", input_type="voice", audio_transcript=text,
            task_text=text, reply=explanation,
        )
    conv = get_store().get(user_id, platform=TELEGRAM_PLATFORM)
    _mark_homework_check_context(conv)
    set_active_homework_context(conv, text, explanation)
    get_store().save(conv)


async def _handle_telegram_photo(
    message: dict, chat_id, telegram, check_mode: bool = False, update: dict | None = None
) -> None:
    """Фото задания из чата: разбор или проверка решения — тем же vision,
    что и в кабинете."""
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
    photo_message_id = str(message.get("message_id") or "") or None
    # Тот же баг, что и у голосовых (финальное ревью, важное #6): message_id
    # уникален только внутри одного чата, а не глобально — как ключ дедупа
    # (external_event_id) он сталкивал фото разных пользователей и тихо
    # ронял вторую запись. update_id — глобально уникален.
    update_id = str((update or {}).get("update_id") or "") or None
    sender = message.get("from") or {}
    user_id = f"tg:{chat_id}"
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

    image_path = save_homework_image(image, ext="jpg")
    # Фото — тоже сообщение клиента: пишем в CRM, чтобы в админке было видно,
    # что человек прислал задание (раньше такие обращения терялись). Путь к
    # сохранённому файлу летит в payload — педагог из карточки CRM открывает
    # тот же снимок, что видела модель.
    crm_ctx = crm_ingest.ingest_inbound(
        TELEGRAM_PLATFORM, user_id, f"[фото] {note}".strip(),
        external_event_id=update_id,
        external_message_id=photo_message_id,
        first_name=str(sender.get("first_name") or ""),
        last_name=str(sender.get("last_name") or ""),
        username=str(sender.get("username") or ""),
        payload={"image_path": image_path},
    )

    conv_for_photo = get_store().get(user_id, platform=TELEGRAM_PLATFORM)
    active_ctx = active_homework_context(conv_for_photo)
    note_with_hint = homework.with_continuation_hint(*(active_ctx or ("", "")), note)
    if check_mode:
        explanation = await _reply_while_alive(
            telegram, chat_id, lambda: check_homework_image(image, "image/jpeg", note_with_hint)
        )
        mode = "check"
    else:
        # Дозасылка страниц того же задания (вопросы на одной, опорный
        # текст на другой) — предыдущие фото уходят в vision вместе с этим.
        prior_images = _load_prior_homework_images(conv_for_photo) if active_ctx is not None else []
        explanation = await _reply_while_alive(
            telegram,
            chat_id,
            lambda: explain_homework_image(image, "image/jpeg", note_with_hint, prior_images=prior_images),
        )
        mode = "explain"

    if not explanation:
        hint = (
            "Не смог разобрать фото решения. Пришлите, пожалуйста, более "
            "чёткий снимок — так смогу проверить."
            if check_mode else
            "Не смог разобрать задание по фото. Напишите, пожалуйста, текстом, "
            "что именно нужно сделать — помогу разобраться."
        )
        await telegram.send_message(chat_id, hint)
        return
    ok = await telegram.send_message(chat_id, explanation)
    crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL, ok=bool(ok))
    if crm_ctx:
        crm_store.record_homework_request(
            platform=TELEGRAM_PLATFORM, user_id=user_id,
            customer_id=crm_ctx.get("customer_id"),
            conversation_id=crm_ctx.get("conversation_id"), channel=TELEGRAM_PLATFORM,
            mode=mode, input_type="image", image_path=image_path,
            task_text=note, reply=explanation,
        )
    # После разбора — следующее фото без подписи считаем решением ученика
    # (см. wants_check в _process_telegram_update); после проверки — это уже
    # не действует, иначе повторная проверка того же фото зациклится.
    conv = get_store().get(user_id, platform=TELEGRAM_PLATFORM)
    if check_mode:
        _clear_homework_check_context(conv)
    else:
        _mark_homework_check_context(conv)
    set_active_homework_context(conv, note, explanation)
    if not check_mode:
        remember_homework_image(conv, image_path)
    get_store().save(conv)


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


@app.get("/admin/learning_log")
async def admin_learning_log(request: Request, limit: int = 50) -> dict:
    """Журнал автоприменений ночного анализатора (approach-1, р. 5.2)."""
    if not _admin_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return {"rows": crm_store.learning_log_list(limit=limit)}


@app.post("/admin/learning_log/{entry_id}/rollback")
async def admin_learning_log_rollback(entry_id: int, request: Request) -> dict:
    """Откат применённого улучшения: возврат версии промпта «до» и пометка записи."""
    if not _admin_authorized(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    entry = crm_store.learning_log_get(entry_id)
    if entry is None:
        return JSONResponse({"detail": "not found"}, status_code=404)
    if entry["status"] != "active":
        return JSONResponse({"detail": "already rolled back"}, status_code=400)
    version_before = int(entry["prompt_version_before"])
    if version_before:
        target = next(
            (row for row in crm_store.prompt_list() if int(row["version"]) == version_before),
            None,
        )
        if target is None:
            return JSONResponse(
                {"detail": f"prompt version {version_before} not found"}, status_code=404)
        crm_store.prompt_activate(int(target["id"]), actor="admin_rollback")
        sales.reset_prompt_cache()
    crm_store.learning_log_mark_rolled_back(entry_id)
    # Откат — тоже изменение: фиксируем его отдельной записью в том же журнале.
    crm_store.learning_log_add(
        prompt_version_before=int(entry["prompt_version_after"]),
        prompt_version_after=version_before,
        changes={"rollback_of": entry_id},
        insights_analyzed=0,
        status="active",
    )
    return {"ok": True, "restored_version": version_before}


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
        # Рост счётчика = основной LLM-провайдер нестабилен (approach-1, р. 7).
        "fallback_switches": llm.fallback_switches,
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
            await _send_max_logged(max_client, user_id, reply, crm_ctx, buttons=_start_buttons(user_id, PLATFORM))
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
        body = message.get("body") or {}
        text = body.get("text", "").strip()
        # Голосовое/аудио — не текст: у него своя ветка распознавания до
        # общего "нет текста — нечего обрабатывать".
        attachments = body.get("attachments") or []
        audio_att = next(
            (a for a in attachments if isinstance(a, dict) and a.get("type") == "audio"), None
        )
        if not text and audio_att:
            url = (audio_att.get("payload") or {}).get("url", "")
            if url:
                await _handle_max_voice(url, user_id, message, update, max_client)
            else:
                # Вложение есть, а ссылки на файл нет — платформа прислала
                # что-то нестандартное. Как и в других сбоях этой ветки,
                # отвечаем человеку, а не молчим.
                await max_client.send_message(
                    user_id, "Не получилось открыть голосовое. Напишите, пожалуйста, текстом."
                )
            return
        contact_phone = phone_from_contact_attachment(attachments)
        if not text and not contact_phone and any(
            isinstance(a, dict) and a.get("type") == "contact" for a in attachments
        ):
            # Формат вложения в документации MAX скупой: если номер не
            # разобрался, в логе останутся ключи, чтобы поправить парсер.
            logger.warning("MAX: контакт без номера, payload=%s", [
                sorted((a.get("payload") or {}).keys()) for a in attachments if isinstance(a, dict)
            ])
        if not text and contact_phone:
            await _handle_max_contact(
                user_id, contact_phone, contact_belongs_to(attachments, user_id),
                sender, message, update, max_client,
            )
            return
        if should_route_max_photo(text, attachments):
            # Чистое фото без подписи — раньше сообщение молча отбрасывалось,
            # и домашка с фото до CRM и педагога не доходила.
            await _handle_max_photo(max_image_url(attachments), user_id, "", message, update, max_client)
            return
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
        # Продолжение уже активного задания — ПЕРЕД веткой «новое задание»
        # ниже (`elif ... == I.HOMEWORK`): та не смотрела на активный
        # контекст вообще, и сообщение вроде «а в этом дз точно они?» про
        # уже обсуждаемое задание запускало разбор с нуля вместо
        # продолжения (владелец, 2026-09-29: «бот не понял что мы
        # обсуждаем задание которое я уже прислал а не новое задание»).
        # intent тем же безопасным подмножеством, что и ветки ниже — явную
        # смену темы (/start, HANDOFF и т.п.) не перехватываем.
        if low not in ("/start", "start") and I.detect_intent(text) in (
            None, "", I.QUESTION, I.HOMEWORK,
        ):
            conv = get_store().get(user_id)
            followup_reply = await ai_core.try_continue_active_homework(conv, text)
            if followup_reply is not None:
                get_store().save(conv)
                await _send_max_logged(
                    max_client, user_id, followup_reply, crm_ctx,
                    buttons=_link_button_rows(text, followup_reply) or None,
                )
                return
        if low in ("/start", "start"):
            reply = await handle_start(user_id)
            await _send_max_logged(max_client, user_id, reply, crm_ctx, buttons=_start_buttons(user_id, PLATFORM))
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
            conv = get_store().get(user_id)
            task_text = _homework_task_text(text)
            if task_text:
                conv.awaiting_homework = False
                get_store().save(conv)
                reply = await _reply_while_alive(
                    max_client, user_id, lambda: explain_homework_text(task_text)
                ) or HOMEWORK_TEXT_FALLBACK
                # Финальное ревью, важное #5: та же дыра, что и у Telegram —
                # текстовая домашка в MAX не попадала ни в homework_requests,
                # ни в контекст ожидания проверки.
                _record_text_homework_request(PLATFORM, user_id, crm_ctx, task_text, reply)
                _mark_homework_check_context(conv)
                set_active_homework_context(conv, task_text, reply)
                get_store().save(conv)
            else:
                conv.awaiting_homework = True
                get_store().save(conv)
                reply = HOMEWORK_INVITE
            buttons = _link_button_rows(text, reply)
            await _send_max_logged(max_client, user_id, reply, crm_ctx, buttons=buttons or None)
        elif get_store().get(user_id).awaiting_homework and I.detect_intent(text) in (None, I.QUESTION):
            # Ждали задание после приглашения — пришёл текст без триггеров.
            conv = get_store().get(user_id)
            conv.awaiting_homework = False
            get_store().save(conv)
            reply = await _reply_while_alive(
                max_client, user_id, lambda: explain_homework_text(text)
            ) or HOMEWORK_TEXT_FALLBACK
            _record_text_homework_request(PLATFORM, user_id, crm_ctx, text, reply)
            _mark_homework_check_context(conv)
            set_active_homework_context(conv, text, reply)
            get_store().save(conv)
            await _send_max_logged(max_client, user_id, reply, crm_ctx, buttons=_link_button_rows(text, reply) or None)
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
        # Нажатие кнопки — тоже сообщение клиента: пишем в CRM, чтобы
        # ответы бота ниже логировались в тот же диалог (а не шли мимо).
        crm_ctx = None
        if user_id:
            crm_ctx = crm_ingest.ingest_inbound(
                PLATFORM, user_id, f"[кнопка: {payload}]",
                external_event_id=str(callback_id or _extract_update_id(update) or "") or None,
            )
        if user_id and payload in _BRANCH_CONTACTS:
            conv = get_store().get(user_id)
            info = _BRANCH_CONTACTS[payload]
            conv.selected_branch = info["name"]
            conv.stage = STAGE_HANDOFF
            await _notify_admins_for_telegram(conv, "контакт по филиалу")
            await _send_max_logged(
                max_client,
                user_id,
                f"Свяжу вас с администратором {info['name']}.",
                crm_ctx,
                buttons=[[link_button(info["name"], info["url"])]],
            )
        elif user_id and str(payload).startswith("contact:"):
            await _send_max_logged(
                max_client,
                user_id,
                "Подскажите, пожалуйста, какой филиал вам удобнее?",
                crm_ctx,
                buttons=_branch_admin_buttons(),
            )
        elif user_id and payload == "menu:admin":
            # Кнопка «Позвать менеджера»: заявка админам + режим менеджера,
            # а не имитация текстового вопроса через _CALLBACK_TEXT.
            reply = await _request_manager(user_id, PLATFORM)
            await _send_max_logged(max_client, user_id, reply, crm_ctx, buttons=_main_menu(user_id))
        elif user_id and payload == identify.SHARE_BUTTON_PAYLOAD:
            # Кнопка request_contact в MAX есть (см. _start_buttons); этот путь —
            # для старых сообщений с callback-кнопкой: просим номер текстом.
            conv = get_store().get(user_id)
            conv.identify_state = identify.STATE_AWAIT_CONTACT
            get_store().save(conv)
            await _send_max_logged(max_client, user_id, identify.ASK_PHONE_TEXT_MAX, crm_ctx)
        elif user_id and payload in _CALLBACK_TEXT:
            text = _CALLBACK_TEXT[payload]
            reply = await handle_message(user_id, text)
            if reply:  # пустой ответ — AI на паузе/у менеджера, молчим
                await _send_max_logged(max_client, user_id, reply, crm_ctx,
                                       buttons=_link_button_rows(text, reply) or None)
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


CONTACT_SAVED_TEXT = "Спасибо, номер сохранила ✅"


async def _handle_max_contact(
    user_id: str, phone: str, own: bool, sender: dict, message: dict, update: dict, max_client,
) -> None:
    """Клиент отдал номер кнопкой «Поделиться номером» (или переслал визитку).

    Номер уходит в диалог и в карточку клиента; подтверждённым он считается
    только когда контакт принадлежит самому отправителю.
    """
    _remember_sender(user_id, sender)
    crm_ctx = crm_ingest.ingest_inbound(
        PLATFORM, user_id, "[поделился номером телефона]",
        external_event_id=_extract_update_id(update),
        external_message_id=_max_message_external_id(message),
        name=str(sender.get("name") or ""),
        phone=phone,
    )
    conv = get_store().get(user_id)
    conv.add("user", "[поделился номером телефона]")
    conv.lead.set_phone(phone, confirmed=own)
    reply = CONTACT_SAVED_TEXT
    buttons = None
    if not registration.is_registered(conv) and registration.uses_form(PLATFORM):
        reply = f"{CONTACT_SAVED_TEXT}\n\n{registration.FORM_INVITE}"
        buttons = _register_button_rows(PLATFORM)
    conv.add("assistant", reply)
    get_store().save(conv)
    try:
        customer_sync.sync_conversation(conv)
    except Exception:
        logger.exception("customer_sync: сбой после контакта user=%s", user_id)
    await _send_max_logged(max_client, user_id, reply, crm_ctx, buttons=buttons)


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


async def _handle_max_voice(url: str, user_id: str, message: dict, update: dict, max_client) -> None:
    """Голосовое вложение MAX с заданием: скачиваем по прямой ссылке из
    payload.url, распознаём, разбираем тем же тьютором, что и текст."""
    sender = message.get("sender") or {}
    crm_ctx = crm_ingest.ingest_inbound(
        PLATFORM, user_id, "[голосовое]",
        external_event_id=_extract_update_id(update),
        external_message_id=_max_message_external_id(message),
        name=str(sender.get("name") or ""),
        username=str(sender.get("username") or ""),
    )
    download = getattr(max_client, "download_file", None)
    if not callable(download):
        await max_client.send_message(user_id, "Пока не могу скачать голосовое здесь. Напишите текстом.")
        return
    audio = await download(url, MAX_HOMEWORK_AUDIO_BYTES)
    if not audio:
        await max_client.send_message(
            user_id, "Не получилось скачать голосовое. Попробуйте ещё раз или напишите текстом."
        )
        return
    text = await _reply_while_alive(
        max_client, user_id, lambda: speech.transcribe(audio, "voice.ogg", "audio/ogg")
    )
    if not text:
        await max_client.send_message(
            user_id, "Не расслышала голосовое 🙏 Попробуйте ещё раз или напишите задание текстом."
        )
        return
    await max_client.send_message(user_id, f"Услышал: «{text}»")

    # Голосовое явно НЕ про домашку (см. _voice_diverts_to_chat) — уходит в
    # обычный чат, а не в разбор задания. При любом сомнении (в том числе
    # COURSES/GREETING) остаёмся в тьюторе — deny-list здесь уводил обычные
    # формулировки задания («по английскому», «грамматика») в консультацию
    # по курсам (финальное ревью, регресс из #8б).
    if _voice_diverts_to_chat(text):
        reply = await _reply_while_alive(
            max_client, user_id, lambda: handle_message(user_id, text, platform=PLATFORM)
        )
        # _send_max_logged (а не голый send_message) — пустой reply (AI на
        # паузе/у менеджера) не должен уйти пустым сообщением и пустой
        # записью в CRM (финальное ревью, Minor #2).
        await _send_max_logged(max_client, user_id, reply, crm_ctx)
        return

    explanation = await _reply_while_alive(
        max_client, user_id, lambda: homework.explain_homework_text(text)
    )
    explanation = explanation or HOMEWORK_TEXT_FALLBACK
    ok = await max_client.send_message(user_id, explanation)
    crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL, ok=bool(ok))
    if crm_ctx:
        crm_store.record_homework_request(
            platform=PLATFORM, user_id=user_id,
            customer_id=crm_ctx.get("customer_id"),
            conversation_id=crm_ctx.get("conversation_id"), channel=PLATFORM,
            mode="explain", input_type="voice", audio_transcript=text,
            task_text=text, reply=explanation,
        )
    conv = get_store().get(user_id, platform=PLATFORM)
    _mark_homework_check_context(conv)
    set_active_homework_context(conv, text, explanation)
    get_store().save(conv)


def max_image_url(attachments: list) -> str | None:
    """Прямая ссылка на первое фото-вложение MAX (type == image) или None."""
    for att in attachments or []:
        if isinstance(att, dict) and att.get("type") == "image":
            url = (att.get("payload") or {}).get("url", "")
            if url:
                return str(url)
    return None


def should_route_max_photo(text: str, attachments: list) -> bool:
    """Чистое фото без текста — в разбор домашки. Сообщение с текстом (даже с
    картинкой-превью или скриншотом) идёт обычным диалогом: иначе вопрос клиента
    уходил бы в разбор задания вместо ответа."""
    return not (text or "").strip() and max_image_url(attachments) is not None


async def _handle_max_photo(
    url: str, user_id: str, caption: str, message: dict, update: dict, max_client
) -> None:
    """Фото от клиента MAX: сохраняем в CRM и разбираем как задание (разбор или
    проверка — по подписи), тем же vision, что и фото в Telegram."""
    sender = message.get("sender") or {}
    download = getattr(max_client, "download_file", None)
    if not callable(download):
        await max_client.send_message(user_id, "Вижу фото 📸 Опишите, пожалуйста, текстом, что за задание.")
        return
    image = await download(url, MAX_HOMEWORK_IMAGE_BYTES)
    if not image:
        await max_client.send_message(
            user_id,
            "Не получилось открыть это фото. Пришлите, пожалуйста, снимок поменьше — или опишите задание текстом.",
        )
        return

    image_path = save_homework_image(image, ext="jpg")
    # Фото — тоже сообщение клиента: в CRM попадает путь к файлу, и педагог в
    # админке видит тот же снимок, что получила модель.
    crm_ctx = crm_ingest.ingest_inbound(
        PLATFORM, user_id, f"[фото] {caption}".strip(),
        external_event_id=_extract_update_id(update),
        external_message_id=_max_message_external_id(message),
        name=str(sender.get("name") or ""),
        username=str(sender.get("username") or ""),
        payload={"image_path": image_path},
    )

    check_mode = _looks_like_check_request(caption)
    conv_for_photo = get_store().get(user_id, platform=PLATFORM)
    active_ctx = active_homework_context(conv_for_photo)
    note_with_hint = homework.with_continuation_hint(*(active_ctx or ("", "")), caption)
    if check_mode:
        explanation = await _reply_while_alive(
            max_client, user_id, lambda: check_homework_image(image, "image/jpeg", note_with_hint)
        )
        mode = "check"
    else:
        prior_images = _load_prior_homework_images(conv_for_photo) if active_ctx is not None else []
        explanation = await _reply_while_alive(
            max_client,
            user_id,
            lambda: explain_homework_image(image, "image/jpeg", note_with_hint, prior_images=prior_images),
        )
        mode = "explain"

    if not explanation:
        hint = (
            "Не смог разобрать фото решения. Пришлите, пожалуйста, более чёткий снимок — так смогу проверить."
            if check_mode else
            "Не смог разобрать задание по фото. Напишите, пожалуйста, текстом, что именно нужно сделать."
        )
        await max_client.send_message(user_id, hint)
        return
    ok = await max_client.send_message(user_id, explanation)
    crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL, ok=bool(ok))
    if crm_ctx:
        crm_store.record_homework_request(
            platform=PLATFORM, user_id=user_id,
            customer_id=crm_ctx.get("customer_id"),
            conversation_id=crm_ctx.get("conversation_id"), channel=PLATFORM,
            mode=mode, input_type="image", image_path=image_path,
            task_text=caption, reply=explanation,
        )
    conv = get_store().get(user_id, platform=PLATFORM)
    if check_mode:
        _clear_homework_check_context(conv)
    else:
        _mark_homework_check_context(conv)
    set_active_homework_context(conv, caption, explanation)
    get_store().save(conv)


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


@app.post("/api/miniapp/event")
async def miniapp_event(request: Request) -> dict:
    """Действие клиента в мини-приложении: открыт раздел или нажата кнопка.

    Пишем только для личности, подтверждённой подписью initData (user_id из
    тела запроса не доверяем). Имена событий — из белого списка аналитики.
    """
    try:
        body = await request.json()
    except ValueError:
        return {"ok": False}
    if not isinstance(body, dict):
        return {"ok": False}
    identity = _identity_from_request(request)
    if identity is None or not identity.verified:
        return {"ok": False}
    event = str(body.get("event") or "")
    if event not in analytics.MINIAPP_EVENTS:
        return {"ok": False}
    action = str(body.get("action") or "")[:120]
    if analytics.is_technical_action_label(action):
        return {"ok": False}
    meta = {
        "section": str(body.get("section") or "")[:64],
        "action": action,
    }
    ok = analytics.track(event, source=identity.platform, anon_id=identity.user_id, meta=meta)
    return {"ok": bool(ok)}


@app.get("/api/miniapp/info")
async def miniapp_info(request: Request, user_id: str = "") -> dict:
    """Витрина: публичные данные школы + состояние доступа.

    Каталог, форматы и филиалы — публичная информация с сайта, она отдаётся
    и без авторизации, чтобы мини-приложение открывалось мгновенно.
    """
    kb = get_kb()
    identity = _identity_from_request(request, fallback_user_id=user_id)
    access = _miniapp_access_state(identity)
    if identity is not None and identity.verified:
        analytics.track("miniapp_opened", source=identity.platform, anon_id=identity.user_id)
        # Открытие мини-приложения — сигнал прочтения: ответы бота, отправленные
        # до этого момента, получают две галочки в админке (MAX не присылает
        # событие прочтения). Сбой отметки не должен ломать витрину.
        try:
            crm_store.mark_outgoing_read(
                identity.platform, identity.user_id,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        except Exception:
            logger.exception("miniapp: не удалось отметить прочтение ответов")
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
        "team": team_sync.get_team(),
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
    request_id = None
    if ok:
        # Заявка из мини-приложения — сущность CRM (карточка «Заявки» в
        # админке), а не только письмо админам: иначе её не отследить.
        request_id = crm_ingest.ingest_lead_request(
            channel=identity.platform if identity else "web",
            external_user_id=identity.user_id if identity else "",
            lead={
                "fio_parent": lead.fio_parent, "fio_child": lead.fio_child,
                "phone": lead.phone, "birthday": lead.birthday,
                "course": lead.course, "branch": lead.branch,
                "comment": lead.comment,
            },
            source=source,
        )
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
        if request_id:
            admin_note += f"\nЗаявка: #{request_id}"
            if _admin_base_url():
                admin_note += f"\n{_admin_base_url()}#/requests/{request_id}"
        for admin_id in settings.admin_ids:
            await get_max().send_message(admin_id, admin_note)
    return {"ok": ok}


REGISTERED_CHAT_TEXT = (
    "Спасибо! Анкета заполнена ✅ Всё открыто 🦊\n\n"
    "Спрашивайте про курсы, расписание и цены, присылайте домашку — помогу."
)


async def _notify_registered_in_chat(identity: miniapp_auth.MiniAppIdentity, text: str) -> None:
    """Подтверждение в нативный чат мессенджера: человек вернётся в чат и
    должен видеть, что анкета дошла, а не гадать, нажалась ли кнопка."""
    try:
        if identity.platform == TELEGRAM_PLATFORM:
            chat_id = identity.user_id.removeprefix("tg:")
            await get_telegram().send_message(
                chat_id, text, buttons=_telegram_menu_buttons(identity.user_id) or None
            )
        else:
            await get_max().send_message(identity.user_id, text, buttons=_main_menu(identity.user_id))
    except Exception:
        logger.exception("miniapp: не удалось отправить подтверждение анкеты в чат")


def _verified_identity_or_401(request: Request):
    """Общая проверка для ручек анкеты: без подписанной личности форму
    принимать нельзя — иначе кто угодно допишет чужому диалогу «регистрацию»."""
    identity = _identity_from_request(request)
    if identity is None or not identity.verified:
        return None, JSONResponse(
            {"ok": False, "error": "Откройте анкету внутри Telegram или MAX"}, status_code=401
        )
    return identity, None


@app.post("/api/miniapp/register")
async def miniapp_register(request: Request, data: dict) -> dict:
    """Анкета мини-приложения вместо четырёх вопросов в переписке."""
    identity, error = _verified_identity_or_401(request)
    if error:
        return error
    store = get_store()
    conv = store.get(identity.user_id, platform=identity.platform)
    if conv.registered and consents.has_required(identity.platform, identity.user_id):
        # Повторная отправка той же формы (двойной тап, ретрай сети) не
        # должна плодить второй лид в BigBen и второе «Анкета заполнена» в
        # чат — человек уже зарегистрирован и согласия уже в журнале.
        return {"ok": True, "access": _miniapp_access_state(identity)}
    form, errors = registration_form.validate(data if isinstance(data, dict) else {})
    if errors:
        analytics.track(
            "form_rejected", source=identity.platform, anon_id=identity.user_id,
            meta={"fields": sorted(errors)},
        )
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)
    analytics.track("form_submitted", source=identity.platform, anon_id=identity.user_id)
    # Журнал согласий пишем первым: если он упадёт, conv ещё не помечен
    # зарегистрированным и человек может просто повторить отправку. Если бы
    # порядок был обратным, ошибка после store.save оставляла бы диалог
    # «зарегистрированным» без единой строки согласия в журнале.
    consents.record(identity.platform, identity.user_id, form.consents, channel="miniapp")
    registration_form.apply(conv, form)
    conv.add("assistant", "[анкета мини-приложения заполнена]")
    store.save(conv)
    try:
        # upsert_customer_for_identity дописывает только пустые поля — это
        # осознанно: анкета не должна затирать то, что менеджер уже поправил
        # в CRM. Сбой здесь — не повод терять лид в BigBen или подтверждение
        # в чат, поэтому гасим исключение и продолжаем.
        crm_store.upsert_customer_for_identity(
            identity.platform, identity.user_id,
            name=form.fio_parent, phone=conv.lead.phone,
            child_name=form.fio_child, child_age=form.age or form.birthday,
            source="анкета мини-приложения",
        )
    except Exception:
        logger.exception("miniapp: не удалось обновить карточку клиента в CRM")
    platform_name = "Telegram" if identity.platform == TELEGRAM_PLATFORM else "MAX"
    try:
        customer_sync.sync_conversation(conv)
    except Exception:
        logger.exception("customer_sync: сбой после анкеты user=%s", identity.user_id)
    await registration._submit_registration(
        conv, get_bigben(),
        source=f"{platform_name} мини-приложение — анкета",
        extra_note=consents.summary_line(identity.platform, identity.user_id),
    )
    await _notify_registered_in_chat(identity, REGISTERED_CHAT_TEXT)
    return {"ok": True, "access": _miniapp_access_state(identity)}


@app.post("/api/miniapp/consents")
async def miniapp_consents(request: Request, data: dict) -> dict:
    """Только согласия — для клиентов, прошедших старую анкету в чате."""
    identity, error = _verified_identity_or_401(request)
    if error:
        return error
    accepted = consents.parse_accepted(data.get("consents"))
    if not all(accepted[kind] for kind in consents.REQUIRED):
        return JSONResponse({"ok": False, "errors": {"consents": "Нужны обязательные согласия"}}, status_code=400)
    consents.record(identity.platform, identity.user_id, accepted, channel="miniapp")
    return {"ok": True}


@app.post("/api/lead")
async def site_lead(request: Request, data: dict) -> dict:
    """Приём заявки со статического сайта dymova-english.ru.

    Реплицирует то, что раньше делала форма конструктора сайта через
    встроенные "сервисы приёма данных из форм": BigBen CRM + уведомление админам (тем же
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
    request_id = None
    if ok:
        # Заявка с сайта — сущность CRM: склеиваем с клиентом по телефону,
        # чтобы админ видел заявку в карточке, а не только письмо в почте.
        request_id = crm_ingest.ingest_lead_request(
            channel="web",
            lead={
                "fio_parent": lead.fio_parent, "fio_child": lead.fio_child,
                "phone": lead.phone, "birthday": lead.birthday,
                "course": lead.course, "branch": lead.branch,
                "comment": lead.comment,
            },
            source=source,
        )
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
    if request_id:
        admin_note += f"\nЗаявка: #{request_id}"
        if _admin_base_url():
            admin_note += f"\n{_admin_base_url()}#/requests/{request_id}"
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
    app.mount("/app", RevalidatingStaticFiles(directory=str(_MINIAPP_DIR), html=True), name="miniapp")

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
from app import world_bridge
from app.platform import account_api as platform_account_api
from app.platform import billing_api as platform_billing_api
from app.platform import podpislon_webhooks as platform_podpislon_webhooks
from app.platform import public_api as platform_public_api
from app.platform import webhooks as platform_webhooks

app.include_router(admin_api.router)
app.include_router(platform_webhooks.router)
app.include_router(platform_podpislon_webhooks.router)
app.include_router(platform_account_api.router)
app.include_router(platform_billing_api.router)
app.include_router(platform_public_api.router)
app.include_router(world_bridge.router)

# Монтируется В САМОМ КОНЦЕ файла осознанно: StaticFiles на "/admin"
# перехватывает всё, что не совпало с уже объявленными маршрутами, поэтому
# любая ручка /admin/* должна быть зарегистрирована выше этой строки.
# Страница публична, но пустая: данные отдаются только по X-Admin-Token.
_ADMINAPP_DIR = Path(__file__).with_name("adminapp")
if _ADMINAPP_DIR.exists():
    app.mount("/admin", RevalidatingStaticFiles(directory=str(_ADMINAPP_DIR), html=True), name="adminapp")
