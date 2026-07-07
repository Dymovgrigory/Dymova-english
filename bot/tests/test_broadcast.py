import pytest
from fastapi.testclient import TestClient

from app import memory
from app.broadcast import audience_counts, get_user_detail, list_users, resolve_recipients
import app.main as main
from app.memory import Conversation, Lead, STAGE_DONE, _conv_from_dict, get_store
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


def test_conversation_add_tracks_transcript_and_history():
    conv = Conversation(user_id="u1")
    for i in range(21):
        conv.add("user" if i % 2 == 0 else "assistant", f"msg-{i}")
    assert len(conv.history) == 20
    assert len(conv.transcript) == 21
    assert all("ts" in item for item in conv.transcript)

    for i in range(1000):
        conv.add("user", f"extra-{i}")
    assert len(conv.transcript) == 1000
    assert len(conv.history) == 20


def test_conv_from_dict_backward_compatibility():
    conv = _conv_from_dict(
        {
            "user_id": "legacy",
            "stage": "greeting",
            "lead": {},
            "history": [{"role": "user", "content": "Привет"}],
        }
    )
    assert conv.user_id == "legacy"
    assert conv.created_at == ""
    assert conv.updated_at == ""
    assert conv.transcript == []


def test_list_users_includes_first_question_and_sorted(fresh_store):
    old = Conversation(
        user_id="old",
        stage="lead",
        lead=Lead(fio_parent="Иван", fio_child="Миша", phone="+79990000000"),
        selected_course="Английский",
        selected_branch="Лихачевский",
        selected_format="Офлайн",
        created_at="2026-06-01T10:00:00+00:00",
        updated_at="2026-06-01T11:00:00+00:00",
        transcript=[
            {"role": "user", "content": "Расскажите про летнюю академию", "ts": "2026-06-01T10:00:00+00:00"},
            {"role": "assistant", "content": "Конечно", "ts": "2026-06-01T10:00:05+00:00"},
        ],
        history=[
            {"role": "user", "content": "Расскажите про летнюю академию"},
            {"role": "assistant", "content": "Конечно"},
        ],
        utm={"source": "vk", "utm_campaign": "spring"},
    )
    partial = Conversation(
        user_id="partial",
        stage="discovery",
        lead=Lead(fio_parent="Анна"),
        selected_course="Немецкий",
        created_at="2026-06-02T10:00:00+00:00",
        updated_at="2026-06-03T09:00:00+00:00",
        transcript=[
            {"role": "user", "content": "Чем занимаетесь?", "ts": "2026-06-02T10:00:00+00:00"},
        ],
        history=[{"role": "user", "content": "Чем занимаетесь?"}],
        utm={"utm_medium": "miniapp"},
    )
    blank = Conversation(
        user_id="blank",
        stage="greeting",
        created_at="2026-06-04T10:00:00+00:00",
        updated_at="",
        transcript=[],
        history=[],
    )
    fresh_store._data = {"old": old, "partial": partial, "blank": blank}

    rows = list_users()
    assert [row["user_id"] for row in rows] == ["partial", "old", "blank"]
    assert rows[0]["lead_status"] == "partial"
    assert rows[0]["fio_parent"] == "Анна"
    assert rows[0]["fio_child"] == ""
    assert rows[0]["birthday"] == ""
    assert rows[0]["age"] == ""
    assert rows[0]["phone"] == ""
    assert rows[1]["lead_status"] == "complete"
    assert rows[1]["fio_parent"] == "Иван"
    assert rows[1]["fio_child"] == "Миша"
    assert rows[1]["birthday"] == ""
    assert rows[1]["age"] == ""
    assert rows[1]["phone"] == "+79990000000"
    assert rows[1]["first_question"] == "Расскажите про летнюю академию"
    assert rows[1]["first_at"] == "2026-06-01T10:00:00+00:00"
    assert rows[1]["last_message"] == "Конечно"
    assert rows[1]["source"] == "vk"
    assert rows[2]["first_question"] == ""
    assert rows[2]["first_at"] == "2026-06-04T10:00:00+00:00"


def test_admin_users_endpoints_and_detail_auth(monkeypatch, fresh_store):
    fresh_store._data = {
        "u1": Conversation(
            user_id="u1",
            created_at="2026-06-01T10:00:00+00:00",
            updated_at="2026-06-01T11:00:00+00:00",
            transcript=[{"role": "user", "content": "Привет", "ts": "2026-06-01T10:00:00+00:00"}],
            history=[{"role": "user", "content": "Привет"}],
        )
    }
    monkeypatch.setattr(config.settings, "ADMIN_TOKEN", "")
    client = TestClient(main.app)
    assert client.get("/admin/users").status_code == 401
    assert client.get("/admin/users/u1").status_code == 401

    monkeypatch.setattr(config.settings, "ADMIN_TOKEN", "secret")
    assert client.get("/admin/users", headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert client.get("/admin/users/u1", headers={"X-Admin-Token": "wrong"}).status_code == 401

    rows = client.get("/admin/users", headers={"X-Admin-Token": "secret"}).json()["rows"]
    assert len(rows) == 1
    detail = client.get("/admin/users/u1", headers={"X-Admin-Token": "secret"}).json()
    assert detail["header"]["user_id"] == "u1"
    assert detail["transcript"][0]["content"] == "Привет"
    assert client.get("/admin/users/unknown", headers={"X-Admin-Token": "secret"}).status_code == 404
