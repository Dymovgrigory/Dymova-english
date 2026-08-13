"""Транспорт MAX: доставка сообщений не должна теряться на первой осечке."""
from __future__ import annotations

import httpx
import pytest

from app import max_client as mc
from app.config import settings


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(settings, "MAX_BOT_TOKEN", "test-token")
    monkeypatch.setattr(settings, "MAX_BOT_API_URL", "https://platform-api2.max.ru")
    monkeypatch.setattr(settings, "MAX_CA_BUNDLE", "")
    mc.reset_max()
    yield
    mc.reset_max()


class FakeTransport:
    """Отдаёт заранее заданную последовательность ответов и пишет запросы."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[dict] = []

    async def request(self, method, url, params=None, headers=None, json=None):
        self.requests.append(
            {"method": method, "url": url, "params": params, "headers": headers, "json": json}
        )
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def is_closed(self):
        return False


def _response(status: int, body: dict | None = None, headers: dict | None = None):
    return httpx.Response(
        status,
        json=body if body is not None else {},
        headers=headers or {},
        request=httpx.Request("POST", "https://platform-api2.max.ru/messages"),
    )


@pytest.fixture
def transport(monkeypatch):
    def install(responses):
        fake = FakeTransport(responses)
        monkeypatch.setattr(mc, "_http", lambda: fake)
        # Ретраи не должны растягивать тест на реальные секунды.
        async def no_sleep(_):
            return None

        monkeypatch.setattr(mc.asyncio, "sleep", no_sleep)
        return fake

    return install


# --------------------------- домен и авторизация ---------------------------

def test_default_domain_is_the_current_one():
    """botapi.max.ru выведен из эксплуатации, срок миграции истёк 19.07.2026."""
    from app.config import Settings

    assert Settings().MAX_BOT_API_URL == "https://platform-api2.max.ru"


async def test_token_goes_into_header_not_query(transport):
    """Передача токена query-параметром платформой больше не поддерживается."""
    fake = transport([_response(200)])
    await mc.get_max().send_message("42", "привет")

    request = fake.requests[0]
    assert request["headers"]["Authorization"] == "test-token"
    assert "Bearer" not in request["headers"]["Authorization"]
    assert "access_token" not in (request["params"] or {})


async def test_message_targets_messages_endpoint(transport):
    fake = transport([_response(200)])
    await mc.get_max().send_message("42", "привет")
    assert fake.requests[0]["url"].endswith("/messages")
    assert fake.requests[0]["params"] == {"user_id": "42"}
    assert fake.requests[0]["json"]["text"] == "привет"


# --------------------------- надёжность доставки ---------------------------

async def test_network_error_is_retried(transport):
    """Одиночная сетевая осечка не должна терять сообщение клиента."""
    fake = transport([
        httpx.ConnectError("сеть недоступна"),
        _response(200),
    ])
    assert await mc.get_max().send_message("42", "привет") is True
    assert len(fake.requests) == 2


async def test_server_error_is_retried(transport):
    fake = transport([_response(503), _response(200)])
    assert await mc.get_max().send_message("42", "привет") is True
    assert len(fake.requests) == 2


async def test_rate_limit_is_respected_and_retried(transport, monkeypatch):
    """429 без ретрая — это молча потерянное сообщение."""
    waited: list[float] = []

    async def record_sleep(seconds):
        waited.append(seconds)

    transport([_response(429, headers={"Retry-After": "2"}), _response(200)])
    # Патчим sleep ПОСЛЕ фикстуры: иначе её заглушка перекроет запись пауз.
    monkeypatch.setattr(mc.asyncio, "sleep", record_sleep)

    assert await mc.get_max().send_message("42", "привет") is True
    assert waited == [2.0]


async def test_rate_limit_wait_is_capped(transport, monkeypatch):
    """Ждать полчаса по требованию сервера бессмысленно — лучше фолбэк."""
    waited: list[float] = []

    async def record_sleep(seconds):
        waited.append(seconds)

    transport([_response(429, headers={"Retry-After": "9999"}), _response(200)])
    # Патчим sleep ПОСЛЕ фикстуры: иначе её заглушка перекроет запись пауз.
    monkeypatch.setattr(mc.asyncio, "sleep", record_sleep)

    await mc.get_max().send_message("42", "привет")
    assert waited == [mc._MAX_RETRY_AFTER]


async def test_client_error_is_not_retried(transport):
    """400 не станет успешным от повтора — только тратит время пользователя."""
    fake = transport([_response(400, {"error": "bad request"})])
    assert await mc.get_max().send_message("42", "привет") is False
    assert len(fake.requests) == 1


async def test_gives_up_after_max_attempts(transport):
    fake = transport([_response(503), _response(503), _response(503)])
    assert await mc.get_max().send_message("42", "привет") is False
    assert len(fake.requests) == mc._MAX_ATTEMPTS


async def test_empty_body_on_success_is_not_a_failure(transport):
    """Успешный ответ без JSON — это доставка, а не ошибка."""
    response = httpx.Response(
        200, content=b"", request=httpx.Request("POST", "https://platform-api2.max.ru/messages")
    )
    transport([response])
    assert await mc.get_max().send_message("42", "привет") is True


async def test_unconfigured_bot_does_not_call_api(transport, monkeypatch):
    monkeypatch.setattr(settings, "MAX_BOT_TOKEN", "")
    mc.reset_max()
    fake = transport([_response(200)])
    assert await mc.get_max().send_message("42", "привет") is False
    assert fake.requests == []


# --------------------------- прочие методы ---------------------------

async def test_answer_callback_retries_less(transport):
    """Спиннер у пользователя всё равно погаснет по таймауту клиента."""
    fake = transport([_response(503), _response(503)])
    assert await mc.get_max().answer_callback("cb-1") is False
    assert len(fake.requests) == 2


async def test_set_webhook_passes_secret(transport):
    fake = transport([_response(200)])
    await mc.get_max().set_webhook("https://bot.example/webhook", "s3cret")
    assert fake.requests[0]["url"].endswith("/subscriptions")
    assert fake.requests[0]["json"] == {"url": "https://bot.example/webhook", "secret": "s3cret"}


async def test_buttons_are_wrapped_into_inline_keyboard(transport):
    fake = transport([_response(200)])
    await mc.get_max().send_message(
        "42", "выберите", buttons=[[mc.callback_button("Курсы", "menu:courses")]]
    )
    attachment = fake.requests[0]["json"]["attachments"][0]
    assert attachment["type"] == "inline_keyboard"
    assert attachment["payload"]["buttons"][0][0]["payload"] == "menu:courses"


# --------------------------- соединение ---------------------------

def test_http_client_is_reused():
    """Новый клиент на каждый вызов = TLS-рукопожатие на каждое сообщение."""
    mc._client = None
    first = mc._http()
    try:
        assert mc._http() is first
    finally:
        mc._client = None


def test_ca_bundle_is_applied(monkeypatch, tmp_path):
    """Сертификат Минцифры подключается настройкой, а не правкой кода."""
    bundle = tmp_path / "russian-trusted.pem"
    bundle.write_text("-----BEGIN CERTIFICATE-----\n", encoding="utf-8")
    monkeypatch.setattr(settings, "MAX_CA_BUNDLE", str(bundle))
    mc._client = None
    captured = {}

    class Spy:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.is_closed = False

    monkeypatch.setattr(mc.httpx, "AsyncClient", Spy)
    try:
        mc._http()
        assert captured["verify"] == str(bundle)
    finally:
        mc._client = None
