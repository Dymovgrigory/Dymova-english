"""Автоматическая запись дохода в CRM после подтверждённой онлайн-оплаты.

BigBen Public API v1 платежи создавать не умеет — только читает. Внутренний
API пульта умеет: POST /user/payments (счёт) + POST /user/incomes (касса).
До этого доход школа заводила руками по уведомлению, и любая забытая
оплата не попадала в кассу вовсе.
"""
from __future__ import annotations

import datetime as _dt

import pytest
from fastapi.testclient import TestClient

from app.platform import bb_store, bigben_internal, billing, booking


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("app.config.settings.BIGBEN_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.DIGEST_ENABLED", False)
    monkeypatch.setattr("app.config.settings.NUDGE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.SITE_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.WATCHDOG_ENABLED", False)
    monkeypatch.setattr("app.config.settings.TELEGRAM_POLLING", False)
    monkeypatch.setattr("app.config.settings.BILLING_RECONCILE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.BIGBEN_INTERNAL_TOKEN", "tok")
    monkeypatch.setattr("app.config.settings.CRM_AUTO_INCOME_ENABLED", True)
    monkeypatch.setattr("app.config.settings.TRIAL_PAID", True)
    bb_store._local.conn = None
    from app.main import app
    with TestClient(app) as c:
        yield c


def _seed() -> None:
    day = (_dt.date.today() + _dt.timedelta(days=10)).isoformat()
    bb_store.upsert_group({"id": 1, "caption": "My Level 1 Пн/Ср 11:00",
                           "capacity": 8, "occupied": 2, "free_slots": 6,
                           "overbooked": False,
                           "filial": {"id": 13296, "caption": "Лихачевский"},
                           "auditory": {"id": 1, "caption": "1"}, "schedule": []})
    bb_store.upsert_lesson({"id": 55, "date": day,
                            "starts_at": day + "T11:00:00+03:00",
                            "ends_at": day + "T12:00:00+03:00",
                            "group": {"id": 1, "caption": "My Level 1"},
                            "filial": {"id": 13296, "caption": "Лихачевский"}})


async def _fresh(gid):
    return {"id": gid, "caption": "My Level 1", "capacity": 8, "occupied": 2,
            "free_slots": 6, "filial": {"id": 13296, "caption": "Лихачевский"}}


def _paid_booking(monkeypatch, calls: dict) -> str:
    """Оплаченная бронь с карточкой ученика — как после подтверждения оплаты."""
    monkeypatch.setattr(booking, "_fresh_group", _fresh)
    monkeypatch.setattr(booking, "_schedule_reminders", lambda *a, **k: None)

    async def _student(**kw):
        return {"id": 1197608}

    async def _demo(**kw):
        return {"id": 800}

    async def _payment(**kw):
        calls.setdefault("payments", []).append(kw)
        return {"payment_id": 23606531}

    async def _income(**kw):
        calls.setdefault("incomes", []).append(kw)
        return {"id": 1705976}

    async def _settle(**kw):
        calls.setdefault("settles", []).append(kw)
        return {"success": True}

    monkeypatch.setattr(bigben_internal, "find_or_create_student", _student)
    monkeypatch.setattr(bigben_internal, "create_payment", _payment, raising=False)
    monkeypatch.setattr(bigben_internal, "create_income", _income, raising=False)
    monkeypatch.setattr(bigben_internal, "settle_payment_full", _settle, raising=False)
    from app.platform.bigben_v2 import get_bigben_v2
    monkeypatch.setattr(get_bigben_v2(), "create_demo_lesson", _demo, raising=False)

    booking_id, _ = bb_store.create_booking(
        parent_name="Ольга", phone="+79852529596", child_name="Пётр",
        child_age="", comment="", source="site-schedule", group_id=1,
        lesson_id=55, filial_id=13296, idempotency_key="idem-income")
    billing._db().execute(
        "INSERT INTO billing_payments (invoice_id, created_at, amount_kopecks,"
        " phone, description) VALUES (?,?,?,?,?)",
        ("inv-i", billing._now(), 112500, "+79852529596", "Пробное"))
    billing._db().commit()
    bb_store.set_booking_awaiting_payment(booking_id, "inv-i", amount_kopecks=112500)
    billing.mark_paid("inv-i", "9206037272", {"Status": "CONFIRMED"})
    return "inv-i"


@pytest.mark.asyncio
async def test_confirmed_payment_creates_paid_invoice(client, monkeypatch):
    """Подтверждённая оплата → счёт в карточке ученика, сразу проведённый.

    Доход в кассу создаёт сама CRM при проведении — руками его писать
    нельзя, иначе деньги задвоятся.
    """
    _seed()
    calls: dict = {}
    invoice = _paid_booking(monkeypatch, calls)

    await booking.handle_payment_confirmed(invoice, source="tbank")

    assert len(calls["payments"]) == 1
    pay = calls["payments"][0]
    assert pay["user_id"] == 1197608 and pay["group_id"] == 1
    assert pay["summ"] == 1125
    assert pay["bycard"] == 2, "способ оплаты — «Онлайн», не «Из приложения»"

    assert len(calls["settles"]) == 1
    assert calls["settles"][0]["payment_id"] == 23606531
    assert calls["settles"][0]["paydate"]

    assert calls.get("incomes") is None, "доход создаёт CRM, иначе задвоение"
    assert billing.get_payment(invoice)["crm_payment_id"] == 23606531


