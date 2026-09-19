"""Провайдеры доставки кода верификации телефона.

SmsAero v2 (https://gate.smsaero.ru/v2) — у него нет отдельного «звонка с кодом»
(есть только /sms/send и рассылки), поэтому канал call реализован тем же SMS
с пометкой в тексте; провайдер-независимый интерфейс это скрывает.
"""
from __future__ import annotations

import logging
import os
from typing import Protocol

log = logging.getLogger("world.identity.sms")

SMSAERO_BASE = "https://gate.smsaero.ru/v2"
CODE_TEXT = "Ваш код Фоксинбург: {code}"
CODE_TEXT_CALL = "Ваш код Фоксинбург (запрошен звонком): {code}"


class ProviderError(Exception):
    """Ошибка провайдера → HTTP 502 provider_error."""


class SmsProvider(Protocol):
    def send_code(self, phone_e164: str, channel: str, code: str) -> str | None:
        """Отправить код. Возвращает provider_id или None (fake)."""


class FakeSmsProvider:
    """Dev/тесты: ничего не шлёт, только лог с маской."""

    def send_code(self, phone_e164: str, channel: str, code: str) -> str | None:
        from .schemas import mask_phone

        log.info("fake-sms channel=%s phone=%s code=******", channel, mask_phone(phone_e164))
        return None


class SmsAeroProvider:
    def __init__(self) -> None:
        self._email = os.environ.get("SMSAERO_EMAIL", "").strip()
        self._key = os.environ.get("SMSAERO_API_KEY", "").strip()
        self._sign = os.environ.get("SMSAERO_SIGN", "").strip()
        if not (self._email and self._key and self._sign):
            raise RuntimeError("SMSAERO_EMAIL/SMSAERO_API_KEY/SMSAERO_SIGN required")

    def send_code(self, phone_e164: str, channel: str, code: str) -> str | None:
        import httpx

        from .schemas import mask_phone

        text = (CODE_TEXT_CALL if channel == "call" else CODE_TEXT).format(code=code)
        try:
            r = httpx.post(
                f"{SMSAERO_BASE}/sms/send",
                auth=(self._email, self._key),
                data={"number": phone_e164.lstrip("+"), "text": text, "sign": self._sign},
                timeout=5.0,
            )
            payload = r.json()
        except Exception as exc:
            log.warning("smsaero error phone=%s: %s", mask_phone(phone_e164), exc)
            raise ProviderError(str(exc)) from exc
        if r.status_code != 200 or not payload.get("success"):
            log.warning("smsaero rejected phone=%s: %s", mask_phone(phone_e164), payload)
            raise ProviderError(f"smsaero {r.status_code}")
        data = payload.get("data") or {}
        return str(data.get("id")) if data.get("id") else None


def verification_required() -> bool:
    return os.environ.get("PHONE_VERIFICATION_REQUIRED", "0").strip() == "1"


def get_provider() -> SmsProvider:
    if verification_required() and os.environ.get("SMSAERO_API_KEY"):
        return SmsAeroProvider()
    return FakeSmsProvider()
