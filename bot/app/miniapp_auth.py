"""Аутентификация мини-приложений (Telegram Mini App и MAX Mini App).

Единственный источник личности пользователя — криптографически подписанный
initData от платформы. Открытый `?user_id=` из запроса личностью не является:
раньше любой мог подставить чужой id и прочитать/изменить чужой профиль,
а заодно обойти проверку регистрации (IDOR).

Алгоритм Telegram (https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app):
    secret_key   = HMAC_SHA256(key="WebAppData", msg=bot_token)
    data_check   = "\\n".join(sorted("key=value" для всех полей, кроме hash))
    valid        = HMAC_SHA256(key=secret_key, msg=data_check).hex() == hash
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)

# Подписанный initData живёт ограниченное время: устаревший auth_date не
# принимаем, иначе перехваченная строка работает вечно.
INIT_DATA_MAX_AGE_SEC = 24 * 60 * 60


@dataclass(frozen=True)
class MiniAppIdentity:
    """Проверенная личность пользователя мини-приложения."""

    user_id: str          # внутренний id диалога, напр. "tg:12345"
    platform: str         # "telegram" | "max"
    display_name: str = ""
    verified: bool = True


def _data_check_string(parsed: dict[str, list[str]]) -> str:
    pairs = []
    for key in sorted(parsed):
        for value in parsed[key]:
            pairs.append(f"{key}={value}")
    return "\n".join(pairs)


def _parse_user(parsed: dict[str, list[str]]) -> dict:
    try:
        return json.loads(parsed.get("user", ["{}"])[0]) or {}
    except Exception:
        return {}


def _auth_date_fresh(parsed: dict[str, list[str]]) -> bool:
    raw = parsed.get("auth_date", [""])[0]
    if not raw:
        return False
    try:
        auth_date = int(raw)
    except (TypeError, ValueError):
        return False
    age = time.time() - auth_date
    # Небольшой запас вперёд на расхождение часов клиента и сервера.
    return -300 <= age <= INIT_DATA_MAX_AGE_SEC


def verify_telegram_init_data(init_data: str, token: str | None = None) -> MiniAppIdentity | None:
    """Проверяет подпись Telegram initData. None — данные доверять нельзя."""
    bot_token = (token if token is not None else settings.TELEGRAM_BOT_TOKEN).strip()
    if not bot_token or not init_data:
        return None
    parsed = urllib.parse.parse_qs(init_data, keep_blank_values=True)
    received_hash = parsed.pop("hash", [""])[0]
    if not received_hash:
        return None
    # signature — поле третьесторонней (Ed25519) проверки, в HMAC не входит.
    parsed.pop("signature", None)

    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(
        secret, _data_check_string(parsed).encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        logger.warning("miniapp: неверная подпись Telegram initData")
        return None
    if not _auth_date_fresh(parsed):
        logger.warning("miniapp: просроченный auth_date в Telegram initData")
        return None

    user = _parse_user(parsed)
    telegram_id = user.get("id")
    if not telegram_id:
        return None
    name = " ".join(
        part for part in (user.get("first_name"), user.get("last_name")) if part
    ).strip()
    return MiniAppIdentity(
        user_id=f"tg:{telegram_id}", platform="telegram", display_name=name
    )


def verify_max_init_data(init_data: str) -> MiniAppIdentity | None:
    """Проверяет подпись MAX initData (тот же HMAC-механизм, токен бота MAX)."""
    from app.max_client import get_max

    verified = get_max().verify_init_data(init_data)
    if not verified or not verified.get("user_id"):
        return None
    return MiniAppIdentity(user_id=str(verified["user_id"]), platform="max")


def identify(
    init_data: str = "",
    platform_hint: str = "",
    fallback_user_id: str = "",
) -> MiniAppIdentity | None:
    """Определяет пользователя мини-приложения.

    Порядок: подписанный Telegram initData → подписанный MAX initData →
    (только если MINIAPP_AUTH_REQUIRED выключен) незаверенный user_id из
    запроса. Последний путь оставлен исключительно для локальной отладки и
    открытой веб-витрины и помечается verified=False.
    """
    init_data = (init_data or "").strip()
    if init_data:
        order = (
            (verify_telegram_init_data, verify_max_init_data)
            if platform_hint != "max"
            else (verify_max_init_data, verify_telegram_init_data)
        )
        for verifier in order:
            try:
                identity = verifier(init_data)
            except Exception:
                logger.exception("miniapp: ошибка проверки initData")
                identity = None
            if identity:
                return identity
        return None

    if settings.MINIAPP_AUTH_REQUIRED:
        return None
    fallback_user_id = (fallback_user_id or "").strip()
    if not fallback_user_id:
        return None
    platform = "telegram" if fallback_user_id.startswith("tg:") else "max"
    return MiniAppIdentity(
        user_id=fallback_user_id, platform=platform, verified=False
    )


__all__ = [
    "INIT_DATA_MAX_AGE_SEC",
    "MiniAppIdentity",
    "identify",
    "verify_max_init_data",
    "verify_telegram_init_data",
]
