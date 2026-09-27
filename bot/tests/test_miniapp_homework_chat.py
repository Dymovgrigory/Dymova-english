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


def test_check_endpoint_rejects_anonymous_before_saving_or_calling_model():
    """Финальное ревью, важное #7: `_miniapp_access_state["locked"]` гейтит
    только УЖЕ распознанную личность — анонимный вызов проходил дальше и до
    этого фикса успевал сохранить фото на диск и вызвать платный vision ДО
    какой-либо проверки идентификации."""
    client = TestClient(main_module.app)
    vision = AsyncMock(return_value="не должно вызваться")
    with patch("app.homework.check_homework_image", new=vision), \
         patch("app.homework.save_homework_image") as save_image:
        resp = client.post(
            "/api/miniapp/homework/check",
            files={"image": ("t.jpg", b"fake-bytes", "image/jpeg")},
        )
    assert resp.status_code == 401
    vision.assert_not_called()
    save_image.assert_not_called()
    assert crm_store.list_homework_requests(mode="check", limit=10) == []


def test_voice_endpoint_rejects_anonymous_before_calling_stt():
    client = TestClient(main_module.app)
    transcribe = AsyncMock(return_value="не должно вызваться")
    with patch("app.speech.transcribe", new=transcribe):
        resp = client.post(
            "/api/miniapp/homework/voice",
            files={"audio": ("v.ogg", b"fake-audio", "audio/ogg")},
        )
    assert resp.status_code == 401
    transcribe.assert_not_called()


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


def test_voice_endpoint_rejects_empty_recording_without_calling_stt():
    """Пустая запись (0 байт) — 400 сразу, распознавание вообще не вызывается."""
    client = TestClient(main_module.app)
    transcribe = AsyncMock(return_value="не должно вызваться")
    with patch("app.speech.transcribe", new=transcribe):
        resp = client.post(
            "/api/miniapp/homework/voice",
            files={"audio": ("v.ogg", b"", "audio/ogg")},
            headers=auth(),
        )
    assert resp.status_code == 400
    transcribe.assert_not_called()


def test_explain_endpoint_records_to_crm_and_homework_requests():
    """Разбор задания по фото (основная ручка чата) должен попадать в CRM и
    в журнал заявок ДЗ так же, как /check и /voice — иначе самый частый путь
    невидим в админке (Task 7 на неё опирается)."""
    client = TestClient(main_module.app)
    with patch("app.homework.explain_homework_image", new=AsyncMock(return_value="Смотри на пункт 2")):
        resp = client.post(
            "/api/miniapp/homework",
            files={"image": ("t.jpg", b"fake-bytes", "image/jpeg")},
            data={"note": "задание 2"},
            headers=auth(),
        )
    body = resp.json()
    assert body["ok"] is True
    assert body["explanation"] == "Смотри на пункт 2"

    rows = crm_store.list_homework_requests(mode="explain", limit=10)
    assert any(r["input_type"] == "image" and r["reply"] == "Смотри на пункт 2" for r in rows)

    conv = crm_store.find_conversation("telegram", "tg:777")
    assert conv is not None
    texts = [m["text"] for m in crm_store.get_messages(conv["id"], limit=10)]
    assert any("[фото задания]" in t for t in texts)
    assert "Смотри на пункт 2" in texts


def test_homework_image_route_rejects_non_owner():
    """IDOR: подписанная личность доказывает, что это кто-то из школы, но не
    то, что фото — его. Чужой filename должен отвечать 404, а не отдавать
    фото чужого ребёнка."""
    client = TestClient(main_module.app)
    with patch("app.homework.check_homework_image", new=AsyncMock(return_value="Пункт 1 верно")):
        resp = client.post(
            "/api/miniapp/homework/check",
            files={"image": ("t.jpg", b"fake-bytes", "image/jpeg")},
            headers=auth(uid=777),
        )
    assert resp.json()["ok"] is True

    rows = crm_store.list_homework_requests(mode="check", limit=10)
    assert rows
    filename = rows[0]["image_path"].split("/", 1)[1]

    owner_resp = client.get(f"/api/miniapp/homework/image/{filename}", headers=auth(uid=777))
    assert owner_resp.status_code == 200

    stranger_resp = client.get(f"/api/miniapp/homework/image/{filename}", headers=auth(uid=888))
    assert stranger_resp.status_code == 404

    anon_resp = client.get(f"/api/miniapp/homework/image/{filename}")
    assert anon_resp.status_code == 401
