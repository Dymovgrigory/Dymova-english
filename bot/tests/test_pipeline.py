"""Тесты CRM-воронки (pipeline) и CSV-экспорта."""
import csv
import io

import pytest
from fastapi.testclient import TestClient

from app import crm_store
from app import main as main_module
from app.config import settings

TOKEN = "test-admin-token"
AUTH = {"X-Admin-Token": TOKEN}


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "crm.db"))
    monkeypatch.setattr(settings, "STATE_FILE", "")
    monkeypatch.setattr(settings, "ADMIN_TOKEN", TOKEN, raising=False)
    crm_store.reset()
    main_module._BACKGROUND_TASKS.clear()
    yield
    crm_store.reset()
    main_module._BACKGROUND_TASKS.clear()


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _customer(channel, external_id, name, **kwargs):
    cid = crm_store.upsert_customer_for_identity(channel, external_id, name=name, **kwargs)
    return cid


def test_pipeline_groups_by_lead_status(client):
    a = _customer("max", "u1", "Анна")
    b = _customer("telegram", "tg:2", "Борис")
    c = _customer("max", "u3", "Вера")
    crm_store.update_customer(b, {"lead_status": "trial"})
    crm_store.update_customer(c, {"lead_status": "client"})

    data = client.get("/admin/api/pipeline", headers=AUTH).json()
    assert data["stages"] == ["new", "contacted", "qualified", "trial",
                              "offer", "payment", "client", "lost"]
    board = data["board"]
    assert [x["name"] for x in board["new"]] == ["Анна"]
    assert [x["name"] for x in board["trial"]] == ["Борис"]
    assert [x["name"] for x in board["client"]] == ["Вера"]
    assert board["qualified"] == []
    # У карточки есть поля для kanban.
    card = board["trial"][0]
    assert card["id"] == b and "channel" in card and "manager" in card


def test_pipeline_kanban_move_writes_audit(client):
    cid = _customer("max", "u1", "Анна")
    # Действие drag-and-drop на доске — это PATCH lead_status.
    resp = client.patch(f"/admin/api/customers/{cid}", headers=AUTH,
                        json={"lead_status": "offer"})
    assert resp.json()["lead_status"] == "offer"
    board = client.get("/admin/api/pipeline", headers=AUTH).json()["board"]
    assert [x["id"] for x in board["offer"]] == [cid]
    audit = crm_store.get_conn().execute(
        "SELECT after_json FROM audit_log WHERE entity_type = 'customer' AND action = 'update'"
    ).fetchone()
    assert "offer" in audit["after_json"]


def test_export_customers_csv(client):
    _customer("max", "u1", "Анна", phone="+7999", child_name="Миша")
    _customer("telegram", "tg:2", "Борис")
    resp = client.get("/admin/api/export/customers.csv", headers=AUTH)
    assert resp.status_code == 200
    # BOM для Excel на первом байте.
    assert resp.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(resp.text.lstrip("﻿"))))
    assert rows[0][0] == "id" and "lead_status" in rows[0]
    assert len(rows) == 3  # заголовок + 2 клиента
    names = {row[1] for row in rows[1:]}
    assert names == {"Анна", "Борис"}


def test_export_messages_csv_with_dates(client):
    cid = _customer("max", "u1", "Анна")
    conv = crm_store.get_or_create_conversation(cid, "max", "u1")
    crm_store.add_message(conv, cid, "max", "in", "customer", "старое",
                          created_at="2026-01-01T10:00:00+00:00")
    crm_store.add_message(conv, cid, "max", "in", "customer", "новое",
                          created_at="2026-03-01T10:00:00+00:00")

    resp = client.get("/admin/api/export/messages.csv", headers=AUTH)
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert len(rows) == 3

    filtered = client.get(
        "/admin/api/export/messages.csv?date_from=2026-02-01&date_to=2026-12-31",
        headers=AUTH)
    rows = list(csv.reader(io.StringIO(filtered.text)))
    assert len(rows) == 2  # только «новое»
    assert rows[1][-1] == "новое"

    # Без токена экспорт закрыт.
    assert client.get("/admin/api/export/customers.csv").status_code == 401
