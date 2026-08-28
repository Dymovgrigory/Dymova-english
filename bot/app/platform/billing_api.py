"""HTTP-контур оплат: создание инвойса из мини-аппа и вебхуки CloudPayments.

- POST /api/miniapp/account/pay — инвойс для виджета (initData-авторизация);
- POST /api/webhooks/cloudpayments/check — CloudPayments спрашивает «можно
  ли принять оплату»: отвечаем {"code": 0}, если инвойс наш;
- POST /api/webhooks/cloudpayments/pay — подтверждение оплаты (единственное
  основание считать деньги полученными);
- POST /api/webhooks/cloudpayments/fail — отказ.
"""
from __future__ import annotations

import asyncio
import logging
import urllib.parse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import miniapp_auth
from app.memory import get_store
from app.platform import analytics, bb_store, billing

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])

SIGNATURE_HEADER = "Content-HMAC-SHA256"


def _verified_identity(request: Request):
    identity = miniapp_auth.identify(
        init_data=request.headers.get("X-Miniapp-Init-Data", ""),
        platform_hint=request.headers.get("X-Miniapp-Platform", ""),
        fallback_user_id="",
    )
    if identity is None or not identity.verified:
        return None
    return identity


class PayRequest(BaseModel):
    # Сумма от клиента используется только если SUBSCRIPTION_PRICE_RUB не задан.
    amount_rub: float | None = Field(default=None, gt=0, le=500000)


def _effective_amount_rub(client_amount: float | None) -> float | None:
    from app.config import settings
    if settings.SUBSCRIPTION_PRICE_RUB > 0:
        return float(settings.SUBSCRIPTION_PRICE_RUB)
    return client_amount


@router.post("/api/miniapp/account/pay")
async def create_payment(req: PayRequest, request: Request) -> JSONResponse:
    identity = _verified_identity(request)
    if identity is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    provider = billing.get_provider()
    if not provider.configured:
        return JSONResponse(
            {"error": "payments_disabled",
             "message": "Онлайн-оплата временно недоступна — оплатите в филиале "
                        "или напишите нам."}, status_code=503)
    conv = await asyncio.to_thread(get_store().get, identity.user_id, identity.platform)
    phone = (conv.lead.phone or "").strip() if conv and conv.lead else ""
    student = await asyncio.to_thread(bb_store.find_student_by_phone, phone) if phone else None
    amount_rub = _effective_amount_rub(req.amount_rub)
    if amount_rub is None:
        return JSONResponse(
            {"error": "amount_required",
             "message": "Цена абонемента не настроена — напишите нам, выставим счёт."},
            status_code=400)
    try:
        result = provider.create_invoice(
            amount_kopecks=round(amount_rub * 100),
            phone=phone, student_id=student["id"] if student else None)
        # Т-Банк делает вызов Init (async), CloudPayments — локальный инвойс
        invoice = await result if asyncio.iscoroutine(result) else result
    except billing.BillingError as exc:
        return JSONResponse({"error": "billing_error", "message": str(exc)}, status_code=400)
    analytics.track("payment_started", source="miniapp",
                    meta={"invoice_id": invoice["invoice_id"]})
    return JSONResponse(invoice, status_code=201)


