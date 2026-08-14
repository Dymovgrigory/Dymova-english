"""Сторож доступности внешних каналов.

Зачем: Telegram лежал две недели, и никто не заметил. `/health` отвечал
«ok», потому что знал только про себя — процесс жив, база открыта. А то,
что бот уже две недели не может достучаться до api.telegram.org, не
проверял никто.

Сторож активно, не дожидаясь пользователей, дёргает getMe и следит, что
цикл long-polling вообще крутится. Как только связь пропала —
администратор получает сообщение в MAX с конкретным действием: какой IP
Telegram сейчас отвечает и что вписать в конфиг.
"""
from __future__ import annotations

import asyncio
import logging
import socket
import time
from dataclasses import dataclass, field

from app.config import settings
from app.max_client import get_max
from app.slack import notify_slack

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT_SEC = 5


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    detail: str = ""


@dataclass
class _State:
    telegram_api_ok: bool = True
    consecutive_failures: int = 0
    last_alert_at: float | None = None
    last_poll_ok: float | None = None
    last_detail: str = ""
    alerting: bool = False
    reachable_ips: list[str] = field(default_factory=list)


_state = _State()


def reset_state() -> None:
    """Сброс между тестами."""
    global _state
    _state = _State()


def record_poll_ok() -> None:
    """Отмечает успешный цикл long-polling. Вызывается из цикла опроса."""
    _state.last_poll_ok = time.time()


def status() -> dict:
    """Состояние для /health."""
    since_poll = None
    if _state.last_poll_ok is not None:
        since_poll = round(time.time() - _state.last_poll_ok, 1)
    return {
        "telegram_api_ok": _state.telegram_api_ok,
        "consecutive_failures": _state.consecutive_failures,
        "seconds_since_poll": since_poll,
        "detail": _state.last_detail,
        "reachable_telegram_ips": list(_state.reachable_ips),
    }


async def check_telegram_api() -> CheckResult:
    """Живой запрос getMe. Дешёвый и не трогает очередь апдейтов."""
    from app.telegram_client import get_telegram

    telegram = get_telegram()
    if not telegram.configured:
        return CheckResult(ok=True, detail="токен не задан — проверка пропущена")
    try:
        # Две попытки, а не одна: канал до Telegram у этого провайдера
        # периодически даёт единичный ConnectTimeout, при том что поллинг
        # продолжает работать. С одной попыткой сторож объявлял бота
        # недоступным из-за случайного таймаута — и поднимал ложную тревогу.
        result = await telegram._post("getMe", {}, timeout=15, attempts=2)
    except Exception as exc:
        return CheckResult(ok=False, detail=f"{type(exc).__name__}")
    if result is None:
        return CheckResult(ok=False, detail="getMe не ответил")
    return CheckResult(ok=True, detail="getMe ok")


async def probe_telegram_ips() -> list[str]:
    """Какие адреса Telegram сейчас пропускает сеть.

    Это и есть «предупредить заранее»: если пин из docker-compose перестал
    отвечать, администратор сразу получает список живых альтернатив, а не
    просто «что-то сломалось».
    """
    candidates = [ip.strip() for ip in settings.TELEGRAM_API_IPS.split(",") if ip.strip()]
    reachable: list[str] = []
    for ip in candidates:
        if await _tcp_reachable(ip, 443):
            reachable.append(ip)
    return reachable


async def _tcp_reachable(host: str, port: int) -> bool:
    def _connect() -> bool:
        try:
            with socket.create_connection((host, port), timeout=_PROBE_TIMEOUT_SEC):
                return True
        except OSError:
            return False

    try:
        return await asyncio.to_thread(_connect)
    except Exception:
        return False


def _poll_is_silent() -> bool:
    """Опрос считается вставшим, если давно не было успешного цикла.

    Ловит не только сеть: тот же признак был бы у зависшего offset —
    getUpdates отвечает, а цикл крутится вхолостую.
    """
    if not (settings.TELEGRAM_POLLING and settings.TELEGRAM_BOT_TOKEN):
        return False
    if _state.last_poll_ok is None:
        # Ещё ни одного успешного цикла с момента старта — молчим, чтобы не
        # ругаться на нормальный холодный запуск.
        return False
    limit = max(1, int(settings.WATCHDOG_POLL_SILENCE_MIN)) * 60
    return (time.time() - _state.last_poll_ok) > limit


