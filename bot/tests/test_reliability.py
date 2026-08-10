import asyncio
import json

import httpx
import pytest

from app import llm as llm_module
from app import main as main_module
from app import memory as memory_module
from app.config import settings


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    # timeout передаётся на каждый запрос: каскад укладывается в общий
    # бюджет LLM_TOTAL_BUDGET_SEC (см. llm._complete_with_provider).
    async def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if not self._responses:
            raise AssertionError("unexpected extra request")
        return self._responses.pop(0)


class _FakeTask:
    def add_done_callback(self, callback):
        callback(self)


@pytest.fixture(autouse=True)
def reset_singletons():
    llm_module._llm = None
    llm_module._client = None
    main_module._BACKGROUND_TASKS.clear()
    memory_module._store = None
    yield
    llm_module._llm = None
    llm_module._client = None
    main_module._BACKGROUND_TASKS.clear()
    memory_module._store = None


def _response(status_code: int, body: dict | str):
    if isinstance(body, dict):
        content = json.dumps(body).encode("utf-8")
    else:
        content = body.encode("utf-8")
    request = httpx.Request("POST", "https://example.test/chat/completions")
    return httpx.Response(status_code, content=content, request=request)


@pytest.mark.asyncio
async def test_llm_cascade_uses_fallback_provider(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "primary-key", raising=False)
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://primary.example/v1", raising=False)
    monkeypatch.setattr(settings, "LLM_MODEL", "primary-model", raising=False)
    monkeypatch.setattr(
        settings,
        "LLM_FALLBACKS",
        '[{"base_url":"https://fallback.example/v1","api_key":"fallback-key","model":"fallback-model"}]',
        raising=False,
    )

    fake_client = _FakeClient(
        [
            _response(500, "oops"),
            _response(500, "oops"),
            _response(500, "oops"),
            _response(200, {"choices": [{"message": {"content": "fallback ok"}}]}),
        ]
    )
    llm_module._client = fake_client

    async def fake_sleep(_delay):
        return None

    monkeypatch.setattr(llm_module.asyncio, "sleep", fake_sleep)

    client = llm_module.get_llm()
    reply = await client.complete([{"role": "user", "content": "hi"}])

    assert reply == "fallback ok"
    assert len(fake_client.calls) == 4
    assert fake_client.calls[0]["url"] == "https://primary.example/v1/chat/completions"
    assert fake_client.calls[3]["url"] == "https://fallback.example/v1/chat/completions"


@pytest.mark.asyncio
async def test_llm_retries_on_429_and_5xx(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "key", raising=False)
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.example/v1", raising=False)
    monkeypatch.setattr(settings, "LLM_MODEL", "model-a", raising=False)
    monkeypatch.setattr(settings, "LLM_FALLBACKS", "[]", raising=False)

    fake_client = _FakeClient(
        [
            _response(429, "rate limited"),
            _response(502, "bad gateway"),
            _response(200, {"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    llm_module._client = fake_client
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(llm_module.asyncio, "sleep", fake_sleep)

    client = llm_module.get_llm()
    reply = await client.complete([{"role": "user", "content": "hi"}])

    assert reply == "ok"
    assert len(fake_client.calls) == 3
    assert sleeps == [0.25, 0.5]


@pytest.mark.asyncio
async def test_llm_returns_none_after_all_failures(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "primary-key", raising=False)
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://primary.example/v1", raising=False)
    monkeypatch.setattr(settings, "LLM_MODEL", "primary-model", raising=False)
    monkeypatch.setattr(
        settings,
        "LLM_FALLBACKS",
        '[{"base_url":"https://fallback.example/v1","api_key":"fallback-key","model":"fallback-model"}]',
        raising=False,
    )

    fake_client = _FakeClient(
        [
            _response(503, "primary down"),
            _response(503, "primary down"),
            _response(503, "primary down"),
            _response(503, "fallback down"),
            _response(503, "fallback down"),
            _response(503, "fallback down"),
        ]
    )
    llm_module._client = fake_client

    async def fake_sleep(_delay):
        return None

    monkeypatch.setattr(llm_module.asyncio, "sleep", fake_sleep)

    client = llm_module.get_llm()
    reply = await client.complete([{"role": "user", "content": "hi"}])

    assert reply is None
    assert len(fake_client.calls) == 6


def test_memory_persists_across_store_recreation(tmp_path, monkeypatch):
    db_path = tmp_path / "bot.db"
    monkeypatch.setattr(settings, "DB_PATH", str(db_path), raising=False)
    monkeypatch.setattr(settings, "STATE_FILE", "", raising=False)

    memory_module._store = None
    store1 = memory_module.get_store()
    conv = store1.reset("user-1")
    conv.stage = memory_module.STAGE_LEAD
    conv.lead.fio_parent = "Иванова Анна"
    conv.lead.phone = "+79991234567"
    conv.history.append({"role": "user", "content": "привет"})
    store1.save(conv)

    memory_module._store = None
    store2 = memory_module.get_store()
    loaded = store2.get("user-1")

    assert loaded.stage == memory_module.STAGE_LEAD
    assert loaded.lead.fio_parent == "Иванова Анна"
    assert loaded.lead.phone == "+79991234567"
    assert loaded.history[-1]["content"] == "привет"


def test_webhook_deduplicates_same_update_id(tmp_path, monkeypatch):
    db_path = tmp_path / "bot.db"
    monkeypatch.setattr(settings, "DB_PATH", str(db_path), raising=False)
    monkeypatch.setattr(settings, "STATE_FILE", "", raising=False)

    memory_module._store = None
    main_module._BACKGROUND_TASKS.clear()

    scheduled = []

    def fake_create_task(coro):
        scheduled.append(coro)
        coro.close()
        return _FakeTask()

    monkeypatch.setattr(main_module.asyncio, "create_task", fake_create_task)

    update = {
        "id": "dup-1",
        "type": "message_created",
        "message": {
            "sender": {"user_id": "42"},
            "body": {"text": "Здравствуйте"},
        },
    }

    assert main_module._schedule_update(update, "message_created", object()) is True
    assert main_module._schedule_update(update, "message_created", object()) is False
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_llm_cascade_stops_when_time_budget_is_exhausted(monkeypatch):
    """Каскад не имеет права держать пользователя дольше бюджета.

    Худший случай без бюджета: провайдеры × 3 попытки × LLM_TIMEOUT — это
    минуты полного молчания в чате.
    """
    monkeypatch.setattr(settings, "LLM_API_KEY", "key", raising=False)
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.example/v1", raising=False)
    monkeypatch.setattr(settings, "LLM_MODEL", "model-a", raising=False)
    monkeypatch.setattr(
        settings,
        "LLM_FALLBACKS",
        '[{"base_url":"https://b.example/v1","api_key":"k","model":"model-b"}]',
        raising=False,
    )
    monkeypatch.setattr(settings, "LLM_TOTAL_BUDGET_SEC", 0.05, raising=False)

    calls = []

    class SlowClient:
        async def post(self, url, headers=None, json=None, timeout=None):
            calls.append(url)
            await asyncio.sleep(0.2)
            raise httpx.ReadTimeout("too slow")

    llm_module._client = SlowClient()
    llm_module._llm = None

    client = llm_module.get_llm()
    started = asyncio.get_running_loop().time()
    reply = await client.complete([{"role": "user", "content": "hi"}])
    elapsed = asyncio.get_running_loop().time() - started

    assert reply is None
    assert elapsed < 2.0, "каскад обязан уложиться в бюджет, а не перебирать всё подряд"
    assert len(calls) <= 2, f"после исчерпания бюджета новые запросы не шлются: {calls}"