@pytest.mark.asyncio
async def test_unsettled_invoice_is_not_left_behind(client, monkeypatch):
    """Если провести не удалось — счёт удаляем: неоплаченный счёт выглядит
    как долг ученика, а деньги школа уже получила."""
    _seed()
    calls: dict = {}
    invoice = _paid_booking(monkeypatch, calls)

    async def _settle_fails(**kw):
        raise bigben_internal.BigBenInternalError("500")

    async def _delete(**kw):
        calls.setdefault("deletes", []).append(kw)
        return {"success": True}

    monkeypatch.setattr(bigben_internal, "settle_payment_full", _settle_fails,
                        raising=False)
    monkeypatch.setattr(bigben_internal, "delete_payment", _delete, raising=False)

    await booking.handle_payment_confirmed(invoice, source="tbank")

    assert calls["deletes"][0]["payment_id"] == 23606531
    assert billing.get_payment(invoice)["crm_payment_id"] is None
    assert bb_store.booking_by_invoice(invoice)["status"] == "confirmed"


@pytest.mark.asyncio
async def test_income_is_not_written_twice(client, monkeypatch):
    """Повторная обработка того же инвойса не задваивает деньги в кассе."""
    _seed()
    calls: dict = {}
    invoice = _paid_booking(monkeypatch, calls)

    await booking.handle_payment_confirmed(invoice, source="tbank")
    await booking.record_crm_income(invoice)

    assert len(calls["payments"]) == 1
    assert len(calls["settles"]) == 1


@pytest.mark.asyncio
async def test_crm_failure_does_not_break_booking(client, monkeypatch):
    """Касса недоступна — запись клиента всё равно подтверждена."""
    _seed()
    calls: dict = {}
    invoice = _paid_booking(monkeypatch, calls)

    async def _boom(**kw):
        raise bigben_internal.BigBenInternalError("500")

    monkeypatch.setattr(bigben_internal, "create_payment", _boom, raising=False)

    await booking.handle_payment_confirmed(invoice, source="tbank")

    assert bb_store.booking_by_invoice(invoice)["status"] == "confirmed"
    assert billing.get_payment(invoice)["crm_payment_id"] is None


@pytest.mark.asyncio
async def test_no_student_card_means_no_income(client, monkeypatch):
    """Без карточки ученика оплату привязать не к кому — оставляем менеджеру."""
    _seed()
    calls: dict = {}
    invoice = _paid_booking(monkeypatch, calls)

    async def _no_student(**kw):
        raise bigben_internal.BigBenInternalError("down")

    async def _lead(**kw):
        return {"id": 900}

    monkeypatch.setattr(bigben_internal, "find_or_create_student", _no_student)
    from app.platform.bigben_v2 import get_bigben_v2
    monkeypatch.setattr(get_bigben_v2(), "create_lead", _lead, raising=False)

    await booking.handle_payment_confirmed(invoice, source="tbank")

    assert calls.get("payments") is None
    assert calls.get("settles") is None


def test_internal_api_asks_for_json(monkeypatch):
    """Пульт на не-JSON запрос отвечает 302 на страницу входа вместо ошибки
    валидации — заголовки XHR обязательны, иначе создание дохода «молчит»."""
    import asyncio

    import httpx as _httpx

    monkeypatch.setattr("app.config.settings.BIGBEN_INTERNAL_TOKEN", "tok")
    seen = {}

    class _Client:
        def __init__(self, **kw):
            seen["headers"] = kw.get("headers") or {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, method, url, json=None, headers=None):
            seen["headers"] = {**seen.get("headers", {}), **(headers or {})}

            class _R:
                status_code = 200

                @staticmethod
                def json():
                    return {"success": True, "data": {"id": 1}}
            return _R()

    monkeypatch.setattr(_httpx, "AsyncClient", _Client)
    asyncio.run(bigben_internal.create_income(
        type_id=1, summ=1125, bycard=4, filial_id=13296))

    assert seen["headers"].get("Accept") == "application/json"
    assert seen["headers"].get("X-Requested-With") == "XMLHttpRequest"


def test_settle_marks_money_as_external(monkeypatch):
    """`/full` с from_user_balance=False: деньги пришли эквайрингом, а не
    списаны с кошелька ученика — иначе CRM спишет несуществующий баланс."""
    import asyncio

    import httpx as _httpx

    monkeypatch.setattr("app.config.settings.BIGBEN_INTERNAL_TOKEN", "tok")
    seen = {}

    class _Client:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, method, url, json=None, headers=None):
            seen["method"] = method
            seen["url"] = url
            seen["json"] = json

            class _R:
                status_code = 200

                @staticmethod
                def json():
                    return {"success": True}
            return _R()

    monkeypatch.setattr(_httpx, "AsyncClient", _Client)
    asyncio.run(bigben_internal.settle_payment_full(
        payment_id=23606531, paydate="2026-09-08 17:14:00"))

    assert seen["method"] == "POST"
    assert seen["url"].endswith("/user/payments/23606531/full")
    assert seen["json"] == {"paydate": "2026-09-08 17:14:00",
                            "from_user_balance": False}