def _cooldown_passed() -> bool:
    if _state.last_alert_at is None:
        return True
    cooldown = max(1, int(settings.WATCHDOG_ALERT_COOLDOWN_MIN)) * 60
    return (time.time() - _state.last_alert_at) >= cooldown


async def _alert(text: str) -> None:
    _state.last_alert_at = time.time()
    logger.error("watchdog: %s", text.replace("\n", " | "))
    max_client = get_max()
    for admin_id in settings.admin_ids:
        try:
            await max_client.send_message(admin_id, text)
        except Exception:
            logger.exception("watchdog: не удалось оповестить администратора %s", admin_id)
    try:
        await notify_slack(text)
    except Exception:
        logger.exception("watchdog: не удалось оповестить Slack")


def _problem_message(reason: str) -> str:
    lines = [f"🚨 Бот не может работать с Telegram\n\nЧто именно: {reason}"]
    if _state.reachable_ips:
        lines.append(
            "Сейчас отвечает: " + ", ".join(_state.reachable_ips) + "\n"
            "Впишите рабочий адрес в docker-compose.yml → bot → extra_hosts:\n"
            f'  - "api.telegram.org:{_state.reachable_ips[0]}"\n'
            "и перезапустите: docker compose up -d bot"
        )
    else:
        lines.append(
            "Ни один известный адрес Telegram не отвечает — сеть закрыта целиком.\n"
            "Нужен рабочий прокси или VPN: задайте TELEGRAM_PROXY_URL и перезапустите бота."
        )
    lines.append("MAX и сайт продолжают работать.")
    return "\n\n".join(lines)


async def run_check_once() -> None:
    """Один цикл проверки. Никогда не бросает исключений наружу."""
    if not settings.WATCHDOG_ENABLED:
        return
    try:
        result = await check_telegram_api()
    except Exception:
        logger.exception("watchdog: проверка Telegram упала")
        result = CheckResult(ok=False, detail="проверка упала с исключением")

    reason = ""
    if not result.ok:
        reason = f"API Telegram недоступен ({result.detail})"
    elif _poll_is_silent():
        minutes = int((time.time() - (_state.last_poll_ok or 0)) / 60)
        reason = f"опрос Telegram молчит {minutes} мин — новые сообщения не забираются"

    _state.last_detail = reason or result.detail
    healthy = not reason

    if healthy:
        was_alerting = _state.alerting
        _state.telegram_api_ok = True
        _state.consecutive_failures = 0
        _state.alerting = False
        if was_alerting:
            await _alert("✅ Telegram снова доступен — бот забирает сообщения.")
        return

    _state.telegram_api_ok = False
    _state.consecutive_failures += 1
    try:
        _state.reachable_ips = await probe_telegram_ips()
    except Exception:
        logger.exception("watchdog: проба адресов Telegram упала")
        _state.reachable_ips = []

    threshold = max(1, int(settings.WATCHDOG_FAILURES_BEFORE_ALERT))
    if _state.consecutive_failures < threshold:
        # Одиночная сетевая осечка — не повод будить человека.
        return
    if _state.alerting and not _cooldown_passed():
        return
    _state.alerting = True
    await _alert(_problem_message(reason))


async def loop() -> None:
    interval = max(1, int(settings.WATCHDOG_INTERVAL_MIN)) * 60
    logger.info("watchdog: проверка доступности каждые %s мин", settings.WATCHDOG_INTERVAL_MIN)
    while True:
        await asyncio.sleep(interval)
        try:
            await run_check_once()
        except Exception:
            logger.exception("watchdog: непредвиденная ошибка цикла")


__all__ = [
    "CheckResult",
    "check_telegram_api",
    "loop",
    "probe_telegram_ips",
    "record_poll_ok",
    "reset_state",
    "run_check_once",
    "status",
]
