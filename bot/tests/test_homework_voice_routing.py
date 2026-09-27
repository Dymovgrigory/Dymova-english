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


@pytest.mark.asyncio
async def test_telegram_voice_non_homework_intent_routes_to_chat_not_homework():
    """Финальное ревью, важное #8б: раньше ЛЮБОЕ голосовое безусловно
    считалось домашкой — родитель, записывающий ребёнка на пробное занятие
    голосом, получал разбор задания вместо ответа по существу. После
    распознавания текста намерение проверяется через _voice_diverts_to_chat:
    явно другая тема (здесь — WANT_SIGNUP, «хочу записать») уходит в обычный
    чат (handle_message), а не в explain_homework_text.

    Фраза намеренно НЕ «Когда у вас пробное занятие?» (использовалась в
    первой версии этого теста) — при доработке #8б (см. регресс ниже,
    test_voice_courses_keyword_does_not_divert_from_tutor) эта фраза стала
    ABOUT с «похожим на задание» текстом по эвристике _homework_task_text и
    больше не разворачивается однозначно — WANT_SIGNUP разворачивается
    всегда, это надёжный пример «точно не домашка»."""
    telegram = AsyncMock()
    telegram.download_file = AsyncMock(return_value=b"fake-ogg-bytes")
    telegram.send_message = AsyncMock(return_value=True)
    message = {
        "voice": {"file_id": "voice-1", "mime_type": "audio/ogg"},
        "chat": {"id": 555},
        "message_id": 10,
        "from": {"id": 555, "first_name": "Аня"},
    }
    explain_mock = AsyncMock(return_value="разбор — не должен был вызваться")
    handle_message_mock = AsyncMock(return_value="Записала на пробное занятие в субботу в 11:00.")
    with patch("app.speech.transcribe", new=AsyncMock(return_value="Хочу записать ребёнка на пробное занятие")), \
         patch("app.homework.explain_homework_text", new=explain_mock), \
         patch("app.main.handle_message", new=handle_message_mock), \
         patch("app.crm_ingest.ingest_inbound", return_value={"conversation_id": 1, "customer_id": 1}):
        await main_module._handle_telegram_voice(message, 555, telegram)
    explain_mock.assert_not_awaited()
    handle_message_mock.assert_awaited_once()
    sent_texts = [call.args[1] for call in telegram.send_message.await_args_list]
    assert any("Записала на пробное занятие" in t for t in sent_texts)


@pytest.mark.asyncio
async def test_voice_courses_keyword_does_not_divert_from_tutor():
    """Финальное ревью: регресс из первой версии #8б. `I.detect_intent`
    матчит COURSES-ключевые слова школы английского («английск», «грамматик»,
    «уровень», «группа») РАНЬШЕ QUESTION/HOMEWORK — а «задание по
    английскому: вставь is или are» это самая обычная формулировка
    голосового задания. Deny-list первой версии уводил такие сообщения в
    консультацию по курсам вместо разбора задания. Пин: этот транскрипт
    по-прежнему доходит до explain_homework_text, а не до handle_message."""
    telegram = AsyncMock()
    telegram.download_file = AsyncMock(return_value=b"fake-ogg-bytes")
    telegram.send_message = AsyncMock(return_value=True)
    message = {
        "voice": {"file_id": "voice-2", "mime_type": "audio/ogg"},
        "chat": {"id": 556},
        "message_id": 11,
        "from": {"id": 556, "first_name": "Боря"},
    }
    explain_mock = AsyncMock(return_value="📘 Правило: is/are...")
    handle_message_mock = AsyncMock(return_value="консультация по курсам — не должна была вызваться")
    with patch(
        "app.speech.transcribe",
        new=AsyncMock(return_value="Задание по английскому: вставь is или are"),
    ), \
         patch("app.homework.explain_homework_text", new=explain_mock), \
         patch("app.main.handle_message", new=handle_message_mock), \
         patch("app.crm_ingest.ingest_inbound", return_value={"conversation_id": 1, "customer_id": 1}), \
         patch("app.crm_store.record_homework_request", return_value=1):
        await main_module._handle_telegram_voice(message, 556, telegram)
    handle_message_mock.assert_not_awaited()
    explain_mock.assert_awaited_once()


