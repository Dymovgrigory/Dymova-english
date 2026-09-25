"""Доставка кода верификации на email родителя.

SMTP через stdlib smtplib (SSL): Gmail (smtp.gmail.com:465, App Password)
или любой другой SMTP — хост/порт настраиваются env'ами. Провайдер-
независимый интерфейс скрывает детали от домена (как было с sms-провайдером).

Без учётных данных (WORLD_SMTP_USER/WORLD_SMTP_PASSWORD) или при
EMAIL_VERIFICATION_REQUIRED != 1 — fake-провайдер: письмо не уходит,
код возвращается в ответе API как dev_code (локальная разработка и
переходный период, пока не настроен почтовый ящик).
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText
from typing import Protocol

log = logging.getLogger("world.identity.emailer")

CODE_SUBJECT = "Код подтверждения — Мир Фоксинбурга"
CODE_TEXT_REGISTRATION = (
    "Здравствуйте!\n\n"
    "Ваш код подтверждения для регистрации в Мире Фоксинбурга: {code}\n\n"
    "Код действует 10 минут. Если вы не заполняли анкету — просто "
    "проигнорируйте это письмо.\n\n"
    "Языковая школа «Дашенька», Мир Фоксинбурга"
)
CODE_TEXT_RECOVERY = (
    "Здравствуйте!\n\n"
    "Ваш код для восстановления доступа к Миру Фоксинбурга: {code}\n\n"
    "Код действует 10 минут. Если вы не запрашивали восстановление — "
    "просто проигнорируйте это письмо.\n\n"
    "Языковая школа «Дашенька», Мир Фоксинбурга"
)


class ProviderError(Exception):
    """Ошибка провайдера → HTTP 502 provider_error."""


class EmailProvider(Protocol):
    def send_code(self, email: str, purpose: str, code: str) -> None:
        """Отправить код. purpose: registration|recovery (текст письма)."""


def _mask(email: str) -> str:
    """mama@example.com → m***@example.com (для логов, без утечки ящика)."""
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


class FakeEmailProvider:
    """Dev/тесты/переходный период: ничего не шлёт, только лог с маской."""

    def send_code(self, email: str, purpose: str, code: str) -> None:
        log.info("fake-email purpose=%s email=%s code=******", purpose, _mask(email))


class SmtpEmailProvider:
    def __init__(self) -> None:
        self._host = os.environ.get("WORLD_SMTP_HOST", "").strip() or "smtp.gmail.com"
        self._port = int(os.environ.get("WORLD_SMTP_PORT", "").strip() or "465")
        self._user = os.environ.get("WORLD_SMTP_USER", "").strip()
        self._password = os.environ.get("WORLD_SMTP_PASSWORD", "").strip()
        self._from = os.environ.get("WORLD_EMAIL_FROM", "").strip() or self._user
        if not (self._user and self._password):
            raise RuntimeError("WORLD_SMTP_USER/WORLD_SMTP_PASSWORD required")

    def send_code(self, email: str, purpose: str, code: str) -> None:
        template = CODE_TEXT_RECOVERY if purpose == "recovery" else CODE_TEXT_REGISTRATION
        msg = MIMEText(template.format(code=code), "plain", "utf-8")
        msg["Subject"] = CODE_SUBJECT
        msg["From"] = self._from
        msg["To"] = email
        try:
            with smtplib.SMTP_SSL(self._host, self._port, timeout=15) as server:
                server.login(self._user, self._password)
                server.sendmail(self._from, [email], msg.as_string())
        except Exception as exc:
            log.warning("smtp error email=%s: %s", _mask(email), exc)
            raise ProviderError(str(exc)) from exc


def verification_required() -> bool:
    return os.environ.get("EMAIL_VERIFICATION_REQUIRED", "0").strip() == "1"


def get_provider() -> EmailProvider:
    if verification_required() and os.environ.get("WORLD_SMTP_USER"):
        return SmtpEmailProvider()
    return FakeEmailProvider()
