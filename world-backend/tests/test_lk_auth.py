"""Тесты Этапа 1 ЛК: регистрация по телефону, подтверждение через ботов, профили.

Покрытые потоки (ТЗ §7):
- старт: нормализация телефона, согласия, rate-limit (cooldown + daily),
  повторный старт для активного аккаунта;
- подтверждение: happy path через бота, неподтверждённый номер, попытки,
  no_pending, already_active;
- профили: несколько детей на один номер из BigBen, гостевой режим,
  профили по /me, logout, протухшая сессия.
"""
from __future__ import annotations

import json

import pytest

from app.lk import bridge, service
from app.world import core

PHONE = "+79161234567"
PHONE_2 = "+79261234567"
CONSENTS = [
    {"type": "pd_child", "version": service.CONSENT_VERSION},
    {"type": "privacy", "version": service.CONSENT_VERSION},
]

STUDENTS = [
    {"id": 101, "fio": "Иванова Маша", "phone": PHONE,
     "active_groups": [{"id": 7, "caption": "SP1 Группа А"}]},
    {"id": 102, "fio": "Иванов Пётр", "phone": PHONE,
     "active_groups": []},
]
GROUP_NAMES = {7: {"id": 7, "caption": "SP1 Группа А"}}


@pytest.fixture()
def lk_db(tmp_path, monkeypatch):
    from app.world.db import reset_for_tests

    monkeypatch.setattr(bridge, "phone_confirmed", lambda phone: (True, ["telegram"]))
    reset_for_tests(str(tmp_path / "lk.sqlite"))
    yield
    reset_for_tests(str(tmp_path / "lk-after.sqlite"))


@pytest.fixture()
def lk_db_bigben(lk_db, monkeypatch):
    from app.lk import bigben

    # Подменяем list_students, а не students_by_phone — так через фикстуру
    # проходит реальная логика сопоставления номеров (+7/8, ребёнок=родитель).
    monkeypatch.setattr(bigben, "configured", lambda: True)
    monkeypatch.setattr(bigben, "list_students",
                        lambda *a, **kw: list(STUDENTS))
    monkeypatch.setattr(bigben, "groups_by_ids",
                        lambda ids: {i: GROUP_NAMES[i] for i in ids if i in GROUP_NAMES})
    return lk_db


def _start(phone: str = PHONE, name: str = "Ольга Иванова"):
    return service.start_auth(phone, name, _consents(), "127.0.0.1", "pytest")


def _consents():
    from app.lk.schemas import ConsentIn

    return [ConsentIn(**c) for c in CONSENTS]


def _confirm(phone: str = PHONE):
    return service.confirm_via_bot(phone)


# ---------- старт ----------

def test_start_creates_pending_account(lk_db):
    out = _start()
    assert out["status"] == "awaiting_bot"
    assert out["phone_masked"] == "+7 916 ***-**-67"
    assert out["bot_links"]["max"].startswith("https://max.ru/")
    assert service.get_status(PHONE)["status"] == "pending"


def test_start_requires_consents(lk_db):
    from app.lk.schemas import ConsentIn

    with pytest.raises(core.Conflict) as ei:
        service.start_auth(PHONE, "Ольга", [ConsentIn(type="privacy", version=service.CONSENT_VERSION)],
                           None, None)
    assert "consent_required" in str(ei.value)


def test_start_normalizes_phone(lk_db):
    out = _start("8 (916) 123-45-67")
    assert service.get_status(PHONE)["status"] == "pending"
    assert out["phone_masked"] == "+7 916 ***-**-67"


def test_start_rejects_bad_phone(lk_db):
    from app.lk.schemas import StartAuth

    with pytest.raises(ValueError):
        StartAuth(phone="123", parent_name="Ольга")


def test_start_rate_limit(lk_db):
    _start()
    with pytest.raises(core.Conflict) as ei:
        _start()
    assert "recently_sent" in str(ei.value)


def test_start_daily_limit(lk_db, monkeypatch):
    from app.lk import service as svc

    monkeypatch.setattr(svc, "START_COOLDOWN_SEC", 0)
    for _ in range(svc.START_DAILY_LIMIT):
        _start()
    with pytest.raises(core.Conflict) as ei:
        _start()
    assert "daily_limit" in str(ei.value)


def test_status_unknown_phone(lk_db):
    st = service.get_status(PHONE_2)
    assert st["status"] == "none"
    assert st["has_pending"] is False


# ---------- подтверждение ----------

def test_confirm_happy_path_with_children(lk_db_bigben):
    _start()
    out = _confirm()
    assert out["status"] == "verified"
    assert out["token"]
    assert out["guest"] is False
    names = {p["child_name"] for p in out["profiles"]}
    assert names == {"Иванова Маша", "Иванов Пётр"}
    masha = next(p for p in out["profiles"] if p["child_name"] == "Иванова Маша")
    assert masha["student_id"] == 101
    assert masha["active_groups"] == [GROUP_NAMES[7]]
    assert service.get_status(PHONE)["status"] == "active"


def test_confirm_not_confirmed_in_bot(lk_db, monkeypatch):
    monkeypatch.setattr(bridge, "phone_confirmed", lambda phone: (False, []))
    _start()
    with pytest.raises(core.Conflict) as ei:
        _confirm()
    assert "bot_phone_unconfirmed" in str(ei.value)
    assert service.get_status(PHONE)["status"] == "pending"


def test_confirm_bridge_down_is_502_domain(lk_db, monkeypatch):
    def _boom(phone):
        raise bridge.BridgeError("timeout")

    monkeypatch.setattr(bridge, "phone_confirmed", _boom)
    _start()
    with pytest.raises(bridge.BridgeError):
        _confirm()


