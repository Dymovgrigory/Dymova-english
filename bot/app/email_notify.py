"""Email-уведомления о новых заявках через Gmail SMTP (App Password).

Нужен для миграции сайта с Tilda: раньше письма на dymovgrigory@gmail.com и
kidsfoxclub@yandex.ru отправляла сама Tilda через встроенный сервис приёма
данных форм. Готового email-механизма в боте не было — добавлен здесь.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def send_lead_email(subject: str, body: str) -> bool:
    """Синхронная отправка (вызывать через asyncio.to_thread из async-кода)."""
    if not (settings.GMAIL_SMTP_USER and settings.GMAIL_SMTP_APP_PASSWORD and settings.LEAD_NOTIFY_EMAILS):
        logger.info("email: not configured, skipping lead notification")
        return False
    recipients = [x.strip() for x in settings.LEAD_NOTIFY_EMAILS.split(",") if x.strip()]
    if not recipients:
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.GMAIL_SMTP_USER
    msg["To"] = ", ".join(recipients)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(settings.GMAIL_SMTP_USER, settings.GMAIL_SMTP_APP_PASSWORD)
            server.sendmail(settings.GMAIL_SMTP_USER, recipients, msg.as_string())
        return True
    except Exception:
        logger.exception("email: failed to send lead notification")
        return False
