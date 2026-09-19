"""Bridge-endpoint /world-bridge/profile и кнопка «Мир Фоксинбурга» в меню."""
from __future__ import annotations

import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.config import settings
from app.memory import get_store

SECRET = "test-world-bridge-secret"
DEFAULT_WORLD_URL = "https://new.dymova-english.ru/world"


def _sign(provider: str, user_id: str, ts: int) -> str:
    """Независимый подсчёт подписи по контракту — как это делает world-backend."""
    msg = f"{provider}\n{user_id}\n{ts}".encode()
    return hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def _bridge_on(monkeypatch):
    monkeypatch.setattr(settings, "WORLD_BRIDGE_SECRET", SECRET)
    monkeypatch.setattr(settings, "WORLD_APP_URL", "")
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _get(client, provider="telegram", user_id="wb-unknown", ts=None, sign=None):
    ts = int(time.time()) if ts is None else ts
    sign = _sign(provider, user_id, ts) if sign is None else sign
    return client.get(
        "/world-bridge/profile",
        params={"provider": provider, "user_id": user_id, "ts": ts, "sign": sign},
    )


def test_bridge_off_without_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "WORLD_BRIDGE_SECRET", "")
    assert _get(client).status_code == 404


def test_bad_provider(client):
    resp = _get(client, provider="vk", sign="x")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "bad_provider"


def test_stale_ts_past_and_future(client):
    assert _get(client, ts=0).status_code == 401
    resp = _get(client, ts=int(time.time()) + 1000)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "stale"


def test_non_numeric_ts_is_stale(client):
    resp = client.get(
        "/world-bridge/profile",
        params={"provider": "telegram", "user_id": "x", "ts": "now", "sign": "x"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "stale"


def test_bad_signature(client):
    resp = _get(client, sign="0" * 64)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "bad_signature"


def test_unknown_user_found_false(client):
    store = get_store()
    store.reset("wb-unknown", platform="telegram")
    resp = _get(client)
    assert resp.status_code == 200
    assert resp.json() == {"found": False, "lead": None}


def test_known_user_returns_only_filled_fields(client):
    store = get_store()
    conv = store.reset("wb-known", platform="telegram")
    conv.lead.fio_parent = "  Иванова Анна  "
    conv.lead.fio_child = "Иванов Пётр"
    conv.lead.birthday = "   "
    conv.lead.phone = "+7 900 123-45-67"
    store.save(conv)

    resp = _get(client, user_id="wb-known")

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["lead"] == {
        "fio_parent": "Иванова Анна",
        "fio_child": "Иванов Пётр",
        "phone": "+7 900 123-45-67",
    }


def test_store_failure_is_fail_open(client, monkeypatch):
    monkeypatch.setattr(
        "app.world_bridge.get_store", lambda: (_ for _ in ()).throw(RuntimeError("db down"))
    )
    resp = _get(client)
    assert resp.status_code == 200
    assert resp.json() == {"found": False, "lead": None}


# --- кнопка «Мир Фоксинбурга» в меню ---------------------------------------


def test_telegram_menu_world_button_first_row():
    rows = main_module._telegram_menu_buttons("u1")
    assert rows[0][0] == {"type": "web_app", "text": "🏰 Мир Фоксинбурга", "web_app": DEFAULT_WORLD_URL}


def test_telegram_menu_world_button_hidden_without_https(monkeypatch):
    monkeypatch.setattr(settings, "WORLD_APP_URL", "http://x")
    rows = main_module._telegram_menu_buttons("u1")
    assert all(b.get("text") != "🏰 Мир Фоксинбурга" for row in rows for b in row)


def test_max_menu_world_button_first_row():
    rows = main_module._main_menu("u1")
    assert rows[0][0]["type"] == "link"
    assert rows[0][0]["text"] == "🏰 Мир Фоксинбурга"
    assert rows[0][0]["url"] == DEFAULT_WORLD_URL


def test_max_menu_world_button_hidden_without_https(monkeypatch):
    monkeypatch.setattr(settings, "WORLD_APP_URL", "http://x")
    rows = main_module._main_menu("u1")
    assert all(b.get("text") != "🏰 Мир Фоксинбурга" for row in rows for b in row)
