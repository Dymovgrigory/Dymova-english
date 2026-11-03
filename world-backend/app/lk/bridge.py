"""Мост world→bot для ЛК: проверка, что номер подтверждён нативным контактом в боте.

Бот отдаёт статус по адресу <WORLD_BOT_BRIDGE_URL>/world-bridge/phone-status:
GET ?phone=+7...&ts=<unix>&sign=<hex>,
sign = HMAC_SHA256(key=WORLD_BRIDGE_SECRET, msg=f"phone-status\\n{phone}\\n{ts}").

Ответ: 200 {"confirmed": bool, "providers": ["max"|"telegram", ...]}.
Fail-close для подтверждения: любая ошибка/таймаут/не-200 → confirmed=False
(в отличие от fail-open prefill-а Мира: там вход не блокировали, здесь
подтверждение — именно точка доверия).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

import httpx

log = logging.getLogger("world.lk.bridge")

DEFAULT_BRIDGE_URL = "http://bot:8000"
TIMEOUT_SEC = 3.0


class BridgeError(Exception):
    """Мост недоступен или ответ невалиден."""


def _sign(secret: str, phone: str, ts: int) -> str:
    msg = f"phone-status\n{phone}\n{ts}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def phone_confirmed(phone_e164: str) -> tuple[bool, list[str]]:
    """(подтверждён ли номер в боте, список провайдеров)."""
    secret = os.environ.get("WORLD_BRIDGE_SECRET", "").strip()
    if not secret:
        # Локальная разработка/тесты: явный обход только через env-флаг.
        if os.environ.get("LK_CONFIRM_BYPASS", "").strip() == "1":
            log.warning("LK_CONFIRM_BYPASS=1 — подтверждение телефона обходится")
            return True, ["bypass"]
        raise BridgeError("WORLD_BRIDGE_SECRET не настроен")
    base = os.environ.get("WORLD_BOT_BRIDGE_URL", "").strip().rstrip("/") or DEFAULT_BRIDGE_URL
    ts = int(time.time())
    params = {"phone": phone_e164, "ts": ts, "sign": _sign(secret, phone_e164, ts)}
    try:
        with httpx.Client(timeout=TIMEOUT_SEC) as client:
            r = client.get(f"{base}/world-bridge/phone-status", params=params)
    except Exception as exc:  # noqa: BLE001 — мост недоступен, подтверждение невозможно
        log.warning("lk-bridge phone-status failed: %s", exc)
        raise BridgeError(str(exc)) from exc
    if r.status_code != 200:
        log.warning("lk-bridge phone-status status=%s", r.status_code)
        raise BridgeError(f"HTTP {r.status_code}")
    payload = r.json()
    confirmed = bool(payload.get("confirmed"))
    providers = payload.get("providers") or []
    return confirmed, [str(p) for p in providers]
