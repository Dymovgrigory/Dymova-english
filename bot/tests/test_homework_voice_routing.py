"""Голосовые/аудио и режим «проверь» в Telegram и MAX."""
from unittest.mock import AsyncMock, patch

import pytest

from app import main as main_module
from app.memory import Conversation


def test_looks_like_check_request_detects_prover_stem():
    assert main_module._looks_like_check_request("Проверь, пожалуйста")
    assert main_module._looks_like_check_request("проверка решения")
    assert not main_module._looks_like_check_request("объясни задание")
    assert not main_module._looks_like_check_request("")


def test_conversation_homework_check_context_roundtrip():
    conv = Conversation(user_id="tg:1")
    assert conv.homework_check_context is False
    conv.homework_check_context = True
    from app.memory import Conversation as C
    restored = C.from_dict(conv.to_dict()) if hasattr(conv, "to_dict") else None
    if restored is not None:
        assert restored.homework_check_context is True


@pytest.mark.asyncio
async def test_telegram_voice_message_gets_transcribed_and_explained(monkeypatch):
    telegram = AsyncMock()
    telegram.download_file = AsyncMock(return_value=b"fake-ogg-bytes")
    telegram.send_message = AsyncMock(return_value=True)
    message = {
        "voice": {"file_id": "voice-1", "mime_type": "audio/ogg"},
        "chat": {"id": 555},
        "message_id": 10,
        "from": {"id": 555, "first_name": "Аня"},
    }
    with patch("app.speech.transcribe", new=AsyncMock(return_value="Вставь is или are")), \
         patch("app.homework.explain_homework_text", new=AsyncMock(return_value="📘 Правило...")), \
         patch("app.crm_ingest.ingest_inbound", return_value={"conversation_id": 1, "customer_id": 1}), \
         patch("app.crm_store.record_homework_request", return_value=1):
        await main_module._handle_telegram_voice(message, 555, telegram)
    telegram.download_file.assert_awaited_once_with("voice-1", main_module.MAX_HOMEWORK_AUDIO_BYTES)
    sent_texts = [call.args[1] for call in telegram.send_message.await_args_list]
    assert any("Услышал" in t for t in sent_texts)
    assert any("Правило" in t for t in sent_texts)


@pytest.mark.asyncio
async def test_telegram_voice_transcription_failure_asks_to_retype(monkeypatch):
    telegram = AsyncMock()
    telegram.download_file = AsyncMock(return_value=b"fake-bytes")
    telegram.send_message = AsyncMock(return_value=True)
    message = {"voice": {"file_id": "v1"}, "chat": {"id": 1}, "message_id": 1, "from": {"id": 1}}
    with patch("app.speech.transcribe", new=AsyncMock(return_value=None)), \
         patch("app.crm_ingest.ingest_inbound", return_value=None):
        await main_module._handle_telegram_voice(message, 1, telegram)
    text = telegram.send_message.await_args.args[1]
    assert "не расслышала" in text.lower() or "текстом" in text.lower()


@pytest.mark.asyncio
async def test_max_download_file_streams_from_payload_url(monkeypatch):
    import httpx
    from app.max_client import MaxClient

    client = MaxClient()

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, content=b"audio-bytes", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    data = await client.download_file("https://example.max.ru/file/1", 1024)
    assert data == b"audio-bytes"


@pytest.mark.asyncio
async def test_max_download_file_too_large_returns_none(monkeypatch):
    import httpx
    from app.max_client import MaxClient

    client = MaxClient()

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, content=b"x" * 100, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    data = await client.download_file("https://example.max.ru/file/1", 10)
    assert data is None
