"""Действия клиента в мини-приложении: запись, лента в админке и защита фото из переписки."""
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


def test_miniapp_events_are_whitelisted_and_readable_by_client():
    assert analytics.track("miniapp_section_view", source="max", anon_id="7442748",
                           meta={"section": "mylessons"})
    assert analytics.track("miniapp_click", source="max", anon_id="7442748",
                           meta={"section": "mylessons", "action": "Записаться"})
    assert not analytics.track("miniapp_wipe_all", source="max", anon_id="7442748")
    items = analytics.client_activity(["7442748"])
    assert [i["event"] for i in items] == ["miniapp_click", "miniapp_section_view"]
    assert items[0]["meta"]["action"] == "Записаться"
    assert analytics.client_activity(["someone-else"]) == []


def test_miniapp_event_endpoint_ignores_unsigned_requests(client):
    r = client.post("/api/miniapp/event", json={"event": "miniapp_click", "user_id": "7442748"})
    assert r.status_code == 200
    assert r.json() == {"ok": False}
    assert analytics.client_activity(["7442748"]) == []


def test_media_endpoint_refuses_paths_outside_homework_dir(client):
    r = client.get("/admin/api/media/..%2F..%2Fbot.db", headers={"X-Admin-Token": "admintoken"})
    assert r.status_code == 404
    r = client.get("/admin/api/media/missing.jpg", headers={"X-Admin-Token": "admintoken"})
    assert r.status_code == 404
