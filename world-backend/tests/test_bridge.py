"""Мост бот→world (prefill анкеты) и привязки мессенджеров в админке."""
from __future__ import annotations

import hashlib
import hmac

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin import service as admin_service
from app.identity import api as identity_api
from app.identity import bridge, messenger
from app.world import core
from app.world.db import get_conn, reset_for_tests

from test_messenger_auth import TEST_TOKEN, USER, make_init_data

SECRET = "test-bridge-secret"
LEAD = {
    "fio_parent": "Петрова Анна",
    "fio_child": "Маша Петрова",
    "birthday": "2015-04-01",
    "phone": "+79161234567",
}


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeClient:
    """Подмена httpx.Client: записывает вызовы, отвечает по сценарию."""
    calls: list[dict] = []
    status_code = 200
    payload: dict = {}
    raises: Exception | None = None

    def __init__(self, timeout=None):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None):
        _FakeClient.calls.append({"url": url, "params": params})
        if _FakeClient.raises is not None:
            raise _FakeClient.raises
        return _FakeResponse(_FakeClient.status_code, _FakeClient.payload)


@pytest.fixture()
def fake_http(monkeypatch):
    _FakeClient.calls = []
    _FakeClient.status_code = 200
    _FakeClient.payload = {}
    _FakeClient.raises = None
    monkeypatch.setattr(bridge.httpx, "Client", _FakeClient)
    return _FakeClient


def test_prefill_disabled_without_secret(monkeypatch, fake_http):
    monkeypatch.delenv("WORLD_BRIDGE_SECRET", raising=False)
    assert bridge.fetch_bot_prefill("telegram", "123") is None
    assert fake_http.calls == []


def test_prefill_found_returns_lead(monkeypatch, fake_http):
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", SECRET)
    fake_http.payload = {"found": True, "lead": LEAD}
    assert bridge.fetch_bot_prefill("telegram", "123") == LEAD


def test_prefill_not_found_returns_none(monkeypatch, fake_http):
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", SECRET)
    fake_http.payload = {"found": False, "lead": None}
    assert bridge.fetch_bot_prefill("telegram", "123") is None


def test_prefill_non_200_returns_none(monkeypatch, fake_http):
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", SECRET)
    for status in (400, 401, 404, 500):
        fake_http.status_code = status
        assert bridge.fetch_bot_prefill("telegram", "123") is None


def test_prefill_network_error_returns_none(monkeypatch, fake_http):
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", SECRET)
    fake_http.raises = TimeoutError("bot unreachable")
    assert bridge.fetch_bot_prefill("telegram", "123") is None


def test_prefill_filters_unknown_lead_keys(monkeypatch, fake_http):
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", SECRET)
    fake_http.payload = {
        "found": True,
        "lead": {**LEAD, "admin_notes": "secret", "phone": "+79161234567",
                 "birthday": 2015, "extra": [1, 2]},
    }
    out = bridge.fetch_bot_prefill("telegram", "123")
    assert out == {k: LEAD[k] for k in ("fio_parent", "fio_child", "phone")}


def test_prefill_preserves_phone_confirmed_flag(monkeypatch, fake_http):
    """Булев phone_confirmed переживает строковый фильтр LEAD_KEYS."""
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", SECRET)
    fake_http.payload = {"found": True, "lead": {**LEAD, "phone_confirmed": True}}
    out = bridge.fetch_bot_prefill("telegram", "123")
    assert out["phone_confirmed"] is True
    fake_http.payload = {"found": True, "lead": {**LEAD, "phone_confirmed": "да"}}
    out = bridge.fetch_bot_prefill("telegram", "123")
    assert "phone_confirmed" not in out


