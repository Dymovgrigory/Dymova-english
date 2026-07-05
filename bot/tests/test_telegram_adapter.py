import pytest
from fastapi.testclient import TestClient

from app import ai_core
from app import dedup as dedup_module
from app import main as main_module
from app import memory as memory_module
from app import telegram_client as telegram_module
from app.config import settings


class DisabledLLM:
    enabled = False


class FakeTelegramClient:
    def __init__(self):
        self.sent = []
        self.webhooks = []

    async def send_message(self, chat_id, text, buttons=None):
        self.sent.append({"chat_id": chat_id, "text": text, "buttons": buttons})
        return True

    async def set_webhook(self, url, secret=None):
        self.webhooks.append({"url": url, "secret": secret})
        return True


class FakeMaxClient:
    def __init__(self):
        self.sent = []

    async def send_message(self, user_id, text, buttons=None):
        self.sent.append({"user_id": user_id, "text": text, "buttons": buttons})
        return True


class FakeTask:
    def add_done_callback(self, callback):
        callback(self)


class FakeHttpxResponse:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


class FakeHttpxAsyncClient:
    created_kwargs = []
    posted = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.__class__.created_kwargs.append(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, data=None):
        self.__class__.posted.append({"url": url, "data": data, "kwargs": self.kwargs})
        return FakeHttpxResponse()


@pytest.fixture(autouse=True)
def reset_state():
    main_module._BACKGROUND_TASKS.clear()
    dedup_module._store = None
    memory_module._store = None
    telegram_module._client = None
    FakeHttpxAsyncClient.created_kwargs = []
    FakeHttpxAsyncClient.posted = []
    yield
    main_module._BACKGROUND_TASKS.clear()
    dedup_module._store = None
    memory_module._store = None
    telegram_module._client = None
    FakeHttpxAsyncClient.created_kwargs = []
    FakeHttpxAsyncClient.posted = []


def test_telegram_webhook_secret_guard(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "secret", raising=False)
    client = TestClient(main_module.app)

    denied = client.post("/telegram/webhook", json={"update_id": 1, "message": {}})
    assert denied.status_code == 403

    denied_wrong = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        json={"update_id": 1, "message": {}},
    )
    assert denied_wrong.status_code == 403


@pytest.mark.asyncio
async def test_telegram_message_route_uses_handle_message(monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())

    async def fake_handle_message(user_id, text):
        return "Спасибо!"

    monkeypatch.setattr(main_module, "handle_message", fake_handle_message)
    monkeypatch.setattr(main_module, "_contextual_buttons", lambda question, reply: [])
    telegram = FakeTelegramClient()

    await main_module._process_telegram_update(
        {
            "update_id": 1001,
            "message": {
                "chat": {"id": 42},
                "text": "Расскажи о курсах",
            },
        },
        telegram,
    )

    assert len(telegram.sent) == 1
    sent = telegram.sent[0]
    assert sent["chat_id"] == 42
    assert sent["text"] == "Спасибо!"
    assert sent["buttons"] is None


@pytest.mark.asyncio
async def test_telegram_start_and_homework_routes(monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example/app/", raising=False)
    telegram = FakeTelegramClient()

    await main_module._process_telegram_update(
        {
            "update_id": 1002,
            "message": {
                "chat": {"id": 77},
                "text": "/start",
            },
        },
        telegram,
    )
    await main_module._process_telegram_update(
        {
            "update_id": 1003,
            "message": {
                "chat": {"id": 77},
                "text": "Помоги с домашкой по английскому",
            },
        },
        telegram,
    )

    assert len(telegram.sent) == 2
    start_reply = telegram.sent[0]
    homework_reply = telegram.sent[1]
    assert start_reply["text"].startswith("Привет!")
    assert homework_reply["text"].startswith("Помощь с домашкой у нас бесплатная")
    assert homework_reply["buttons"]
    assert homework_reply["buttons"][0][0]["url"].endswith("#homework")


@pytest.mark.asyncio
async def test_telegram_handoff_uses_max_for_admins(monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    monkeypatch.setattr(settings, "ADMIN_MAX_IDS", "111", raising=False)
    fake_max = FakeMaxClient()
    monkeypatch.setattr(main_module, "get_max", lambda: fake_max)
    store = memory_module.get_store()
    conv = store.get("tg:77")
    conv.selected_branch = "Филиал на Лихачевском"
    store.save(conv)
    telegram = FakeTelegramClient()

    await main_module._process_telegram_update(
        {
            "update_id": 1004,
            "message": {
                "chat": {"id": 77},
                "text": "Верните деньги",
            },
        },
        telegram,
    )

    assert len(fake_max.sent) == 1
    admin_message = fake_max.sent[0]
    assert admin_message["user_id"] == "111"
    assert "Требуется администратор" in admin_message["text"]
    assert "Филиал на Лихачевском" in admin_message["text"]

    assert len(telegram.sent) == 1
    user_reply = telegram.sent[0]
    assert user_reply["chat_id"] == 77
    assert user_reply["text"].startswith("Свяжу вас с администратором Филиал на Лихачевском")


def test_telegram_deduplicates_update_id(monkeypatch):
    scheduled = []

    def fake_create_task(coro):
        scheduled.append(coro)
        coro.close()
        return FakeTask()

    monkeypatch.setattr(main_module.asyncio, "create_task", fake_create_task)

    update = {"update_id": 2001, "message": {"chat": {"id": 1}, "text": "hi"}}
    assert main_module._schedule_telegram_update(update, FakeTelegramClient()) is True
    assert main_module._schedule_telegram_update(update, FakeTelegramClient()) is False
    assert len(scheduled) == 1


def test_admin_telegram_set_webhook(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "token", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_URL", "https://bot.example/telegram/webhook", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "secret", raising=False)
    telegram = FakeTelegramClient()
    monkeypatch.setattr(main_module, "get_telegram", lambda: telegram)

    client = TestClient(main_module.app)
    resp = client.post("/admin/telegram/set-webhook", headers={"X-Admin-Token": "token"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert telegram.webhooks == [
        {"url": "https://bot.example/telegram/webhook", "secret": "secret"}
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "args", "url_suffix"),
    [
        ("send_message", (123, "Привет"), "/sendMessage"),
        ("set_webhook", ("https://bot.example/hook", "secret"), "/setWebhook"),
        ("delete_webhook", tuple(), "/deleteWebhook"),
    ],
)
async def test_telegram_client_passes_proxy_kwarg(monkeypatch, method_name, args, url_suffix):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "token", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_PROXY_URL", "socks5://user:pass@host:1080", raising=False)
    monkeypatch.setattr(telegram_module.httpx, "AsyncClient", FakeHttpxAsyncClient)

    client = telegram_module.TelegramClient()
    method = getattr(client, method_name)
    result = await method(*args)

    assert result is True
    assert FakeHttpxAsyncClient.created_kwargs[-1]["proxy"] == "socks5://user:pass@host:1080"
    assert FakeHttpxAsyncClient.posted[-1]["url"].endswith(url_suffix)


@pytest.mark.asyncio
async def test_telegram_client_omits_proxy_kwarg_when_empty(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "token", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_PROXY_URL", "", raising=False)
    monkeypatch.setattr(telegram_module.httpx, "AsyncClient", FakeHttpxAsyncClient)

    client = telegram_module.TelegramClient()
    result = await client.send_message(321, "Привет")

    assert result is True
    assert "proxy" not in FakeHttpxAsyncClient.created_kwargs[-1]
