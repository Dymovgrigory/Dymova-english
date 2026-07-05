import pytest
from fastapi.testclient import TestClient

from app import ai_core
from app import main as main_module
from app import memory as memory_module
from app.config import settings


class DisabledLLM:
    enabled = False


@pytest.fixture(autouse=True)
def reset_state():
    memory_module._store = None
    main_module._BACKGROUND_TASKS.clear()
    yield
    memory_module._store = None
    main_module._BACKGROUND_TASKS.clear()


def test_api_chat_validates_text_and_generates_session(monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())

    client = TestClient(main_module.app)

    empty_resp = client.post("/api/chat", json={"text": "   "})
    assert empty_resp.status_code == 400

    first_resp = client.post("/api/chat", json={"text": "Здравствуйте"})
    assert first_resp.status_code == 200
    first_data = first_resp.json()
    assert first_data["session_id"]
    assert first_data["reply"].startswith("Привет!")
    assert isinstance(first_data["buttons"], list)

    second_resp = client.post(
        "/api/chat",
        json={"session_id": first_data["session_id"], "text": "Что умеешь?"},
    )
    assert second_resp.status_code == 200
    second_data = second_resp.json()
    assert second_data["session_id"] == first_data["session_id"]
    assert second_data["reply"].startswith("Привет!")


def test_api_chat_homework_returns_widget_button(monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example/app/", raising=False)

    client = TestClient(main_module.app)
    resp = client.post("/api/chat", json={"text": "Помоги с домашкой по английскому"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["buttons"]
    button = data["buttons"][0]
    assert button["title"] == "📸 Помощь с домашкой (бесплатно)"
    assert button["url"].endswith("#homework")
