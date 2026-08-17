"""Тесты CRM Admin API (/admin/api/*) и AI pause/resume в handle_message."""
import pytest
from fastapi.testclient import TestClient

from app import ai_core
from app import crm_store
from app import main as main_module
from app import memory as memory_module
from app.config import settings

TOKEN = "test-admin-token"
AUTH = {"X-Admin-Token": TOKEN}


class DisabledLLM:
    enabled = False


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "crm.db"))
    monkeypatch.setattr(settings, "STATE_FILE", "")
    monkeypatch.setattr(settings, "ADMIN_TOKEN", TOKEN, raising=False)
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


def _dialog(channel="max", external_id="u1", name="Анна"):
    customer_id = crm_store.upsert_customer_for_identity(channel, external_id, name=name)
    conv_id = crm_store.get_or_create_conversation(customer_id, channel, external_id)
    return customer_id, conv_id


def test_auth_required(client):
    assert client.get("/admin/api/inbox").status_code == 401
    assert client.get("/admin/api/inbox", headers={"X-Admin-Token": "nope"}).status_code == 401
    assert client.get("/admin/api/inbox", headers=AUTH).status_code == 200


def test_inbox_filters(client):
    cid1, conv1 = _dialog("max", "u1", "Анна")
    cid2, conv2 = _dialog("telegram", "tg:7", "Борис")
    crm_store.add_message(conv1, cid1, "max", "in", "customer", "Интересует ЕГЭ")
    crm_store.add_message(conv2, cid2, "telegram", "in", "customer", "Цена?")

    items = client.get("/admin/api/inbox", headers=AUTH).json()["items"]
    assert len(items) == 2
    assert {item["customer_name"] for item in items} == {"Анна", "Борис"}

    assert len(client.get("/admin/api/inbox?channel=telegram", headers=AUTH).json()["items"]) == 1
    assert len(client.get("/admin/api/inbox?unread=true", headers=AUTH).json()["items"]) == 2
    assert len(client.get("/admin/api/inbox?search=Борис", headers=AUTH).json()["items"]) == 1
    assert len(client.get("/admin/api/inbox?q=ЕГЭ", headers=AUTH).json()["items"]) == 1


def test_read_marks_conversation(client):
    cid, conv = _dialog()
    crm_store.add_message(conv, cid, "max", "in", "customer", "привет")
    resp = client.post(f"/admin/api/conversations/{conv}/read", headers=AUTH)
    assert resp.status_code == 200
    assert client.get("/admin/api/inbox?unread=true", headers=AUTH).json()["items"] == []


def test_reply_max_channel(client, monkeypatch):
    sent = []

    class FakeMax:
        async def send_message(self, user_id, text, buttons=None):
            sent.append((user_id, text))
            return True

    monkeypatch.setattr("app.admin_api.get_max", lambda: FakeMax())
    cid, conv = _dialog("max", "u-max")
    resp = client.post(f"/admin/api/conversations/{conv}/reply",
                       headers=AUTH, json={"text": "Здравствуйте, я менеджер"})
    assert resp.status_code == 200 and resp.json()["ok"]
    assert sent == [("u-max", "👤 Менеджер:\nЗдравствуйте, я менеджер")]

    msg = crm_store.get_conn().execute(
        "SELECT * FROM crm_messages WHERE conversation_id = ?", (conv,)).fetchone()
    assert msg["direction"] == "out" and msg["sender_type"] == "manager"
    assert msg["status"] == "sent"
    # Ответ менеджера перевёл диалог в режим manager.
    assert crm_store.get_conversation(conv)["ai_mode"] == "manager"


def test_reply_telegram_channel(client, monkeypatch):
    sent = []

    class FakeTg:
        async def send_message(self, chat_id, text, buttons=None):
            sent.append((chat_id, text))
            return True

    monkeypatch.setattr("app.admin_api.get_telegram", lambda: FakeTg())
    cid, conv = _dialog("telegram", "tg:12345")
    resp = client.post(f"/admin/api/conversations/{conv}/reply",
                       headers=AUTH, json={"text": "Ответ из админки"})
    assert resp.json()["ok"]
    # Префикс tg: срезается — клиенту нужен голый chat_id.
    assert sent == [("12345", "👤 Менеджер:\nОтвет из админки")]


