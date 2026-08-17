"""Тесты заявок (callback_requests) и честной доставки ответов менеджера.

Контракты:
- чат мини-приложения пишет входящее и исходящее в CRM;
- handoff создаёт заявку, повторный handoff её обновляет, а не плодит дубль;
- /api/lead создаёт заявку kind=lead и склеивается с клиентом по телефону;
- reply с client_message_id идемпотентен (повтор — duplicate без отправки);
- retry шлёт только failed исходящие и обновляет факт доставки;
- availability честно выключает отправку при «бот заблокирован»;
- backfill: dry-run не пишет, --apply идемпотентен.
"""
import json
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from app import ai_core
from app import crm_ingest
from app import crm_store
from app import main as main_module
from app import memory as memory_module
from app.config import settings

from tests.conftest import make_telegram_init_data

TOKEN = "test-admin-token"
AUTH = {"X-Admin-Token": TOKEN}
TG_TOKEN = "test-tg-token"


class DisabledLLM:
    enabled = False


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "crm.db"))
    monkeypatch.setattr(settings, "STATE_FILE", "")
    monkeypatch.setattr(settings, "ADMIN_TOKEN", TOKEN, raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", TG_TOKEN)
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://example.test/app/")
    memory_module._store = None
    crm_store.reset()
    main_module._BACKGROUND_TASKS.clear()
    yield
    memory_module._store = None
    crm_store.reset()
    main_module._BACKGROUND_TASKS.clear()


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _dialog(channel="max", external_id="u1", name="Анна", phone=""):
    customer_id = crm_store.upsert_customer_for_identity(
        channel, external_id, name=name, phone=phone)
    conv_id = crm_store.get_or_create_conversation(customer_id, channel, external_id)
    return customer_id, conv_id


# --------- чат мини-приложения ---------


def test_miniapp_chat_ingests_in_and_out(client, monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    init_data = make_telegram_init_data(TG_TOKEN, telegram_user_id=777)

    resp = client.post("/api/miniapp/chat",
                       json={"text": "Здравствуйте, сколько стоит?"},
                       headers={main_module.INIT_DATA_HEADER: init_data})
    assert resp.status_code == 200

    messages = crm_store.get_conn().execute(
        "SELECT direction, sender_type, text, channel FROM crm_messages ORDER BY id"
    ).fetchall()
    assert [m["direction"] for m in messages] == ["in", "out"]
    assert messages[0]["channel"] == "telegram"
    assert messages[0]["sender_type"] == "customer"
    assert messages[1]["sender_type"] == "ai"
    conv = crm_store.find_conversation("telegram", "tg:777")
    assert conv is not None


# --------- handoff создаёт заявку ---------


def test_handoff_creates_request_and_dedupes():
    cid, conv_id = _dialog("max", "u-hand")
    crm_store.add_message(conv_id, cid, "max", "in", "customer", "позовите человека")

    req1 = crm_ingest.ingest_handoff("max", "u-hand", "запрос администратора")
    assert req1 is not None
    req2 = crm_ingest.ingest_handoff("max", "u-hand", "повторная эскалация")
    assert req2 == req1

    item = crm_store.get_callback_request(req1)
    assert item["kind"] == "admin_request"
    assert item["customer_id"] == cid
    assert item["conversation_id"] == conv_id
    assert item["reason"] == "повторная эскалация"
    assert item["last_message_id"] is not None
    assert crm_store.requests_counts()["new"] == 1


# --------- заявка с сайта ---------


class FakeBigBen:
    async def create_lead(self, lead, source=""):
        return True


def test_site_lead_creates_request_and_links_by_phone(client, monkeypatch):
    monkeypatch.setattr(main_module, "get_bigben", lambda: FakeBigBen())
    # Существующий клиент из Telegram с тем же телефоном.
    cid, _conv_id = _dialog("telegram", "tg:55", name="Мария", phone="+7 916 123-45-67")

    resp = client.post("/api/lead", json={
        "fio_parent": "Мария", "phone": "8 (916) 123 45 67",
        "course": "Kids", "branch": "Лихачёвский", "comment": "Хотим пробное",
    })
    assert resp.status_code == 200 and resp.json()["ok"]

    items = crm_store.list_callback_requests(kind="lead")
    assert len(items) == 1
    item = items[0]
    assert item["customer_id"] == cid  # склейка по телефону, а не новый клиент
    assert item["channel"] == "web"
    assert "Kids" in item["reason"]
    assert item["contact"]["phone"] == "8 (916) 123 45 67"
    assert item["contact"]["fio_child"] == "" or "fio_child" in item["contact"]


# --------- идемпотентный reply ---------


def test_reply_client_message_id_dedupes(client, monkeypatch):
    sent = []

    class FakeMax:
        async def send_message_ext(self, user_id, text, buttons=None):
            sent.append(text)
            return True, "ext-100", None

    monkeypatch.setattr("app.admin_api.get_max", lambda: FakeMax())
    cid, conv = _dialog("max", "u-dedup")

    body = {"text": "Ответ менеджера", "client_message_id": "ui-abc-1"}
    resp1 = client.post(f"/admin/api/conversations/{conv}/reply", headers=AUTH, json=body)
    resp2 = client.post(f"/admin/api/conversations/{conv}/reply", headers=AUTH, json=body)
    assert resp1.status_code == 200 and resp2.status_code == 200
    assert resp2.json()["duplicate"] is True
    assert resp2.json()["message_id"] == resp1.json()["message_id"]
    assert sent == ["Ответ менеджера"]  # клиенту ушло ровно одно сообщение
    msg = crm_store.get_message(resp1.json()["message_id"])
    assert msg["external_message_id"] == "ext-100"


# --------- retry недоставленного ---------


def test_retry_failed_outbound(client, monkeypatch):
    calls = []

    class FlakyMax:
        async def send_message_ext(self, user_id, text, buttons=None):
            calls.append(text)
            if len(calls) == 1:
                return False, None, "403: bot was blocked by the user"
            return True, "ext-200", None

    monkeypatch.setattr("app.admin_api.get_max", lambda: FlakyMax())
    cid, conv = _dialog("max", "u-retry")
    resp = client.post(f"/admin/api/conversations/{conv}/reply",
                       headers=AUTH, json={"text": "Привет!"})
    assert resp.json()["status"] == "failed"
    message_id = resp.json()["message_id"]

    retry = client.post(f"/admin/api/messages/{message_id}/retry", headers=AUTH)
    assert retry.status_code == 200
    assert retry.json()["ok"] is True
    msg = crm_store.get_message(message_id)
    assert msg["status"] == "sent"
    assert msg["external_message_id"] == "ext-200"
    # Второй retry уже доставленного запрещён: это был бы дубль клиенту.
    again = client.post(f"/admin/api/messages/{message_id}/retry", headers=AUTH)
    assert again.status_code == 400


# --------- requests API ---------


def test_requests_api_flow(client):
    cid, conv_id = _dialog("max", "u-req")
    req = crm_ingest.ingest_handoff("max", "u-req", "запрос администратора")

    listing = client.get("/admin/api/requests", headers=AUTH).json()
    assert listing["counts"]["new"] == 1
    assert listing["items"][0]["id"] == req
    assert listing["items"][0]["customer_name"] == "Анна"

    detail = client.get(f"/admin/api/requests/{req}", headers=AUTH).json()
    assert detail["request"]["id"] == req
    assert detail["customer"]["id"] == cid
    assert detail["conversation"]["id"] == conv_id

    bad = client.post(f"/admin/api/requests/{req}/status",
                      headers=AUTH, json={"status": "bogus"})
    assert bad.status_code == 400

    assign = client.post(f"/admin/api/requests/{req}/assign",
                         headers=AUTH, json={"manager": "Ольга"})
    assert assign.json()["request"]["status"] == "in_progress"
    assert assign.json()["request"]["manager"] == "Ольга"

    status = client.post(f"/admin/api/requests/{req}/status",
                         headers=AUTH, json={"status": "resolved"})
    assert status.json()["request"]["status"] == "resolved"

    notes = client.post(f"/admin/api/requests/{req}/notes",
                        headers=AUTH, json={"notes": "Созвонились, ждём пробное"})
    assert notes.json()["request"]["notes"] == "Созвонились, ждём пробное"

    assert client.get("/admin/api/requests/9999", headers=AUTH).status_code == 404


def test_requests_forbidden_for_role_without_permission(client):
    # marketing не имеет права requests.
    user_id = crm_store.admin_user_create("marketer", "secret-password", role="marketing")
    token = crm_store.session_create(user_id)
    resp = client.get("/admin/api/requests", headers={"X-Admin-Token": token})
    assert resp.status_code == 403


# --------- availability ---------


def test_availability_blocked_bot(client):
    cid, conv = _dialog("telegram", "tg:99", phone="8 900 111-22-33")
    crm_store.add_message(conv, cid, "telegram", "out", "manager", "Привет",
                          status="failed", error="Forbidden: bot was blocked by the user")

    resp = client.get(f"/admin/api/conversations/{conv}/availability", headers=AUTH)
    body = resp.json()
    assert body["can_send"] is False
    assert "заблокировал бота" in body["reason"]
    assert body["contacts"]["phone"] == "8 900 111-22-33"


def test_availability_web_widget(client):
    cid, conv = _dialog("web", "web:sess-9")
    resp = client.get(f"/admin/api/conversations/{conv}/availability", headers=AUTH)
    body = resp.json()
    assert body["can_send"] is True
    assert "поллинг" in body["reason"]


# --------- backfill ---------


def _seed_legacy(db_path):
    """Legacy-таблица conversations с транскриптом, как в проде."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS conversations("
        " platform TEXT, user_id TEXT, payload TEXT,"
        " PRIMARY KEY(platform, user_id))"
    )
    ts = "2024-05-01T10:00:00+00:00"
    payload = json.dumps({"transcript": [
        {"role": "user", "content": "Здравствуйте", "ts": ts},
        {"role": "assistant", "content": "Добрый день! Чем помочь?", "ts": ts},
    ]}, ensure_ascii=False)
    conn.execute("INSERT OR REPLACE INTO conversations VALUES ('max', 'legacy-u1', ?)",
                 (payload,))
    conn.commit()
    conn.close()


def _run_backfill(db_path, apply=False):
    cmd = [sys.executable, "scripts/backfill_crm_history.py", "--db", str(db_path)]
    if apply:
        cmd.append("--apply")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def test_backfill_dry_run_then_apply(tmp_path, monkeypatch):
    db_path = tmp_path / "backfill.db"
    monkeypatch.setattr(settings, "DB_PATH", str(db_path))
    crm_store.reset()
    crm_store.get_conn()  # создаём CRM-схему рядом с legacy-таблицей
    crm_store.reset()
    _seed_legacy(db_path)

    dry = _run_backfill(db_path)
    assert dry.returncode == 0
    assert "DRY-RUN" in dry.stdout
    conn = crm_store.get_conn(str(db_path))
    assert conn.execute("SELECT COUNT(*) c FROM crm_messages").fetchone()["c"] == 0

    applied = _run_backfill(db_path, apply=True)
    assert applied.returncode == 0
    conn = crm_store.get_conn(str(db_path))
    rows = conn.execute(
        "SELECT direction, sender_type FROM crm_messages ORDER BY id").fetchall()
    assert [(r["direction"], r["sender_type"]) for r in rows] == [
        ("in", "customer"), ("out", "ai")]

    # Повторный --apply: всё распознаётся как дубли, ничего не добавляется.
    again = _run_backfill(db_path, apply=True)
    assert again.returncode == 0
    crm_store.reset()
    conn = crm_store.get_conn(str(db_path))
    assert conn.execute("SELECT COUNT(*) c FROM crm_messages").fetchone()["c"] == 2