async def _cp_webhook(request: Request, action: str) -> JSONResponse:
    raw = await request.body()
    provider = billing.get_provider()
    signature = request.headers.get(SIGNATURE_HEADER, "")
    if not provider.verify_webhook_signature(raw, signature):
        logger.warning("billing: %s webhook с неверной подписью", action)
        return JSONResponse({"code": 13}, status_code=401)
    try:
        form = urllib.parse.parse_qs(raw.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError:
        return JSONResponse({"code": 13}, status_code=400)
    data = {k: v[0] for k, v in form.items()}
    invoice_id = data.get("InvoiceId", "")

    if action == "check":
        exists = billing.get_payment(invoice_id) is not None if invoice_id else False
        # code 0 — можно проводить; 10 — неверный номер заказа.
        return JSONResponse({"code": 0 if exists else 10})

    if action == "pay":
        transaction_id = data.get("TransactionId", "")
        is_new, row = billing.mark_paid(invoice_id, transaction_id, data)
        if is_new and row:
            analytics.track("payment_success", source="cloudpayments",
                            meta={"invoice_id": invoice_id})
            amount_rub = round(row["amount_kopecks"] / 100, 2)
            try:
                from app.platform import automations
                automations.schedule_payment_thankyou(
                    invoice_id=invoice_id, phone=row["phone"], amount_rub=amount_rub)
            except Exception:
                logger.exception("billing: не удалось запланировать thankyou")
            await _notify_admins(
                f"💳 Онлайн-оплата: {amount_rub} ₽\n"
                f"Телефон: {row['phone'] or '—'}, ученик: {row['student_id'] or '—'}\n"
                f"Инвойс: {invoice_id}, транзакция: {transaction_id}\n"
                f"Отразите оплату в BigBen вручную — API v1 платежи не принимает.")
            # Платное пробное: если инвойс привязан к записи — подтверждаем
            # её в CRM (лид + демо-урок) и уведомляем методиста.
            try:
                from app.platform import booking as _booking
                res = await _booking.fulfill_paid_booking(invoice_id)
                if res is not None:
                    status_line = ("запись подтверждена в CRM"
                                   if res.status in ("confirmed", "duplicate")
                                   else f"ВНИМАНИЕ: запись НЕ подтверждена ({res.error})")
                    from app.platform.public_api import _notify_staff
                    await _notify_staff(
                        f"✅ Оплаченное пробное #{res.booking_id}: {amount_rub} ₽\n"
                        f"{status_line}")
            except Exception:
                logger.exception("billing: fulfill_paid_booking упал (инвойс %s)",
                                 invoice_id)
        return JSONResponse({"code": 0})

    if action == "fail":
        billing.mark_failed(invoice_id, data)
        return JSONResponse({"code": 0})

    return JSONResponse({"code": 13}, status_code=400)


@router.post("/api/webhooks/cloudpayments/check")
async def cp_check(request: Request) -> JSONResponse:
    return await _cp_webhook(request, "check")


@router.post("/api/webhooks/cloudpayments/pay")
async def cp_pay(request: Request) -> JSONResponse:
    return await _cp_webhook(request, "pay")


@router.post("/api/webhooks/cloudpayments/fail")
async def cp_fail(request: Request) -> JSONResponse:
    return await _cp_webhook(request, "fail")


@router.post("/api/webhooks/tbank")
async def tbank_notification(request: Request) -> JSONResponse:
    """Нотификация Т-Банка: единственное основание считать деньги полученными
    — статус CONFIRMED с валидной подписью и совпадающей суммой."""
    provider = billing.get_provider()
    if provider.name != "tbank":
        return JSONResponse({"error": "provider_mismatch"}, status_code=400)
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "bad_request"}, status_code=400)
    if not provider.verify_notification(data):
        logger.warning("billing: tbank webhook с неверной подписью")
        return JSONResponse({"error": "bad_token"}, status_code=401)
    invoice_id = str(data.get("OrderId", ""))
    status = str(data.get("Status", ""))
    row = billing.get_payment(invoice_id) if invoice_id else None
    if row is None:
        return JSONResponse({"error": "unknown_order"}, status_code=404)
    if status == "CONFIRMED":
        if int(data.get("Amount", -1)) != row["amount_kopecks"]:
            logger.error("billing: tbank сумма не совпала: %s != %s (инвойс %s)",
                         data.get("Amount"), row["amount_kopecks"], invoice_id)
            return JSONResponse({"error": "amount_mismatch"}, status_code=400)
        is_new, row = billing.mark_paid(invoice_id, str(data.get("PaymentId", "")), data)
        if is_new and row:
            analytics.track("payment_success", source="tbank",
                            meta={"invoice_id": invoice_id})
            amount_rub = round(row["amount_kopecks"] / 100, 2)
            try:
                from app.platform import automations
                automations.schedule_payment_thankyou(
                    invoice_id=invoice_id, phone=row["phone"], amount_rub=amount_rub)
            except Exception:
                logger.exception("billing: не удалось запланировать thankyou")
            await _notify_admins(
                f"💳 Онлайн-оплата (Т-Банк): {amount_rub} ₽\n"
                f"Телефон: {row['phone'] or '—'}, ученик: {row['student_id'] or '—'}\n"
                f"Инвойс: {invoice_id}, платёж: {data.get('PaymentId')}\n"
                f"Отразите оплату в BigBen вручную — API v1 платежи не принимает.")
    elif status in ("REJECTED", "CANCELED", "DEADLINE_EXPIRED"):
        billing.mark_failed(invoice_id, data)
    return JSONResponse({"ok": True})


async def _notify_admins(text: str) -> None:
    from app.config import settings
    from app.max_client import get_max
    client = get_max()
    if not client.configured:
        return
    for admin_id in settings.admin_ids:
        try:
            await client.send_message(admin_id, text)
        except Exception:
            logger.exception("billing: не удалось уведомить админа %s", admin_id)