def test_voice_diverts_to_chat_matches_finding1_examples():
    """Юнит на саму функцию (используется и Telegram-, и MAX-обработчиком) —
    все три фразы из ревью, которые раньше ошибочно уводились в COURSES, и
    контрпримеры однозначно других тем."""
    from app.main import _voice_diverts_to_chat

    # Раньше ошибочно разворачивались (COURSES) — теперь остаются в тьюторе.
    assert _voice_diverts_to_chat("Задание по английскому: вставь is или are") is False
    assert _voice_diverts_to_chat(
        "Помоги с упражнением по английскому, надо вставить a или an"
    ) is False
    assert _voice_diverts_to_chat("Помоги с грамматикой, present simple") is False

    # Однозначно другие темы — разворачиваются всегда.
    assert _voice_diverts_to_chat("Сколько стоит абонемент?") is True
    assert _voice_diverts_to_chat("Хочу записать ребёнка на пробное занятие") is True
    assert _voice_diverts_to_chat("Позовите, пожалуйста, администратора") is True

    # CONTACTS/ABOUT без похожего на задание текста — разворачиваются;
    # с похожим на задание текстом — остаются в тьюторе.
    assert _voice_diverts_to_chat("Адрес") is True


def test_homework_check_context_expires_after_ttl():
    """Финальное ревью, важное #8а: homework_check_context без TTL жил
    вечно — случайное фото без подписи спустя дни после разбора уходило в
    режим проверки решения вместо обычного разбора нового задания."""
    from datetime import datetime, timedelta, timezone

    conv = Conversation(user_id="tg:1")
    conv.homework_check_context = True
    fresh = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stale = (
        datetime.now(timezone.utc)
        - timedelta(minutes=main_module.HOMEWORK_CHECK_CONTEXT_TTL_MIN + 1)
    ).isoformat(timespec="seconds")

    conv.homework_check_context_at = fresh
    assert main_module._homework_check_context_active(conv) is True

    conv.homework_check_context_at = stale
    assert main_module._homework_check_context_active(conv) is False

    # Записи до этого фикса — без метки времени вообще: не терять молча уже
    # выставленный на проде контекст, считаем активным один раз.
    conv.homework_check_context_at = ""
    assert main_module._homework_check_context_active(conv) is True

    conv.homework_check_context = False
    conv.homework_check_context_at = fresh
    assert main_module._homework_check_context_active(conv) is False


@pytest.mark.asyncio
async def test_stale_homework_check_context_does_not_force_photo_check_mode():
    """Продолжение #8а на реальном пути: фото без подписи после истёкшего
    homework_check_context должно уйти в обычный разбор (explain), а не в
    режим проверки решения (check)."""
    from datetime import datetime, timedelta, timezone

    from app import memory as memory_module

    memory_module._store = None
    try:
        telegram = AsyncMock()
        telegram.download_file = AsyncMock(return_value=b"img-bytes")
        telegram.send_message = AsyncMock(return_value=True)

        conv = memory_module.get_store().get("tg:900", platform=main_module.TELEGRAM_PLATFORM)
        conv.homework_check_context = True
        conv.homework_check_context_at = (
            datetime.now(timezone.utc)
            - timedelta(minutes=main_module.HOMEWORK_CHECK_CONTEXT_TTL_MIN + 5)
        ).isoformat(timespec="seconds")
        memory_module.get_store().save(conv)

        update = {
            "update_id": 42,
            "message": {"chat": {"id": 900}, "photo": [{"file_id": "f1", "file_size": 10}]},
        }
        explain_mock = AsyncMock(return_value="📘 Правило")
        check_mock = AsyncMock(return_value="🔎 Пункт 1")
        with patch("app.main.explain_homework_image", new=explain_mock), \
             patch("app.main.check_homework_image", new=check_mock), \
             patch("app.crm_ingest.ingest_inbound", return_value=None):
            await main_module._process_telegram_update(update, telegram)

        explain_mock.assert_awaited_once()
        check_mock.assert_not_awaited()
    finally:
        memory_module._store = None


