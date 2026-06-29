import pytest
from fastapi.testclient import TestClient

from app import memory
from app.broadcast import audience_counts, resolve_recipients
import app.main as main
from app.memory import Conversation, Lead, STAGE_DONE, get_store
from app import config


class FakeMaxClient:
    def __init__(self, ok: bool = True):
        self.ok = ok
        self.calls = []

    async def send_message(self, user_id, text, buttons=None):
        self.calls.append((user_id, text, buttons))
        return self.ok


@pytest.fixture
def fresh_store(monkeypatch):
    monkeypatch.setattr(config.settings, "STATE_FILE", "")
    store = memory.MemoryStore()
    monkeypatch.setattr(memory, "_store", store)
    return store


def _seed_store(store):
    store.save(Conversation(user_id="u1", selected_course="Английский"))
    store.save(
        Conversation(
            user_id="u2",
            stage=STAGE_DONE,
            lead=Lead(fio_parent="Иванова Анна", fio_child="Иванов Миша", phone="+79991234567"),
            selected_course="Немецкий",
        )
    )
    store.save(
        Conversation(
            user_id="u3",
            lead=Lead(fio_parent="Петрова Ольга", fio_child="Петров Вася", phone="+79990000000", branch="Лихачевский"),
            selected_branch="Лихачевский",
        )
    )
    store.save(
        Conversation(
            user_id="u4",
            lead=Lead(fio_parent="Смирнова Ирина", fio_child="Смирнов Лёва", phone="+79991111111", course="Немецкий", branch="Центральный"),
        )
    )


def test_audience_counts_and_recipients(fresh_store):
    _seed_store(fresh_store)
    counts = audience_counts()
    assert counts["total"] == 4
    assert counts["segments"]["all"] == 4
    assert counts["segments"]["leads"] == 3
    assert counts["segments"]["course"] == 3
    assert counts["segments"]["branch"] == 2
    assert {item["value"] for item in counts["courses"]} == {"Английский", "Немецкий"}
    assert {item["value"] for item in counts["branches"]} == {"Лихачевский", "Центральный"}

    assert resolve_recipients("all") == ["u1", "u2", "u3", "u4"]
    assert resolve_recipients("leads") == ["u2", "u3", "u4"]
    assert resolve_recipients("course", course="англ") == ["u1"]
    assert resolve_recipients("course", course="немец") == ["u2", "u4"]
    assert resolve_recipients("branch", branch="лихач") == ["u3"]


def test_broadcast_endpoints_auth_and_send(monkeypatch, fresh_store):
    _seed_store(fresh_store)
    fake = FakeMaxClient()

    monkeypatch.setattr(config.settings, "ADMIN_TOKEN", "")
    monkeypatch.setattr(config.settings, "ADMIN_MAX_IDS", "admin1,admin2")
    monkeypatch.setattr(main, "get_max", lambda: fake)
    client = TestClient(main.app)

    assert client.get("/admin/broadcast/audience").status_code == 401
    assert client.post("/admin/broadcast/test", json={"text": "x"}, headers={"X-Admin-Token": "wrong"}).status_code == 401

    monkeypatch.setattr(config.settings, "ADMIN_TOKEN", "secret")
    assert client.get("/admin/broadcast/audience", headers={"X-Admin-Token": "wrong"}).status_code == 401

    audience = client.get("/admin/broadcast/audience", headers={"X-Admin-Token": "secret"}).json()
    assert audience["segments"]["all"] == 4

    test_resp = client.post(
        "/admin/broadcast/test",
        json={"text": "Тестовая рассылка", "button_text": "Открыть", "button_url": "https://example.com"},
        headers={"X-Admin-Token": "secret"},
    )
    assert test_resp.status_code == 200
    assert test_resp.json() == {"total": 2, "delivered": 2, "failed": 0}
    assert [call[0] for call in fake.calls[:2]] == ["admin1", "admin2"]
    assert fake.calls[0][2] == [[{"type": "link", "text": "Открыть", "url": "https://example.com"}]]

    fake.calls.clear()
    send_resp = client.post(
        "/admin/broadcast/send",
        json={"text": "Письмо", "segment": "course", "course": "англ"},
        headers={"X-Admin-Token": "secret"},
    )
    assert send_resp.status_code == 200
    assert send_resp.json() == {"total": 1, "delivered": 1, "failed": 0}
    assert [call[0] for call in fake.calls] == ["u1"]
