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
            "provider": "cloudpayments",
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


class TBankProvider:
    """Онлайн-оплата через Т-Банк (securepay API v2).

    Инвойс — вызов Init (OrderId = наш invoice_id), клиенту отдаём PaymentURL.
    Подпись: sha256 от конкатенации значений параметров (отсортированных по
    ключу) + пароль терминала — и для запроса, и для проверки нотификации.
    Суммы — копейки int по всей цепочке.
    """

    name = "tbank"

    @property
    def configured(self) -> bool:
        return bool(settings.TBANK_ENABLED
                    and settings.TBANK_TERMINAL_KEY
                    and settings.TBANK_PASSWORD)

    @staticmethod
    def _token(params: dict) -> str:
        """Подпись Т-Банка: пароль участвует как параметр Password, все
        скалярные значения сортируются по имени ключа и конкатенируются
        (проверено на боевом терминале: иная схема даёт ошибку 204)."""
        def _norm(v):
            # В подписи нотификаций булевы значения — строчными ("true"/"false")
            if v is True:
                return "true"
            if v is False:
                return "false"
            return str(v)
        merged = {k: _norm(v) for k, v in params.items()
                  if k != "Token" and not isinstance(v, (dict, list))}
        merged["Password"] = settings.TBANK_PASSWORD
        raw = "".join(merged[k] for k in sorted(merged))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def create_invoice_local(self, *, amount_kopecks: int, phone: str = "",
                             student_id: int | None = None,
                             description: str = "") -> str:
        """Локальная запись инвойса (OrderId) до вызова Init."""
        if amount_kopecks <= 0:
            raise BillingError("Сумма должна быть положительной")
        invoice_id = uuid.uuid4().hex[:20]
        _db().execute(
            "INSERT INTO billing_payments (invoice_id, created_at, amount_kopecks,"
            " student_id, phone, description) VALUES (?,?,?,?,?,?)",
            (invoice_id, _now(), amount_kopecks, student_id, phone,
             description or settings.CLOUDPAYMENTS_DESCRIPTION))
        _db().commit()
        return invoice_id

    def _receipt(self, *, amount_kopecks: int, phone: str,
                 description: str) -> dict:
        """Фискальный чек — терминал школы требует его в каждом Init
        (без Receipt отвечает ошибкой 309)."""
        receipt: dict = {
            "Taxation": settings.TBANK_TAXATION,
            "Items": [{
                "Name": (description or settings.CLOUDPAYMENTS_DESCRIPTION)[:128],
                "Price": amount_kopecks,
                "Quantity": 1,
                "Amount": amount_kopecks,
                "Tax": settings.TBANK_ITEM_TAX,
                "PaymentMethod": "full_payment",
                "PaymentObject": "service",
            }],
        }
        if phone:
            receipt["Phone"] = phone
        elif settings.TBANK_RECEIPT_EMAIL:
            receipt["Email"] = settings.TBANK_RECEIPT_EMAIL
        else:
            raise BillingError(
                "Для чека нужен телефон клиента или TBANK_RECEIPT_EMAIL")
        return receipt

    async def _api(self, method: str, params: dict) -> dict:
        params = dict(params)
        params["TerminalKey"] = settings.TBANK_TERMINAL_KEY
        params["Token"] = self._token(params)
        import httpx
        async with httpx.AsyncClient(timeout=15, verify=_tbank_verify()) as client:
            resp = await client.post(f"{settings.TBANK_API_BASE}/v2/{method}",
                                     json=params)
        return resp.json()

    async def create_invoice(self, *, amount_kopecks: int, phone: str = "",
                             student_id: int | None = None,
                             description: str = "") -> dict:
        if not self.configured:
            raise BillingError("Т-Банк не сконфигурирован")
        invoice_id = self.create_invoice_local(
            amount_kopecks=amount_kopecks, phone=phone,
            student_id=student_id, description=description)
        params = {
            "Amount": amount_kopecks,
            "OrderId": invoice_id,
            "Description": (description or settings.CLOUDPAYMENTS_DESCRIPTION)[:140],
            "Receipt": self._receipt(amount_kopecks=amount_kopecks,
                                     phone=phone, description=description),
        }
        try:
            data = await self._api("Init", params)
        except Exception as exc:
            raise BillingError(f"Т-Банк недоступен: {exc}") from exc
        if not data.get("Success"):
            raise BillingError(
                f"Т-Банк отклонил инвойс: {data.get('Message') or data.get('Details') or data.get('ErrorCode')}")
        payment_id = data.get("PaymentId")
        payment_url = data.get("PaymentURL", "")
        sbp_url, sbp_qr_svg = "", ""
        try:  # СБП-линк (deeplink qr.nspk.ru) — главный способ оплаты
            qr = await self._api("GetQr", {"PaymentId": payment_id,
                                           "DataType": "PAYLOAD"})
            if qr.get("Success"):
                sbp_url = qr.get("Data", "")
        except Exception:
            logger.warning("tbank: GetQr PAYLOAD не удался", exc_info=True)
        try:  # QR-картинка (SVG) — для оплаты с десктопа
            qr_img = await self._api("GetQr", {"PaymentId": payment_id,
                                               "DataType": "IMAGE"})
            if qr_img.get("Success"):
                sbp_qr_svg = qr_img.get("Data", "")
        except Exception:
            logger.warning("tbank: GetQr IMAGE не удался", exc_info=True)
        # Реквизиты платежа — для повторной выдачи (дубль заявки) и поллинга.
        _db().execute(
            "UPDATE billing_payments SET transaction_id=?, raw_json=?"
            " WHERE invoice_id=?",
            (str(payment_id or ""),
             json.dumps({"payment_id": payment_id, "payment_url": payment_url,
                         "sbp_url": sbp_url, "sbp_qr_svg": sbp_qr_svg},
                        ensure_ascii=False)[:4000], invoice_id))
        _db().commit()
        return {"invoice_id": invoice_id, "provider": "tbank",
                "payment_url": payment_url,
                "sbp_url": sbp_url, "sbp_qr_svg": sbp_qr_svg}

    async def get_state(self, payment_id) -> dict | None:
        """Статус платежа (GetState) — запасной канал к вебхуку."""
        try:
            data = await self._api("GetState", {"PaymentId": payment_id})
        except Exception as exc:
            logger.warning("tbank: GetState недоступен: %s", exc)
            return None
        return data if data.get("Success") else None

    def verify_notification(self, data: dict) -> bool:
        """Проверка подписи нотификации Т-Банка."""
        token = data.get("Token", "")
        if not token or not settings.TBANK_PASSWORD:
            return False
        expected = self._token(data)
        return hmac.compare_digest(expected.lower(), token.lower())




