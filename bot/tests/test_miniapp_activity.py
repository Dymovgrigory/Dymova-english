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
    items = analytics.client_activity([("max", "7442748")])
    assert [i["event"] for i in items] == ["miniapp_click", "miniapp_section_view"]
    assert items[0]["meta"]["action"] == "Записаться"
    assert analytics.client_activity([("max", "someone-else")]) == []
    # Тот же числовой id в другом канале — не тот же клиент.
    assert analytics.client_activity([("telegram", "7442748")]) == []


def test_miniapp_event_endpoint_ignores_unsigned_requests(client):
    r = client.post("/api/miniapp/event", json={"event": "miniapp_click", "user_id": "7442748"})
    assert r.status_code == 200
    assert r.json() == {"ok": False}
    assert analytics.client_activity([("max", "7442748")]) == []


def test_media_endpoint_refuses_paths_outside_homework_dir(client):
    r = client.get("/admin/api/media/..%2F..%2Fbot.db", headers={"X-Admin-Token": "admintoken"})
    assert r.status_code == 404
    r = client.get("/admin/api/media/missing.jpg", headers={"X-Admin-Token": "admintoken"})
    assert r.status_code == 404


def test_media_served_only_when_attached_to_a_message(client, tmp_path, monkeypatch):
    from app import crm_ingest, crm_store
    from app import homework as homework_module

    monkeypatch.setattr(homework_module, "HOMEWORK_IMAGE_DIR", str(tmp_path))
    crm_store._conn = None
    (tmp_path / "abc123.jpg").write_bytes(b"jpeg")
    headers = {"X-Admin-Token": "admintoken"}
    # Файл лежит на диске, но ни одно сообщение его не ссылается — не отдаём.
    assert client.get("/admin/api/media/abc123.jpg", headers=headers).status_code == 404
    crm_ingest.ingest_inbound("max", "42", "[фото]", payload={"image_path": "homework/abc123.jpg"})
    assert client.get("/admin/api/media/abc123.jpg", headers=headers).status_code == 200


def test_admin_static_assets_are_revalidated_not_heuristically_cached(client):
    """Регрессия: без Cache-Control браузер хранит старый app.js админки по
    эвристике (Last-Modified недельной давности), и новые функции не видны."""
    r = client.get("/admin/app.js")
    assert r.status_code == 200
    assert "no-cache" in r.headers.get("cache-control", "")


def test_mini_app_page_script_sends_click_events():
    """Страница, которую открывает клиент в MAX (/app/), грузит /tg/app.js:
    именно там должен работать трекер кликов."""
    from pathlib import Path

    script = (Path(__file__).resolve().parents[1] / "app" / "tgapp" / "app.js").read_text(encoding="utf-8")
    assert "miniapp_click" in script
    assert "/api/miniapp/event" in script
    page = (Path(__file__).resolve().parents[1] / "app" / "tgapp" / "index.html").read_text(encoding="utf-8")
    assert "/tg/app.js?v=11" in page


def test_technical_labels_are_not_treated_as_button_text():
    """MAX передаёт в мини-приложение служебные строки (WebAppData=ip=…&user=…):
    это не текст нажатой кнопки и в ленте клиента их быть не должно."""
    from app.platform import analytics as a

    assert a.is_technical_action_label("WebAppData=ip%3D94.25.173.21%26user%3D%257B")
    assert a.is_technical_action_label("https://dymova-english.ru/x")
    assert a.is_technical_action_label("a=1")
    assert not a.is_technical_action_label("Подобрать курс")
    assert not a.is_technical_action_label("Мир Фоксинбурга уроки-приключения для детей")
    assert not a.is_technical_action_label("")
