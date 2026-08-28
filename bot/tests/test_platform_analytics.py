"""Продуктовая аналитика: приём событий, воронка, серверные треки брони."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.platform import analytics, bb_store


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
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_events_accepts_whitelisted(client):
    r = client.post("/api/platform/events",
                    json={"event": "schedule_open", "session_id": "s1",
                          "meta": {"groups": 75}})
    assert r.status_code == 204
    f = analytics.funnel()
    assert f["counts"].get("schedule_open") == 1


def test_events_rejects_unknown_silently(client):
    r = client.post("/api/platform/events", json={"event": "rm -rf /"})
    assert r.status_code == 204
    assert analytics.funnel()["counts"] == {}
    # Серверные события извне не принимаем.
    client.post("/api/platform/events", json={"event": "payment_success"})
    assert analytics.funnel()["counts"] == {}


def test_events_bad_json_still_204(client):
    r = client.post("/api/platform/events", content=b"not json",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 204


def test_funnel_admin_endpoint(client):
    analytics.track("schedule_open", source="site")
    analytics.track("booking_completed", source="site", meta={"group_id": 1})
    r = client.get("/admin/api/platform/analytics/funnel",
                   headers={"X-Admin-Token": "admintoken"})
    assert r.status_code == 200
    data = r.json()
    assert data["counts"]["schedule_open"] == 1
    assert data["counts"]["booking_completed"] == 1
    names = [s["event"] for s in data["funnel"]]
    assert names[0] == "page_view" and "booking_completed" in names


def test_funnel_requires_auth(client):
    assert client.get("/admin/api/platform/analytics/funnel").status_code == 401


def test_booking_posts_server_events(client, monkeypatch):
    """При подтверждённой брони сервер пишет started/completed/lead_created."""
    tracked = []
    monkeypatch.setattr(analytics, "track",
                        lambda e, **kw: tracked.append(e) or True)
    from app.platform import public_api, booking

    class R:
        status = "confirmed"
        booking_id = 5
        lead_id = 77
        alternatives = None
        error = ""

    async def fake_book(**kw):
        return R()

    monkeypatch.setattr(booking, "book_trial", fake_book)
    monkeypatch.setattr(public_api.booking, "book_trial", fake_book)
    async def noop(*a, **kw):
        return None
    monkeypatch.setattr(public_api, "_notify_booking", noop)

    r = client.post("/api/platform/booking", json={
        "parent_name": "Мама", "phone": "+79251112233",
        "child_name": "Детёныш", "child_age": "8",
        "group_id": 1, "lesson_id": 2, "source": "site",
        "idempotency_key": "evt-1"})
    assert r.status_code == 201
    assert "booking_started" in tracked
    assert "booking_completed" in tracked
    assert "lead_created" in tracked
