"""Сквозные сценарии «как настоящий пользователь».

Проверяем не отдельные функции, а поведение бота целиком: три сообщения
подряд, повторный webhook, нажатие кнопки дважды, ошибка платформы.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app import ai_core
from app import main as main_module
from app import memory as memory_module
from app.config import settings


@pytest.fixture(autouse=True)
def reset_state():
    main_module._BACKGROUND_TASKS.clear()
    memory_module._store = None
    ai_core.reset_conversation_locks()
    main_module._chat_hits.clear()
    yield
    main_module._BACKGROUND_TASKS.clear()
    memory_module._store = None
    ai_core.reset_conversation_locks()
    main_module._chat_hits.clear()


class RecordingTelegram:
    def __init__(self):
        self.sent = []
        self.actions = []
        self.answered = []

    async def send_message(self, chat_id, text, buttons=None):
        self.sent.append({"chat_id": chat_id, "text": text, "buttons": buttons})
        return True

    async def send_chat_action(self, chat_id, action="typing"):
        self.actions.append(action)
        return True

    async def answer_callback_query(self, callback_query_id, text=None):
        self.answered.append(callback_query_id)
        return True


def _text_update(update_id, chat_id, text):
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, "text": text}}


# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_messages_in_a_row_all_get_answers_in_order(monkeypatch):
    """«Привет» → «цены?» → «онлайн есть?» с интервалом в доли секунды."""
    replies = {"привет": "Здравствуйте!", "цены?": "Цены такие", "онлайн есть?": "Да, есть"}

    async def fake_handle(user_id, text, platform="max"):
        await asyncio.sleep(0.01)
        return replies[text]

    monkeypatch.setattr(main_module, "handle_message", fake_handle)
    telegram = RecordingTelegram()

    await asyncio.gather(
        main_module._process_telegram_update(_text_update(1, 10, "привет"), telegram),
        main_module._process_telegram_update(_text_update(2, 10, "цены?"), telegram),
        main_module._process_telegram_update(_text_update(3, 10, "онлайн есть?"), telegram),
    )

    texts = [s["text"] for s in telegram.sent]
    assert sorted(texts) == sorted(replies.values()), "ни одно сообщение не должно потеряться"


@pytest.mark.asyncio
async def test_message_during_generation_is_not_lost(monkeypatch):
    """Пользователь пишет, пока бот ещё формирует предыдущий ответ."""
    seen = []

    async def slow_route(conv, text, kb, intent):
        seen.append(text)
        await asyncio.sleep(0.03)
        return "ответ: " + text

    monkeypatch.setattr(ai_core, "_route", slow_route)

    first = asyncio.create_task(ai_core.handle_message("tg:11", "первый", platform="telegram"))
    await asyncio.sleep(0.005)
    second = await ai_core.handle_message("tg:11", "второй", platform="telegram")

    assert await first == "ответ: первый"
    assert second == "ответ: второй"
    assert seen == ["первый", "второй"]

    conv = memory_module.get_store().get("tg:11", platform="telegram")
    contents = [m["content"] for m in conv.history]
    assert contents == ["первый", "ответ: первый", "второй", "ответ: второй"]


def test_duplicate_webhook_delivery_is_answered_once(monkeypatch):
    """Telegram и MAX переотдают webhook при таймауте подтверждения."""
    scheduled = []

    class FakeTask:
        def add_done_callback(self, cb):
            cb(self)

    def fake_create_task(coro):
        scheduled.append(coro)
        coro.close()
        return FakeTask()

    monkeypatch.setattr(main_module.asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "", raising=False)
    client = TestClient(main_module.app)

    payload = _text_update(777, 12, "Сколько стоит?")
    assert client.post("/telegram/webhook", json=payload).status_code == 200
    assert client.post("/telegram/webhook", json=payload).status_code == 200

    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_double_button_tap_answers_both_callbacks(monkeypatch):
    """Быстрый двойной тап: оба callback обязаны быть подтверждены,
    иначе клиент оставляет кнопку в состоянии загрузки."""
    monkeypatch.setattr(settings, "ADMIN_MAX_IDS", "", raising=False)
    telegram = RecordingTelegram()

    callback = {
        "update_id": 20,
        "callback_query": {
            "id": "cb-1",
            "from": {"id": 13},
            "message": {"chat": {"id": 13}},
            "data": "contact:lihachevsky",
        },
    }
    second = {**callback, "update_id": 21}
    second["callback_query"] = {**callback["callback_query"], "id": "cb-2"}

    await asyncio.gather(
        main_module._process_telegram_update(callback, telegram),
        main_module._process_telegram_update(second, telegram),
    )

    assert sorted(telegram.answered) == ["cb-1", "cb-2"]


@pytest.mark.asyncio
async def test_platform_error_still_produces_a_reply(monkeypatch):
    """Telegram API отвалился на первой отправке — бот не должен умолкнуть."""
    calls = {"n": 0}

    class FlakyTelegram(RecordingTelegram):
        async def send_message(self, chat_id, text, buttons=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("connection reset")
            return await super().send_message(chat_id, text, buttons)

    async def fake_handle(user_id, text, platform="max"):
        return "ответ"

    monkeypatch.setattr(main_module, "handle_message", fake_handle)
    telegram = FlakyTelegram()

    await main_module._process_telegram_update(_text_update(30, 14, "вопрос"), telegram)

    assert telegram.sent, "после сбоя отправки пользователь всё равно получает сообщение"


def test_chat_endpoint_rate_limits_abuse():
    client = TestClient(main_module.app)

    statuses = [
        client.post("/api/chat", json={"text": "привет"}).status_code
        for _ in range(main_module._CHAT_RATE_LIMIT + 3)
    ]

    assert 429 in statuses
    assert statuses[0] == 200


def test_chat_endpoint_rejects_oversized_payload():
    client = TestClient(main_module.app)

    resp = client.post("/api/chat", json={"text": "а" * (main_module.MAX_CHAT_TEXT_CHARS + 1)})

    assert resp.status_code == 413
