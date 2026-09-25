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
    app.include_router(identity_api.auth_router)
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
        "password": "secret123",
        "channel": "email",
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
    assert data["channel"] == "email"
    assert data["email_masked"] == "m***a@example.com"
    assert data["cooldown_sec"] == 60
    code = data["dev_code"]

    bad = client.post("/api/v2/registration/verify",
                      json={"code": "000000" if code != "000000" else "111111"},
                      headers=HEADERS)
    assert bad.status_code == 409
    assert bad.json()["detail"] == "code_invalid"
    assert bad.json()["attempts_left"] == 4

    ok = client.post("/api/v2/registration/verify", json={"code": code}, headers=HEADERS)
    assert ok.status_code == 200
    assert ok.json()["status"] == "verified"
    assert ok.json()["token"].startswith("wses.")
    assert ok.json()["external_key"] == "kid-reg"

    st = client.get("/api/v2/registration/status", headers=HEADERS).json()
    assert st["identity"]["email_verified"] is True
    assert st["identity"]["verified"] is True
    assert "parent_phone" not in st["identity"]
    assert st["identity"]["parent_phone_masked"] == "+7 916 ***-**-67"
    assert {c["type"] for c in st["consents"]} == {"pd_child", "privacy"}


def test_resend_within_cooldown_rejected(client):
    client.post("/api/v2/registration/start", json=_body(), headers=HEADERS)
    again = client.post("/api/v2/registration/start", json=_body(), headers=HEADERS)
    assert again.status_code == 409
    assert again.json()["detail"] == "email_recently_sent"


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
    # Код на почту не отправлялся: верификаций нет, повторный start не бьёт rate-limit.
    player_id = core.get_or_create_player("kid-reg")["id"]
    cnt = get_conn().execute(
        "SELECT COUNT(*) AS c FROM email_verifications WHERE player_id=?",
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
    assert r.json()["status"] == "verified"
    assert r.json()["token"].startswith("wses.")
    assert calls == [("telegram", "555000111")]

    st = client.get("/api/v2/registration/status", headers=HEADERS).json()
    assert st["is_registered"] is True
    assert st["identity"]["phone_verified"] is True
    assert st["identity"]["email_verified"] is True

    # Повторный вызов — успех, но мост больше не дёргаем.
    again = client.post("/api/v2/registration/confirm-bot", headers=HEADERS)
    assert again.status_code == 200
    assert again.json()["status"] == "verified"
    assert len(calls) == 1


def test_login_after_email_registration(client):
    r = client.post("/api/v2/registration/start", json=_body(), headers=HEADERS).json()
    client.post("/api/v2/registration/verify", json={"code": r["dev_code"]}, headers=HEADERS)

    bad = client.post("/api/v2/auth/login",
                      json={"email": "mama@example.com", "password": "wrong-pass"})
    assert bad.status_code == 409
    assert bad.json()["detail"] == "bad_credentials"

    ok = client.post("/api/v2/auth/login",
                     json={"email": "Mama@Example.com", "password": "secret123"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "ok"
    assert body["external_key"] == "kid-reg"
    assert body["token"].startswith("wses.")


def test_login_after_telegram_registration(client, monkeypatch):
    client.post("/api/v2/registration/start", json=_body(channel="telegram"), headers=HEADERS)
    _link_telegram("kid-reg")
    monkeypatch.setattr(
        "app.identity.service.bridge.fetch_bot_prefill",
        lambda p, u: {"phone": "+79161234567", "phone_confirmed": True},
    )
    client.post("/api/v2/registration/confirm-bot", headers=HEADERS)
    ok = client.post("/api/v2/auth/login",
                     json={"email": "mama@example.com", "password": "secret123"})
    assert ok.status_code == 200
    assert ok.json()["external_key"] == "kid-reg"


def test_login_unverified_email(client):
    client.post("/api/v2/registration/start", json=_body(), headers=HEADERS)
    r = client.post("/api/v2/auth/login",
                    json={"email": "mama@example.com", "password": "secret123"})
    assert r.status_code == 409
    assert r.json()["detail"] == "email_not_verified"


def test_email_taken_blocks_second_registration(client):
    first = client.post("/api/v2/registration/start", json=_body(), headers=HEADERS).json()
    client.post("/api/v2/registration/verify", json={"code": first["dev_code"]}, headers=HEADERS)
    other = {"X-World-Player": "kid-other"}
    again = client.post(
        "/api/v2/registration/start",
        json=_body(parent_phone="8 916 999-88-77", parent_email="mama@example.com"),
        headers=other,
    )
    assert again.status_code == 409
    assert again.json()["detail"] == "email_taken"


def test_password_too_short_rejected(client):
    assert client.post("/api/v2/registration/start",
                       json=_body(password="short"), headers=HEADERS).status_code == 422


def test_start_telegram_then_email_channel_keeps_flow(client):
    """После awaiting_bot можно переключиться на email — обычный флоу не сломан."""
    client.post("/api/v2/registration/start", json=_body(channel="telegram"), headers=HEADERS)
    r = client.post("/api/v2/registration/start", json=_body(channel="email"), headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "code_sent"
    ok = client.post("/api/v2/registration/verify",
                     json={"code": r.json()["dev_code"]}, headers=HEADERS)
    assert ok.status_code == 200


def test_email_change_resets_verification(client):
    r = client.post("/api/v2/registration/start", json=_body(), headers=HEADERS).json()
    client.post("/api/v2/registration/verify", json={"code": r["dev_code"]}, headers=HEADERS)
    assert client.get("/api/v2/registration/status", headers=HEADERS).json()["identity"]["email_verified"] is True
    # новый email → верификация сброшена
    other = FastAPI()
    other.include_router(identity_api.router)
    with TestClient(other) as c2:
        # другой игрок, чтобы не сработал cooldown по player_id
        c2.post("/api/v2/registration/start", json=_body(parent_email="new@example.com"),
                headers={"X-World-Player": "kid-reg-2"})
    # тот же игрок, но снять cooldown через правку created_at
    from app.world.db import get_conn
    get_conn().execute(
        "UPDATE email_verifications SET created_at='2020-01-01 00:00:00' WHERE player_id=?",
        (core.get_or_create_player("kid-reg")["id"],),
    )
    client.post("/api/v2/registration/start",
                json=_body(parent_email="other@example.com"), headers=HEADERS)
    st = client.get("/api/v2/registration/status", headers=HEADERS).json()
    assert st["identity"]["email_verified"] is False
    assert st["identity"]["verified"] is False


def test_legacy_phone_verified_counts_as_registered(client):
    """Игроки, подтвердившие телефон через бота до email-эпохи, остаются зарегистрированными."""
    from app.world.db import get_conn

    client.post("/api/v2/registration/start", json=_body(channel="telegram"), headers=HEADERS)
    player_id = core.get_or_create_player("kid-reg")["id"]
    get_conn().execute(
        "UPDATE player_identity SET phone_verified_at='2026-09-19 10:00:00' WHERE player_id=?",
        (player_id,),
    )
    st = client.get("/api/v2/registration/status", headers=HEADERS).json()
    assert st["is_registered"] is True
    assert st["identity"]["verified"] is True
    assert st["identity"]["email_verified"] is False


# --- восстановление доступа по email (сайт) ----------------------------------


def test_recovery_start_and_verify(client):
    r = client.post("/api/v2/registration/start", json=_body(), headers=HEADERS).json()
    client.post("/api/v2/registration/verify", json={"code": r["dev_code"]}, headers=HEADERS)

    from app.world.db import get_conn
    get_conn().execute(
        "UPDATE email_verifications SET created_at='2020-01-01 00:00:00' WHERE player_id=?",
        (core.get_or_create_player("kid-reg")["id"],),
    )

    start = client.post("/api/v2/registration/recovery/start",
                        json={"email": "Mama@Example.com"})
    assert start.status_code == 200
    data = start.json()
    assert data["status"] == "code_sent"
    assert data["email_masked"] == "m***a@example.com"
    code = data["dev_code"]

    bad = client.post("/api/v2/registration/recovery/verify",
                      json={"email": "mama@example.com",
                            "code": "000000" if code != "000000" else "111111"})
    assert bad.status_code == 409
    assert bad.json()["detail"] == "code_invalid"

    ok = client.post("/api/v2/registration/recovery/verify",
                     json={"email": "mama@example.com", "code": code})
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "code_ok"
    assert "reset_token" in body
    assert "token" not in body

    pw = client.post("/api/v2/registration/recovery/password",
                     json={"reset_token": body["reset_token"], "password": "newpass99"})
    assert pw.status_code == 200
    assert pw.json()["status"] == "verified"
    assert pw.json()["token"].startswith("wses.")
    assert pw.json()["external_key"] == "kid-reg"

    login = client.post("/api/v2/auth/login",
                        json={"email": "mama@example.com", "password": "newpass99"})
    assert login.status_code == 200

    # токен одноразовый
    again = client.post("/api/v2/registration/recovery/password",
                        json={"reset_token": body["reset_token"], "password": "another99"})
    assert again.status_code == 409


def test_recovery_by_phone(client):
    r = client.post("/api/v2/registration/start", json=_body(), headers=HEADERS).json()
    client.post("/api/v2/registration/verify", json={"code": r["dev_code"]}, headers=HEADERS)
    from app.world.db import get_conn
    get_conn().execute(
        "UPDATE email_verifications SET created_at='2020-01-01 00:00:00' WHERE player_id=?",
        (core.get_or_create_player("kid-reg")["id"],),
    )

    start = client.post("/api/v2/registration/recovery/start",
                        json={"phone": "8 916 123-45-67"})
    assert start.status_code == 200
    assert start.json()["status"] == "code_sent"
    assert start.json()["email_masked"] == "m***a@example.com"
    code = start.json()["dev_code"]

    ok = client.post("/api/v2/registration/recovery/verify",
                     json={"phone": "+79161234567", "code": code})
    assert ok.status_code == 200
    assert ok.json()["status"] == "code_ok"
    pw = client.post("/api/v2/registration/recovery/password",
                     json={"reset_token": ok.json()["reset_token"], "password": "phonepass1"})
    assert pw.status_code == 200
    assert pw.json()["token"].startswith("wses.")
    assert pw.json()["external_key"] == "kid-reg"


def test_phone_taken_blocks_second_registration(client):
    first = client.post("/api/v2/registration/start", json=_body(), headers=HEADERS).json()
    client.post("/api/v2/registration/verify", json={"code": first["dev_code"]}, headers=HEADERS)

    other = {"X-World-Player": "kid-other"}
    client.post("/api/world/players", json={"display_name": "Другой"}, headers=other)
    again = client.post("/api/v2/registration/start",
                        json=_body(parent_email="other@example.com"), headers=other)
    assert again.status_code == 409
    assert again.json()["detail"] == "phone_taken"


def test_verify_returns_session_token(client):
    r = client.post("/api/v2/registration/start", json=_body(), headers=HEADERS).json()
    verified = client.post("/api/v2/registration/verify",
                           json={"code": r["dev_code"]}, headers=HEADERS)
    assert verified.status_code == 200
    body = verified.json()
    assert body["status"] == "verified"
    assert body["token"].startswith("wses.")
    assert body["external_key"] == "kid-reg"


def test_recovery_unknown_email_same_response(client):
    """Anti-enumeration: для неизвестного ящика ответ неотличим."""
    r = client.post("/api/v2/registration/recovery/start",
                    json={"email": "ghost@example.com"})
    assert r.status_code == 200
    assert r.json()["status"] == "code_sent"
    assert r.json()["email_masked"] == "g***t@example.com"
    assert "dev_code" not in r.json()
    # verify без запрошенного кода
    v = client.post("/api/v2/registration/recovery/verify",
                    json={"email": "ghost@example.com", "code": "123456"})
    assert v.status_code == 409
    assert v.json()["detail"] == "no_pending_verification"


def test_recovery_verify_without_start(client):
    r = client.post("/api/v2/registration/recovery/verify",
                    json={"email": "mama@example.com", "code": "123456"})
    assert r.status_code == 409
    assert r.json()["detail"] == "no_pending_verification"
