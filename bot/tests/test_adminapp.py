"""Админка: страница отдаётся, но данные — только по токену."""
from pathlib import Path

from fastapi.testclient import TestClient

from app import main as main_module
from app.config import settings

ADMINAPP = Path(main_module.__file__).with_name("adminapp")


def test_admin_page_is_served():
    client = TestClient(main_module.app)

    resp = client.get("/admin/")

    assert resp.status_code == 200
    assert "Фоксинбург" in resp.text


def test_static_mount_does_not_shadow_the_api(monkeypatch):
    """Статика висит на /admin — ручки /admin/* обязаны продолжать работать."""
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "secret", raising=False)
    client = TestClient(main_module.app)

    resp = client.get("/admin/users", headers={"X-Admin-Token": "secret"})

    assert resp.status_code == 200
    assert "rows" in resp.json()


def test_api_still_rejects_a_wrong_token(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "secret", raising=False)
    client = TestClient(main_module.app)

    assert client.get("/admin/users").status_code == 401
    assert client.get("/admin/users", headers={"X-Admin-Token": "nope"}).status_code == 401


def test_page_contains_no_token():
    """Токен вводит человек, в исходниках страницы его быть не должно."""
    html = (ADMINAPP / "index.html").read_text(encoding="utf-8")
    js = (ADMINAPP / "app.js").read_text(encoding="utf-8")

    for text in (html, js):
        assert "ADMIN_TOKEN=" not in text
        assert "dh6yUgyufHJGJh893jdvnj" not in text


def test_page_sends_the_token_as_a_header():
    js = (ADMINAPP / "app.js").read_text(encoding="utf-8")

    assert "X-Admin-Token" in js
    # Токен не должен уезжать в URL: он осядет в логах прокси и в истории.
    assert "token=" not in js


def test_user_rows_expose_platform_and_registration():
    from app import broadcast

    rows = broadcast.list_users()

    for row in rows:
        assert "platform" in row
        assert "registered" in row
