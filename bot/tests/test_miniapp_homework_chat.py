"""Кнопки помощи с ДЗ и история чата прямо в мини-приложении."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import crm_store
from app import main as main_module
from app import memory as memory_module
from app.config import settings
from tests.conftest import make_telegram_init_data

TOKEN = "123456:AA-test-token"


def auth(uid: int = 777) -> dict:
    return {
        "X-Miniapp-Init-Data": make_telegram_init_data(TOKEN, telegram_user_id=uid),
        "X-Miniapp-Platform": "telegram",
    }


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    memory_module._store = None
    crm_store.reset()
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", TOKEN, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_AUTH_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_REQUIRE_REGISTRATION", False, raising=False)
    yield
    memory_module._store = None
    crm_store.reset()


def test_chat_history_requires_signed_identity():
    client = TestClient(main_module.app)
    resp = client.get("/api/miniapp/chat/history")
    assert resp.status_code == 401


def test_chat_history_returns_past_messages_in_order():
    from app import crm_ingest

    crm_ingest.ingest_inbound("telegram", "tg:777", "первый вопрос", external_event_id="e1")
    ctx = crm_ingest.ingest_inbound("telegram", "tg:777", "второй вопрос", external_event_id="e2")
    crm_ingest.ingest_outbound(ctx, "ответ бота")
    client = TestClient(main_module.app)
    resp = client.get("/api/miniapp/chat/history", headers=auth())
    body = resp.json()
    assert body["ok"] is True
    texts = [m["text"] for m in body["messages"]]
    assert texts == ["первый вопрос", "второй вопрос", "ответ бота"]
    assert body["messages"][0]["role"] == "me"
    assert body["messages"][-1]["role"] == "bot"


def test_check_endpoint_returns_explanation():
    client = TestClient(main_module.app)
    with patch("app.homework.check_homework_image", new=AsyncMock(return_value="🔎 Пункт 1\nВерно!")):
        resp = client.post(
            "/api/miniapp/homework/check",
            files={"image": ("t.jpg", b"fake-bytes", "image/jpeg")},
            headers=auth(),
        )
    body = resp.json()
    assert body["ok"] is True
    assert "Пункт 1" in body["explanation"]


def test_voice_endpoint_transcribes_and_explains():
    client = TestClient(main_module.app)
    with patch("app.speech.transcribe", new=AsyncMock(return_value="Вставь is или are")), \
         patch("app.homework.explain_homework_text", new=AsyncMock(return_value="📘 Правило")):
        resp = client.post(
            "/api/miniapp/homework/voice",
            files={"audio": ("v.ogg", b"fake-audio", "audio/ogg")},
            headers=auth(),
        )
    body = resp.json()
    assert body["ok"] is True
    assert body["transcript"] == "Вставь is или are"
    assert "Правило" in body["explanation"]


def test_voice_endpoint_unrecognized_audio_returns_error_not_500():
    client = TestClient(main_module.app)
    with patch("app.speech.transcribe", new=AsyncMock(return_value=None)):
        resp = client.post(
            "/api/miniapp/homework/voice",
            files={"audio": ("v.ogg", b"fake-audio", "audio/ogg")},
            headers=auth(),
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
