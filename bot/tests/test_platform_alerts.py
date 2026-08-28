"""Alert Center: уровни, детекторы, retry вебхука."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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
    monkeypatch.setattr("app.config.settings.ADMIN_TOKEN", "admintoken")
    monkeypatch.setattr("app.config.settings.BIGBEN_PUBLIC_API_KEY", "bb_key")
    monkeypatch.setattr("app.config.settings.BIGBEN_WEBHOOK_SECRET", "")
    bb_store._local.conn = None
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_alerts_requires_auth(client):
    assert client.get("/admin/api/platform/alerts").status_code == 401


def test_alerts_detects_empty_and_unconfigured(client):
    r = client.get("/admin/api/platform/alerts",
                   headers={"X-Admin-Token": "admintoken"})
    assert r.status_code == 200
    codes = [a["code"] for a in r.json()["alerts"]]
    assert "webhook_not_configured" in codes
    assert any(c.startswith("sync_empty_") for c in codes)
    assert "payments_disabled" in codes


def test_alerts_quiet_when_fresh(client):
    bb_store.upsert_filial({"id": 1, "caption": "F", "city": "", "address": "", "active": True})
    bb_store.upsert_group({"id": 1, "caption": "G", "capacity": 8, "occupied": 1,
                           "free_slots": 7, "overbooked": False,
                           "filial": {"id": 1, "caption": "F"}, "auditory": {}, "schedule": []})
    bb_store.upsert_lesson({"id": 1, "date": "2030-01-01", "starts_at": None, "ends_at": None,
                            "group": {"id": 1, "caption": "G"},
                            "filial": {"id": 1, "caption": "F"}})
    bb_store.upsert_student({"id": 1, "fio": "S", "phone": "", "email": "", "balance_kopecks": 0})
    bb_store.upsert_payment({"id": 1, "student_id": 1, "student_fio": "S", "group_id": 1,
                             "amount_kopecks": 100, "paid_at": "2030-01-01"})
    r = client.get("/admin/api/platform/alerts",
                   headers={"X-Admin-Token": "admintoken"})
    codes = [a["code"] for a in r.json()["alerts"]]
    assert not any(c.startswith("sync_empty_") or c.startswith("sync_stale_") for c in codes)
    critical = [a for a in r.json()["alerts"] if a["level"] == "critical"]
    assert critical == []