def test_bridge_signature_matches_contract(monkeypatch, fake_http):
    """sign = HMAC_SHA256(key=WORLD_BRIDGE_SECRET, msg=f"{provider}\\n{user_id}\\n{ts}")."""
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", SECRET)
    monkeypatch.setenv("WORLD_BOT_BRIDGE_URL", "http://bot:8000/world-bridge/profile")
    fake_http.payload = {"found": True, "lead": LEAD}
    bridge.fetch_bot_prefill("telegram", "123")
    assert len(fake_http.calls) == 1
    params = fake_http.calls[0]["params"]
    expected = hmac.new(
        SECRET.encode(), f"telegram\n123\n{params['ts']}".encode(), hashlib.sha256
    ).hexdigest()
    assert params["sign"] == expected
    assert params["provider"] == "telegram"
    assert params["user_id"] == "123"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("PHONE_VERIFICATION_REQUIRED", "0")
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    app = FastAPI()
    app.include_router(messenger.router)
    app.include_router(identity_api.router)
    with TestClient(app) as c:
        yield c
    reset_for_tests(str(tmp_path / "world-after.sqlite"))


def _register(client, token: str) -> None:
    body = {
        "first_name": "Маша", "last_name": "Петрова", "birth_date": "2015-04-01",
        "school_number": "12", "class_grade": 5,
        "parent_email": "mama@example.com", "parent_phone": "+79161234567",
        "password": "secret123",
        "channel": "email",
        "consents": [
            {"type": "pd_child", "version": "2026-09-19"},
            {"type": "privacy", "version": "2026-09-19"},
        ],
    }
    headers = {"X-World-Player": token}
    r = client.post("/api/v2/registration/start", json=body, headers=headers)
    assert r.status_code == 200
    r = client.post("/api/v2/registration/verify",
                    json={"code": r.json()["dev_code"]}, headers=headers)
    assert r.status_code == 200


def test_login_unregistered_returns_prefill(client, monkeypatch):
    calls = []
    monkeypatch.setattr(messenger.bridge, "fetch_bot_prefill",
                        lambda provider, uid: calls.append((provider, uid)) or LEAD)
    r = client.post("/api/world/auth/telegram", json={"init_data": make_init_data()})
    assert r.status_code == 200
    data = r.json()
    assert data["is_registered"] is False
    assert data["prefill"] == LEAD
    assert calls == [("telegram", "777001")]


def test_login_registered_skips_prefill(client, monkeypatch):
    first = client.post("/api/world/auth/telegram", json={"init_data": make_init_data()}).json()
    _register(client, first["token"])
    mock_called = []
    monkeypatch.setattr(messenger.bridge, "fetch_bot_prefill",
                        lambda *a: mock_called.append(a) or LEAD)
    r = client.post("/api/world/auth/telegram", json={"init_data": make_init_data()})
    assert r.status_code == 200
    data = r.json()
    assert data["is_registered"] is True
    assert data["prefill"] is None
    assert mock_called == []


def test_relogin_updates_display_name(client, monkeypatch):
    monkeypatch.setattr(messenger.bridge, "fetch_bot_prefill", lambda *a: None)
    client.post("/api/world/auth/telegram", json={"init_data": make_init_data()})
    renamed = {**USER, "first_name": "Мария"}
    client.post("/api/world/auth/telegram",
                json={"init_data": make_init_data(user=renamed)})
    row = get_conn().execute(
        "SELECT display_name FROM external_identities"
        " WHERE provider='telegram' AND provider_user_id='777001'",
    ).fetchone()
    assert row["display_name"] == "Мария Петрова"


def test_student_card_includes_identities(client, monkeypatch):
    monkeypatch.setattr(messenger.bridge, "fetch_bot_prefill", lambda *a: None)
    data = client.post("/api/world/auth/telegram", json={"init_data": make_init_data()}).json()
    card = admin_service.student_card(data["id"])
    assert card["identities"] == [
        {"provider": "telegram", "provider_user_id": "777001",
         "display_name": "Маша Петрова", "created_at": card["identities"][0]["created_at"]}
    ]
    ghost = core.get_or_create_player("ghost-no-links", "Призрак")
    assert admin_service.student_card(ghost["id"])["identities"] == []
