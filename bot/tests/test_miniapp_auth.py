"""Аутентификация мини-приложений: подпись initData — единственный источник личности."""
import time

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app import memory as memory_module
from app import miniapp_auth
from app.config import settings

from tests.conftest import make_telegram_init_data

TOKEN = "123456:AA-test-token"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    memory_module._store = None
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", TOKEN, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_AUTH_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_REQUIRE_REGISTRATION", False, raising=False)
    yield
    memory_module._store = None


# --- проверка подписи -----------------------------------------------------


def test_valid_init_data_is_accepted():
    identity = miniapp_auth.verify_telegram_init_data(
        make_telegram_init_data(TOKEN, telegram_user_id=777, first_name="Аня"), TOKEN
    )

    assert identity is not None
    assert identity.user_id == "tg:777"
    assert identity.platform == "telegram"
    assert identity.display_name == "Аня"
    assert identity.verified is True


def test_tampered_signature_is_rejected():
    init_data = make_telegram_init_data(TOKEN, telegram_user_id=777, tamper=True)

    assert miniapp_auth.verify_telegram_init_data(init_data, TOKEN) is None


def test_init_data_signed_with_another_token_is_rejected():
    """Подпись чужим токеном не должна открывать наш кабинет."""
    init_data = make_telegram_init_data("someone-elses-token", telegram_user_id=777)

    assert miniapp_auth.verify_telegram_init_data(init_data, TOKEN) is None


def test_forged_user_id_without_signature_is_rejected():
    """Классический подлог: подставить чужой user= без пересчёта hash."""
    honest = make_telegram_init_data(TOKEN, telegram_user_id=1)
    forged = honest.replace("%22id%22%3A1", "%22id%22%3A999")

    assert forged != honest
    assert miniapp_auth.verify_telegram_init_data(forged, TOKEN) is None


def test_expired_init_data_is_rejected():
    stale = make_telegram_init_data(
        TOKEN, auth_date=int(time.time()) - miniapp_auth.INIT_DATA_MAX_AGE_SEC - 60
    )

    assert miniapp_auth.verify_telegram_init_data(stale, TOKEN) is None


def test_empty_init_data_is_rejected():
    assert miniapp_auth.verify_telegram_init_data("", TOKEN) is None
    assert miniapp_auth.verify_telegram_init_data("hash=abc", TOKEN) is None


def test_plain_user_id_is_not_an_identity_when_auth_required():
    assert miniapp_auth.identify(fallback_user_id="tg:999") is None


def test_plain_user_id_is_unverified_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(settings, "MINIAPP_AUTH_REQUIRED", False, raising=False)

    identity = miniapp_auth.identify(fallback_user_id="tg:999")

    assert identity is not None
    assert identity.verified is False


# --- API ------------------------------------------------------------------


def test_profile_requires_signed_init_data():
    client = TestClient(main_module.app)

    assert client.get("/api/miniapp/profile").status_code == 401
    assert (
        client.get(
            "/api/miniapp/profile", headers={"X-Miniapp-Init-Data": "hash=fake"}
        ).status_code
        == 401
    )


def test_profile_never_leaks_another_users_data(monkeypatch):
    """IDOR: раньше ?user_id=<чужой> отдавал чужой профиль."""
    store = memory_module.get_store()
    victim = store.get("tg:1000", platform="telegram")
    victim.lead.fio_parent = "Иванова Анна"
    victim.lead.phone = "+79991234567"
    store.save(victim)

    client = TestClient(main_module.app)
    attacker = make_telegram_init_data(TOKEN, telegram_user_id=2000)

    resp = client.get(
        "/api/miniapp/profile",
        params={"user_id": "tg:1000"},
        headers={"X-Miniapp-Init-Data": attacker},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "tg:2000"
    assert body["profile"]["phone"] == ""
    assert "Иванова Анна" not in resp.text


def test_profile_returns_own_data():
    store = memory_module.get_store()
    conv = store.get("tg:3000", platform="telegram")
    conv.lead.fio_parent = "Петрова Мария"
    conv.lead.phone = "+79990000000"
    conv.registered = True
    store.save(conv)

    client = TestClient(main_module.app)
    resp = client.get(
        "/api/miniapp/profile",
        headers={"X-Miniapp-Init-Data": make_telegram_init_data(TOKEN, telegram_user_id=3000)},
    )

    body = resp.json()
    assert body["ok"] is True
    assert body["registered"] is True
    assert body["profile"]["fio_parent"] == "Петрова Мария"


def test_access_state_ignores_unsigned_user_id():
    client = TestClient(main_module.app)

    body = client.get("/api/miniapp/access", params={"user_id": "tg:1"}).json()

    assert body["has_identity"] is False
    assert body["user_id"] == ""


def test_catalog_stays_public_without_auth():
    """Витрина обязана открываться мгновенно и без авторизации."""
    client = TestClient(main_module.app)

    resp = client.get("/api/miniapp/info")

    assert resp.status_code == 200
    assert "courses" in resp.json()


def test_miniapp_chat_requires_identity():
    client = TestClient(main_module.app)

    resp = client.post("/api/miniapp/chat", json={"text": "привет"})

    assert resp.status_code == 401


# --- админские ручки ------------------------------------------------------


def test_max_set_webhook_requires_admin_token(monkeypatch):
    """Открытая ручка позволяла переподписать бота на чужой URL и
    перехватывать все входящие сообщения клиентов."""
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "adm", raising=False)
    client = TestClient(main_module.app)

    assert client.post("/admin/set-webhook", json={"url": "https://evil/x"}).status_code == 401


def test_admin_endpoints_closed_when_token_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "", raising=False)
    client = TestClient(main_module.app)

    assert client.get("/admin/nudge/preview").status_code == 401
    assert client.get("/admin/users").status_code == 401
    assert client.post("/admin/set-webhook", json={"url": "https://x"}).status_code == 401
