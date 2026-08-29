"""Платное пробное: серверная цена по длительности, awaiting_payment,
подтверждение через webhook CloudPayments, диагностика."""
from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import hmac
import urllib.parse

import pytest
from fastapi.testclient import TestClient

from app.platform import bb_store, billing, booking


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("app.config.settings.BIGBEN_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.DIGEST_ENABLED", False)
    monkeypatch.setattr("app.config.settings.NUDGE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.SITE_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.WATCHDOG_ENABLED", False)
    monkeypatch.setattr("app.config.settings.TELEGRAM_POLLING", False)
    monkeypatch.setattr("app.config.settings.CLOUDPAYMENTS_ENABLED", True)
    monkeypatch.setattr("app.config.settings.CLOUDPAYMENTS_PUBLIC_ID", "pk_test")
    monkeypatch.setattr("app.config.settings.CLOUDPAYMENTS_API_SECRET", "cpsecret")
    monkeypatch.setattr("app.config.settings.TRIAL_PAID", True)
    monkeypatch.setattr("app.config.settings.TRIAL_PRICE_60_RUB", 1125)
    monkeypatch.setattr("app.config.settings.TRIAL_PRICE_45_RUB", 875)
    monkeypatch.setattr("app.config.settings.KNOWN_TEACHERS", "Вероника Дымова")
    bb_store._local.conn = None
    from app.main import app
    with TestClient(app) as c:
        yield c


def _seed(duration_min: int = 60):
    bb_store._local.conn = None
    day = (_dt.date.today() + _dt.timedelta(days=10)).isoformat()
    t0 = _dt.time(17, 0)
    t1 = (_dt.datetime.combine(_dt.date.today(), t0)
          + _dt.timedelta(minutes=duration_min)).time()
    bb_store.upsert_group({"id": 1,
                           "caption": "Get Involved A1+ Вероника Дымова",
                           "capacity": 8, "occupied": 5, "free_slots": 3,
                           "overbooked": False,
                           "filial": {"id": 10, "caption": "Фоксинбург Лихачевский"},
                           "auditory": {"id": 1, "caption": "1"}, "schedule": []})
    bb_store.upsert_lesson({"id": 55, "date": day,
                            "starts_at": day + f"T{t0:%H:%M}:00+03:00",
                            "ends_at": day + f"T{t1:%H:%M}:00+03:00",
                            "group": {"id": 1, "caption": "Get Involved A1+"},
                            "filial": {"id": 10, "caption": "Фоксинбург Лихачевский"}})


def _sig(body: bytes) -> str:
    return base64.b64encode(
        hmac.new(b"cpsecret", body, hashlib.sha256).digest()).decode()


def test_derive_helpers():
    assert booking.derive_level("Get Involved A1+ Пн/Ср") == "A1+"
    assert booking.derive_level("Starters kids") == "STARTERS"
    assert booking.derive_level("Разговорный клуб") == ""
    assert booking.trial_price_rub(60) == 1125
    assert booking.trial_price_rub(45) == 875
    assert booking.trial_price_rub(30) is None
    assert booking.trial_price_rub(None) is None
    assert booking.level_rank("A1") < booking.level_rank("B2")


def test_groups_card_enriched(client):
    _seed(60)
    r = client.get("/api/platform/groups")
    card = r.json()["data"][0]
    assert card["level"] == "A1+"
    assert card["teacher"] == "Вероника Дымова"
    assert card["duration_min"] == 60
    assert card["trial_price_rub"] == 1125


def test_groups_card_price_45(client):
    _seed(45)
    r = client.get("/api/platform/groups")
    assert r.json()["data"][0]["trial_price_rub"] == 875


