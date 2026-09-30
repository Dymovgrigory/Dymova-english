"""Customer 360: объединённая карточка клиента (CRM + BigBen + платежи + заявки)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import crm_store
from app.platform import bb_store, billing


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("app.config.settings.BIGBEN_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.DIGEST_ENABLED", False)
    monkeypatch.setattr("app.config.settings.NUDGE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.SITE_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.WATCHDOG_ENABLED", False)
    monkeypatch.setattr("app.config.settings.TELEGRAM_POLLING", False)
    monkeypatch.setattr("app.config.settings.ADMIN_TOKEN", "admintoken")
    bb_store._local.conn = None
    crm_store._conn = None
    from app.main import app
    with TestClient(app) as c:
        yield c


def _customer_id() -> int:
    return crm_store.upsert_customer_for_identity(
        channel="telegram", external_id="u1",
        first_name="Мама", phone="+7 (925) 111-22-33")


def test_crm360_requires_auth(client):
    assert client.get("/admin/api/customers/1/crm360").status_code == 401


def test_crm360_unlinked(client):
    cid = _customer_id()
    r = client.get(f"/admin/api/customers/{cid}/crm360",
                   headers={"X-Admin-Token": "admintoken"})
    assert r.status_code == 200
    data = r.json()
    assert data["customer"]["id"] == cid
    assert data["bb_student"] is None
    assert data["bookings"] == [] and data["bb_payments"] == []
    assert data["billing_payments"] == []
    assert "lessons" in data["freshness"]


def test_crm360_linked_full_picture(client):
    cid = _customer_id()
    bb_store.upsert_student({"id": 42, "fio": "Ребёнок", "phone": "89251112233",
                             "email": "m@x.ru", "balance_kopecks": 320000})
    bb_store.upsert_payment({"id": 7, "student_id": 42, "student_fio": "Ребёнок",
                             "group_id": 1, "amount_kopecks": 650000,
                             "paid_at": "2026-08-01"})
    bb_store.create_booking(parent_name="Мама", phone="+7 925 111-22-33",
                            child_name="Ребёнок", child_age="8", comment="",
                            source="site", group_id=1, lesson_id=1,
                            filial_id=1, idempotency_key="k1")
    billing._db()  # создать таблицу
    r = client.get(f"/admin/api/customers/{cid}/crm360",
                   headers={"X-Admin-Token": "admintoken"})
    assert r.status_code == 200
    data = r.json()
    assert data["bb_student"]["id"] == 42
    assert data["bb_student"]["balance_kopecks"] == 320000
    assert len(data["bb_payments"]) == 1
    assert data["bb_payments"][0]["amount_kopecks"] == 650000
    assert len(data["bookings"]) == 1
    assert data["bookings"][0]["status"] == "pending"


def test_crm360_unknown_customer_404(client):
    r = client.get("/admin/api/customers/9999/crm360",
                   headers={"X-Admin-Token": "admintoken"})
    assert r.status_code == 404


def _h():
    return {"X-Admin-Token": "admintoken"}


def test_crm360_reason_no_phone(client):
    cid = crm_store.upsert_customer_for_identity(channel="max", external_id="np1", first_name="Аноним")
    data = client.get(f"/admin/api/customers/{cid}/crm360", headers=_h()).json()
    assert data["bb_student"] is None
    assert data["bb_reason"] == "no_phone"


def test_crm360_reason_phone_not_in_bigben(client):
    cid = crm_store.upsert_customer_for_identity(channel="max", external_id="np2", phone="+79990001122")
    data = client.get(f"/admin/api/customers/{cid}/crm360", headers=_h()).json()
    assert data["bb_reason"] == "phone_not_in_bigben"


def test_crm360_enriches_card_and_lists_all_siblings(client):
    bb_store.upsert_student({"id": 1, "fio": "Сидоров Пётр", "phone": "89251112233",
                             "email": "s@x.ru", "balance_kopecks": 100})
    bb_store.upsert_student({"id": 2, "fio": "Сидорова Соня", "phone": "89251112233",
                             "email": "", "balance_kopecks": 0})
    cid = _customer_id()
    data = client.get(f"/admin/api/customers/{cid}/crm360", headers=_h()).json()
    assert data["bb_reason"] == "linked"
    assert {s["id"] for s in data["bb_students"]} == {1, 2}
    assert data["customer"]["child_name"] == "Сидоров Пётр, Сидорова Соня"
    assert data["customer"]["email"] == "s@x.ru"


def test_crm360_offers_candidates_and_link_endpoint(client):
    bb_store.upsert_student({"id": 5, "fio": "Морозова Маша", "phone": "89253334455",
                             "email": "m@x.ru", "balance_kopecks": 0})
    cid = crm_store.upsert_customer_for_identity(
        channel="max", external_id="c1", child_name="Маша")
    data = client.get(f"/admin/api/customers/{cid}/crm360", headers=_h()).json()
    assert [c["id"] for c in data["bb_candidates"]] == [5]
    assert "89253334455" not in str(data["bb_candidates"])  # номер целиком не светим

    r = client.post(f"/admin/api/customers/{cid}/bigben-link", json={"student_id": 5}, headers=_h())
    assert r.status_code == 200
    linked = client.get(f"/admin/api/customers/{cid}/crm360", headers=_h()).json()
    assert linked["bb_reason"] == "linked"
    assert linked["customer"]["phone"] == "89253334455"


def test_bigben_link_unknown_student_404(client):
    cid = _customer_id()
    r = client.post(f"/admin/api/customers/{cid}/bigben-link", json={"student_id": 999}, headers=_h())
    assert r.status_code == 404
    assert client.post("/admin/api/customers/1/bigben-link", json={"student_id": 1}).status_code == 401
