"""Личный кабинет: связка по телефону, живые данные, честные стейты."""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app import miniapp_auth
from app.platform import bb_store


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("app.config.settings.BIGBEN_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.DIGEST_ENABLED", False)
    monkeypatch.setattr("app.config.settings.NUDGE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.SITE_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.WATCHDOG_ENABLED", False)
    monkeypatch.setattr("app.config.settings.TELEGRAM_POLLING", False)
    bb_store._local.conn = None
    identity = miniapp_auth.MiniAppIdentity(user_id="tg:777", platform="telegram")
    monkeypatch.setattr(miniapp_auth, "identify", lambda **kw: identity)
    from app.main import app
    with TestClient(app) as c:
        yield c, monkeypatch


def _seed(monkeypatch, phone="+79261234567"):
    day = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    bb_store.upsert_student({"id": 42, "fio": "Иванова Маша", "phone": phone,
                             "email": "", "balance_kopecks": 450000})
    bb_store.upsert_lesson({"id": 99, "date": day,
                            "starts_at": day + "T17:00:00+03:00", "ends_at": None,
                            "group": {"id": 7, "caption": "English A1"},
                            "filial": {"id": 10, "caption": "Долгопрудный"}})
    # диалог с телефоном из анкеты
    from app.memory import get_store
    conv = get_store().get("tg:777", platform="telegram")
    conv.lead.phone = phone
    get_store().save(conv)

    class _Card:
        async def student(self, sid):
            return {"id": sid, "fio": "Иванова Маша", "balance_kopecks": 450000,
                    "active_groups": [{"id": 7, "caption": "English A1"}]}
    monkeypatch.setattr("app.platform.account_api.get_bigben_v2", lambda: _Card())


def test_unauthorized_without_init_data(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("app.config.settings.BIGBEN_SYNC_ENABLED", False)
    monkeypatch.setattr(miniapp_auth, "identify", lambda **kw: None)
    bb_store._local.conn = None
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/miniapp/account/overview")
    assert r.status_code == 401


def test_overview_linked(client):
    c, monkeypatch = client
    _seed(monkeypatch)
    r = c.get("/api/miniapp/account/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["linked"] and body["live"]
    assert body["balance_rub"] == 4500.0
    assert body["groups"] == [{"id": 7, "caption": "English A1"}]
    assert body["upcoming_lessons"][0]["lesson_id"] == 99


def test_overview_no_phone_asks_registration(client):
    c, monkeypatch = client
    r = c.get("/api/miniapp/account/overview")
    assert r.status_code == 200
    assert r.json()["linked"] is False
    assert "телефон" in r.json()["message"].lower() or "номер" in r.json()["message"].lower()


def test_overview_unknown_phone(client):
    c, monkeypatch = client
    from app.memory import get_store
    conv = get_store().get("tg:777", platform="telegram")
    conv.lead.phone = "+79990001122"
    get_store().save(conv)
    r = c.get("/api/miniapp/account/overview")
    assert r.json()["linked"] is False
