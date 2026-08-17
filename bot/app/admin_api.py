"""CRM Admin API: inbox, Customer 360, ответы менеджера, AI-режим, статистика,
Broadcast Center (сегменты, история, статусы), воронка и CSV-экспорт.

Все ручки — под /admin/api/* и требуют заголовок X-Admin-Token (та же
проверка, что и у старых /admin/users). Старые ручки не трогаем: они нужны
для обратной совместимости вкладок «Рассылка» и «Вопросы».

Роутер подключается в main.py ПЕРЕД монтированием статики /admin —
иначе StaticFiles перехватит запросы.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app import crm_store
from app.config import settings
from app.max_client import get_max
from app.telegram_client import get_telegram

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api")

_AI_MODES = ("active", "paused", "manager")

# Фоновые задачи рассылок: держим ссылки, чтобы GC не собрал task до конца.
_background_tasks: set[asyncio.Task] = set()

_STARTED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")


# Матрица прав RBAC. super_admin — всё ("*"). Старый статический ADMIN_TOKEN
# работает как super_admin (обратная совместимость).
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "super_admin": {"*"},
    # admin — всё, кроме управления пользователями и AI-промптов.
    "admin": {"inbox", "customers", "pipeline", "reply", "ai_mode", "stats",
              "health", "broadcasts", "segments", "analytics", "export",
              "kb", "errors", "system", "requests"},
    # manager — операционная работа: диалоги, клиенты, воронка, ответы, пауза AI.
    "manager": {"inbox", "customers", "pipeline", "reply", "ai_mode", "stats",
                "health", "requests"},
    # marketing — рассылки, сегменты, аналитика, экспорт; отвечать может.
    "marketing": {"broadcasts", "segments", "analytics", "export", "inbox",
                  "customers", "reply", "stats", "health"},
    # support — минимум: диалоги, клиенты, ответы, сводка, заявки.
    "support": {"inbox", "customers", "reply", "stats", "health", "requests"},
}

# Rate-limit логина: 5 попыток в минуту по IP (защита от перебора пароля).
_login_hits: dict[str, list[float]] = {}
_LOGIN_LIMIT = 5
_LOGIN_WINDOW_SEC = 60.0


def _login_limited(ip: str) -> bool:
    import time as _time

    now = _time.monotonic()
    hits = [t for t in _login_hits.get(ip, []) if now - t < _LOGIN_WINDOW_SEC]
    if len(hits) >= _LOGIN_LIMIT:
        _login_hits[ip] = hits
        return True
    hits.append(now)
    _login_hits[ip] = hits
    return False


def _authorize(request: Request, permission: str) -> str:
    """Проверяет токен и право. Возвращает actor (username) для audit_log.

    Порядок: статический ADMIN_TOKEN (super_admin, обратная совместимость),
    затем сессия admin_sessions по токену. 401 — нет валидного токена,
    403 — роль без права.
    """
    token = request.headers.get("X-Admin-Token", "")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if settings.ADMIN_TOKEN and hmac.compare_digest(token, settings.ADMIN_TOKEN):
        return "super_admin"
    session = crm_store.session_get(token)
    if session is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    perms = ROLE_PERMISSIONS.get(session["role"], set())
    if "*" not in perms and permission not in perms:
        raise HTTPException(status_code=403, detail="forbidden")
    return session["username"]


def _conversation_or_404(conversation_id: int) -> dict:
    conv = crm_store.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return conv


def _customer_or_404(customer_id: int) -> dict:
    customer = crm_store.get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return customer


# --------- Inbox ---------


@router.get("/inbox")
async def inbox(request: Request, channel: str = "", ai_mode: str = "",
                unread: bool = False, lead_status: str = "", date_from: str = "",
                date_to: str = "", search: str = "", q: str = "",
                limit: int = 50, offset: int = 0, cursor: str = "") -> dict:
    actor = _authorize(request, "inbox")
    result = crm_store.list_conversations(
        channel=channel or None,
        unread=unread or None,
        ai_mode=ai_mode or None,
        lead_status=lead_status or None,
        date_from=date_from or None,
        date_to=date_to or None,
        search=search or None,
        q=q or None,
        limit=limit,
        offset=offset,
        cursor=cursor or None,
    )
    # Теги клиента — для бейджей в списке диалогов.
    for item in result["items"]:
        customer = crm_store.get_customer(item["customer_id"])
        item["tags"] = customer["tags"] if customer else []
    return result


@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(request: Request, conversation_id: int,
                                before_id: int = 0, limit: int = 50) -> dict:
    actor = _authorize(request, "inbox")
    _conversation_or_404(conversation_id)
    items = crm_store.get_messages(conversation_id, before_id=before_id or None, limit=limit)
    return {"items": items, "has_more": len(items) >= limit}


@router.post("/conversations/{conversation_id}/read")
async def conversation_read(request: Request, conversation_id: int) -> dict:
    actor = _authorize(request, "inbox")
    _conversation_or_404(conversation_id)
    crm_store.mark_conversation_read(conversation_id)
    return {"ok": True}


async def _send_to_channel(channel: str, external_id: str, text: str) -> tuple[bool, str | None, str | None]:
    """Отправка в канал диалога с фактом доставки: (ok, external_message_id,
    описание ошибки из API канала).

    Клиент без send_message_ext (старый адаптер, тестовый фейк) деградирует
    до bool-семантики send_message — вызовы не ломаются.
    """
    try:
        if channel == "max":
            client = get_max()
            chat_id = external_id
        elif channel == "telegram":
            client = get_telegram()
            chat_id = external_id.removeprefix("tg:")
        else:
            return False, None, f"канал {channel} не поддерживает отправку"
        send_ext = getattr(client, "send_message_ext", None)
        if callable(send_ext):
            return await send_ext(chat_id, text)
        ok = bool(await client.send_message(chat_id, text))
        return ok, None, None if ok else "send failed"
    except Exception as exc:
        logger.exception("admin reply: ошибка отправки в %s", channel)
        return False, None, str(exc)[:300]


@router.post("/conversations/{conversation_id}/reply")
async def conversation_reply(request: Request, conversation_id: int, data: dict) -> dict:
    """Ответ менеджера клиенту в канал диалога.

    MAX и Telegram уходят через клиентов мессенджеров; у веб-виджета push
    нет — сообщение ждёт поллинга (status pending). Ответ менеджера переводит
    диалог в ai_mode=manager: бот не перебивает живой разговор.

    client_message_id — ключ идемпотентности из админки: повторный клик
    «отправить» (или ретрай сети) возвращает уже записанное сообщение,
    не отправляя дубль клиенту.
    """
    actor = _authorize(request, "reply")
    conv = _conversation_or_404(conversation_id)
    text = str(data.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    client_message_id = str(data.get("client_message_id") or "").strip()[:64] or None
    if client_message_id:
        existing = crm_store.find_message_by_client_id(client_message_id)
        if existing is not None:
            return {"ok": existing["status"] != "failed", "message_id": existing["id"],
                    "status": existing["status"], "error": existing["error"],
                    "duplicate": True}
    channel = conv["channel"]
    external_id = conv["external_user_id"]
    ok, error = True, None
    external_message_id = None
    status = "sent"
    # Пометка «не бот»: в мессенджерах сообщение менеджера идёт от имени
    # бота, поэтому клиенту явно подписываем, кто пишет — с именем менеджера.
    # В БД храним тот же текст, что ушёл клиенту, — история админки
    # совпадает с его чатом.
    wire_text = text if channel == "web" else f"👤 {actor} (менеджер):\n{text}"
    if channel == "web":
        # Доставка при следующем поллинге виджета (/api/chat/pending).
        status = "pending"
    else:
        ok, external_message_id, error = await _send_to_channel(channel, external_id, wire_text)
    if not ok:
        status = "failed"
        error = error or "send failed"
    message_id, _ = crm_store.add_message(
        conversation_id, conv["customer_id"], channel, "out", "manager", wire_text,
        status=status, error=error,
        external_message_id=external_message_id,
        client_message_id=client_message_id,
        sender_name=actor,
    )
    # Диалог помечаем ведущим: во «Входящих» и в шапке чата видно, кто
    # именно общается с клиентом (у диалогов нескольких менеджеров).
    crm_store.set_conversation_manager(conversation_id, actor, actor=actor)
    if conv["ai_mode"] != "paused":
        # Ответ менеджера держит режим менеджера ещё MANAGER_AUTO_RESUME_MIN
        # минут после этого сообщения, затем бот вернётся сам.
        crm_store.set_ai_mode(conversation_id, "manager",
                              paused_until=crm_store.auto_resume_until(), actor=actor)
    crm_store.audit(actor, "reply", "crm_conversation", conversation_id,
                    after={"status": status, "channel": channel})
    return {"ok": ok, "message_id": message_id, "status": status, "error": error}


@router.post("/conversations/{conversation_id}/ai")
async def conversation_ai_mode(request: Request, conversation_id: int, data: dict) -> dict:
    """AI-режим диалога: active | paused (paused_until ISO или null — до
    ручного включения) | manager."""
    actor = _authorize(request, "ai_mode")
    _conversation_or_404(conversation_id)
    mode = str(data.get("mode", ""))
    if mode not in _AI_MODES:
        raise HTTPException(status_code=400, detail=f"mode must be one of {_AI_MODES}")
    paused_until = data.get("paused_until") or None
    if mode != "paused":
        paused_until = None
    if mode == "manager" and paused_until is None:
        # Режим менеджера всегда с авто-возвратом: не должен зависать навсегда.
        paused_until = crm_store.auto_resume_until()
    crm_store.set_ai_mode(conversation_id, mode, paused_until=paused_until, actor=actor)
    return {"ok": True, "ai_mode": mode, "ai_paused_until": paused_until}


def _human_send_reason(error: str) -> str | None:
    """Причина недоставки человеческим языком — что менеджеру делать дальше."""
    low = (error or "").lower()
    if "403" in low or "blocked" in low or "deactivated" in low:
        return ("Пользователь заблокировал бота — напишите ему с рабочего "
                "телефона или в другом канале")
    if "chat not found" in low:
        return ("Бот не может инициировать диалог с этим пользователем; "
                "используйте телефон/email")
    return None


@router.get("/conversations/{conversation_id}/availability")
async def conversation_availability(request: Request, conversation_id: int) -> dict:
    """Честная проверка канала перед ответом: куда реально можно написать.

    У веб-виджета push нет — ответ уйдёт поллингом. У мессенджеров смотрим
    последнее исходящее: если оно failed с «blocked»/«chat not found»,
    кнопка отправки в админке должна быть честно выключена.
    """
    actor = _authorize(request, "inbox")
    conv = _conversation_or_404(conversation_id)
    channel = conv["channel"]
    can_send = True
    reason = ""
    if channel == "web":
        reason = ("Ответ будет доставлен при следующем поллинге виджета "
                  "(push у веб-чата нет)")
    else:
        last_out = crm_store.get_conn().execute(
            "SELECT status, error FROM crm_messages"
            " WHERE conversation_id = ? AND direction = 'out' ORDER BY id DESC LIMIT 1",
            (conversation_id,),
        ).fetchone()
        if last_out is not None and last_out["status"] == "failed":
            reason = _human_send_reason(last_out["error"] or "")
            if reason is None:
                reason = f"Последнее сообщение не доставлено: {last_out['error'] or 'ошибка отправки'}"
            can_send = False
    contacts: dict = {"phone": "", "email": "", "telegram_username": "",
                      "max_user_id": "", "website": ""}
    customer = crm_store.get_customer(conv["customer_id"])
    if customer:
        contacts["phone"] = customer.get("phone") or ""
        contacts["email"] = customer.get("email") or ""
        for identity in customer.get("identities") or []:
            if identity["channel"] == "telegram":
                contacts["telegram_username"] = customer.get("username") or ""
            if identity["channel"] == "max":
                contacts["max_user_id"] = identity["external_id"]
            if identity["channel"] == "web":
                contacts["website"] = identity["external_id"]
    return {"channel": channel, "can_send": can_send, "reason": reason,
            "contacts": contacts}


@router.post("/messages/{message_id}/retry")
async def message_retry(request: Request, message_id: int) -> dict:
    """Повторная отправка недоставленного исходящего сообщения.

    Только direction=out AND status=failed: ретраить доставленное — значит
    слать клиенту дубль."""
    actor = _authorize(request, "reply")
    message = crm_store.get_message(message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="message not found")
    if message["direction"] != "out" or message["status"] != "failed":
        raise HTTPException(status_code=400, detail="retry allowed only for failed outbound messages")
    conv = _conversation_or_404(int(message["conversation_id"]))
    ok, external_message_id, error = await _send_to_channel(
        conv["channel"], conv["external_user_id"], message["text"])
    status = "sent" if ok else "failed"
    crm_store.update_message_delivery(
        message_id, status,
        error=None if ok else (error or "send failed"),
        external_message_id=external_message_id,
    )
    crm_store.audit(actor, "retry", "crm_message", message_id,
                    before={"status": "failed", "error": message["error"]},
                    after={"status": status, "error": error})
    return {"ok": ok, "status": status, "error": None if ok else (error or "send failed")}


# --------- Заявки (callback_requests) ---------


@router.get("/requests")
async def requests_list(request: Request, status: str = "", kind: str = "",
                        limit: int = 50, offset: int = 0) -> dict:
    actor = _authorize(request, "requests")
    return {
        "items": crm_store.list_callback_requests(
            status=status or None, kind=kind or None, limit=limit, offset=offset),
        "counts": crm_store.requests_counts(),
    }


@router.get("/requests/{request_id}")
async def request_detail(request: Request, request_id: int) -> dict:
    """Карточка заявки: клиент, диалог и свежие сообщения для контекста."""
    actor = _authorize(request, "requests")
    item = crm_store.get_callback_request(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="request not found")
    customer = crm_store.get_customer(item["customer_id"]) if item["customer_id"] else None
    conversation = None
    recent_messages: list[dict] = []
    if item["conversation_id"]:
        conversation = crm_store.get_conversation(item["conversation_id"])
        recent_messages = crm_store.get_messages(item["conversation_id"], limit=30)
    return {"request": item, "customer": customer,
            "conversation": conversation, "recent_messages": recent_messages}


@router.post("/requests/{request_id}/status")
async def request_set_status(request: Request, request_id: int, data: dict) -> dict:
    actor = _authorize(request, "requests")
    status = str(data.get("status", ""))
    if status not in crm_store.REQUEST_STATUSES:
        raise HTTPException(status_code=400,
                            detail=f"status must be one of {crm_store.REQUEST_STATUSES}")
    if not crm_store.update_callback_request(request_id, {"status": status}, actor=actor):
        raise HTTPException(status_code=404, detail="request not found")
    return {"ok": True, "request": crm_store.get_callback_request(request_id)}


@router.post("/requests/{request_id}/assign")
async def request_assign(request: Request, request_id: int, data: dict) -> dict:
    """Назначение менеджера. Новая заявка при этом уходит в работу:
    «взял в работу» и «назначен ответственный» — одно действие."""
    actor = _authorize(request, "requests")
    item = crm_store.get_callback_request(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="request not found")
    fields = {"manager": str(data.get("manager", "")).strip()}
    if item["status"] == "new":
        fields["status"] = "in_progress"
    crm_store.update_callback_request(request_id, fields, actor=actor)
    # Заявка и диалог — одна работа: назначенный на заявку менеджер виден
    # и как ведущий диалога с клиентом.
    if fields["manager"] and item.get("conversation_id"):
        crm_store.set_conversation_manager(item["conversation_id"], fields["manager"], actor=actor)
    return {"ok": True, "request": crm_store.get_callback_request(request_id)}


@router.post("/requests/{request_id}/notes")
async def request_notes(request: Request, request_id: int, data: dict) -> dict:
    actor = _authorize(request, "requests")
    if not crm_store.update_callback_request(
            request_id, {"notes": str(data.get("notes", ""))}, actor=actor):
        raise HTTPException(status_code=404, detail="request not found")
    return {"ok": True, "request": crm_store.get_callback_request(request_id)}


# --------- Customer 360 ---------


@router.get("/customers")
async def customers(request: Request, search: str = "", lead_status: str = "",
                    status: str = "", channel: str = "", date_from: str = "",
                    date_to: str = "", limit: int = 50, offset: int = 0) -> dict:
    actor = _authorize(request, "customers")
    return crm_store.list_customers(
        search=search or None, lead_status=lead_status or None,
        status=status or None, channel=channel or None,
        date_from=date_from or None, date_to=date_to or None,
        limit=limit, offset=offset,
    )


@router.get("/customers/{customer_id}")
async def customer_detail(request: Request, customer_id: int) -> dict:
    actor = _authorize(request, "customers")
    return _customer_or_404(customer_id)


@router.get("/customers/{customer_id}/timeline")
async def customer_timeline(request: Request, customer_id: int, limit: int = 200) -> dict:
    actor = _authorize(request, "customers")
    _customer_or_404(customer_id)
    return {"items": crm_store.customer_timeline(customer_id, limit=limit)}


@router.patch("/customers/{customer_id}")
async def customer_update(request: Request, customer_id: int, data: dict) -> dict:
    actor = _authorize(request, "customers")
    _customer_or_404(customer_id)
    crm_store.update_customer(customer_id, data, actor=actor)
    return _customer_or_404(customer_id)


@router.post("/customers/{customer_id}/archive")
async def customer_archive(request: Request, customer_id: int, data: dict | None = None) -> dict:
    actor = _authorize(request, "customers")
    _customer_or_404(customer_id)
    reason = str((data or {}).get("reason", ""))
    crm_store.archive_customer(customer_id, actor=actor, reason=reason)
    return {"ok": True}


@router.post("/customers/{customer_id}/unarchive")
async def customer_unarchive(request: Request, customer_id: int) -> dict:
    actor = _authorize(request, "customers")
    crm_store.unarchive_customer(customer_id, actor=actor)
    return {"ok": True}


@router.post("/customers/merge")
async def customers_merge(request: Request, data: dict) -> dict:
    actor = _authorize(request, "customers")
    primary_id = int(data.get("primary_id") or 0)
    secondary_id = int(data.get("secondary_id") or 0)
    if not primary_id or not secondary_id or primary_id == secondary_id:
        raise HTTPException(status_code=400, detail="primary_id and secondary_id required")
    _customer_or_404(primary_id)
    _customer_or_404(secondary_id)
    crm_store.merge_customers(primary_id, secondary_id, actor=actor)
    return _customer_or_404(primary_id)


# --------- Заметки, задачи, теги ---------


@router.get("/customers/{customer_id}/notes")
async def notes_list(request: Request, customer_id: int) -> dict:
    actor = _authorize(request, "customers")
    _customer_or_404(customer_id)
    return {"items": crm_store.list_notes(customer_id)}


@router.post("/customers/{customer_id}/notes")
async def notes_add(request: Request, customer_id: int, data: dict) -> dict:
    actor = _authorize(request, "customers")
    _customer_or_404(customer_id)
    text = str(data.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    note_id = crm_store.add_note(customer_id, "admin", text)
    return {"ok": True, "id": note_id}


@router.get("/customers/{customer_id}/tasks")
async def tasks_list(request: Request, customer_id: int) -> dict:
    actor = _authorize(request, "customers")
    _customer_or_404(customer_id)
    return {"items": crm_store.list_tasks(customer_id)}


@router.post("/customers/{customer_id}/tasks")
async def tasks_add(request: Request, customer_id: int, data: dict) -> dict:
    actor = _authorize(request, "customers")
    _customer_or_404(customer_id)
    title = str(data.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="title required")
    task_id = crm_store.add_task(
        customer_id, title,
        due_at=data.get("due_at") or None,
        assignee=str(data.get("assignee") or ""),
    )
    return {"ok": True, "id": task_id}


@router.post("/tasks/{task_id}/done")
async def task_done(request: Request, task_id: int) -> dict:
    actor = _authorize(request, "customers")
    crm_store.complete_task(task_id)
    return {"ok": True}


@router.get("/tags")
async def tags_list(request: Request) -> dict:
    actor = _authorize(request, "customers")
    return {"items": crm_store.list_all_tags()}


@router.post("/customers/{customer_id}/tags")
async def tag_assign(request: Request, customer_id: int, data: dict) -> dict:
    actor = _authorize(request, "customers")
    _customer_or_404(customer_id)
    name = str(data.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    crm_store.assign_tag(customer_id, name)
    return {"ok": True}


@router.delete("/customers/{customer_id}/tags/{tag_name}")
async def tag_unassign(request: Request, customer_id: int, tag_name: str) -> dict:
    actor = _authorize(request, "customers")
    crm_store.unassign_tag(customer_id, tag_name)
    return {"ok": True}


# --------- Статистика и здоровье ---------


@router.get("/stats/today")
async def stats_today(request: Request) -> dict:
    actor = _authorize(request, "stats")
    return crm_store.stats_today()


@router.get("/ai/events")
async def ai_events(request: Request, kind: str = "", days: int = 7,
                    limit: int = 100) -> dict:
    actor = _authorize(request, "stats")
    return {"items": crm_store.list_ai_events(kind=kind or None, days=days, limit=limit)}


@router.get("/health")
async def health(request: Request) -> dict:
    actor = _authorize(request, "health")
    db_ok = True
    try:
        crm_store.get_conn().execute("SELECT 1")
    except Exception:
        db_ok = False
    events = {row["status"]: row["c"] for row in crm_store.inbound_events_health(24)}
    return {
        "db_ok": db_ok,
        "max_ok": bool(settings.MAX_BOT_TOKEN),
        "telegram_ok": bool(settings.TELEGRAM_BOT_TOKEN),
        "inbound_24h": events,
    }


# --------- Этап 8: Broadcast Center ---------


def _rules_from_payload(data: dict) -> list[dict]:
    """Правила из тела запроса: явные rules или сохранённый сегмент."""
    rules = data.get("rules")
    if rules is not None:
        if not isinstance(rules, list):
            raise HTTPException(status_code=400, detail="rules must be a list")
        return rules
    segment_id = data.get("segment_id")
    if segment_id:
        segment = crm_store.get_segment(int(segment_id))
        if segment is None:
            raise HTTPException(status_code=404, detail="segment not found")
        return segment["rules"]
    return []


@router.get("/segments")
async def segments_list(request: Request) -> dict:
    actor = _authorize(request, "segments")
    return {"items": crm_store.list_segments()}


@router.post("/segments")
async def segments_save(request: Request, data: dict) -> dict:
    actor = _authorize(request, "segments")
    name = str(data.get("name", "")).strip()
    rules = data.get("rules")
    if not name or not isinstance(rules, list):
        raise HTTPException(status_code=400, detail="name and rules required")
    segment_id = crm_store.save_segment(name, rules)
    crm_store.audit(actor, "save", "segment", segment_id, after={"name": name})
    return {"ok": True, "id": segment_id}


@router.delete("/segments/{segment_id}")
async def segments_delete(request: Request, segment_id: int) -> dict:
    actor = _authorize(request, "segments")
    crm_store.delete_segment(segment_id)
    crm_store.audit(actor, "delete", "segment", segment_id)
    return {"ok": True}


@router.post("/broadcasts/preview")
async def broadcast_preview(request: Request, data: dict) -> dict:
    """Считает аудиторию сегмента. Ничего не отправляет."""
    actor = _authorize(request, "broadcasts")
    rules = _rules_from_payload(data)
    resolved = crm_store.resolve_segment(rules)
    by_channel: dict[str, int] = {}
    for rec in resolved["recipients"]:
        by_channel[rec["channel"]] = by_channel.get(rec["channel"], 0) + 1
    return {
        "total": len(resolved["recipients"]),
        "by_channel": by_channel,
        "skipped_web": resolved["skipped_web"],
        "sample": resolved["recipients"][:10],
    }


@router.post("/broadcasts")
async def broadcast_create(request: Request, data: dict) -> dict:
    actor = _authorize(request, "broadcasts")
    title = str(data.get("title", "")).strip()
    text = str(data.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    rules = _rules_from_payload(data)
    broadcast_id = crm_store.create_broadcast(
        title or text[:50], text, segment={"rules": rules}, created_by=actor)
    crm_store.audit(actor, "create", "broadcast", broadcast_id, after={"title": title})
    return {"ok": True, "id": broadcast_id}


@router.post("/broadcasts/{broadcast_id}/send")
async def broadcast_send(request: Request, broadcast_id: int, data: dict) -> dict:
    """Запуск рассылки в фоне. Требует confirm=true — защита от случайного
    клика; повторный запуск уже отправленной заблокирован."""
    actor = _authorize(request, "broadcasts")
    if not data.get("confirm"):
        raise HTTPException(status_code=400, detail="confirm=true required")
    broadcast = crm_store.get_broadcast(broadcast_id)
    if broadcast is None:
        raise HTTPException(status_code=404, detail="broadcast not found")
    if broadcast["status"] in ("sending", "done"):
        raise HTTPException(status_code=409, detail=f"already {broadcast['status']}")
    rules = json.loads(broadcast["segment_json"] or "{}").get("rules", [])
    resolved = crm_store.resolve_segment(rules)
    crm_store.fill_recipients(broadcast_id, resolved["recipients"])
    if resolved["skipped_web"]:
        # Web-only клиенты фиксируются как пропущенные: их видно в деталях.
        pass
    from app import broadcast_runner

    task = asyncio.create_task(broadcast_runner.run_broadcast(broadcast_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"ok": True, "total": len(resolved["recipients"]),
            "skipped_web": resolved["skipped_web"]}


@router.get("/broadcasts")
async def broadcasts_history(request: Request, limit: int = 50, offset: int = 0) -> dict:
    actor = _authorize(request, "broadcasts")
    return {"items": crm_store.list_broadcasts(limit=limit, offset=offset)}


@router.get("/broadcasts/{broadcast_id}")
async def broadcast_detail(request: Request, broadcast_id: int, status: str = "",
                           limit: int = 100, offset: int = 0) -> dict:
    actor = _authorize(request, "broadcasts")
    broadcast = crm_store.get_broadcast(broadcast_id)
    if broadcast is None:
        raise HTTPException(status_code=404, detail="broadcast not found")
    broadcast["recipients"] = crm_store.list_recipients(
        broadcast_id, status=status or None, limit=limit, offset=offset)
    return broadcast


@router.post("/broadcasts/{broadcast_id}/recipients/{recipient_id}/retry")
async def broadcast_recipient_retry(request: Request, broadcast_id: int,
                                    recipient_id: int) -> dict:
    actor = _authorize(request, "broadcasts")
    from app import broadcast_runner

    result = await broadcast_runner.retry_recipient(recipient_id)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    crm_store.audit(actor, "retry", "broadcast_recipient", recipient_id)
    return result


# --------- Этап 9: воронка и экспорт ---------


@router.get("/pipeline")
async def pipeline_board(request: Request) -> dict:
    actor = _authorize(request, "pipeline")
    return crm_store.pipeline()


@router.get("/export/customers.csv")
async def export_customers(request: Request):
    actor = _authorize(request, "export")
    from fastapi.responses import StreamingResponse

    rows = crm_store.export_customers_rows()
    header = ["id", "name", "phone", "email", "child_name", "child_age",
              "lead_status", "status", "source", "manager", "interests",
              "channels", "first_seen_at", "last_seen_at"]
    return StreamingResponse(
        _csv_stream(header, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=customers.csv"},
    )


@router.get("/export/messages.csv")
async def export_messages(request: Request, date_from: str = "", date_to: str = ""):
    actor = _authorize(request, "export")
    from fastapi.responses import StreamingResponse

    rows = crm_store.export_messages_rows(date_from or None, date_to or None)
    header = ["id", "created_at", "channel", "direction", "sender_type",
              "status", "customer_id", "conversation_id", "text"]
    return StreamingResponse(
        _csv_stream(header, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=messages.csv"},
    )


def _csv_stream(header: list[str], rows: list[dict]):
    """CSV-поток с UTF-8 BOM: без него Excel открывает кириллицу кракозябрами."""
    import csv
    import io

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        buf.write("\ufeff")  # UTF-8 BOM: без него Excel ломает кириллицу
        writer.writerow(header)
        yield buf.getvalue()
        for row in rows:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([row.get(col, "") for col in header])
            yield buf.getvalue()

    return generate()


# --------- Этап 10: Analytics ---------


@router.get("/analytics")
async def analytics(request: Request, days: int = 30) -> dict:
    actor = _authorize(request, "analytics")
    return crm_store.analytics(days=days)


@router.get("/errors")
async def errors(request: Request, days: int = 7, category: str = "",
                 limit: int = 100) -> dict:
    actor = _authorize(request, "errors")
    return {"items": crm_store.errors_feed(days=days, category=category or None,
                                           limit=limit)}


# --------- Этап 11: база знаний и промпты ---------


@router.get("/kb")
async def kb_list(request: Request) -> dict:
    actor = _authorize(request, "kb")
    return {"items": crm_store.kb_list()}


@router.post("/kb")
async def kb_create(request: Request, data: dict) -> dict:
    actor = _authorize(request, "kb")
    text = str(data.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    doc_id = crm_store.kb_add(
        title=str(data.get("title", "")).strip(),
        text=text,
        category=str(data.get("category", "custom")).strip() or "custom",
    )
    crm_store.audit(actor, "create", "kb_document", doc_id)
    return {"ok": True, "id": doc_id}


@router.patch("/kb/{doc_id}")
async def kb_patch(request: Request, doc_id: int, data: dict) -> dict:
    actor = _authorize(request, "kb")
    if not crm_store.kb_update(doc_id, data):
        raise HTTPException(status_code=404, detail="document not found or nothing to update")
    crm_store.audit(actor, "update", "kb_document", doc_id, after=data)
    return {"ok": True}


@router.delete("/kb/{doc_id}")
async def kb_delete(request: Request, doc_id: int) -> dict:
    """Мягкое выключение: документ остаётся в базе, но уходит из поиска."""
    actor = _authorize(request, "kb")
    if not crm_store.kb_update(doc_id, {"enabled": 0}):
        raise HTTPException(status_code=404, detail="document not found")
    crm_store.audit(actor, "disable", "kb_document", doc_id)
    return {"ok": True}


@router.get("/ai/prompts")
async def prompts_list(request: Request) -> dict:
    actor = _authorize(request, "prompts")
    # Сеем кодовый промпт как v1 при первом открытии раздела — иначе до
    # первого LLM-ответа список пуст, и откатиться не на что.
    from app import sales

    crm_store.prompt_seed(sales.SYSTEM_PROMPT)
    return {"items": crm_store.prompt_list()}


@router.get("/ai/prompts/{prompt_id}")
async def prompt_detail(request: Request, prompt_id: int) -> dict:
    actor = _authorize(request, "prompts")
    prompt = crm_store.prompt_get(prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="prompt not found")
    return prompt


@router.post("/ai/prompts")
async def prompt_create(request: Request, data: dict) -> dict:
    actor = _authorize(request, "prompts")
    content = str(data.get("content", "")).strip()
    if not content:
        raise HTTPException(status_code=400, detail="content required")
    prompt_id = crm_store.prompt_add(content, created_by=actor)
    crm_store.audit(actor, "create", "ai_prompt", prompt_id)
    return {"ok": True, "id": prompt_id}


@router.post("/ai/prompts/{prompt_id}/activate")
async def prompt_activate(request: Request, prompt_id: int) -> dict:
    actor = _authorize(request, "prompts")
    if not crm_store.prompt_activate(prompt_id, actor=actor):
        raise HTTPException(status_code=404, detail="prompt not found")
    # Сбрасываем кэш sales: новая версия вступает в силу сразу, не через 60с.
    from app import sales

    sales.reset_prompt_cache()
    return {"ok": True}


# --------- Этап 12: система ---------


@router.get("/system")
async def system_health(request: Request) -> dict:
    actor = _authorize(request, "system")
    import os
    import time

    db_ok = True
    db_size = 0
    try:
        conn = crm_store.get_conn()
        conn.execute("SELECT 1")
        row = conn.execute("PRAGMA database_list").fetchone()
        if row and row["file"]:
            db_size = os.path.getsize(row["file"])
    except Exception:
        db_ok = False
    events = {row["status"]: row["c"] for row in crm_store.inbound_events_health(24)}
    return {
        "db_ok": db_ok,
        "db_size_bytes": db_size,
        "max_ok": bool(settings.MAX_BOT_TOKEN),
        "telegram_ok": bool(settings.TELEGRAM_BOT_TOKEN),
        "web_ok": True,
        "ai_ok": bool(settings.LLM_API_KEY),
        "llm_model": settings.LLM_MODEL,
        "inbound_24h": events,
        "process_uptime_sec": int(time.monotonic()),
        "started_at": _STARTED_AT,
    }


# --------- Этап 13: вход, сессии, управление пользователями ---------


@router.post("/login")
async def login(request: Request, data: dict) -> dict:
    """Вход по логину/паролю. Rate-limit 5 попыток/мин по IP."""
    ip = request.client.host if request.client else "unknown"
    if _login_limited(ip):
        raise HTTPException(status_code=429, detail="too many attempts")
    username = str(data.get("username", ""))
    password = str(data.get("password", ""))
    user = crm_store.admin_user_verify(username, password)
    if user is None:
        # Одинаковый ответ на «нет пользователя» и «неверный пароль».
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = crm_store.session_create(user["id"])
    crm_store.audit(user["username"], "login", "admin_session", user["id"])
    return {"token": token, "role": user["role"], "username": user["username"]}


@router.post("/logout")
async def logout(request: Request) -> dict:
    token = request.headers.get("X-Admin-Token", "")
    if token and not (settings.ADMIN_TOKEN and hmac.compare_digest(token, settings.ADMIN_TOKEN)):
        crm_store.session_delete(token)
    return {"ok": True}


@router.get("/me")
async def me(request: Request) -> dict:
    """Текущий пользователь: роль и права — фронт прячет недоступные разделы."""
    token = request.headers.get("X-Admin-Token", "")
    if settings.ADMIN_TOKEN and hmac.compare_digest(token, settings.ADMIN_TOKEN):
        return {"username": "super_admin", "role": "super_admin",
                "permissions": ["*"]}
    session = crm_store.session_get(token)
    if session is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    perms = ROLE_PERMISSIONS.get(session["role"], set())
    return {"username": session["username"], "role": session["role"],
            "permissions": sorted(perms)}


@router.get("/admin-users")
async def admin_users_list(request: Request) -> dict:
    _authorize(request, "users")
    return {"items": crm_store.admin_user_list()}


@router.post("/admin-users")
async def admin_users_create(request: Request, data: dict) -> dict:
    actor = _authorize(request, "users")
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    role = str(data.get("role", "manager"))
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail="unknown role")
    if not username or len(password) < 6:
        raise HTTPException(status_code=400, detail="username required, password >= 6 chars")
    try:
        user_id = crm_store.admin_user_create(username, password, role)
    except Exception:
        raise HTTPException(status_code=409, detail="username already exists")
    crm_store.audit(actor, "create", "admin_user", user_id,
                    after={"username": username, "role": role})
    return {"ok": True, "id": user_id}


@router.patch("/admin-users/{user_id}")
async def admin_users_patch(request: Request, user_id: int, data: dict) -> dict:
    """role, active, сброс пароля. Только super_admin."""
    actor = _authorize(request, "users")
    if data.get("role") and data["role"] not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail="unknown role")
    if data.get("password") and len(str(data["password"])) < 6:
        raise HTTPException(status_code=400, detail="password >= 6 chars")
    if not crm_store.admin_user_update(user_id, data):
        raise HTTPException(status_code=404, detail="user not found or nothing to update")
    crm_store.audit(actor, "update", "admin_user", user_id,
                    after={k: v for k, v in data.items() if k != "password"})
    return {"ok": True}
