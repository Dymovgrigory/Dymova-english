"""Мост бот→world: prefill анкеты при входе через Telegram/MAX.

Бот отдаёт профиль лида по адресу WORLD_BOT_BRIDGE_URL:
GET <url>?provider=telegram&user_id=123&ts=<unix>&sign=<hex>,
sign = HMAC_SHA256(key=WORLD_BRIDGE_SECRET, msg=f"{provider}\\n{user_id}\\n{ts}").

Ответ бота: 200 {"found": bool, "lead": {...} | null}; 400/401/404 — проблемы.
Fail-open: любая ошибка/таймаут/не-200 → None, вход в мир не блокируется.
Без WORLD_BRIDGE_SECRET фича выключена (всегда None).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

import httpx

log = logging.getLogger("world.identity.bridge")

DEFAULT_BRIDGE_URL = "http://bot:8000/world-bridge/profile"
TIMEOUT_SEC = 2.5
LEAD_KEYS = ("fio_parent", "fio_child", "birthday", "phone")


def _sign(secret: str, provider: str, provider_user_id: str, ts: int) -> str:
    msg = f"{provider}\n{provider_user_id}\n{ts}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def fetch_bot_prefill(provider: str, provider_user_id: str) -> dict | None:
    """Профиль лида из бота для prefill анкеты или None."""
    secret = os.environ.get("WORLD_BRIDGE_SECRET", "").strip()
    if not secret:
        return None
    url = os.environ.get("WORLD_BOT_BRIDGE_URL", "").strip() or DEFAULT_BRIDGE_URL
    ts = int(time.time())
    params = {
        "provider": provider,
        "user_id": provider_user_id,
        "ts": ts,
        "sign": _sign(secret, provider, provider_user_id, ts),
    }
    try:
        with httpx.Client(timeout=TIMEOUT_SEC) as client:
            r = client.get(url, params=params)
        if r.status_code != 200:
            log.warning("bot-bridge %s provider=%s status=%s", url, provider, r.status_code)
            return None
        payload = r.json()
    except Exception as exc:  # noqa: BLE001 — fail-open: вход в мир не зависит от бота
        log.warning("bot-bridge %s provider=%s failed: %s", url, provider, exc)
        return None
    if not isinstance(payload, dict) or not payload.get("found"):
        return None
    lead = payload.get("lead")
    if not isinstance(lead, dict):
        return None
    out = {k: v for k, v in lead.items() if k in LEAD_KEYS and isinstance(v, str)}
    # Флаг подтверждения номера нативным контактом Telegram — булев, поэтому
    # через строковый LEAD_KEYS-фильтр не проходит, переносим отдельно.
    if isinstance(lead.get("phone_confirmed"), bool):
        out["phone_confirmed"] = lead["phone_confirmed"]
    return out
