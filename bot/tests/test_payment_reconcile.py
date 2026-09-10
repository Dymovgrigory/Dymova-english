"""Серверная сверка оплат: платёж подтверждается, даже если клиент ушёл.

Инцидент 2026-09-08 (заявка #11, 1125 ₽): клиентка оплатила картой, ушла со
страницы дольше чем на 30 секунд клиентского поллинга, HTTP-нотификация в ЛК
Т-Банка не настроена — платёж CONFIRMED в банке, а бронь навсегда осталась
в awaiting_payment: ни лида, ни ученика, ни демо-урока, ни уведомления.
Единственная защита, не зависящая ни от браузера, ни от ЛК банка, —
фоновая сверка незакрытых инвойсов со статусом у провайдера.
"""
from __future__ import annotations

import datetime as _dt

import pytest
from fastapi.testclient import TestClient

from app.platform import bb_store, billing, booking, reconcile


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("app.config.settings.BIGBEN_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.DIGEST_ENABLED", False)
    monkeypatch.setattr("app.config.settings.NUDGE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.SITE_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.WATCHDOG_ENABLED", False)
    monkeypatch.setattr("app.config.settings.TELEGRAM_POLLING", False)
    monkeypatch.setattr("app.config.settings.BILLING_PROVIDER", "tbank")
    monkeypatch.setattr("app.config.settings.TBANK_ENABLED", True)
    monkeypatch.setattr("app.config.settings.TBANK_TERMINAL_KEY", "1726756291526")
    monkeypatch.setattr("app.config.settings.TBANK_PASSWORD", "pwd")
    monkeypatch.setattr("app.config.settings.TRIAL_PAID", True)
    monkeypatch.setattr("app.config.settings.TRIAL_PRICE_60_RUB", 1125)
    bb_store._local.conn = None
    from app.main import app
    with TestClient(app) as c:
        yield c


def _seed() -> None:
    day = (_dt.date.today() + _dt.timedelta(days=10)).isoformat()
    bb_store.upsert_group({"id": 1, "caption": "My Level 1 Пн/Ср 11:00",
                           "capacity": 8, "occupied": 2, "free_slots": 6,
                           "overbooked": False,
                           "filial": {"id": 10, "caption": "Фоксинбург Лихачевский"},
                           "auditory": {"id": 1, "caption": "1"}, "schedule": []})
    bb_store.upsert_lesson({"id": 55, "date": day,
                            "starts_at": day + "T11:00:00+03:00",
                            "ends_at": day + "T12:00:00+03:00",
                            "group": {"id": 1, "caption": "My Level 1"},
                            "filial": {"id": 10, "caption": "Фоксинбург Лихачевский"}})


async def _fresh(gid):
    return {"id": gid, "caption": "My Level 1", "capacity": 8, "occupied": 2,
            "free_slots": 6, "filial": {"id": 10, "caption": "Ф"}}


def _crm(monkeypatch) -> dict:
    """Заглушки CRM: считаем создания лида и демо-урока."""
    from app.platform.bigben_v2 import get_bigben_v2
    calls = {"lead": 0, "demo": 0}

    async def _lead(**kw):
        calls["lead"] += 1
        return {"id": 900}

    async def _demo(**kw):
        calls["demo"] += 1
        return {"id": 800}

    monkeypatch.setattr(get_bigben_v2(), "create_lead", _lead, raising=False)
    monkeypatch.setattr(get_bigben_v2(), "create_demo_lesson", _demo, raising=False)
    monkeypatch.setattr(booking, "_schedule_reminders", lambda *a, **k: None)
    return calls


def _awaiting(monkeypatch, invoice_id: str = "inv-1") -> int:
    """Бронь в awaiting_payment с выставленным инвойсом — как после Init."""
    monkeypatch.setattr(booking, "_fresh_group", _fresh)
    booking_id, _ = bb_store.create_booking(
        parent_name="Ольга", phone="+79852529596", child_name="Пётр",
        child_age="", comment="", source="site-schedule", group_id=1,
        lesson_id=55, filial_id=10, idempotency_key=f"idem-{invoice_id}")
    billing._db().execute(
        "INSERT INTO billing_payments (invoice_id, created_at, amount_kopecks,"
        " phone, description, transaction_id) VALUES (?,?,?,?,?,?)",
        (invoice_id, billing._now(), 112500, "+79852529596", "Пробное", "9206037272"))
    billing._db().commit()
    bb_store.set_booking_awaiting_payment(booking_id, invoice_id,
                                          amount_kopecks=112500)
    return booking_id


def _state(monkeypatch, status: str) -> None:
    async def _get_state(self, payment_id):
        return {"Success": True, "Status": status, "PaymentId": "9206037272",
                "OrderId": "inv-1", "Amount": 112500}
    monkeypatch.setattr(billing.TBankProvider, "get_state", _get_state)


@pytest.mark.asyncio
async def test_reconcile_confirms_payment_when_client_left_page(client, monkeypatch):
    """Ровно инцидент #11: браузер закрыт, вебхука нет — сверка спасает запись."""
    _seed()
    crm = _crm(monkeypatch)
    booking_id = _awaiting(monkeypatch)
    _state(monkeypatch, "CONFIRMED")

    stats = await reconcile.reconcile_pending_payments()

    assert stats["confirmed"] == 1
    row = bb_store.booking_by_id(booking_id)
    assert row["status"] == "confirmed"
    assert row["demo_lesson_id"] == 800
    assert billing.get_payment("inv-1")["status"] == "paid"
    assert crm["demo"] == 1


