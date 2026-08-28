"""Billing: абстракция провайдера + CloudPayments (онлайн-касса школы).

Модель доверия (§43/47 мандата):
- «успешная» страница/редирект оплаты НЕ является подтверждением;
- подтверждение — только webhook pay от CloudPayments с валидной подписью
  (X-Content-HMAC-SHA256 = base64(HMAC_SHA256(raw_body, api_secret)));
- зачисление идемпотентно по TransactionId — повторный webhook не начислит
  дважды и не отправит второе «спасибо».

BigBen API v1 не умеет создавать счета/платежи, поэтому факт оплаты мы
фиксируем локально (billing_payments) и уведомляем администраторов —
менеджер отражает оплату в CRM вручную. Когда в API появится запись
платежей — добавим синхронизацию туда же, провайдер менять не придётся.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)

_local = threading.local()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS billing_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL UNIQUE,
    transaction_id TEXT UNIQUE,
    created_at TEXT NOT NULL,
    paid_at TEXT,
    status TEXT NOT NULL DEFAULT 'created',
    amount_kopecks INTEGER NOT NULL,
    student_id INTEGER,
    phone TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL DEFAULT '{}'
);
"""


def _db() -> sqlite3.Connection:
    from app.platform import bb_store  # та же база, что и read-model
    conn = bb_store._db()
    conn.executescript(_SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BillingError(Exception):
    pass


class CloudPaymentsProvider:
    """Онлайн-оплата через CloudPayments (виджет + вебхуки check/pay/fail)."""

    name = "cloudpayments"

    @property
    def configured(self) -> bool:
        return bool(settings.CLOUDPAYMENTS_ENABLED
                    and settings.CLOUDPAYMENTS_PUBLIC_ID
                    and settings.CLOUDPAYMENTS_API_SECRET)

    def create_invoice(self, *, amount_kopecks: int, phone: str = "",
                       student_id: int | None = None,
                       description: str = "") -> dict:
        """Создаёт локальный инвойс и возвращает параметры для виджета CP.

        Сумма виджету — в рублях с копейками (decimal), храним копейки int.
        """
        if not self.configured:
            raise BillingError("CloudPayments не сконфигурирован")
        if amount_kopecks <= 0:
            raise BillingError("Сумма должна быть положительной")
        invoice_id = uuid.uuid4().hex[:20]
        _db().execute(
            "INSERT INTO billing_payments (invoice_id, created_at, amount_kopecks,"
            " student_id, phone, description) VALUES (?,?,?,?,?,?)",
            (invoice_id, _now(), amount_kopecks, student_id, phone,
             description or settings.CLOUDPAYMENTS_DESCRIPTION))
        _db().commit()
        return {
            "invoice_id": invoice_id,
            "widget": {
                "publicId": settings.CLOUDPAYMENTS_PUBLIC_ID,
                "amount": round(amount_kopecks / 100, 2),
                "currency": "RUB",
                "invoiceId": invoice_id,
                "accountId": phone or (str(student_id) if student_id else ""),
                "description": description or settings.CLOUDPAYMENTS_DESCRIPTION,
            },
        }

    def verify_webhook_signature(self, raw_body: bytes, signature_b64: str) -> bool:
        if not settings.CLOUDPAYMENTS_API_SECRET or not signature_b64:
            return False
        digest = hmac.new(settings.CLOUDPAYMENTS_API_SECRET.encode(),
                          raw_body, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode()
        return hmac.compare_digest(expected, signature_b64)


def get_provider() -> CloudPaymentsProvider:
    return CloudPaymentsProvider()


# --- учёт оплат (идемпотентно) ---

def mark_paid(invoice_id: str, transaction_id: str, raw: dict) -> tuple[bool, dict | None]:
    """Фиксирует оплату. Возвращает (is_new, row). Повтор — (False, row)."""
    db = _db()
    row = db.execute("SELECT * FROM billing_payments WHERE invoice_id=?",
                     (invoice_id,)).fetchone()
    if row is None:
        logger.warning("billing: pay webhook по неизвестному invoice %s", invoice_id)
        return False, None
    if row["status"] == "paid":
        return False, dict(row)
    db.execute(
        "UPDATE billing_payments SET status='paid', transaction_id=?, paid_at=?,"
        " raw_json=? WHERE invoice_id=? AND status!='paid'",
        (transaction_id, _now(), json.dumps(raw, ensure_ascii=False)[:4000], invoice_id))
    db.commit()
    row = db.execute("SELECT * FROM billing_payments WHERE invoice_id=?",
                     (invoice_id,)).fetchone()
    return True, dict(row)


def mark_failed(invoice_id: str, raw: dict) -> None:
    _db().execute(
        "UPDATE billing_payments SET status='failed', raw_json=? WHERE invoice_id=?",
        (json.dumps(raw, ensure_ascii=False)[:4000], invoice_id))
    _db().commit()


def get_payment(invoice_id: str) -> dict | None:
    row = _db().execute("SELECT * FROM billing_payments WHERE invoice_id=?",
                        (invoice_id,)).fetchone()
    return dict(row) if row else None