def test_reply_send_failure_marked_failed(client, monkeypatch):
    class BrokenMax:
        async def send_message(self, user_id, text, buttons=None):
            return False

    monkeypatch.setattr("app.admin_api.get_max", lambda: BrokenMax())
    cid, conv = _dialog("max", "u1")
    resp = client.post(f"/admin/api/conversations/{conv}/reply", headers=AUTH, json={"text": "х"})
    assert resp.json()["status"] == "failed"
    msg = crm_store.get_conn().execute("SELECT status FROM crm_messages").fetchone()
    assert msg["status"] == "failed"


def test_reply_web_goes_pending(client, monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    cid, conv = _dialog("web", "web:sess-9")
    resp = client.post(f"/admin/api/conversations/{conv}/reply",
                       headers=AUTH, json={"text": "Ответ менеджера в виджет"})
    assert resp.json()["status"] == "pending"

    # Виджет забирает накопленное поллингом.
    pending = client.get("/api/chat/pending?session_id=sess-9").json()["messages"]
    assert [m["text"] for m in pending] == ["Ответ менеджера в виджет"]
    # Повторный поллинг — уже пусто (доставлено).
    assert client.get("/api/chat/pending?session_id=sess-9").json()["messages"] == []


def test_web_chat_response_includes_pending(client, monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    cid, conv = _dialog("web", "web:sess-8")
    client.post(f"/admin/api/conversations/{conv}/reply", headers=AUTH, json={"text": "Менеджер на связи"})
    resp = client.post("/api/chat", json={"session_id": "sess-8", "text": "алло"})
    assert resp.status_code == 200
    assert [m["text"] for m in resp.json()["pending_messages"]] == ["Менеджер на связи"]


def test_ai_pause_silences_bot_and_resume_restores(client, monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    cid, conv = _dialog("web", "web:sess-pause")

    # Пауза до ручного включения.
    resp = client.post(f"/admin/api/conversations/{conv}/ai", headers=AUTH,
                       json={"mode": "paused", "paused_until": None})
    assert resp.json()["ai_mode"] == "paused"

    resp = client.post("/api/chat", json={"session_id": "sess-pause", "text": "Вы тут?"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == ""  # бот молчит
    # …но входящее записано в CRM.
    msgs = crm_store.get_conn().execute(
        "SELECT direction FROM crm_messages WHERE conversation_id = ?", (conv,)).fetchall()
    assert [m["direction"] for m in msgs] == ["in"]

    # Ручное включение — бот снова отвечает.
    client.post(f"/admin/api/conversations/{conv}/ai", headers=AUTH, json={"mode": "active"})
    resp = client.post("/api/chat", json={"session_id": "sess-pause", "text": "Здравствуйте"})
    assert resp.json()["reply"] != ""


def test_ai_pause_expires_automatically(client, monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    cid, conv = _dialog("web", "web:sess-exp")
    # Пауза уже истекла (в прошлом) — handle_message должен ответить и снять её.
    client.post(f"/admin/api/conversations/{conv}/ai", headers=AUTH,
                json={"mode": "paused", "paused_until": "2020-01-01T00:00:00+00:00"})
    resp = client.post("/api/chat", json={"session_id": "sess-exp", "text": "Здравствуйте"})
    assert resp.json()["reply"] != ""
    assert crm_store.get_conversation(conv)["ai_mode"] == "active"


def test_manager_mode_silences_bot(client, monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    cid, conv = _dialog("web", "web:sess-mgr")
    client.post(f"/admin/api/conversations/{conv}/reply", headers=AUTH, json={"text": "я отвечу сам"})
    resp = client.post("/api/chat", json={"session_id": "sess-mgr", "text": "?"})
    assert resp.json()["reply"] == ""


def test_notes_tasks_tags_via_api(client):
    cid, _ = _dialog()
    assert client.post(f"/admin/api/customers/{cid}/notes", headers=AUTH,
                       json={"text": "Перезвонить"}).json()["ok"]
    assert client.get(f"/admin/api/customers/{cid}/notes", headers=AUTH).json()["items"][0]["text"] == "Перезвонить"

    task = client.post(f"/admin/api/customers/{cid}/tasks", headers=AUTH,
                       json={"title": "Отправить договор"}).json()
    assert client.post(f"/admin/api/tasks/{task['id']}/done", headers=AUTH).json()["ok"]
    tasks = client.get(f"/admin/api/customers/{cid}/tasks", headers=AUTH).json()["items"]
    assert tasks[0]["status"] == "done"

    assert client.post(f"/admin/api/customers/{cid}/tags", headers=AUTH, json={"name": "vip"}).json()["ok"]
    customer = client.get(f"/admin/api/customers/{cid}", headers=AUTH).json()
    assert customer["tags"][0]["name"] == "vip"
    assert client.delete(f"/admin/api/customers/{cid}/tags/vip", headers=AUTH).json()["ok"]
    assert client.get("/admin/api/tags", headers=AUTH).status_code == 200


def test_customer_patch_archive_merge_via_api(client):
    cid, _ = _dialog()
    resp = client.patch(f"/admin/api/customers/{cid}", headers=AUTH,
                        json={"name": "Анна Иванова", "lead_status": "qualified",
                              "hacker_field": "drop me"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Анна Иванова"
    assert body["lead_status"] == "qualified"
    # Аудит записан.
    audit = crm_store.get_conn().execute(
        "SELECT action FROM audit_log WHERE entity_type = 'customer' AND action = 'update'"
    ).fetchone()
    assert audit is not None

    client.post(f"/admin/api/customers/{cid}/archive", headers=AUTH, json={"reason": "спам"})
    assert client.get(f"/admin/api/customers/{cid}", headers=AUTH).json()["status"] == "archived"
    client.post(f"/admin/api/customers/{cid}/unarchive", headers=AUTH)
    assert client.get(f"/admin/api/customers/{cid}", headers=AUTH).json()["status"] == "active"

    # Merge: secondary вливается в primary через API.
    cid2, conv2 = _dialog("web", "web:dup")
    crm_store.add_message(conv2, cid2, "web", "in", "customer", "старая история")
    merged = client.post("/admin/api/customers/merge", headers=AUTH,
                         json={"primary_id": cid, "secondary_id": cid2}).json()
    assert merged["counts"]["messages"] == 1
    assert client.get(f"/admin/api/customers/{cid2}", headers=AUTH).json()["status"] == "archived"


def test_customers_list_and_timeline(client):
    cid, conv = _dialog()
    crm_store.add_message(conv, cid, "max", "in", "customer", "привет")
    crm_store.add_note(cid, "admin", "заметка")

    data = client.get("/admin/api/customers", headers=AUTH).json()
    assert data["total"] == 1 and data["items"][0]["channels"] == ["max"]
    timeline = client.get(f"/admin/api/customers/{cid}/timeline", headers=AUTH).json()["items"]
    assert {e["type"] for e in timeline} >= {"message", "note"}


def test_stats_health_and_ai_events(client):
    cid, conv = _dialog()
    crm_store.add_message(conv, cid, "max", "in", "customer", "вопрос")
    crm_store.add_ai_event("no_answer", conv, cid, {"question": "китайский?"})

    stats = client.get("/admin/api/stats/today", headers=AUTH).json()
    assert stats["new_customers"]["today"] == 1
    assert stats["messages_today"]["in"] == 1
    assert stats["ai_events_today"]["no_answer"] == 1

    events = client.get("/admin/api/ai/events?kind=no_answer&days=1", headers=AUTH).json()["items"]
    assert len(events) == 1

    health = client.get("/admin/api/health", headers=AUTH).json()
    assert health["db_ok"] is True
    assert "inbound_24h" in health


def test_old_admin_endpoints_still_work(client, monkeypatch):
    """Обратная совместимость: старые ручки /admin/users не тронуты."""
    resp = client.get("/admin/users", headers=AUTH)
    assert resp.status_code == 200 and "rows" in resp.json()
    assert client.get("/admin/users").status_code == 401
