"""Доставка сообщений в Telegram: кнопки, лимиты, flood control.

Раньше эти случаи выглядели для пользователя одинаково — «бот молчит».
"""


import pytest

from app import telegram_client as tg
from app.config import settings


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="ok"):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {"ok": True, "result": {}}
        self.text = text

    def json(self):
        return self._json


class FakeAsyncClient:
    """Заглушка httpx.AsyncClient со сценарием ответов."""

    responses: list = []
    posted: list = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, data=None):
        FakeAsyncClient.posted.append({"url": url, "data": data})
        if FakeAsyncClient.responses:
            return FakeAsyncClient.responses.pop(0)
        return FakeResponse()


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "token", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_PROXY_URL", "", raising=False)
    monkeypatch.setattr(tg.httpx, "AsyncClient", FakeAsyncClient)
    FakeAsyncClient.responses = []
    FakeAsyncClient.posted = []
    yield
    FakeAsyncClient.responses = []
    FakeAsyncClient.posted = []


# --- кнопки ---------------------------------------------------------------


def test_callback_buttons_are_not_dropped():
    """Кнопки выбора филиала приходят как callback — раньше их выкидывало
    в _normalize_buttons, и пользователь видел вопрос без единой кнопки."""
    rows = tg._normalize_buttons(
        [[{"type": "callback", "text": "Филиал на Лихачевском", "payload": "contact:lihachevsky"}]]
    )

    assert rows == [[{"text": "Филиал на Лихачевском", "callback_data": "contact:lihachevsky"}]]


def test_web_app_button_requires_https():
    assert tg._normalize_buttons([[{"type": "web_app", "text": "Кабинет", "web_app": "http://x"}]]) == []
    rows = tg._normalize_buttons([[{"type": "web_app", "text": "Кабинет", "web_app": "https://x/tg/"}]])
    assert rows == [[{"text": "Кабинет", "web_app": {"url": "https://x/tg/"}}]]


def test_callback_data_is_truncated_to_telegram_limit():
    rows = tg._normalize_buttons([[{"text": "x", "payload": "p" * 200}]])
    assert len(rows[0][0]["callback_data"]) == 64


# --- длинные сообщения ----------------------------------------------------


def test_split_message_respects_limit_and_keeps_all_text():
    text = "\n\n".join(f"Абзац номер {i} " + "слово " * 40 for i in range(30))
    parts = tg.split_message(text)

    assert len(parts) > 1
    assert all(len(p) <= tg.TELEGRAM_MAX_MESSAGE_CHARS for p in parts)
    joined = " ".join(parts)
    assert "Абзац номер 0" in joined and "Абзац номер 29" in joined


def test_split_message_returns_single_part_for_short_text():
    assert tg.split_message("привет") == ["привет"]
    assert tg.split_message("") == []


@pytest.mark.asyncio
async def test_long_reply_is_delivered_in_chunks():
    """4096+ символов раньше отбивались 400-й ошибкой — молчание в чате."""
    client = tg.TelegramClient()
    long_text = "а" * 9000

    ok = await client.send_message(1, long_text)

    assert ok is True
    sends = [p for p in FakeAsyncClient.posted if p["url"].endswith("/sendMessage")]
    assert len(sends) == 3
    assert all(len(p["data"]["text"]) <= tg.TELEGRAM_MAX_MESSAGE_CHARS for p in sends)


@pytest.mark.asyncio
async def test_keyboard_attaches_only_to_last_chunk():
    client = tg.TelegramClient()

    await client.send_message(1, "б" * 5000, buttons=[[{"text": "Записаться", "url": "https://x"}]])

    sends = [p for p in FakeAsyncClient.posted if p["url"].endswith("/sendMessage")]
    assert "reply_markup" not in sends[0]["data"]
    assert "reply_markup" in sends[-1]["data"]


# --- устойчивость ---------------------------------------------------------


@pytest.mark.asyncio
async def test_flood_control_waits_retry_after_and_succeeds(monkeypatch):
    slept = []

    async def fake_sleep(delay):
        slept.append(delay)

    monkeypatch.setattr(tg.asyncio, "sleep", fake_sleep)
    FakeAsyncClient.responses = [
        FakeResponse(429, {"ok": False, "parameters": {"retry_after": 7}}),
        FakeResponse(200, {"ok": True, "result": {"message_id": 1}}),
    ]
    client = tg.TelegramClient()

    assert await client.send_message(1, "привет") is True
    assert slept == [7.0]


@pytest.mark.asyncio
async def test_server_error_is_retried(monkeypatch):
    async def no_sleep(delay):
        return None

    monkeypatch.setattr(tg.asyncio, "sleep", no_sleep)
    FakeAsyncClient.responses = [
        FakeResponse(500, text="boom"),
        FakeResponse(200, {"ok": True, "result": {"message_id": 2}}),
    ]
    client = tg.TelegramClient()

    assert await client.send_message(1, "привет") is True


@pytest.mark.asyncio
async def test_bad_request_is_not_retried_forever():
    FakeAsyncClient.responses = [FakeResponse(400, {"ok": False}, text="chat not found")]
    client = tg.TelegramClient()

    assert await client.send_message(1, "привет") is False
    assert len(FakeAsyncClient.posted) == 1


@pytest.mark.asyncio
async def test_answer_callback_query_is_sent():
    client = tg.TelegramClient()

    assert await client.answer_callback_query("cbq-9") is True
    assert FakeAsyncClient.posted[-1]["url"].endswith("/answerCallbackQuery")
    assert FakeAsyncClient.posted[-1]["data"]["callback_query_id"] == "cbq-9"


@pytest.mark.asyncio
async def test_send_chat_action_typing():
    client = tg.TelegramClient()

    assert await client.send_chat_action(5) is True
    assert FakeAsyncClient.posted[-1]["url"].endswith("/sendChatAction")
    assert FakeAsyncClient.posted[-1]["data"]["action"] == "typing"
