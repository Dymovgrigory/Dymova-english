"""Вход в ЛК по телефону и паролю, регистрация нового клиента, пароль от администратора.

- регистрация: аккаунт с паролем, гостевой профиль с именем ребёнка, заявка в CRM;
- уже клиент школы (номер есть в CRM) → регистрация не создаёт аккаунт (already_client);
- чужой номер: самостоятельная регистрация не открывает детей из CRM;
- вход: верный/неверный пароль, одинаковая ошибка, лимит неудачных попыток;
- администратор задаёт пароль → номер подтверждён, видны дети из CRM, старые сессии закрыты;
- смена пароля из кабинета.
"""
from __future__ import annotations

import pytest

from app.lk import bigben, password_auth, service
from app.world import core
from app.world.db import get_conn

from tests.test_lk_auth import CONSENTS, PHONE, PHONE_2, STUDENTS, lk_db, lk_db_bigben  # noqa: F401


def _consents():
    from app.lk.schemas import ConsentIn

    return [ConsentIn(**c) for c in CONSENTS]


@pytest.fixture()
def leads(monkeypatch):
    sent = []
    monkeypatch.setattr(bigben, "create_lead", lambda name, phone, comment="", source="": sent.append(
        {"name": name, "phone": phone, "comment": comment, "source": source}) or 555)
    return sent


def test_register_new_client_creates_account_and_crm_lead(lk_db_bigben, leads):
    out = password_auth.register(PHONE_2, "secret77", "Анна Петрова", "Миша", "7", _consents())
    assert out["status"] == "registered" and out["token"] and out["guest"]
    assert [p["child_name"] for p in out["profiles"]] == ["Миша"]
    assert leads == [{"name": "Анна Петрова", "phone": PHONE_2, "source": "Личный кабинет",
                      "comment": "Регистрация в личном кабинете. Ребёнок: Миша, возраст: 7"}]
    row = get_conn().execute("SELECT * FROM lk_accounts WHERE phone=?", (PHONE_2,)).fetchone()
    assert row["password_hash"] and "secret77" not in row["password_hash"] and row["crm_lead_id"] == "555"
    with pytest.raises(core.Conflict, match="already_registered"):
        password_auth.register(PHONE_2, "other123", "Анна", "Миша", "", _consents())


def test_register_rejects_existing_school_client_and_weak_password(lk_db_bigben, leads):
    with pytest.raises(core.Conflict, match="already_client"):
        password_auth.register(PHONE, "secret77", "Ольга", "Маша", "", _consents())
    with pytest.raises(core.Conflict, match="password_too_short"):
        password_auth.register(PHONE_2, "123", "Анна", "Миша", "", _consents())
    with pytest.raises(core.Conflict, match="consent_required"):
        password_auth.register(PHONE_2, "secret77", "Анна", "Миша", "", [])
    assert leads == []


def test_self_registered_unverified_phone_never_sees_crm_children(lk_db_bigben, leads, monkeypatch):
    # номер ещё не в CRM — регистрация проходит
    monkeypatch.setattr(bigben, "list_students", lambda *a, **kw: [])
    password_auth.register(PHONE, "secret77", "Кто-то", "Ребёнок", "", _consents())
    # потом этот номер появляется в CRM (например, чужая семья) — дети не подтягиваются без подтверждения
    monkeypatch.setattr(bigben, "list_students", lambda *a, **kw: list(STUDENTS))
    out = password_auth.login(PHONE, "secret77")
    assert out["guest"] and all(p["source"] == "guest" for p in out["profiles"])


def test_login_password_errors_and_limit(lk_db_bigben, leads):
    password_auth.register(PHONE_2, "secret77", "Анна", "Миша", "", _consents())
    assert password_auth.login("8 (926) 123-45-67", "secret77")["status"] == "logged_in"
    with pytest.raises(core.Conflict, match="bad_credentials"):
        password_auth.login(PHONE_2, "wrong-pass")
    with pytest.raises(core.Conflict, match="bad_credentials"):
        password_auth.login("+79991112233", "secret77")  # нет такого номера — та же ошибка
    for _ in range(password_auth.LOGIN_FAILS_LIMIT):
        with pytest.raises(core.Conflict):
            password_auth.login(PHONE_2, "wrong-pass")
    with pytest.raises(core.Conflict, match="too_many_attempts"):
        password_auth.login(PHONE_2, "secret77")


def test_admin_sets_password_for_school_client(lk_db_bigben):
    password_auth.admin_set_password(PHONE, "fox12345", "Ольга Иванова")
    out = password_auth.login(PHONE, "fox12345")
    # администратор подтверждает номер — видны оба ребёнка из CRM
    assert sorted(p["child_name"] for p in out["profiles"]) == ["Иванов Пётр", "Иванова Маша"]
    password_auth.admin_set_password(PHONE, "new-pass-1")
    assert service.resolve_session(out["token"]) is None  # старые сессии закрыты
    with pytest.raises(core.Conflict):
        password_auth.login(PHONE, "fox12345")
    acc = password_auth.admin_accounts("Ольга")["accounts"]
    assert acc[0]["has_password"] and acc[0]["verified"] and "Маша" in acc[0]["kids"]


