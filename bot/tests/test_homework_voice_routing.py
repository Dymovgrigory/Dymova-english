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


def test_looks_like_check_request_does_not_match_provernut():
    """«Провернуть» — постороннее слово с тем же стемом «провер», не просьба
    проверить решение. Одновременно настоящая просьба продолжает работать."""
    assert not main_module._looks_like_check_request("Можете провернуть эту тему?")
    assert not main_module._looks_like_check_request("хочу провернуть фокус")
    assert main_module._looks_like_check_request("Проверь, пожалуйста")
    assert main_module._looks_like_check_request("проверьте моё решение")
    assert main_module._looks_like_check_request("нужно проверить домашку")


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


class _FakeStreamResponse:
    """Имитирует httpx.Response в режиме стрима — отдаёт чанки по одному,
    а не всё тело сразу, как настоящий client.stream()."""

    def __init__(self, status_code: int, chunks: list[bytes]):
        self.status_code = status_code
        self._chunks = chunks

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeStreamCtx:
    """Асинхронный контекстный менеджер — то, что реально возвращает
    (синхронно) httpx.AsyncClient.stream(...)."""

    def __init__(self, response: _FakeStreamResponse):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_max_download_file_streams_from_payload_url(monkeypatch):
    import httpx
    from app.max_client import MaxClient

    client = MaxClient()

    def fake_stream(self, method, url, **kwargs):
        # client.stream(...) — синхронный метод, отдающий асинхронный CM.
        return _FakeStreamCtx(_FakeStreamResponse(200, [b"audio-", b"bytes"]))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    data = await client.download_file("https://example.max.ru/file/1", 1024)
    assert data == b"audio-bytes"


@pytest.mark.asyncio
async def test_max_download_file_too_large_returns_none(monkeypatch):
    """Большой файл обрывается по ходу стрима, а не после полной загрузки в
    память — проверяем это по числу принятых чанков, а не только по итогу."""
    import httpx
    from app.max_client import MaxClient

    client = MaxClient()
    seen_chunks: list[bytes] = []

    def fake_stream(self, method, url, **kwargs):
        async def chunks():
            for _ in range(5):
                chunk = b"x" * 100
                seen_chunks.append(chunk)
                yield chunk

        response = _FakeStreamResponse(200, [])
        response.aiter_bytes = chunks
        return _FakeStreamCtx(response)

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    data = await client.download_file("https://example.max.ru/file/1", 10)
    assert data is None
    # Лимит 10 байт — обрыв должен случиться на первом же чанке (100 байт),
    # а не после того, как все 5 чанков (500 байт) уже прочитаны.
    assert len(seen_chunks) == 1


@pytest.mark.asyncio
async def test_check_stem_does_not_override_clearly_different_caption_intent(monkeypatch):
    """«Проверьте, сколько стоит абонемент?» матчит стем «провер», но
    detect_intent явно распознаёт цену — цена должна победить: фото не
    должно улетать в vision-проверку, ответ идёт про цену."""
    telegram = AsyncMock()
    telegram.download_file = AsyncMock(return_value=b"img-bytes")
    telegram.send_message = AsyncMock(return_value=True)

    async def fake_handle_message(user_id, text, platform="max"):
        return f"ответ на: {text}"

    monkeypatch.setattr(main_module, "handle_message", fake_handle_message)
    monkeypatch.setattr(main_module, "_contextual_buttons", lambda question, reply: [])

    update = {
        "update_id": 9101,
        "message": {
            "chat": {"id": 700},
            "photo": [{"file_id": "f1", "file_size": 10}],
            "caption": "Проверьте, пожалуйста, сколько стоит абонемент?",
        },
    }
    await main_module._process_telegram_update(update, telegram)

    telegram.download_file.assert_not_awaited()
    reply = telegram.send_message.await_args.args[1]
    assert "Проверьте, пожалуйста, сколько стоит абонемент?" in reply


@pytest.mark.asyncio
async def test_max_audio_attachment_without_url_gets_a_reply():
    """Раньше вложение audio без payload.url молча приводило к return без
    единого ответа пользователю — единственный такой случай в этой ветке."""
    max_client = AsyncMock()
    max_client.send_message = AsyncMock(return_value=True)

    update = {
        "message": {
            "sender": {"user_id": 42},
            "body": {"text": "", "attachments": [{"type": "audio", "payload": {}}]},
        }
    }
    await main_module._process_update(update, "message_created", max_client)

    max_client.send_message.assert_awaited_once()
    text = max_client.send_message.await_args.args[1]
    assert "голосов" in text.lower() or "текстом" in text.lower()
