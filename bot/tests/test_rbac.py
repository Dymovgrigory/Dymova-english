"""Тесты RBAC: логин/сессии, матрица прав, rate-limit, admin-users, audit."""
import pytest
from fastapi.testclient import TestClient

from app import crm_store
from app import main as main_module
from app.config import settings

TOKEN = "legacy-admin-token"
AUTH = {"X-Admin-Token": TOKEN}


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "crm.db"))
    monkeypatch.setattr(settings, "STATE_FILE", "")
    monkeypatch.setattr(settings, "ADMIN_TOKEN", TOKEN, raising=False)
    crm_store.reset()
    import app.admin_api as admin_api_module
    admin_api_module._login_hits.clear()
    main_module._BACKGROUND_TASKS.clear()
    yield
    crm_store.reset()
    main_module._BACKGROUND_TASKS.clear()


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _make_user(client, username, password, role):
    resp = client.post("/admin/api/admin-users", headers=AUTH,
                       json={"username": username, "password": password, "role": role})
    assert resp.status_code == 200, resp.text


def _login(client, username, password):
    resp = client.post("/admin/api/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_login_logout_and_me(client):
    _make_user(client, "olga", "secret1", "manager")
    session = _login(client, "olga", "secret1")
    assert session["role"] == "manager" and session["username"] == "olga"
    auth = {"X-Admin-Token": session["token"]}

    me = client.get("/admin/api/me", headers=auth).json()
    assert me["role"] == "manager"
    assert "inbox" in me["permissions"]

    # Неверный пароль — 401, ответ одинаковый для «нет пользователя».
    bad = client.post("/admin/api/login", json={"username": "olga", "password": "wrong"})
    assert bad.status_code == 401
    ghost = client.post("/admin/api/login", json={"username": "nobody", "password": "wrong"})
    assert ghost.status_code == 401 and ghost.json()["detail"] == bad.json()["detail"]

    # Logout убивает сессию.
    client.post("/admin/api/logout", headers=auth)
    assert client.get("/admin/api/me", headers=auth).status_code == 401


def test_expired_session_rejected(client):
    _make_user(client, "ivan", "secret1", "support")
    session = _login(client, "ivan", "secret1")
    crm_store.get_conn().execute(
        "UPDATE admin_sessions SET expires_at = datetime('now', '-1 hour')")
    assert client.get("/admin/api/me",
                      headers={"X-Admin-Token": session["token"]}).status_code == 401


def test_role_matrix(client):
    _make_user(client, "mgr", "secret1", "manager")
    _make_user(client, "mkt", "secret1", "marketing")
    _make_user(client, "sup", "secret1", "support")
    mgr = {"X-Admin-Token": _login(client, "mgr", "secret1")["token"]}
    mkt = {"X-Admin-Token": _login(client, "mkt", "secret1")["token"]}
    sup = {"X-Admin-Token": _login(client, "sup", "secret1")["token"]}

    # manager: inbox/customers — можно; промпты, рассылки, KB — 403.
    assert client.get("/admin/api/inbox", headers=mgr).status_code == 200
    assert client.get("/admin/api/customers", headers=mgr).status_code == 200
    assert client.get("/admin/api/ai/prompts", headers=mgr).status_code == 403
    assert client.get("/admin/api/broadcasts", headers=mgr).status_code == 403
    assert client.get("/admin/api/kb", headers=mgr).status_code == 403
    assert client.get("/admin/api/export/customers.csv", headers=mgr).status_code == 403

    # marketing: рассылки/аналитика/экспорт — можно; KB и промпты — 403.
    assert client.get("/admin/api/broadcasts", headers=mkt).status_code == 200
    assert client.get("/admin/api/analytics", headers=mkt).status_code == 200
    assert client.get("/admin/api/export/customers.csv", headers=mkt).status_code == 200
    assert client.get("/admin/api/kb", headers=mkt).status_code == 403
    assert client.get("/admin/api/ai/prompts", headers=mkt).status_code == 403
    assert client.get("/admin/api/system", headers=mkt).status_code == 403

    # support: inbox/customers/reply/stats — можно; всё остальное — 403.
    assert client.get("/admin/api/inbox", headers=sup).status_code == 200
    assert client.get("/admin/api/stats/today", headers=sup).status_code == 200
    assert client.get("/admin/api/analytics", headers=sup).status_code == 403
    assert client.get("/admin/api/broadcasts", headers=sup).status_code == 403
    assert client.get("/admin/api/admin-users", headers=sup).status_code == 403


def test_legacy_token_is_super_admin(client):
    """Старый статический ADMIN_TOKEN продолжает работать со всеми правами."""
    assert client.get("/admin/api/admin-users", headers=AUTH).status_code == 200
    assert client.get("/admin/api/ai/prompts", headers=AUTH).status_code == 200
    me = client.get("/admin/api/me", headers=AUTH).json()
    assert me["role"] == "super_admin"


def test_admin_users_crud_only_super_admin(client):
    _make_user(client, "adm", "secret1", "admin")
    adm = {"X-Admin-Token": _login(client, "adm", "secret1")["token"]}
    # admin — не super_admin: управление пользователями закрыто.
    assert client.get("/admin/api/admin-users", headers=adm).status_code == 403

    _make_user(client, "newguy", "secret1", "manager")
    users = client.get("/admin/api/admin-users", headers=AUTH).json()["items"]
    guy = [u for u in users if u["username"] == "newguy"][0]

    # Смена роли и выключение.
    assert client.patch(f"/admin/api/admin-users/{guy['id']}", headers=AUTH,
                        json={"role": "support"}).json()["ok"]
    assert client.patch(f"/admin/api/admin-users/{guy['id']}", headers=AUTH,
                        json={"active": 0}).json()["ok"]
    # Выключенный пользователь не входит.
    assert client.post("/admin/api/login",
                       json={"username": "newguy", "password": "secret1"}).status_code == 401

    # Сброс пароля: старый не работает, новый работает.
    client.patch(f"/admin/api/admin-users/{guy['id']}", headers=AUTH,
                 json={"active": 1, "password": "newpass9"})
    assert client.post("/admin/api/login",
                       json={"username": "newguy", "password": "secret1"}).status_code == 401
    assert client.post("/admin/api/login",
                       json={"username": "newguy", "password": "newpass9"}).status_code == 200


def test_audit_actor_is_username(client):
    _make_user(client, "olga", "secret1", "manager")
    auth = {"X-Admin-Token": _login(client, "olga", "secret1")["token"]}
    cid = crm_store.upsert_customer_for_identity("max", "u1", name="Анна")
    client.patch(f"/admin/api/customers/{cid}", headers=auth, json={"lead_status": "trial"})
    row = crm_store.get_conn().execute(
        "SELECT actor FROM audit_log WHERE entity_type = 'customer' AND action = 'update'"
    ).fetchone()
    assert row["actor"] == "olga"


def test_login_rate_limit(client):
    _make_user(client, "olga", "secret1", "manager")
    for _ in range(5):
        client.post("/admin/api/login", json={"username": "olga", "password": "bad"})
    resp = client.post("/admin/api/login", json={"username": "olga", "password": "secret1"})
    assert resp.status_code == 429


def test_bootstrap_seed():
    """Пустая таблица — создаётся super_admin admin; повторный вызов ничего не делает."""
    crm_store.seed_bootstrap_admin()
    users = crm_store.admin_user_list()
    assert len(users) == 1 and users[0]["username"] == "admin"
    assert users[0]["role"] == "super_admin"
    crm_store.seed_bootstrap_admin()
    assert len(crm_store.admin_user_list()) == 1
