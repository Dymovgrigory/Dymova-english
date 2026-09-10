"""Сверка оплат: последняя линия обороны денег клиента.

Подтверждение оплаты может не дойти двумя штатными путями сразу:
HTTP-нотификация провайдера (URL может быть не прописан или недоступен) и
поллинг из открытой вкладки клиента (человек уходит в приложение банка и
не возвращается). Тогда деньги у банка, а бронь висит в awaiting_payment:
ни лида, ни ученика, ни демо-урока, ни уведомления менеджеру.

Сверка ни от браузера, ни от ЛК банка не зависит: она периодически
спрашивает провайдера об исходе каждого незакрытого инвойса и доводит
запись до конца тем же обработчиком, что и вебхук. Идемпотентность —
на mark_paid: повторное подтверждение сюда просто не доходит.

Здесь же добираются брони paid_unfulfilled — деньги получены, но CRM в тот
момент была недоступна.
"""
from __future__ import annotations

import logging

from app.config import settings
from app.platform import bb_store, billing, booking

logger = logging.getLogger(__name__)


async def reconcile_pending_payments(*, max_age_hours: int | None = None,
                                     limit: int = 100) -> dict:
    """Один проход сверки. Возвращает счётчики для журнала и алертов."""
    max_age_hours = (max_age_hours if max_age_hours is not None
                     else settings.BILLING_RECONCILE_MAX_AGE_HOURS)
    stats = {"checked": 0, "confirmed": 0, "failed": 0, "refulfilled": 0}

    for row in billing.list_unresolved_invoices(max_age_hours=max_age_hours,
                                                limit=limit):
        invoice_id = row["invoice_id"]
        try:
            remote = await billing.fetch_remote_state(invoice_id)
        except Exception:
            logger.exception("reconcile: провайдер не ответил по инвойсу %s",
                             invoice_id)
            continue
        if remote is None:
            continue
        state, txn, raw = remote
        stats["checked"] += 1
        if state == "paid":
            is_new, _row = billing.mark_paid(invoice_id, txn, raw)
            if not is_new:
                continue
            logger.warning(
                "reconcile: оплата инвойса %s не дошла ни вебхуком, ни поллингом "
                "— подтверждаем сверкой", invoice_id)
            await booking.handle_payment_confirmed(
                invoice_id, source=f"{settings.BILLING_PROVIDER}-reconcile")
            stats["confirmed"] += 1
        elif state == "failed":
            billing.mark_failed(invoice_id, raw)
            booked = bb_store.booking_by_invoice(invoice_id)
            if booked and booked.get("status") == "awaiting_payment":
                bb_store.fail_booking(booked["id"], "payment_failed_reconcile")
            stats["failed"] += 1

    stats["refulfilled"] = await _retry_paid_unfulfilled()
    return stats


async def _retry_paid_unfulfilled() -> int:
    """Брони с полученными деньгами, которые не удалось записать в CRM."""
    rows = bb_store._rows(
        "SELECT * FROM bookings WHERE status='paid_unfulfilled'"
        " AND invoice_id IS NOT NULL ORDER BY id DESC LIMIT 50")
    done = 0
    for row in rows:
        try:
            result = await booking.fulfill_paid_booking(row["invoice_id"])
        except Exception:
            logger.exception("reconcile: не удалось довести бронь %s", row["id"])
            continue
        if result is not None and result.status in ("confirmed", "duplicate"):
            done += 1
    return done


async def alerts() -> list[dict]:
    """Оплаченные деньги без записи в CRM — в Alert Center админки."""
    stuck = bb_store._rows(
        "SELECT b.id, b.phone, b.parent_name, b.invoice_id FROM bookings b"
        " JOIN billing_payments p ON p.invoice_id = b.invoice_id"
        " WHERE p.status='paid' AND b.status NOT IN ('confirmed','duplicate')")
    if not stuck:
        return []
    return [{
        "level": "critical",
        "code": "paid_booking_unfulfilled",
        "text": (f"Оплачено, но не оформлено в CRM: {len(stuck)} заявк(и) — "
                 + ", ".join(f"#{r['id']} {r['parent_name']} {r['phone']}"
                             for r in stuck[:5])),
    }]