def test_confirm_no_pending(lk_db):
    with pytest.raises(core.Conflict) as ei:
        _confirm()
    assert "no_pending" in str(ei.value)


def test_confirm_attempts_limited(lk_db, monkeypatch):
    monkeypatch.setattr(bridge, "phone_confirmed", lambda phone: (False, []))
    _start()
    from app.lk import service as svc

    monkeypatch.setattr(svc, "CONFIRM_MAX_ATTEMPTS", 2)
    for _ in range(2):
        with pytest.raises(core.Conflict):
            _confirm()
    with pytest.raises(core.Conflict) as ei:
        _confirm()
    assert "too_many_attempts" in str(ei.value)


def test_confirm_active_account_reissues_session(lk_db_bigben):
    _start()
    first = _confirm()
    second = _confirm()
    assert second["status"] == "already_active"
    assert second["token"] != first["token"]
    assert {p["child_name"] for p in second["profiles"]} == {"Иванова Маша", "Иванов Пётр"}


# ---------- гостевой режим ----------

def test_guest_mode_when_no_students_in_crm(lk_db_bigben):
    _start(PHONE_2)
    out = _confirm(PHONE_2)
    assert out["guest"] is True
    assert len(out["profiles"]) == 1
    assert out["profiles"][0]["source"] == "guest"
    assert out["profiles"][0]["student_id"] is None


def test_guest_profile_created_once(lk_db_bigben):
    _start(PHONE_2)
    _confirm(PHONE_2)
    out = _confirm(PHONE_2)
    assert len(out["profiles"]) == 1  # не дублируется


def test_profiles_sync_removes_stale_children(lk_db_bigben, monkeypatch):
    from app.lk import bigben

    _start()
    out = _confirm()
    assert len(out["profiles"]) == 2
    # Один ребёнок ушёл из CRM (сменил номер) — профиль подтягивается заново.
    monkeypatch.setattr(bigben, "students_by_phone", lambda phone: [STUDENTS[0]])
    me = service.me(out["token"])
    assert [p["child_name"] for p in me["profiles"]] == ["Иванова Маша"]


# ---------- сессии ----------

def test_me_and_logout(lk_db_bigben):
    _start()
    out = _confirm()
    me = service.me(out["token"])
    assert me["account"]["parent_name"] == "Ольга Иванова"
    assert me["account"]["guest"] is False
    assert me["account"]["phone_masked"] == "+7 916 ***-**-67"

    service.logout(out["token"])
    with pytest.raises(core.Conflict) as ei:
        service.me(out["token"])
    assert "unauthorized" in str(ei.value)


def test_me_expired_session(lk_db_bigben, monkeypatch):
    from datetime import datetime, timedelta

    _start()
    out = _confirm()
    past = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    from app.world.db import get_conn

    get_conn().execute(
        "UPDATE lk_sessions SET expires_at=? WHERE account_id=?",
        (past, service.resolve_session(out["token"])["id"]),
    )
    with pytest.raises(core.Conflict):
        service.me(out["token"])


def test_me_requires_active_account(lk_db):
    _start()
    # Аккаунт ещё pending — resolve_session его не отдаст, поэтому имитируем
    # прямую вставку сессии и проверяем, что pending-аккаунт не пускает.
    from app.world.db import get_conn

    account_id = get_conn().execute(
        "SELECT id FROM lk_accounts WHERE phone=?", (PHONE,)
    ).fetchone()["id"]
    token = "x" * 64
    get_conn().execute(
        "INSERT INTO lk_sessions (token, account_id, expires_at) VALUES (?,?,"
        " datetime('now','+1 day'))",
        (token, account_id),
    )
    with pytest.raises(core.Conflict):
        service.me(token)


# ---------- HTTP-слой ----------

def test_http_flow_end_to_end(lk_db_bigben):
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    r = client.post("/api/lk/auth/start", json={
        "phone": "8 916 123-45-67", "parent_name": "Ольга Иванова", "consents": CONSENTS,
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "awaiting_bot"

    r = client.get("/api/lk/auth/status", params={"phone": PHONE})
    assert r.json()["status"] == "pending"

    r = client.post("/api/lk/auth/confirm-bot", json={"phone": PHONE})
    assert r.status_code == 200, r.text
    token = r.json()["token"]

    r = client.get("/api/lk/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.json()["account"]["phone_masked"] == "+7 916 ***-**-67"

    r = client.get("/api/lk/me", headers={"Authorization": "Bearer bad"})
    assert r.status_code == 409

    r = client.post("/api/lk/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    r = client.get("/api/lk/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 409


def test_http_bridge_down_returns_502(lk_db, monkeypatch):
    from fastapi.testclient import TestClient

    from main import app

    def _boom(phone):
        raise bridge.BridgeError("timeout")

    monkeypatch.setattr(bridge, "phone_confirmed", _boom)
    client = TestClient(app)
    client.post("/api/lk/auth/start", json={
        "phone": PHONE, "parent_name": "Ольга", "consents": CONSENTS,
    })
    r = client.post("/api/lk/auth/confirm-bot", json={"phone": PHONE})
    assert r.status_code == 502
    assert r.json()["detail"] == "bot_unreachable"


# ---------- телефон ребёнка = телефон родителя ----------

def test_child_phone_with_8_prefix_matches(lk_db_bigben):
    """Номер ребёнка из CRM в формате 8... сопоставляется с +7 родителя."""
    from app.lk import bigben

    students = [{"id": 201, "fio": "Петрова Аня", "phone": "8 916 123-45-67",
                 "active_groups": []}]
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(
            bigben, "list_students",
            lambda *a, **kw: list(students))
        found = bigben.students_by_phone(PHONE)
        assert [s["id"] for s in found] == [201]
    finally:
        monkeypatch.undo()