@pytest.mark.asyncio
async def test_reconcile_is_idempotent(client, monkeypatch):
    """Повторный прогон не создаёт второй лид/демо и не шлёт второе спасибо."""
    _seed()
    crm = _crm(monkeypatch)
    _awaiting(monkeypatch)
    _state(monkeypatch, "CONFIRMED")

    await reconcile.reconcile_pending_payments()
    stats = await reconcile.reconcile_pending_payments()

    assert stats["confirmed"] == 0
    assert crm["demo"] == 1


@pytest.mark.asyncio
async def test_reconcile_marks_rejected_as_failed(client, monkeypatch):
    """Отказ банка закрывает бронь, а не держит место вечно."""
    _seed()
    _crm(monkeypatch)
    booking_id = _awaiting(monkeypatch)
    _state(monkeypatch, "REJECTED")

    stats = await reconcile.reconcile_pending_payments()

    assert stats["failed"] == 1
    assert bb_store.booking_by_id(booking_id)["status"] == "failed"
    assert billing.get_payment("inv-1")["status"] == "failed"


@pytest.mark.asyncio
async def test_reconcile_leaves_pending_alone(client, monkeypatch):
    """Клиент ещё не заплатил — бронь ждёт, ничего в CRM не уходит."""
    _seed()
    crm = _crm(monkeypatch)
    booking_id = _awaiting(monkeypatch)
    _state(monkeypatch, "NEW")

    stats = await reconcile.reconcile_pending_payments()

    assert stats == {"checked": 1, "confirmed": 0, "failed": 0, "refulfilled": 0}
    assert bb_store.booking_by_id(booking_id)["status"] == "awaiting_payment"
    assert crm["demo"] == 0


@pytest.mark.asyncio
async def test_reconcile_retries_paid_unfulfilled(client, monkeypatch):
    """Деньги получены, но CRM тогда лежала — доводим запись до конца."""
    _seed()
    crm = _crm(monkeypatch)
    booking_id = _awaiting(monkeypatch)
    billing.mark_paid("inv-1", "9206037272", {"Status": "CONFIRMED"})
    bb_store.mark_booking_paid_unfulfilled(booking_id)

    stats = await reconcile.reconcile_pending_payments()

    assert stats["refulfilled"] == 1
    assert bb_store.booking_by_id(booking_id)["status"] == "confirmed"
    assert crm["demo"] == 1


@pytest.mark.asyncio
async def test_reconcile_skips_stale_invoices(client, monkeypatch):
    """Инвойсы старше окна сверки не дёргают банк без нужды."""
    _seed()
    _crm(monkeypatch)
    _awaiting(monkeypatch)
    old = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=30)).isoformat()
    billing._db().execute(
        "UPDATE billing_payments SET created_at=? WHERE invoice_id='inv-1'", (old,))
    billing._db().commit()

    calls = {"n": 0}

    async def _get_state(self, payment_id):
        calls["n"] += 1
        return {"Success": True, "Status": "CONFIRMED"}

    monkeypatch.setattr(billing.TBankProvider, "get_state", _get_state)

    stats = await reconcile.reconcile_pending_payments(max_age_hours=168)

    assert stats["checked"] == 0
    assert calls["n"] == 0


def test_cp_find_payment_uses_post(client, monkeypatch):
    """CloudPayments /payments/find принимает только POST: GET молча
    возвращал «Only POST method allowed» — запасной канал CP не работал."""
    import asyncio

    import httpx as _httpx

    monkeypatch.setattr("app.config.settings.CLOUDPAYMENTS_ENABLED", True)
    monkeypatch.setattr("app.config.settings.CLOUDPAYMENTS_PUBLIC_ID", "pk")
    monkeypatch.setattr("app.config.settings.CLOUDPAYMENTS_API_SECRET", "s")
    seen = {}

    class _Client:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, **kw):
            seen["url"] = url
            seen["json"] = json

            class _R:
                @staticmethod
                def json():
                    return {"Success": True, "Model": {"Status": "Completed"}}
            return _R()

        async def get(self, *a, **kw):
            raise AssertionError("CloudPayments find требует POST, не GET")

    monkeypatch.setattr(_httpx, "AsyncClient", _Client)
    model = asyncio.run(billing.cp_find_payment("inv-cp"))

    assert model == {"Status": "Completed"}
    assert seen["url"].endswith("/payments/find")
    assert seen["json"] == {"InvoiceId": "inv-cp"}


def test_receipt_taxation_matches_patent(monkeypatch):
    """ИП школы на патенте: в чеке система налогообложения — patent,
    ставка НДС — none («без НДС»)."""
    monkeypatch.setattr("app.config.settings.TBANK_TAXATION", "patent")
    receipt = billing.TBankProvider()._receipt(
        amount_kopecks=112500, phone="+79852529596", description="Пробное")

    assert receipt["Taxation"] == "patent"
    assert receipt["Items"][0]["Tax"] == "none"