def test_paid_booking_creates_invoice_not_crm(client, monkeypatch):
    _seed(60)
    called = {"lead": 0}
    monkeypatch.setattr(booking, "_fresh_group", lambda gid: _async_fresh(gid))
    async def _no_crm(**kw):
        called["lead"] += 1
        raise AssertionError("CRM не должен вызываться до оплаты")
    from app.platform.bigben_v2 import get_bigben_v2
    monkeypatch.setattr(get_bigben_v2(), "create_lead", _no_crm, raising=False)
    r = client.post("/api/platform/booking", json={
        "parent_name": "Анна", "phone": "+7 900 111-22-33",
        "child_name": "Маша", "child_age": "9",
        "group_id": 1, "lesson_id": 55, "idempotency_key": "k1"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "awaiting_payment"
    assert body["widget"]["amount"] == 1125.0
    assert body["widget"]["publicId"] == "pk_test"
    assert called["lead"] == 0
    row = bb_store.booking_by_id(body["booking_id"])
    assert row["status"] == "awaiting_payment"
    assert row["amount_kopecks"] == 112500


async def _async_fresh(gid):
    return {"id": gid, "caption": "G", "capacity": 8, "occupied": 1,
            "free_slots": 7, "filial": {"id": 10, "caption": "F"}}


def test_paid_booking_webhook_confirms(client, monkeypatch):
    _seed(60)
    monkeypatch.setattr(booking, "_fresh_group", lambda gid: _async_fresh(gid))
    crm = {"lead": 0, "demo": 0}
    from app.platform.bigben_v2 import get_bigben_v2
    async def _lead(**kw):
        crm["lead"] += 1
        return {"id": 900}
    async def _demo(**kw):
        crm["demo"] += 1
        return {"id": 800}
    monkeypatch.setattr(get_bigben_v2(), "create_lead", _lead, raising=False)
    monkeypatch.setattr(get_bigben_v2(), "create_demo_lesson", _demo, raising=False)
    monkeypatch.setattr(booking, "_schedule_reminders", lambda *a, **k: None)

    r = client.post("/api/platform/booking", json={
        "parent_name": "Анна", "phone": "+7 900 111-22-33",
        "group_id": 1, "lesson_id": 55, "idempotency_key": "k2"})
    inv = r.json()["invoice_id"]
    # webhook pay
    form = urllib.parse.urlencode({"InvoiceId": inv, "TransactionId": "555",
                                   "Amount": "1125.00"}).encode()
    r = client.post("/api/webhooks/cloudpayments/pay", content=form,
                    headers={"Content-HMAC-SHA256": _sig(form)})
    assert r.json()["code"] == 0
    assert crm["lead"] == 1 and crm["demo"] == 1
    row = bb_store.booking_by_invoice(inv)
    assert row["status"] == "confirmed"
    assert row["lead_id"] == 900 and row["demo_lesson_id"] == 800
    # повторный webhook — без дублей в CRM
    r = client.post("/api/webhooks/cloudpayments/pay", content=form,
                    headers={"Content-HMAC-SHA256": _sig(form)})
    assert crm["lead"] == 1 and crm["demo"] == 1


def test_booking_status_polling(client, monkeypatch):
    _seed(60)
    monkeypatch.setattr(booking, "_fresh_group", lambda gid: _async_fresh(gid))
    r = client.post("/api/platform/booking", json={
        "parent_name": "Анна", "phone": "+7 900 111-22-33",
        "group_id": 1, "lesson_id": 55, "idempotency_key": "k3"})
    bid = r.json()["booking_id"]
    r = client.get(f"/api/platform/booking/{bid}")
    assert r.json()["status"] == "awaiting_payment"
    assert "phone" not in r.json()  # PII не отдаём


def test_diagnostics_flow(client, monkeypatch):
    _seed()
    from app.platform.bigben_v2 import get_bigben_v2
    async def _lead(**kw):
        return {"id": 321}
    monkeypatch.setattr(get_bigben_v2(), "create_lead", _lead, raising=False)
    notified = []
    from app.platform import public_api
    async def _notify(text):
        notified.append(text)
    monkeypatch.setattr(public_api, "_notify_staff", _notify)
    r = client.post("/api/platform/diagnostics", json={
        "parent_name": "Олег", "phone": "8 900 222-33-44",
        "child_name": "Тим", "child_age": "7", "slot": "ср 17:00",
        "idempotency_key": "d1"})
    assert r.status_code == 201
    assert r.json()["lead_id"] == 321
    assert notified and "Диагностика" in notified[0]


def test_diagnostics_slots_empty_by_default(client):
    r = client.get("/api/platform/diagnostics/slots")
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_booking_status_polls_cp_when_webhook_missing(client, monkeypatch):
    """Вебхук CP не настроен → polling booking/{id} сам подтверждает оплату."""
    _seed(60)
    monkeypatch.setattr(booking, "_fresh_group", lambda gid: _async_fresh(gid))
    from app.platform.bigben_v2 import get_bigben_v2
    async def _lead(**kw):
        return {"id": 901}
    async def _demo(**kw):
        return {"id": 801}
    monkeypatch.setattr(get_bigben_v2(), "create_lead", _lead, raising=False)
    monkeypatch.setattr(get_bigben_v2(), "create_demo_lesson", _demo, raising=False)
    monkeypatch.setattr(booking, "_schedule_reminders", lambda *a, **k: None)

    r = client.post("/api/platform/booking", json={
        "parent_name": "Анна", "phone": "+7 900 111-22-33",
        "group_id": 1, "lesson_id": 55, "idempotency_key": "k9"})
    inv = r.json()["invoice_id"]
    bid = r.json()["booking_id"]

    from app.platform import billing as _billing
    async def _find(invoice_id):
        assert invoice_id == inv
        return {"Status": "Completed", "TransactionId": 777}
    monkeypatch.setattr(_billing, "cp_find_payment", _find)

    r = client.get(f"/api/platform/booking/{bid}")
    assert r.json()["status"] == "confirmed"
    row = bb_store.booking_by_invoice(inv)
    assert row["lead_id"] == 901 and row["demo_lesson_id"] == 801


def test_no_price_falls_back_to_free_booking(client, monkeypatch):
    """Группа без определимой цены (30-мин консультация) — бесплатная запись."""
    _seed(30)
    monkeypatch.setattr(booking, "_fresh_group", lambda gid: _async_fresh(gid))
    from app.platform.bigben_v2 import get_bigben_v2
    async def _lead(**kw):
        return {"id": 902}
    async def _demo(**kw):
        return {"id": 802}
    monkeypatch.setattr(get_bigben_v2(), "create_lead", _lead, raising=False)
    monkeypatch.setattr(get_bigben_v2(), "create_demo_lesson", _demo, raising=False)
    monkeypatch.setattr(booking, "_schedule_reminders", lambda *a, **k: None)
    r = client.post("/api/platform/booking", json={
        "parent_name": "Анна", "phone": "+7 900 111-22-33",
        "group_id": 1, "lesson_id": 55, "idempotency_key": "k30"})
    assert r.status_code == 201
    assert r.json()["status"] == "confirmed"


def test_course_level_mapping(monkeypatch):
    monkeypatch.setattr("app.config.settings.KNOWN_TEACHERS", "Вероника Дымова")
    assert booking.derive_course_level("My level 1 Пн/Ср 11:00") == ("My Level 1", "Pre-A1")
    assert booking.derive_course_level("My Level 5 Вт/Чт") == ("My Level 5", "A1+")
    assert booking.derive_course_level("Экспресс курс ML3 ML4") == ("My Level 3", "A1")
    assert booking.derive_course_level("Get Involved A2 Вт/Чт") == ("Get Involved", "A2")
    assert booking.derive_course_level("GEt Involved B1+ Пн/ср") == ("Get Involved", "B1+")
    assert booking.derive_course_level("Baby 2-3 года") == ("Дошкольная программа", "Pre-A1")
    assert booking.derive_course_level("Группа 4-5 лет Пн/Ср") == ("Дошкольная программа", "Pre-A1")
    assert booking.derive_course_level("Супер-папы. Гонка!") == ("", "")


def test_is_individual(monkeypatch):
    monkeypatch.setattr("app.config.settings.KNOWN_TEACHERS", "Вероника Дымова")
    assert booking.is_individual("Индивидуальное Оганесян Анна ВС 12:30")
    assert booking.is_individual("Вероника Дымова")
    assert not booking.is_individual("My Level 1 Пн/Ср")


def test_price_120():
    assert booking.trial_price_rub(120) == 2250
    assert booking.trial_price_rub(90) == 2250
    assert booking.trial_price_rub(60) == 1125


def test_individual_hidden_from_groups(client):
    _seed(60)
    day = (_dt.date.today() + _dt.timedelta(days=10)).isoformat()
    bb_store.upsert_group({"id": 9, "caption": "Индивидуальное Иванов",
                           "capacity": 1, "occupied": 1, "free_slots": 0,
                           "overbooked": False,
                           "filial": {"id": 10, "caption": "F"}, "auditory": {},
                           "schedule": []})
    bb_store.upsert_lesson({"id": 56, "date": day,
                            "starts_at": day + "T12:00:00+03:00",
                            "ends_at": day + "T13:00:00+03:00",
                            "group": {"id": 9, "caption": "Индивидуальное"},
                            "filial": {"id": 10, "caption": "F"}})
    r = client.get("/api/platform/groups")
    ids = [g["id"] for g in r.json()["data"]]
    assert 9 not in ids and 1 in ids
    r = client.get("/api/platform/schedule?days=30")
    gids = {l["group_id"] for l in r.json()["data"]}
    assert 9 not in gids


def test_event_group_has_no_price(client):
    """Мероприятие (без курса/уровня) не получает цену даже при 120 мин."""
    _seed(60)
    day = (_dt.date.today() + _dt.timedelta(days=10)).isoformat()
    bb_store.upsert_group({"id": 7, "caption": "Супер-папы. Гонка чемпионов!",
                           "capacity": 20, "occupied": 0, "free_slots": 20,
                           "overbooked": False,
                           "filial": {"id": 10, "caption": "F"}, "auditory": {},
                           "schedule": []})
    bb_store.upsert_lesson({"id": 57, "date": day,
                            "starts_at": day + "T12:00:00+03:00",
                            "ends_at": day + "T14:00:00+03:00",
                            "group": {"id": 7, "caption": "Супер-папы"},
                            "filial": {"id": 10, "caption": "F"}})
    r = client.get("/api/platform/groups")
    card = [g for g in r.json()["data"] if g["id"] == 7][0]
    assert card["trial_price_rub"] is None
    card1 = [g for g in r.json()["data"] if g["id"] == 1][0]
    assert card1["trial_price_rub"] == 1125
    assert card1["course"] == "Get Involved"
    assert card1["period_start"] and card1["period_end"]


def test_teacher_from_meta_overlay(client):
    _seed(60)
    bb_store.upsert_group_meta(1, teacher="Дымова Вероника Александровна",
                               period_start="2026-09-01", period_end="2027-05-31")
    r = client.get("/api/platform/groups")
    card = r.json()["data"][0]
    assert card["teacher"] == "Вероника Дымова"
    assert card["period_start"] == "2026-09-01"
    assert card["period_end"] == "2027-05-31"


def test_event_full_payment(client, monkeypatch):
    """Мероприятие с cost_per_event: оплата полной стоимости, не пробного."""
    _seed(60)
    day = (_dt.date.today() + _dt.timedelta(days=10)).isoformat()
    bb_store.upsert_group({"id": 21, "caption": "Осенняя Академия 5.10-9.10",
                           "capacity": 10, "occupied": 2, "free_slots": 8,
                           "overbooked": False,
                           "filial": {"id": 10, "caption": "F"}, "auditory": {},
                           "schedule": []})
    bb_store.upsert_lesson({"id": 77, "date": day,
                            "starts_at": day + "T09:00:00+03:00",
                            "ends_at": day + "T13:00:00+03:00",
                            "group": {"id": 21, "caption": "Осенняя Академия"},
                            "filial": {"id": 10, "caption": "F"}})
    bb_store.upsert_group_meta(21, teacher="Анохин Роман Леонидович",
                               period_start="2026-10-05", period_end="2026-10-09",
                               for_events=True, cost_per_event=12000)
    monkeypatch.setattr(booking, "_fresh_group", lambda gid: _async_fresh(gid))
    # карточка: мероприятие с ценой участия
    r = client.get("/api/platform/groups")
    card = [g for g in r.json()["data"] if g["id"] == 21][0]
    assert card["is_event"] and card["event_price_rub"] == 12000
    assert card["trial_price_rub"] is None
    # запись → инвойс на 12000 с описанием «Мероприятие»
    r = client.post("/api/platform/booking", json={
        "parent_name": "Анна", "phone": "+7 900 111-22-33",
        "group_id": 21, "lesson_id": 77, "idempotency_key": "ev1"})
    assert r.status_code == 201
    body = r.json()
    assert body["widget"]["amount"] == 12000.0
    assert body["widget"]["description"].startswith("Мероприятие")


def test_free_event_simple_booking(client, monkeypatch):
    """Бесплатное мероприятие (cost_per_event=0) — запись без оплаты."""
    _seed(60)
    bb_store.upsert_group_meta(1, for_events=True, cost_per_event=None)
    monkeypatch.setattr(booking, "_fresh_group", lambda gid: _async_fresh(gid))
    from app.platform.bigben_v2 import get_bigben_v2
    async def _lead(**kw):
        return {"id": 903}
    async def _demo(**kw):
        return {"id": 803}
    monkeypatch.setattr(get_bigben_v2(), "create_lead", _lead, raising=False)
    monkeypatch.setattr(get_bigben_v2(), "create_demo_lesson", _demo, raising=False)
    monkeypatch.setattr(booking, "_schedule_reminders", lambda *a, **k: None)
    r = client.post("/api/platform/booking", json={
        "parent_name": "Анна", "phone": "+7 900 111-22-33",
        "group_id": 1, "lesson_id": 55, "idempotency_key": "ev2"})
    assert r.status_code == 201
    assert r.json()["status"] == "confirmed"


def test_fulfill_creates_student_card(client, monkeypatch):
    """Оплаченная запись: карточка ученика через внутренний API,
    демо от user_id, лид НЕ создаётся."""
    _seed(60)
    monkeypatch.setattr(booking, "_fresh_group", lambda gid: _async_fresh(gid))
    monkeypatch.setattr("app.config.settings.BIGBEN_INTERNAL_TOKEN", "tok")
    monkeypatch.setattr("app.config.settings.TRIAL_PAID", False)

    from app.platform import bigben_internal
    created = {}
    async def _find_or_create(**kw):
        created.update(kw)
        return {"id": 777111}
    monkeypatch.setattr(bigben_internal, "find_or_create_student", _find_or_create)

    from app.platform.bigben_v2 import get_bigben_v2
    calls = {"lead": 0, "demo_user": None}
    async def _lead(**kw):
        calls["lead"] += 1
        return {"id": 1}
    async def _demo(**kw):
        calls["demo_user"] = kw.get("user_id")
        return {"id": 800}
    monkeypatch.setattr(get_bigben_v2(), "create_lead", _lead, raising=False)
    monkeypatch.setattr(get_bigben_v2(), "create_demo_lesson", _demo, raising=False)
    monkeypatch.setattr(booking, "_schedule_reminders", lambda *a, **k: None)

    r = client.post("/api/platform/booking", json={
        "parent_name": "Анна", "phone": "+7 900 111-22-33",
        "child_name": "Маша", "child_age": "9",
        "group_id": 1, "lesson_id": 55, "idempotency_key": "k-student"})
    assert r.status_code == 201, r.json()
    assert created["fio"] == "Маша"
    assert created["parentname"] == "Анна"
    assert calls["lead"] == 0
    assert calls["demo_user"] == 777111
    row = bb_store.booking_by_id(r.json()["booking_id"])
    assert row["status"] == "confirmed"
    assert row["student_id"] == 777111


def test_fulfill_fallback_to_lead(client, monkeypatch):
    """Внутренний API недоступен/упал — прежний флоу: лид + демо от lead_id."""
    _seed(60)
    monkeypatch.setattr(booking, "_fresh_group", lambda gid: _async_fresh(gid))
    monkeypatch.setattr("app.config.settings.BIGBEN_INTERNAL_TOKEN", "tok")
    monkeypatch.setattr("app.config.settings.TRIAL_PAID", False)

    from app.platform import bigben_internal
    async def _boom(**kw):
        raise bigben_internal.BigBenInternalError("down")
    monkeypatch.setattr(bigben_internal, "find_or_create_student", _boom)

    from app.platform.bigben_v2 import get_bigben_v2
    calls = {"lead": 0, "demo_lead": None}
    async def _lead(**kw):
        calls["lead"] += 1
        return {"id": 900}
    async def _demo(**kw):
        calls["demo_lead"] = kw.get("lead_id")
        return {"id": 800}
    monkeypatch.setattr(get_bigben_v2(), "create_lead", _lead, raising=False)
    monkeypatch.setattr(get_bigben_v2(), "create_demo_lesson", _demo, raising=False)
    monkeypatch.setattr(booking, "_schedule_reminders", lambda *a, **k: None)

    r = client.post("/api/platform/booking", json={
        "parent_name": "Анна", "phone": "+7 900 111-22-33",
        "group_id": 1, "lesson_id": 55, "idempotency_key": "k-fallback"})
    assert r.status_code == 201, r.json()
    assert calls["lead"] == 1
    assert calls["demo_lead"] == 900
    row = bb_store.booking_by_id(r.json()["booking_id"])
    assert row["status"] == "confirmed"
    assert row["lead_id"] == 900
