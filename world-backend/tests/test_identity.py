"""HTTP-контракт /api/v2/registration/*: анкета, согласия, верификация телефона."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.identity import api as identity_api
from app.world import core
from app.world.db import reset_for_tests

HEADERS = {"X-World-Player": "kid-reg"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PHONE_VERIFICATION_REQUIRED", "0")
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    app = FastAPI()
    app.include_router(identity_api.router)
    with TestClient(app) as c:
        yield c
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def _body(**over):
    base = {
        "first_name": "Иван",
        "last_name": "Петров",
        "birth_date": "2014-05-10",
        "school_number": "12",
        "class_grade": 5,
        "class_letter": "А",
        "parent_email": "mama@example.com",
        "parent_phone": "8 (916) 123-45-67",
        "channel": "sms",
        "consents": [
            {"type": "pd_child", "version": "2026-09-19"},
            {"type": "privacy", "version": "2026-09-19"},
        ],
    }
    base.update(over)
    return base


def test_start_and_verify_happy_path(client):
    r = client.post("/api/v2/registration/start", json=_body(), headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "code_sent"
    assert data["channel"] == "sms"
    assert data["phone_masked"] == "+7 916 ***-**-67"
    assert data["cooldown_sec"] == 60
    code = data["dev_code"]

    bad = client.post("/api/v2/registration/verify",
                      json={"code": "000000" if code != "000000" else "111111"},
                      headers=HEADERS)
    assert bad.status_code == 409
    assert bad.json()["detail"] == "code_invalid"
    assert bad.json()["attempts_left"] == 4

    ok = client.post("/api/v2/registration/verify", json={"code": code}, headers=HEADERS)
    assert ok.status_code == 200 and ok.json() == {"status": "verified"}

    st = client.get("/api/v2/registration/status", headers=HEADERS).json()
    assert st["identity"]["phone_verified"] is True
    assert "parent_phone" not in st["identity"]
    assert st["identity"]["parent_phone_masked"] == "+7 916 ***-**-67"
    assert {c["type"] for c in st["consents"]} == {"pd_child", "privacy"}


def test_resend_within_cooldown_rejected(client):
    client.post("/api/v2/registration/start", json=_body(), headers=HEADERS)
    again = client.post("/api/v2/registration/start", json=_body(), headers=HEADERS)
    assert again.status_code == 409
    assert again.json()["detail"] == "phone_recently_sent"


def test_missing_consent_rejected(client):
    r = client.post("/api/v2/registration/start",
                    json=_body(consents=[{"type": "privacy", "version": "2026-09-19"}]),
                    headers=HEADERS)
    assert r.status_code == 409
    assert r.json()["detail"] == "consent_required:pd_child"
    old = client.post("/api/v2/registration/start",
                      json=_body(consents=[
                          {"type": "pd_child", "version": "2025-01-01"},
                          {"type": "privacy", "version": "2026-09-19"},
                      ]), headers=HEADERS)
    assert old.status_code == 409
    assert old.json()["detail"] == "consent_required:pd_child"


def test_optional_marketing_consent_recorded(client):
    r = client.post("/api/v2/registration/start",
                    json=_body(consents=[
                        {"type": "pd_child", "version": "2026-09-19"},
                        {"type": "privacy", "version": "2026-09-19"},
                        {"type": "marketing", "version": "2026-09-19"},
                    ]), headers=HEADERS)
    assert r.status_code == 200
    st = client.get("/api/v2/registration/status", headers=HEADERS).json()
    assert "marketing" in {c["type"] for c in st["consents"]}


def test_validation_phone_age_email(client):
    assert client.post("/api/v2/registration/start",
                       json=_body(parent_phone="123"), headers=HEADERS).status_code == 422
    assert client.post("/api/v2/registration/start",
                       json=_body(birth_date="2024-01-01"), headers=HEADERS).status_code == 422
    assert client.post("/api/v2/registration/start",
                       json=_body(birth_date="2000-01-01"), headers=HEADERS).status_code == 422
    assert client.post("/api/v2/registration/start",
                       json=_body(parent_email="nope"), headers=HEADERS).status_code == 422
    assert client.post("/api/v2/registration/start",
                       json=_body(class_grade=12), headers=HEADERS).status_code == 422


def test_verify_without_start(client):
    r = client.post("/api/v2/registration/verify", json={"code": "123456"}, headers=HEADERS)
    assert r.status_code == 409
    assert r.json()["detail"] == "no_pending_verification"


def test_status_empty_for_new_player(client):
    st = client.get("/api/v2/registration/status", headers=HEADERS).json()
    assert st == {"identity": None, "consents": [], "is_registered": False}


def test_requires_player_header(client):
    assert client.get("/api/v2/registration/status").status_code == 401


def test_phone_change_resets_verification(client):
    r = client.post("/api/v2/registration/start", json=_body(), headers=HEADERS).json()
    client.post("/api/v2/registration/verify", json={"code": r["dev_code"]}, headers=HEADERS)
    assert client.get("/api/v2/registration/status", headers=HEADERS).json()["identity"]["phone_verified"] is True
    # новый телефон → верификация сброшена
    other = FastAPI()
    other.include_router(identity_api.router)
    with TestClient(other) as c2:
        # другой игрок, чтобы не сработал cooldown по player_id
        c2.post("/api/v2/registration/start", json=_body(parent_phone="+7 900 111-22-33"),
                headers={"X-World-Player": "kid-reg-2"})
    # тот же игрок, но снять cooldown через правку created_at
    from app.world.db import get_conn
    get_conn().execute(
        "UPDATE phone_verifications SET created_at='2020-01-01 00:00:00' WHERE player_id=?",
        (core.get_or_create_player("kid-reg")["id"],),
    )
    client.post("/api/v2/registration/start",
                json=_body(parent_phone="+7 903 999-88-77"), headers=HEADERS)
    st = client.get("/api/v2/registration/status", headers=HEADERS).json()
    assert st["identity"]["phone_verified"] is False
    assert st["identity"]["parent_phone_masked"] == "+7 903 ***-**-77"