async def cp_find_payment(invoice_id: str) -> dict | None:
    """Статус платежа по InvoiceId напрямую из CloudPayments API.

    Запасной канал подтверждения, если вебхук ещё не настроен в ЛК CP:
    polling из /api/platform/booking/{id}. Вебхук остаётся основным.
    """
    import httpx
    if not (settings.CLOUDPAYMENTS_ENABLED and settings.CLOUDPAYMENTS_PUBLIC_ID
            and settings.CLOUDPAYMENTS_API_SECRET):
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.CLOUDPAYMENTS_API_BASE}/payments/find",
                params={"InvoiceId": invoice_id},
                auth=(settings.CLOUDPAYMENTS_PUBLIC_ID,
                      settings.CLOUDPAYMENTS_API_SECRET))
        data = resp.json()
    except Exception as exc:
        logger.warning("billing: CP find недоступен для %s: %s", invoice_id, exc)
        return None
    if not data.get("Success"):
        return None
    return data.get("Model")


async def tbank_find_payment(invoice_id: str) -> dict | None:
    """Статус платежа напрямую из Т-Банка (запасной канал к вебхуку):
    polling из /api/platform/booking/{id}. Вебхук остаётся основным."""
    if not settings.TBANK_ENABLED:
        return None
    row = get_payment(invoice_id)
    if not row:
        return None
    payment_id = (row.get("transaction_id") or "").strip()
    if not payment_id:
        try:
            raw = json.loads(row.get("raw_json") or "{}")
        except ValueError:
            raw = {}
        payment_id = str(raw.get("payment_id") or "")
    if not payment_id:
        return None
    return await TBankProvider().get_state(payment_id)


def _tbank_verify():
    """CA для Т-Банка: certifi + Russian Trusted Root CA (Минцифры).

    Сервер Т-Банка отдаёт национальную цепочку, которой нет в certifi.
    Бандл собирается лениво в каталоге данных; при отсутствии корневого
    сертификата в образе — обычная верификация (упадёт с понятной ошибкой).
    """
    import certifi
    from pathlib import Path
    bundle = settings.TBANK_CA_BUNDLE
    if bundle and Path(bundle).exists():
        return bundle
    rca = Path(__file__).resolve().parents[2] / "deploy" / "certs" / "russian_trusted_root_ca.pem"
    if not rca.exists():
        return True
    out = Path(certifi.where()).with_name("tbank-ca-bundle.pem")
    try:
        if not out.exists() or out.stat().st_mtime < rca.stat().st_mtime:
            out.write_text(Path(certifi.where()).read_text() + rca.read_text(),
                           encoding="utf-8")
        return str(out)
    except OSError:
        return True


def get_provider():
    if settings.BILLING_PROVIDER == "tbank":
        return TBankProvider()
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


def list_payments_by_phone(phone: str, limit: int = 50) -> list[dict]:
    """Инвойсы CloudPayments по телефону (нормализация по последним 10 цифрам)."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())[-10:]
    if not digits:
        return []
    conn = _db()
    rows = conn.execute(
        "SELECT * FROM billing_payments ORDER BY id DESC LIMIT 1000").fetchall()
    out = [dict(r) for r in rows
           if "".join(ch for ch in (dict(r).get("phone") or "") if ch.isdigit())[-10:] == digits]
    return out[:limit]


def get_payment(invoice_id: str) -> dict | None:
    row = _db().execute("SELECT * FROM billing_payments WHERE invoice_id=?",
                        (invoice_id,)).fetchone()
    return dict(row) if row else None
