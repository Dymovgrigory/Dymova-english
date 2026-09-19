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


# --- канал telegram: подтверждение через бота без SMS -------------------------


def _link_telegram(player_key: str, tg_user_id: str = "555000111") -> None:
    from app.world.db import get_conn

    player_id = core.get_or_create_player(player_key)["id"]
    get_conn().execute(
        "INSERT INTO external_identities (provider, provider_user_id, player_id, display_name)"
        " VALUES ('telegram', ?, ?, 'Тест')",
        (tg_user_id, player_id),
    )


def test_start_telegram_channel_awaiting_bot(client):
    from app.world.db import get_conn

    r = client.post("/api/v2/registration/start",
                    json=_body(channel="telegram"), headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data == {
        "status": "awaiting_bot",
        "channel": "telegram",
        "phone_masked": "+7 916 ***-**-67",
        "cooldown_sec": 0,
    }
    # SMS не отправлялась: верификаций нет, повторный start не бьёт rate-limit.
    player_id = core.get_or_create_player("kid-reg")["id"]
    cnt = get_conn().execute(
        "SELECT COUNT(*) AS c FROM phone_verifications WHERE player_id=?",
        (player_id,),
    ).fetchone()["c"]
    assert cnt == 0
    again = client.post("/api/v2/registration/start",
                        json=_body(channel="telegram"), headers=HEADERS)
    assert again.status_code == 200
    # Анкета и согласия сохранены.
    st = client.get("/api/v2/registration/status", headers=HEADERS).json()
    assert st["identity"]["phone_verified"] is False
    assert {c["type"] for c in st["consents"]} == {"pd_child", "privacy"}


def test_confirm_bot_without_start(client):
    r = client.post("/api/v2/registration/confirm-bot", headers=HEADERS)
    assert r.status_code == 409
    assert r.json()["detail"] == "no_pending_verification"


def test_confirm_bot_no_telegram_link(client):
    client.post("/api/v2/registration/start", json=_body(channel="telegram"), headers=HEADERS)
    r = client.post("/api/v2/registration/confirm-bot", headers=HEADERS)
    assert r.status_code == 409
    assert r.json()["detail"] == "no_telegram_link"


def test_confirm_bot_phone_unconfirmed(client, monkeypatch):
    client.post("/api/v2/registration/start", json=_body(channel="telegram"), headers=HEADERS)
    _link_telegram("kid-reg")
    monkeypatch.setattr(
        "app.identity.service.bridge.fetch_bot_prefill",
        lambda provider, uid: {"phone": "+79161234567", "phone_confirmed": False},
    )
    r = client.post("/api/v2/registration/confirm-bot", headers=HEADERS)
    assert r.status_code == 409
    assert r.json()["detail"] == "bot_phone_unconfirmed"


def test_confirm_bot_bridge_down(client, monkeypatch):
    client.post("/api/v2/registration/start", json=_body(channel="telegram"), headers=HEADERS)
    _link_telegram("kid-reg")
    monkeypatch.setattr("app.identity.service.bridge.fetch_bot_prefill", lambda p, u: None)
    r = client.post("/api/v2/registration/confirm-bot", headers=HEADERS)
    assert r.status_code == 409
    assert r.json()["detail"] == "bot_phone_unconfirmed"


def test_confirm_bot_phone_mismatch(client, monkeypatch):
    client.post("/api/v2/registration/start", json=_body(channel="telegram"), headers=HEADERS)
    _link_telegram("kid-reg")
    monkeypatch.setattr(
        "app.identity.service.bridge.fetch_bot_prefill",
        lambda provider, uid: {"phone": "+79009998877", "phone_confirmed": True},
    )
    r = client.post("/api/v2/registration/confirm-bot", headers=HEADERS)
    assert r.status_code == 409
    assert r.json()["detail"] == "phone_mismatch"


def test_confirm_bot_happy_path_and_idempotent(client, monkeypatch):
    client.post("/api/v2/registration/start", json=_body(channel="telegram"), headers=HEADERS)
    _link_telegram("kid-reg")
    calls = []

    def fake_prefill(provider, uid):
        calls.append((provider, uid))
        assert provider == "telegram"
        return {"phone": "8 916 123-45-67", "phone_confirmed": True}

    monkeypatch.setattr("app.identity.service.bridge.fetch_bot_prefill", fake_prefill)
    r = client.post("/api/v2/registration/confirm-bot", headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == {"status": "verified"}
    assert calls == [("telegram", "555000111")]

    st = client.get("/api/v2/registration/status", headers=HEADERS).json()
    assert st["is_registered"] is True
    assert st["identity"]["phone_verified"] is True

    # Повторный вызов — успех, но мост больше не дёргаем.
    again = client.post("/api/v2/registration/confirm-bot", headers=HEADERS)
    assert again.status_code == 200
    assert len(calls) == 1


def test_start_telegram_then_sms_channel_keeps_flow(client):
    """После awaiting_bot можно переключиться на SMS — обычный флоу не сломан."""
    client.post("/api/v2/registration/start", json=_body(channel="telegram"), headers=HEADERS)
    r = client.post("/api/v2/registration/start", json=_body(channel="sms"), headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "code_sent"
    ok = client.post("/api/v2/registration/verify",
                     json={"code": r.json()["dev_code"]}, headers=HEADERS)
    assert ok.status_code == 200


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
