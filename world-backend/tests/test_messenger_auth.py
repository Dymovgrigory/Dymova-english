"""Вход через Telegram/MAX mini apps: валидация initData, привязка, сессия."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.identity import messenger
from app.world import core
from app.world.db import reset_for_tests

TEST_TOKEN = "123456:test-bot-token"
USER = {"id": 777001, "first_name": "Маша", "last_name": "Петрова", "username": "masha_p"}


def make_init_data(token: str = TEST_TOKEN, user: dict | None = None,
                   auth_date: int | None = None) -> str:
    pairs = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAtest-query",
        "user": json.dumps(user if user is not None else USER),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-" + TEST_TOKEN)
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    app = FastAPI()
    app.include_router(messenger.router)
    with TestClient(app) as c:
        yield c
    reset_for_tests(str(tmp_path / "world-after.sqlite"))


def test_telegram_happy_path_creates_player_and_binding(client):
    r = client.post("/api/world/auth/telegram", json={"init_data": make_init_data()})
    assert r.status_code == 200
    data = r.json()
    assert data["token"].startswith("wses.")
    assert data["external_key"] == "telegram:777001"
    assert data["display_name"] == "Маша Петрова"
    assert data["is_registered"] is False

    again = client.post("/api/world/auth/telegram", json={"init_data": make_init_data()})
    assert again.status_code == 200
    assert again.json()["id"] == data["id"]  # тот же игрок по привязке
    assert again.json()["token"] != data["token"]  # новая сессия


def test_telegram_bad_signature_rejected(client):
    init_data = make_init_data(token="wrong-token")
    r = client.post("/api/world/auth/telegram", json={"init_data": init_data})
    assert r.status_code == 401
    assert r.json()["detail"]["reason"] == "bad_signature"


def test_telegram_stale_auth_date_rejected(client):
    stale = int(time.time()) - 3 * 24 * 3600
    r = client.post("/api/world/auth/telegram",
                    json={"init_data": make_init_data(auth_date=stale)})
    assert r.status_code == 401
    assert r.json()["detail"]["reason"] == "stale_auth_date"


def test_telegram_without_hash_rejected(client):
    r = client.post("/api/world/auth/telegram", json={"init_data": "auth_date=1&user=%7B%7D"})
    assert r.status_code == 401
    assert r.json()["detail"]["reason"] == "no_hash"


def test_provider_not_configured(client, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    r = client.post("/api/world/auth/telegram", json={"init_data": make_init_data()})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "provider_not_configured"


def test_max_happy_path(client):
    init_data = make_init_data(token="max-" + TEST_TOKEN,
                               user={"id": 555, "first_name": "Тёма"})
    r = client.post("/api/world/auth/max", json={"init_data": init_data})
    assert r.status_code == 200
    data = r.json()
    assert data["external_key"] == "max:555"
    assert data["display_name"] == "Тёма"
    assert data["is_registered"] is False


def test_max_not_configured(client, monkeypatch):
    monkeypatch.delenv("MAX_BOT_TOKEN")
    r = client.post("/api/world/auth/max", json={"init_data": "x=1"})
    assert r.status_code == 503
    assert r.json()["detail"]["provider"] == "max"


def test_providers_are_separate_identities(client):
    tg = client.post("/api/world/auth/telegram", json={"init_data": make_init_data()}).json()
    mx = client.post("/api/world/auth/max", json={
        "init_data": make_init_data(token="max-" + TEST_TOKEN),
    }).json()
    assert tg["id"] != mx["id"]
