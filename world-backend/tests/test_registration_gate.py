"""Гейт обязательной регистрации: 403 registration_required до анкеты, 200 после."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.world import core
from app.world.db import reset_for_tests
from main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REGISTRATION_GATE", "1")
    monkeypatch.setenv("PHONE_VERIFICATION_REQUIRED", "0")
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    with TestClient(app) as c:
        yield c
    reset_for_tests(str(tmp_path / "world-after.sqlite"))


def _register(client: TestClient, headers: dict) -> None:
    body = {
        "first_name": "Иван", "last_name": "Петров", "birth_date": "2014-05-10",
        "school_number": "12", "class_grade": 5,
        "parent_email": "mama@example.com", "parent_phone": "+79161234567",
        "channel": "sms",
        "consents": [
            {"type": "pd_child", "version": "2026-09-19"},
            {"type": "privacy", "version": "2026-09-19"},
        ],
    }
    r = client.post("/api/v2/registration/start", json=body, headers=headers)
    assert r.status_code == 200
    r = client.post("/api/v2/registration/verify",
                    json={"code": r.json()["dev_code"]}, headers=headers)
    assert r.status_code == 200


def test_unregistered_player_gets_403_everywhere(client):
    player = client.post("/api/world/players", json={"display_name": "Маша"}, headers={"X-World-Player": "kid-gate"}).json()
    headers = {"X-World-Player": player["token"]}
    for path in ("/api/world/player", "/api/world/inventory", "/api/v2/home",
                 "/api/v2/profile", "/api/v2/castle"):
        r = client.get(path, headers=headers)
        assert r.status_code == 403, path
        assert r.json()["detail"]["code"] == "registration_required"


def test_open_endpoints_work_without_registration(client):
    player = client.post("/api/world/players", json={"display_name": "Маша"}, headers={"X-World-Player": "kid-gate"}).json()
    headers = {"X-World-Player": player["token"]}
    r = client.get("/api/v2/registration/status", headers=headers)
    assert r.status_code == 200
    assert r.json()["is_registered"] is False
    assert client.get("/health").status_code == 200
    # повторный bootstrap игрока не закрыт гейтом
    assert client.post("/api/world/players", json={"display_name": "Маша"},
                       headers={"X-World-Player": "fresh-key"}).status_code == 200


def test_registered_player_passes_gate(client):
    player = client.post("/api/world/players", json={"display_name": "Маша"}, headers={"X-World-Player": "kid-gate"}).json()
    headers = {"X-World-Player": player["token"]}
    _register(client, headers)
    assert client.get("/api/v2/registration/status", headers=headers).json()["is_registered"] is True
    assert client.get("/api/world/player", headers=headers).status_code == 200
    assert client.get("/api/world/inventory", headers=headers).status_code == 200


def test_gate_disabled_by_env(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_GATE", "0")
    player = client.post("/api/world/players", json={"display_name": "Маша"}, headers={"X-World-Player": "kid-gate"}).json()
    headers = {"X-World-Player": player["token"]}
    assert client.get("/api/world/player", headers=headers).status_code == 200


def test_no_header_still_401_not_403(client):
    assert client.get("/api/world/player").status_code == 401
