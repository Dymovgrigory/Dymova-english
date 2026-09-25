"""HTTP-контракт /api/v2/admin/*: логин, ученики, корректировки, аудит."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin import api as admin_api
from app.admin import auth as admin_auth
from app.identity import api as identity_api
from app.world import core
from app.world.db import reset_for_tests

HEADERS = {"X-World-Player": "kid-admin"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PHONE_VERIFICATION_REQUIRED", "0")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_LOGIN", "owner")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "secret-pass")
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    admin_auth.bootstrap()
    admin_api.reset_rate_limit()
    app = FastAPI()
    app.include_router(admin_api.router)
    app.include_router(identity_api.router)
    with TestClient(app) as c:
        yield c
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def _token(client) -> dict:
    r = client.post("/api/v2/admin/login",
                    json={"login": "owner", "password": "secret-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _register(client, key=HEADERS["X-World-Player"], last_name="Сидорова", phone="8 916 111-22-33"):
    body = {
        "first_name": "Анна", "last_name": last_name, "birth_date": "2013-03-03",
        "school_number": "7", "class_grade": 6, "class_letter": "Б",
        "parent_email": "papa@example.com", "parent_phone": phone, "channel": "email",
        "password": "secret123",
        "consents": [
            {"type": "pd_child", "version": "2026-09-19"},
            {"type": "privacy", "version": "2026-09-19"},
        ],
    }
    r = client.post("/api/v2/registration/start", json=body,
                    headers={"X-World-Player": key})
    assert r.status_code == 200, r.text
    return r.json()


def test_bootstrap_login_me_logout(client):
    bad = client.post("/api/v2/admin/login",
                      json={"login": "owner", "password": "wrong"})
    assert bad.status_code == 401 and bad.json()["detail"] == "invalid_credentials"

    r = client.post("/api/v2/admin/login",
                    json={"login": "owner", "password": "secret-pass"})
    assert r.status_code == 200
    data = r.json()
    assert data["login"] == "owner" and data["role"] == "owner"
    assert data["token"].startswith("wadm.")

    auth = {"Authorization": f"Bearer {data['token']}"}
    assert client.get("/api/v2/admin/me", headers=auth).json() == {
        "login": "owner", "role": "owner",
    }
    assert client.post("/api/v2/admin/logout", headers=auth).json() == {"ok": True}
    assert client.get("/api/v2/admin/me", headers=auth).status_code == 401


def test_unauthorized_without_token(client):
    assert client.get("/api/v2/admin/me").status_code == 401
    assert client.get("/api/v2/admin/me",
                      headers={"Authorization": "Bearer nope"}).status_code == 401


def test_login_rate_limit(client):
    for _ in range(5):
        client.post("/api/v2/admin/login", json={"login": "owner", "password": "x"})
    r = client.post("/api/v2/admin/login", json={"login": "owner", "password": "x"})
    assert r.status_code == 429 and r.json()["detail"] == "too_many_attempts"


def test_students_list_with_and_without_identity(client):
    auth = _token(client)
    core.get_or_create_player("ghost-kid", "Призрак")   # игрок без анкеты
    _register(client)

    r = client.get("/api/v2/admin/students", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2 and data["page"] == 1
    ghost = next(i for i in data["items"] if i["display_name"] == "Призрак")
    assert ghost["first_name"] is None and ghost["phone_verified"] is False
    anna = next(i for i in data["items"] if i["first_name"] == "Анна")
    assert anna["parent_phone"] == "+7 916 111-22-33"
    assert anna["class_grade"] == 6


def test_students_search_and_filters(client):
    auth = _token(client)
    _register(client)
    _register(client, key="kid-2", last_name="Козлов", phone="8 900 555-66-77")

    r = client.get("/api/v2/admin/students", params={"q": "Козлов"}, headers=auth)
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["last_name"] == "Козлов"

    assert client.get("/api/v2/admin/students",
                      params={"verified": "false"}, headers=auth).json()["total"] == 2
    assert client.get("/api/v2/admin/students",
                      params={"verified": "true"}, headers=auth).json()["total"] == 0
    assert client.get("/api/v2/admin/students",
                      params={"class_grade": 6}, headers=auth).json()["total"] == 2
    assert client.get("/api/v2/admin/students",
                      params={"class_grade": 3}, headers=auth).json()["total"] == 0
    # LIKE-спецсимволы экранируются
    assert client.get("/api/v2/admin/students",
                      params={"q": "%"}, headers=auth).json()["total"] == 0


def test_student_card_and_404(client):
    auth = _token(client)
    _register(client)
    pid = core.get_or_create_player(HEADERS["X-World-Player"])["id"]

    r = client.get(f"/api/v2/admin/students/{pid}", headers=auth)
    assert r.status_code == 200
    card = r.json()
    assert card["player"]["id"] == pid
    assert card["identity"]["first_name"] == "Анна"
    assert card["identity"]["parent_phone"] == "+7 916 111-22-33"
    assert len(card["consents"]) == 2
    assert card["profile"] is None
    assert card["counters"]["inventory"] == 0
    assert client.get("/api/v2/admin/students/99999", headers=auth).status_code == 404
    assert client.get("/api/v2/admin/students/99999",
                      headers=auth).json()["detail"] == "player_not_found"


def test_patch_phone_resets_verified_and_audits(client):
    auth = _token(client)
    code = _register(client)["dev_code"]
    key = HEADERS["X-World-Player"]
    client.post("/api/v2/registration/verify", json={"code": code},
                headers={"X-World-Player": key})
    pid = core.get_or_create_player(key)["id"]

    r = client.patch(f"/api/v2/admin/students/{pid}",
                     json={"parent_phone": "+7 901 222-33-44", "reason": "мама попросила"},
                     headers=auth)
    assert r.status_code == 200
    assert r.json()["identity"]["phone_verified"] is False
    assert r.json()["identity"]["parent_phone"] == "+7 901 222-33-44"
    assert r.json()["identity"]["parent_phone_masked"] == "+7 901 ***-**-44"

    feed = client.get("/api/v2/admin/audit", params={"player_id": pid}, headers=auth).json()
    actions = [i["action"] for i in feed["items"]]
    assert "patch_identity" in actions
    entry = next(i for i in feed["items"] if i["action"] == "patch_identity")
    assert entry["payload"]["reason"] == "мама попросила"
    assert entry["actor"] == "owner"
    assert "+79012223344" not in str(entry["payload"])  # телефон в аудит не пишем


def test_adjust_coins_and_xp(client):
    auth = _token(client)
    key = HEADERS["X-World-Player"]
    core.get_or_create_player(key)
    pid = core.get_or_create_player(key)["id"]

    r = client.post(f"/api/v2/admin/students/{pid}/adjust",
                    json={"kind": "coins", "delta": 50, "reason": "поощрение"},
                    headers=auth)
    assert r.status_code == 200 and r.json() == {"coins": 50, "xp": 0}

    r = client.post(f"/api/v2/admin/students/{pid}/adjust",
                    json={"kind": "coins", "delta": -20, "reason": "штраф"},
                    headers=auth)
    assert r.json()["coins"] == 30

    over = client.post(f"/api/v2/admin/students/{pid}/adjust",
                       json={"kind": "coins", "delta": -999, "reason": "в минус нельзя"},
                       headers=auth)
    assert over.status_code == 409 and over.json()["detail"] == "not_enough_coins"

    r = client.post(f"/api/v2/admin/students/{pid}/adjust",
                    json={"kind": "xp", "delta": 100, "reason": "бонус"},
                    headers=auth)
    assert r.json()["xp"] == 100


def test_mastery_reset_and_master(client):
    auth = _token(client)
    key = HEADERS["X-World-Player"]
    pid = core.get_or_create_player(key)["id"]

    r = client.post(f"/api/v2/admin/students/{pid}/mastery",
                    json={"atom_id": "lex:cat", "action": "master", "reason": "зачёт"},
                    headers=auth)
    assert r.status_code == 200 and r.json() == {"ok": True}
    card = client.get(f"/api/v2/admin/students/{pid}", headers=auth).json()
    assert card["weakest_atoms"] == [
        {"atom_id": "lex:cat", "strength": 3, "wrong_count": 0}
    ]

    r = client.post(f"/api/v2/admin/students/{pid}/mastery",
                    json={"atom_id": "lex:cat", "action": "reset", "reason": "пересдача"},
                    headers=auth)
    assert r.json() == {"ok": True}
    card = client.get(f"/api/v2/admin/students/{pid}", headers=auth).json()
    assert card["weakest_atoms"] == []


def test_items_grant_revoke_and_404(client):
    auth = _token(client)
    key = HEADERS["X-World-Player"]
    pid = core.get_or_create_player(key)["id"]

    r = client.post(f"/api/v2/admin/students/{pid}/items",
                    json={"item_id": "fox-badge-first", "action": "grant",
                          "reason": "подарок"}, headers=auth)
    assert r.json() == {"ok": True}
    card = client.get(f"/api/v2/admin/students/{pid}", headers=auth).json()
    assert card["counters"]["inventory"] == 1

    missing = client.post(f"/api/v2/admin/students/{pid}/items",
                          json={"item_id": "no-such-item", "action": "grant",
                                "reason": "тест"}, headers=auth)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "item_not_found"

    r = client.post(f"/api/v2/admin/students/{pid}/items",
                    json={"item_id": "fox-badge-first", "action": "revoke",
                          "reason": "ошибка"}, headers=auth)
    assert r.json() == {"ok": True}
    card = client.get(f"/api/v2/admin/students/{pid}", headers=auth).json()
    assert card["counters"]["inventory"] == 0

    feed = client.get("/api/v2/admin/audit", params={"player_id": pid},
                      headers=auth).json()
    actions = [i["action"] for i in feed["items"]]
    assert actions.count("items") == 2  # grant + revoke; 404 в аудит не пишется