@pytest.mark.asyncio
async def test_telegram_voice_dedup_key_is_global_not_per_chat():
    """Финальное ревью, важное #6: message_id Telegram уникален только
    внутри одного чата, а не глобально. _handle_telegram_voice раньше
    использовал его как external_event_id — второе голосовое ДРУГОГО
    пользователя с тем же (маленьким, последовательным) message_id тихо
    считалось дублем в inbound_events (UNIQUE(channel, external_event_id)):
    ingest_inbound возвращал None, и `if crm_ctx:` молча терял запись в
    homework_requests. Тест намеренно НЕ мокает ingest_inbound — мок скрывал
    бы именно этот баг, как и было в остальных тестах этого файла."""
    from app import crm_store
    from app import memory as memory_module

    crm_store.reset()
    memory_module._store = None
    try:
        telegram = AsyncMock()
        telegram.download_file = AsyncMock(return_value=b"fake-ogg-bytes")
        telegram.send_message = AsyncMock(return_value=True)

        message_a = {
            "voice": {"file_id": "voice-a", "mime_type": "audio/ogg"},
            "chat": {"id": 100},
            "message_id": 7,
            "from": {"id": 100, "first_name": "Аня"},
        }
        update_a = {"update_id": 5001, "message": message_a}
        message_b = {
            "voice": {"file_id": "voice-b", "mime_type": "audio/ogg"},
            "chat": {"id": 200},
            "message_id": 7,  # тот же message_id, ДРУГОЙ чат — раньше коллизия
            "from": {"id": 200, "first_name": "Боря"},
        }
        update_b = {"update_id": 5002, "message": message_b}

        with patch("app.speech.transcribe", new=AsyncMock(return_value="Вставь is или are")), \
             patch("app.homework.explain_homework_text", new=AsyncMock(return_value="📘 Правило...")):
            await main_module._handle_telegram_voice(message_a, 100, telegram, update_a)
            await main_module._handle_telegram_voice(message_b, 200, telegram, update_b)

        rows = crm_store.list_homework_requests(limit=10)
        user_ids = {r["user_id"] for r in rows}
        assert user_ids == {"tg:100", "tg:200"}
        assert len(rows) == 2
    finally:
        crm_store.reset()
        memory_module._store = None


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


def _resolve_to_public_ip(monkeypatch, module):
    """Подменяет DNS-резолв в _is_safe_download_url на публичный адрес,
    чтобы тесты не зависели от реальной сети/DNS."""
    monkeypatch.setattr(
        module.socket, "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("93.184.216.34", 0))],
    )


@pytest.mark.asyncio
async def test_max_download_file_streams_from_payload_url(monkeypatch):
    import httpx
    from app import max_client as max_client_module
    from app.max_client import MaxClient

    _resolve_to_public_ip(monkeypatch, max_client_module)
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
    from app import max_client as max_client_module
    from app.max_client import MaxClient

    _resolve_to_public_ip(monkeypatch, max_client_module)
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
async def test_max_download_file_blocks_private_ip(monkeypatch):
    """SSRF-защита: хост, резолвящийся во внутренний адрес (metadata облака,
    localhost и т.п.), не должен скачиваться — запрос даже не уходит."""
    import httpx
    from app import max_client as max_client_module
    from app.max_client import MaxClient

    monkeypatch.setattr(
        max_client_module.socket, "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("169.254.169.254", 0))],
    )
    client = MaxClient()

    called = False

    def fake_stream(self, method, url, **kwargs):
        nonlocal called
        called = True
        return _FakeStreamCtx(_FakeStreamResponse(200, [b"leak"]))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    data = await client.download_file("https://internal.example/steal", 1024)
    assert data is None
    assert called is False


@pytest.mark.asyncio
async def test_max_download_file_blocks_non_https(monkeypatch):
    from app import max_client as max_client_module
    from app.max_client import MaxClient

    _resolve_to_public_ip(monkeypatch, max_client_module)
    client = MaxClient()
    data = await client.download_file("http://example.max.ru/file/1", 1024)
    assert data is None


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
