"""Runtime-гарантии диалога: сериализация, дедлайны и структурные логи.

Один пользователь = одна очередь обработки. Без этого три сообщения подряд
(«привет» / «сколько стоит?» / «а онлайн есть?») параллельно мутируют один и
тот же объект Conversation: история перемешивается, ответы приходят не в том
порядке, а сохранение затирает друг друга.

Логи пишутся событиями с общим request_id, чтобы по журналу было видно,
на каком именно шаге бот перестал двигаться.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar

logger = logging.getLogger("bot.flow")

# Ключ — (platform, user_id). Держим asyncio.Lock на каждый активный диалог.
_locks: dict[tuple[str, str], asyncio.Lock] = {}
# Сколько корутин сейчас держит/ждёт лок — по нулю освобождаем запись, чтобы
# словарь не рос бесконечно на долгоживущем процессе.
_waiters: dict[tuple[str, str], int] = {}
# Реестр защищаем обычным threading.Lock, а не asyncio.Lock: критическая
# секция — пара операций со словарём без await, зато asyncio.Lock жёстко
# привязывается к первому event loop и ломается, если процесс когда-нибудь
# заведёт второй (тесты, воркеры, скрипты обслуживания).
_locks_guard = threading.Lock()

_request_id: ContextVar[str] = ContextVar("request_id", default="")


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def get_request_id() -> str:
    return _request_id.get()


def log_event(event: str, **fields: object) -> None:
    """Структурная строка журнала: EVENT key=value key=value.

    Специально плоский формат: его одинаково легко грепать в journalctl и
    парсить скриптом, а внешних зависимостей (structlog) в проекте нет.
    """
    parts = [event]
    rid = _request_id.get()
    if rid:
        parts.append(f"request_id={rid}")
    for key, value in fields.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    logger.info(" ".join(parts))


@asynccontextmanager
async def conversation_lock(platform: str, user_id: str):
    """Эксклюзивный доступ к диалогу одного пользователя."""
    key = (platform or "", user_id or "")
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _locks[key] = lock
        _waiters[key] = _waiters.get(key, 0) + 1

    waited_since = time.monotonic()
    try:
        async with lock:
            waited = time.monotonic() - waited_since
            if waited > 1.0:
                log_event("QUEUE_WAIT", user_id=user_id, platform=platform, waited=f"{waited:.1f}s")
            yield
    finally:
        with _locks_guard:
            remaining = _waiters.get(key, 1) - 1
            if remaining <= 0:
                _waiters.pop(key, None)
                _locks.pop(key, None)
            else:
                _waiters[key] = remaining


def reset_locks() -> None:
    """Сброс между тестами — в проде не вызывается."""
    _locks.clear()
    _waiters.clear()


__all__ = [
    "conversation_lock",
    "get_request_id",
    "log_event",
    "new_request_id",
    "reset_locks",
    "set_request_id",
]
