"""HTTP-уровень платформенных API: группы, расписание, вебхук, health."""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.platform import bb_store


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("app.config.settings.BIGBEN_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.BIGBEN_WEBHOOK_SECRET", "whsec")
    monkeypatch.setattr("app.config.settings.DIGEST_ENABLED", False)
    monkeypatch.setattr("app.config.settings.NUDGE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.SITE_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.WATCHDOG_ENABLED", False)
    monkeypatch.setattr("app.config.settings.TELEGRAM_POLLING", False)
    bb_store._local.conn = None
    from app.main import app
    with TestClient(app) as c:
        yield c


def _seed():
    import datetime as _dt
    bb_store._local.conn = None
    day = (_dt.date.today() + _dt.timedelta(days=10)).isoformat()
    bb_store.upsert_group({"id": 1, "caption": "English A1", "capacity": 8,
                           "occupied": 5, "free_slots": 3, "overbooked": False,
                           "filial": {"id": 10, "caption": "Долгопрудный"},
                           "auditory": {"id": 1, "caption": "1"}, "schedule": []})
    bb_store.upsert_group({"id": 2, "caption": "Архивная", "capacity": 8,
                           "occupied": 0, "free_slots": 8, "overbooked": False,
                           "filial": {"id": 10, "caption": "Долгопрудный"},
                           "auditory": {}, "schedule": []})
    bb_store.upsert_lesson({"id": 55, "date": day,
                            "starts_at": day + "T17:00:00+03:00",
                            "ends_at": day + "T18:00:00+03:00",
                            "group": {"id": 1, "caption": "English A1"},
                            "filial": {"id": 10, "caption": "Долгопрудный"}})


def test_groups_only_active_by_default(client):
    _seed()
    r = client.get("/api/platform/groups")
    assert r.status_code == 200
    ids = [g["id"] for g in r.json()["data"]]
    assert ids == [1]  # архивная без уроков скрыта
    r = client.get("/api/platform/groups?all=true")
    assert len(r.json()["data"]) == 2


def test_schedule_has_freshness(client):
    _seed()
    r = client.get("/api/platform/schedule?days=30")
    assert r.status_code == 200
    body = r.json()
    assert "freshness" in body and "groups_synced_at" in body["freshness"]
    assert body["data"][0]["lesson_id"] == 55
    assert body["data"][0]["free_slots"] == 3


def test_webhook_signature_flow(client):
    body = json.dumps({"event": "webhook.test", "account_id": 1,
                       "payload": {}, "timestamp": "2026-08-28T00:00:00Z"}).encode()
    r = client.post("/api/webhooks/bigben", content=body)
    assert r.status_code == 401
    sig = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    r = client.post("/api/webhooks/bigben", content=body,
                    headers={"X-BigBen-Signature": sig})
    assert r.status_code == 200 and r.json()["ok"]
    r = client.post("/api/webhooks/bigben", content=body,
                    headers={"X-BigBen-Signature": sig})
    assert r.json().get("duplicate")


def test_health_endpoint(client):
    r = client.get("/api/platform/health")
    assert r.status_code == 200
    assert "freshness" in r.json()


def test_booking_validation(client):
    _seed()
    r = client.post("/api/platform/booking", json={"parent_name": "Я", "phone": "123",
                                                   "group_id": 1, "lesson_id": 55})
    assert r.status_code == 422  # pydantic-валидация до бизнес-логики