def test_set_password_from_cabinet_after_bot_login(lk_db_bigben):
    service.start_auth(PHONE, "Ольга", _consents(), None, None)
    token = service.confirm_via_bot(PHONE)["token"]
    assert password_auth.set_password(token, "mypass99")["status"] == "ok"
    assert password_auth.login(PHONE, "mypass99")["token"]
    with pytest.raises(core.Conflict, match="password_too_short"):
        password_auth.set_password(token, "1")


# ---------- основной путь: «Данные для входа» из карточки BigBen (внутренний API пульта) ----------

@pytest.fixture()
def crm(monkeypatch, lk_db):
    from app.lk import bigben_internal

    cards: list[dict] = []
    saved: list[tuple] = []
    monkeypatch.setattr(bigben, "configured", lambda: False)  # публичный API не нужен
    monkeypatch.setattr(bigben_internal, "configured", lambda: True)
    monkeypatch.setattr(bigben_internal, "find_students_by_phone", lambda phone: [
        c for c in cards if any(bigben_internal.digits10(c.get(f)) == bigben_internal.digits10(phone)
                                for f in bigben_internal.PHONE_FIELDS)])

    def create(**kw):
        card = {"id": 900 + len(cards), "fio": kw["fio"], "phone": kw["phone"], "parent_phone": kw["phone"],
                "parentname": kw["parentname"], "password_raw": "", "parent_password": ""}
        cards.append(card)
        return card

    def set_login(sid, phone, password):
        saved.append((sid, phone, password))
        for c in cards:
            if c["id"] == sid:
                c.update(password_raw=password, parent_password=password)

    monkeypatch.setattr(bigben_internal, "create_student", create)
    monkeypatch.setattr(bigben_internal, "set_login_data", set_login)
    return {"cards": cards, "saved": saved}


def test_crm_login_with_card_credentials(crm):
    crm["cards"] += [
        {"id": 301, "fio": "Иванова Маша", "phone": "89161234567", "password_raw": "masha1", "parent_phone": "",
         "parent_password": "", "parentname": "Ольга"},
        {"id": 302, "fio": "Иванов Пётр", "phone": "", "parent_phone": "+7 916 123-45-67",
         "parent_password": "mama77", "password_raw": "", "parentname": "Ольга"},
    ]
    # пароль ученика и пароль родителя из карточек подходят; видны оба ребёнка с этим номером
    for pw in ("masha1", "mama77"):
        out = password_auth.login(PHONE, pw)
        assert sorted(p["child_name"] for p in out["profiles"]) == ["Иванов Пётр", "Иванова Маша"]
    with pytest.raises(core.Conflict, match="bad_credentials"):
        password_auth.login(PHONE, "wrong")
    # в ЛК пароль не сохраняется — его хранит CRM
    assert get_conn().execute("SELECT password_hash FROM lk_accounts WHERE phone=?", (PHONE,)).fetchone()[0] is None


def test_crm_register_creates_card_with_login_data(crm):
    out = password_auth.register(PHONE_2, "secret77", "Анна Петрова", "Миша", "7", _consents())
    assert out["status"] == "registered" and out["crm_card"] and not out["guest"]
    assert [p["child_name"] for p in out["profiles"]] == ["Миша"]
    assert crm["saved"] == [(900, PHONE_2, "secret77")]  # телефон и пароль записаны в карточку
    assert crm["cards"][0]["parentname"] == "Анна Петрова"
    # дальше вход — по данным из карточки
    assert password_auth.login(PHONE_2, "secret77")["status"] == "logged_in"
    # повторная регистрация того же номера: уже клиент
    with pytest.raises(core.Conflict, match="already_client"):
        password_auth.register(PHONE_2, "secret77", "Анна", "Миша", "", _consents())


def test_bigben_session_relogin_on_expired_token(monkeypatch):
    """Доступ к пульту не «протухает»: ЛК сам входит учётной записью сотрудника и при 401 входит заново."""
    import httpx

    from app.lk import bigben_internal as bi

    monkeypatch.setenv("BIGBEN_LK_LOGIN", "lk@school")
    monkeypatch.setenv("BIGBEN_LK_PASSWORD", "staff-pass")
    monkeypatch.delenv("BIGBEN_INTERNAL_TOKEN", raising=False)
    bi._session.update(token="", refresh="", expires=0.0)
    state = {"logins": 0, "valid": set()}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/auth/login"):
            state["logins"] += 1
            tok = f"tok{state['logins']}"
            state["valid"] = {tok}
            return httpx.Response(200, json={"token": tok, "refreshToken": "", "expiresAt": "2099-01-01T00:00:00Z"})
        if req.headers.get("Authorization", "")[7:] not in state["valid"]:
            return httpx.Response(401, json={"message": "Unauthenticated."})
        return httpx.Response(200, json={"data": []})

    real = httpx.Client
    monkeypatch.setattr(bi.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler)))
    assert bi.configured()
    assert bi.health() == {"ok": True, "mode": "login"} and state["logins"] == 1
    bi._request("GET", "/user/students?per_page=1")
    assert state["logins"] == 1            # сессия переиспользуется
    state["valid"] = set()                 # пульт отозвал токен
    assert bi.health()["ok"] and state["logins"] == 2  # вошли заново сами
    bi._session.update(token="", refresh="", expires=0.0)
