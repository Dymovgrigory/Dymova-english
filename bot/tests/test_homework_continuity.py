"""Продолжение обсуждения уже показанного задания — владелец, 2026-09-28:
«после того как направил задание, дальше можно было обсуждать это домашнее
задание ... контекст должен сохраняться, пока это задание обсуждается»."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import crm_store
from app import main as main_module
from app import memory as memory_module
from app.ai_core import handle_message
from app.config import settings
from app.memory import (
    ACTIVE_HOMEWORK_CONTEXT_TTL_MIN,
    Conversation,
    active_homework_context,
    clear_active_homework_context,
    get_store,
    set_active_homework_context,
)
from tests.conftest import make_telegram_init_data

TOKEN = "123456:AA-test-token"


# --- memory.py: хранение и TTL ---------------------------------------------


def test_set_and_read_active_homework_context():
    conv = Conversation(user_id="tg:1")
    assert active_homework_context(conv) is None
    set_active_homework_context(conv, "Вставь is/are", "📘 Правило...")
    ctx = active_homework_context(conv)
    assert ctx == ("Вставь is/are", "📘 Правило...")


def test_active_homework_context_survives_roundtrip():
    from dataclasses import asdict

    from app.memory import _conv_from_dict

    conv = Conversation(user_id="tg:2")
    set_active_homework_context(conv, "задание", "ответ")
    restored = _conv_from_dict(asdict(conv))
    assert active_homework_context(restored) == ("задание", "ответ")


def test_active_homework_context_expires_after_ttl():
    conv = Conversation(user_id="tg:3")
    set_active_homework_context(conv, "задание", "ответ")
    stale = datetime.now(timezone.utc) - timedelta(minutes=ACTIVE_HOMEWORK_CONTEXT_TTL_MIN + 1)
    conv.active_homework_at = stale.isoformat(timespec="seconds")
    assert active_homework_context(conv) is None


def test_clear_active_homework_context():
    conv = Conversation(user_id="tg:4")
    set_active_homework_context(conv, "задание", "ответ")
    clear_active_homework_context(conv)
    assert active_homework_context(conv) is None


# --- ai_core._route: продолжение диалога через handle_message --------------


@pytest.fixture(autouse=True)
def _fresh_store():
    get_store()._data.clear()


@pytest.mark.asyncio
async def test_followup_question_continues_active_homework(monkeypatch):
    store = get_store()
    conv = store.get("cont-1", platform="web")
    conv.registered = True
    set_active_homework_context(conv, "Вставь is/are: They ... happy.", "🔎 Пункт 1\nПосмотри на подлежащее.")
    store.save(conv)

    fake_followup = AsyncMock(return_value="Ещё раз: подлежащее They — множественное число.")
    monkeypatch.setattr("app.ai_core.homework.explain_homework_followup", fake_followup)

    reply = await handle_message("cont-1", "Объясни ещё раз, пожалуйста", platform="web")

    fake_followup.assert_awaited_once()
    args = fake_followup.await_args.args
    assert args[0] == "Вставь is/are: They ... happy."
    assert "Посмотри на подлежащее" in args[1]
    assert args[2] == "Объясни ещё раз, пожалуйста"
    assert "множественное число" in reply


@pytest.mark.asyncio
async def test_followup_not_triggered_when_context_expired(monkeypatch):
    store = get_store()
    conv = store.get("cont-2", platform="web")
    conv.registered = True
    set_active_homework_context(conv, "задание", "прошлый ответ")
    stale = datetime.now(timezone.utc) - timedelta(minutes=ACTIVE_HOMEWORK_CONTEXT_TTL_MIN + 1)
    conv.active_homework_at = stale.isoformat(timespec="seconds")
    store.save(conv)

    fake_followup = AsyncMock(return_value="не должно вызваться")
    monkeypatch.setattr("app.ai_core.homework.explain_homework_followup", fake_followup)

    await handle_message("cont-2", "а расскажи ещё", platform="web")

    fake_followup.assert_not_awaited()


@pytest.mark.asyncio
async def test_followup_not_triggered_by_unrelated_topic_change(monkeypatch):
    """Явная смена темы (цена) не должна перехватываться тьютором — только
    сообщения с неопределённым/вопросительным намерением."""
    store = get_store()
    conv = store.get("cont-3", platform="web")
    conv.registered = True
    set_active_homework_context(conv, "задание", "прошлый ответ")
    store.save(conv)

    fake_followup = AsyncMock(return_value="не должно вызваться")
    monkeypatch.setattr("app.ai_core.homework.explain_homework_followup", fake_followup)

    reply = await handle_message("cont-3", "Сколько стоит английский для ребёнка 9 лет?", platform="web")

    fake_followup.assert_not_awaited()
    assert reply


@pytest.mark.asyncio
async def test_followup_falls_back_to_consultation_when_model_unavailable(monkeypatch):
    """Критик/модель недоступны — не молчим, скатываемся в обычную
    консультацию вместо пустого ответа."""
    store = get_store()
    conv = store.get("cont-4", platform="web")
    conv.registered = True
    set_active_homework_context(conv, "задание", "прошлый ответ")
    store.save(conv)

    fake_followup = AsyncMock(return_value=None)
    monkeypatch.setattr("app.ai_core.homework.explain_homework_followup", fake_followup)

    reply = await handle_message("cont-4", "а расскажи ещё", platform="web")

    fake_followup.assert_awaited_once()
    assert reply  # обычная консультация ответила чем-то, а не пустотой


# --- мини-приложение: эндпоинты выставляют активный контекст ---------------


def auth(uid: int = 888) -> dict:
    return {
        "X-Miniapp-Init-Data": make_telegram_init_data(TOKEN, telegram_user_id=uid),
        "X-Miniapp-Platform": "telegram",
    }


@pytest.fixture()
def miniapp_configured(monkeypatch):
    memory_module._store = None
    crm_store.reset()
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", TOKEN, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_AUTH_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_REQUIRE_REGISTRATION", False, raising=False)
    yield
    memory_module._store = None
    crm_store.reset()


def test_explain_endpoint_sets_active_homework_context(miniapp_configured):
    client = TestClient(main_module.app)
    with patch("app.homework.explain_homework_image", new=AsyncMock(return_value="🔎 Пункт 1\nСмотри сюда.")):
        resp = client.post(
            "/api/miniapp/homework",
            headers=auth(),
            files={"image": ("hw.jpg", b"fake-bytes", "image/jpeg")},
            data={"note": "разбери задание"},
        )
    assert resp.status_code == 200
    conv = get_store().get("tg:888", platform="telegram")
    ctx = active_homework_context(conv)
    assert ctx is not None
    assert ctx[1] == "🔎 Пункт 1\nСмотри сюда."


def test_check_endpoint_sets_active_homework_context(miniapp_configured):
    client = TestClient(main_module.app)
    with patch("app.homework.check_homework_image", new=AsyncMock(return_value="🔎 Пункт 1\nВерно!")):
        resp = client.post(
            "/api/miniapp/homework/check",
            headers=auth(),
            files={"image": ("hw.jpg", b"fake-bytes", "image/jpeg")},
        )
    assert resp.status_code == 200
    conv = get_store().get("tg:888", platform="telegram")
    assert active_homework_context(conv) is not None


def test_voice_endpoint_sets_active_homework_context(miniapp_configured):
    client = TestClient(main_module.app)
    with patch("app.speech.transcribe", new=AsyncMock(return_value="Вставь is/are")), patch(
        "app.homework.explain_homework_text", new=AsyncMock(return_value="🔎 Пункт 1\nСмотри.")
    ):
        resp = client.post(
            "/api/miniapp/homework/voice",
            headers=auth(),
            files={"audio": ("voice.webm", b"fake-audio", "audio/webm")},
        )
    assert resp.status_code == 200
    conv = get_store().get("tg:888", platform="telegram")
    ctx = active_homework_context(conv)
    assert ctx is not None
    assert ctx[0] == "Вставь is/are"


def test_second_photo_gets_continuation_hint_when_task_active(miniapp_configured):
    """«добавлять ещё фотографии к этому заданию» — вторая фотография,
    пока задание ещё обсуждается, должна прийти в модель с подсказкой о
    контексте, а не как полностью не связанный новый вопрос."""
    client = TestClient(main_module.app)
    conv = get_store().get("tg:888", platform="telegram")
    set_active_homework_context(conv, "Вставь is/are", "🔎 Пункт 1\nСмотри на подлежащее.")
    get_store().save(conv)

    fake_explain = AsyncMock(return_value="🔎 Пункт 1\nЕщё разбор.")
    with patch("app.homework.explain_homework_image", new=fake_explain):
        resp = client.post(
            "/api/miniapp/homework",
            headers=auth(),
            files={"image": ("hw2.jpg", b"fake-bytes-2", "image/jpeg")},
            data={"note": "вот вторая страница"},
        )
    assert resp.status_code == 200
    note_sent = fake_explain.await_args.args[2]
    assert "вот вторая страница" in note_sent
    assert "Вставь is/are" in note_sent or "Смотри на подлежащее" in note_sent
