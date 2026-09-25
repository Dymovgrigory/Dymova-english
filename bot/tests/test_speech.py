"""Каскад распознавания речи: OpenAI (основной провайдер → proxyapi-запасной
провайдер из LLM_FALLBACKS) → опционально Yandex SpeechKit."""
import httpx
import pytest

from app import speech
from app.config import settings


@pytest.fixture(autouse=True)
def _stt_settings(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FALLBACKS",
                        '[{"base_url": "https://api.proxyapi.ru/openai/v1", '
                        '"api_key": "proxy-key", "model": "gpt-4o-mini"}]')
    monkeypatch.setattr(settings, "STT_OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "STT_OPENAI_BASE_URL", "")
    monkeypatch.setattr(settings, "STT_MODELS", "gpt-4o-mini-transcribe,gpt-4o-transcribe")
    monkeypatch.setattr(settings, "STT_YANDEX_API_KEY", "")
    monkeypatch.setattr(settings, "STT_YANDEX_FOLDER_ID", "")
    yield


@pytest.mark.asyncio
async def test_transcribe_success_on_first_model(monkeypatch):
    calls = []

    async def fake_post(self, url, **kwargs):
        calls.append((url, kwargs.get("data", {}).get("model")))
        return httpx.Response(200, json={"text": "Вставь is или are"},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await speech.transcribe(b"fake-audio-bytes", "voice.ogg", "audio/ogg")
    assert result == "Вставь is или are"
    assert calls[0][1] == "gpt-4o-mini-transcribe"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_transcribe_falls_back_to_second_model_on_error(monkeypatch):
    responses = iter([
        httpx.Response(400, json={"error": "bad request"}, request=httpx.Request("POST", "u")),
        httpx.Response(200, json={"text": "OK текст"}, request=httpx.Request("POST", "u")),
    ])

    async def fake_post(self, url, **kwargs):
        return next(responses)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await speech.transcribe(b"bytes", "a.ogg", "audio/ogg")
    assert result == "OK текст"


@pytest.mark.asyncio
async def test_transcribe_uses_proxyapi_fallback_when_openai_key_not_set(monkeypatch):
    seen_urls = []

    async def fake_post(self, url, **kwargs):
        seen_urls.append(url)
        return httpx.Response(200, json={"text": "текст"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await speech.transcribe(b"bytes", "a.ogg", "audio/ogg")
    assert "api.proxyapi.ru" in seen_urls[0]


@pytest.mark.asyncio
async def test_transcribe_uses_explicit_openai_key_when_set(monkeypatch):
    monkeypatch.setattr(settings, "STT_OPENAI_API_KEY", "direct-key")
    monkeypatch.setattr(settings, "STT_OPENAI_BASE_URL", "https://api.openai.com/v1")
    seen_urls = []
    seen_auth = []

    async def fake_post(self, url, **kwargs):
        seen_urls.append(url)
        seen_auth.append(kwargs.get("headers", {}).get("Authorization"))
        return httpx.Response(200, json={"text": "текст"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await speech.transcribe(b"bytes", "a.ogg", "audio/ogg")
    assert "api.openai.com" in seen_urls[0]
    assert seen_auth[0] == "Bearer direct-key"


@pytest.mark.asyncio
async def test_transcribe_sends_context_prompt(monkeypatch):
    seen_prompts = []

    async def fake_post(self, url, **kwargs):
        seen_prompts.append(kwargs.get("data", {}).get("prompt"))
        return httpx.Response(200, json={"text": "текст"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await speech.transcribe(b"bytes", "a.ogg", "audio/ogg")
    assert seen_prompts[0] == speech.STT_CONTEXT_PROMPT
    assert "латиницей" in speech.STT_CONTEXT_PROMPT


@pytest.mark.asyncio
async def test_transcribe_falls_back_to_yandex_when_openai_cascade_fails(monkeypatch):
    monkeypatch.setattr(settings, "STT_YANDEX_API_KEY", "yandex-key")
    monkeypatch.setattr(settings, "STT_YANDEX_FOLDER_ID", "folder-1")

    async def fake_post(self, url, **kwargs):
        if "yandex" in url:
            return httpx.Response(200, json={"result": "распознано яндексом"},
                                  request=httpx.Request("POST", url))
        return httpx.Response(500, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await speech.transcribe(b"bytes", "a.ogg", "audio/ogg")
    assert result == "распознано яндексом"


@pytest.mark.asyncio
async def test_transcribe_returns_none_when_everything_fails(monkeypatch):
    async def fake_post(self, url, **kwargs):
        return httpx.Response(500, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await speech.transcribe(b"bytes", "a.ogg", "audio/ogg")
    assert result is None


@pytest.mark.asyncio
async def test_transcribe_no_provider_configured_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FALLBACKS", "[]")
    result = await speech.transcribe(b"bytes", "a.ogg", "audio/ogg")
    assert result is None


@pytest.mark.asyncio
async def test_transcribe_network_exception_does_not_crash(monkeypatch):
    async def fake_post(self, url, **kwargs):
        raise httpx.ConnectError("сеть недоступна", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await speech.transcribe(b"bytes", "a.ogg", "audio/ogg")
    assert result is None


@pytest.mark.asyncio
async def test_transcribe_malformed_json_response_does_not_crash(monkeypatch):
    # 200, но тело — не JSON: resp.json() бросает JSONDecodeError, каскад
    # обязан пойти дальше, а не упасть.
    async def fake_post(self, url, **kwargs):
        return httpx.Response(200, text="<html>not json</html>",
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await speech.transcribe(b"bytes", "a.ogg", "audio/ogg")
    assert result is None


@pytest.mark.asyncio
async def test_transcribe_null_text_field_does_not_crash(monkeypatch):
    # 200 с валидным JSON, но {"text": null} / {"result": null} — .strip()
    # на None раньше валился AttributeError; каскад обязан просто пойти дальше.
    async def fake_post(self, url, **kwargs):
        if "yandex" in url:
            return httpx.Response(200, json={"result": None}, request=httpx.Request("POST", url))
        return httpx.Response(200, json={"text": None}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await speech.transcribe(b"bytes", "a.ogg", "audio/ogg")
    assert result is None
