import json

import httpx
import pytest

from app import dedup as dedup_module
from app import llm as llm_module
from app import main as main_module
from app.config import settings


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if not self.responses:
            raise AssertionError("unexpected extra request")
        return self.responses.pop(0)


class FakeTask:
    def add_done_callback(self, callback):
        callback(self)


@pytest.fixture(autouse=True)
def reset_singletons(monkeypatch):
    llm_module._client = None
    llm_module._http_client = None
    main_module._BACKGROUND_TASKS.clear()
    dedup_module._store = None
    yield
    llm_module._client = None
    llm_module._http_client = None
    main_module._BACKGROUND_TASKS.clear()
    dedup_module._store = None


def _response(status_code: int, payload):
    if isinstance(payload, dict):
        content = json.dumps(payload).encode("utf-8")
    else:
        content = str(payload).encode("utf-8")
    request = httpx.Request("POST", "https://example.test/chat/completions")
    return httpx.Response(status_code, content=content, request=request)


@pytest.mark.asyncio
async def test_llm_cascade_falls_back_to_second_provider(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "primary-key", raising=False)
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://primary.example/v1", raising=False)
    monkeypatch.setattr(settings, "LLM_MODEL", "primary-model", raising=False)
    monkeypatch.setattr(
        settings,
        "LLM_FALLBACKS",
        '[{"base_url":"https://fallback.example/v1","api_key":"fallback-key","model":"fallback-model"}]',
        raising=False,
    )

    fake_client = FakeClient(
        [
            _response(503, "primary down"),
            _response(503, "primary down"),
            _response(503, "primary down"),
            _response(200, {"choices": [{"message": {"content": "Привет, всё хорошо"}}]}),
        ]
    )
    llm_module._http_client = fake_client

    async def fake_sleep(delay):
        return None

    monkeypatch.setattr(llm_module.asyncio, "sleep", fake_sleep)

    client = llm_module.get_llm()
    reply = await client.complete([{"role": "user", "content": "hi"}])

    assert reply == "Привет, всё хорошо"
    assert len(fake_client.calls) == 4
    assert fake_client.calls[0]["json"]["model"] == "primary-model"
    assert fake_client.calls[3]["json"]["model"] == "fallback-model"


@pytest.mark.asyncio
async def test_llm_retries_on_429_and_5xx(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "key", raising=False)
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.example/v1", raising=False)
    monkeypatch.setattr(settings, "LLM_MODEL", "model-a", raising=False)
    monkeypatch.setattr(settings, "LLM_FALLBACKS", "[]", raising=False)

    fake_client = FakeClient(
        [
            _response(429, "rate limited"),
            _response(502, "bad gateway"),
            _response(200, {"choices": [{"message": {"content": "Привет, всё ок"}}]}),
        ]
    )
    llm_module._http_client = fake_client
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(llm_module.asyncio, "sleep", fake_sleep)

    client = llm_module.get_llm()
    reply = await client.complete([{"role": "user", "content": "hi"}])

    assert reply == "Привет, всё ок"
    assert len(fake_client.calls) == 3
    assert sleeps == [0.25, 0.5]


def test_webhook_deduplicates_same_update_id(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STATE_FILE", str(tmp_path / "state.json"), raising=False)
    dedup_module._store = None
    main_module._BACKGROUND_TASKS.clear()

    scheduled = []

    def fake_create_task(coro):
        scheduled.append(coro)
        coro.close()
        return FakeTask()

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
