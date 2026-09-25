# Помощник по ДЗ 2.0 — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Бот подробно разбирает каждый пункт домашнего задания (не давая готового ответа), проверяет решённое задание по фото, принимает голосовые/аудио во всех трёх каналах, а каждое обращение видно в админке и в переписке CRM.

**Architecture:** Новый модуль `app/speech.py` — каскад распознавания речи (OpenAI → OpenAI-запасной → опционально Yandex). `app/homework.py` расширяется: более подробный промпт «разбора» с явным пунктным разбором, новый режим «проверь решение», критик-проверка (`ROLE_CRITIC`) с одной перегенерацией. Каждое обращение пишется в новую таблицу `homework_requests` (в `crm_store.py`) и в общую переписку CRM. Точки входа: `app/main.py` (Telegram/MAX голосовые, фото с подписью «проверь», follow-up фото после разбора), мини-приложение (`app/tgapp`, кнопки прямо в чате вместо отдельного экрана), админка (`app/admin_api.py` + `app/adminapp`).

**Tech Stack:** Python 3.11, FastAPI, `httpx`, существующий `app.llm_gateway` (роли `ROLE_VISION`/`ROLE_REASONING`/`ROLE_CRITIC`), SQLite (`crm_store`), pytest, ванильный JS мини-приложения и админки.

**Spec:** `docs/superpowers/specs/2026-09-24-bot-miniapp-upgrade-design.md`, раздел «Подпроект 2».

## Разведка, зафиксированная для этого плана

- **Принципы владельца (не переопределять):** готового ответа — никогда; педагогу не передаём; разбор — подробный, по каждому пункту задания.
- **Распознавание речи проверено на проде 2026-09-24:** основной провайдер (Cloudflare-воркер, тот же что `LLM_BASE_URL`/`LLM_API_KEY`) `/audio/transcriptions` отвечает 403. Запасной `api.proxyapi.ru` из `LLM_FALLBACKS` (тот же ключ) — 200, модель `gpt-4o-mini-transcribe` с `prompt`-подсказкой распознаёт смешанную рус/англ речь точно («вставь is или are» — без подсказки превращается в «из Ильяр»).
- **`app/llm.py:_build_provider_configs()`** — эталон разбора `LLM_FALLBACKS` (JSON-массив `{"base_url","api_key","model"}`); `app/speech.py` пишет свой аналог (нужны свои STT-модели, не чат-модели).
- **`app/homework.py` (247 строк)** уже даёт единую точку входа `explain_homework_text(task_text)` / `explain_homework_image(image_bytes, content_type, note="")`, системный промпт, зачистку markdown (`_strip_markdown`), расстановку переносов (`_format_tutor_reply`). Это расширяем, не переписываем с нуля.
- **`app.llm_gateway`**: `get_gateway().vision(messages, temperature=...) -> str | None`, `get_gateway().complete(role, messages, ...) -> str | None`, `get_gateway().structured(role, messages, schema, name=..., vault=None, temperature=0.0) -> dict | None` (роли `ROLE_REASONING`/`ROLE_VISION`/`ROLE_CRITIC` уже настроены на проде: `gpt-6-astra`/`gpt-6-astra`/`gpt-5.6-sol`).
- **Образец структурированного критика** — `app/critic.py`: `_SCORE_SCHEMA` (JSON Schema с `required`) + `gateway.structured(ROLE_CRITIC, messages, SCHEMA, name="...")`. Тот же приём годится для критика домашки.
- **`app/main.py`, Telegram:** входящие без текста уходят в `_TELEGRAM_MEDIA_FIELDS = ("voice", "photo", "sticker", "video", "document", "audio", "video_note")`; сейчас на голос/аудио бот отвечает «Пока не умею читать голосовые…» (main.py, внутри `_process_telegram_update`, сразу после блока фото/контакта). Фото с подписью уже разбирается через `_handle_telegram_photo(message, chat_id, telegram)`, вызывается когда `caption_intent in (I.QUESTION, I.HOMEWORK)`. `telegram.download_file(file_id, max_bytes) -> bytes | None` — общий метод для любого типа файла (voice/audio/photo одинаково).
- **`app/main.py`, MAX:** `_process_update()` в ветке `message_created` делает `if not text: return` — **любое сообщение без текста, включая с аудио-вложением, сейчас молча отбрасывается**. Фото через чат MAX вообще не обрабатывается (только через мини-приложение) — это вне рамок задания по спеке (спека просит аудио для всех трёх каналов, фото явно только для TG+мини-апп).
- **Формат вложений MAX** (официальная схема Bot API, идентичная TamTam — тот же вендор): `message.body.attachments` — список объектов `{"type": "audio", "payload": {"url": "...", "token": "..."}}` (аналогично `"type": "image"`, `payload.photo_id`). `payload.url` — прямая ссылка на файл, качается обычным GET. В `max_client.py` сейчас нет `download_file` — добавляем.
- **`_reply_while_alive(client, chat_id, produce)`** (main.py) — общий для TG и MAX индикатор «печатает» + промежуточный статус, переиспользуем для транскрибации и разбора голосовых.
- **`Conversation` (`app/memory.py`)** уже хранит `awaiting_homework: bool = False`, сериализуется в `from_dict`. По аналогии добавляем `homework_check_context: bool = False` — «последний ответ был разбором задания, следующее фото — это уже решение, проверяем, а не объясняем заново».
- **CRM:** `crm_store.add_message(conversation_id, customer_id, channel, direction, sender_type, text, payload=None, ...)` — `payload` уже есть как параметр (сохраняется в `payload_json`), но `crm_ingest.ingest_inbound(...)` его сейчас не принимает и не прокидывает — добавляем параметр `payload: dict | None = None`.
- **Таблица-образец** — `callback_requests` (`crm_store.py`, `id/customer_id/conversation_id/channel/status/created_at/updated_at` + предметные поля). `homework_requests` строим по этому же шаблону.
- **Админка, образец CRUD-раздела** — `callback_requests`: `admin_api.py` — `GET /admin/api/requests`, `GET /admin/api/requests/{id}` (авторизация `_authorize(request, "requests")`, `crm_store.list_callback_requests(status=, kind=, limit=, offset=)`, `crm_store.get_callback_request(id)`); `adminapp/app.js` — `showSection`/`SECTION`-роутер, `nav-item[data-section]`, `loadRequests()`, `requests-list` (~строка 1096-1157). `ROLE_PERMISSIONS` (admin_api.py:41) — словарь роль→права; добавляем `"homework"` в `admin`, `manager`, `support` (не `marketing`).
- **Мини-приложение (`app/tgapp`):** отдельный экран ДЗ — `SHEETS.homework` (build: `buildHomework`, app.js:248, 990-1023), открывается листом (`openSheet`). Убираем, заменяем кнопками прямо в чате. Чат сейчас (`app.js:1059-1137`): `greetInChat()` — приветствие один раз, БЕЗ подгрузки истории; `addMessage(role, text)` — создаёт `.bubble` в `#chat-log`; поллинг исходящих `pollChatMessages`/`startChatPolling` через `GET /api/miniapp/messages?after_id=`; отправка текста — `sendChat()` → `POST /api/miniapp/chat`. Общий `request(path, opts)` уже поддерживает `FormData`-body (используется в `submitHomework`: `request("/api/miniapp/homework", {method:"POST", body: form, timeout: 90000})`).
- **Изображения** нигде в проекте пока не отдаются с диска по HTTP отдельным роутом — добавляем свой (`GET /admin/api/homework/{id}/image`, гейт тем же `_authorize`), не публичный `StaticFiles` (на фото — дети).

## Global Constraints

- Готовый ответ ребёнку не даётся никогда, ни в одном режиме (включая «Проверь решение» — только наводящие подсказки).
- Педагогу задание не передаём ни при каких условиях.
- Комментарии — по-русски, объясняют «почему», в стиле окружающего кода.
- Никаких новых зависимостей без крайней необходимости; для HTTP — существующий `httpx`.
- Тесты — из `bot/`, интерпретатором venv: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest ...` (голого `python` в PATH нет).
- Коммиты — Conventional Commits, `feat(bot): …`/`fix(bot): …`, трейлер `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Ветка `world-v2`; в ней параллельно коммитит владелец над Миром Фоксинбурга (`world-backend/`, `world/`) — эти коммиты `bot/` не трогают, но перед `review-package` для диапазона нужно проверять `git log`/`git diff --name-only <commit>~1..<commit> -- bot/` и при необходимости строить диф с `-- bot/`, как в предыдущих сессиях.
- Владелец разрешил мержить и деплоить без запроса подтверждения. Перед деплоем на сервере — `git status --short`; если там снова обнаружатся чужие незакоммиченные правки — не трогать, остановиться и сообщить.

---

### Task 1: `app/speech.py` — каскад распознавания речи

**Files:**
- Create: `bot/app/speech.py`
- Modify: `bot/app/config.py`
- Test: `bot/tests/test_speech.py`

**Interfaces:**
- Produces:
  - `speech.transcribe(audio_bytes: bytes, filename: str, mime_type: str) -> str | None` — текст или `None`, если ни один провайдер не смог.
  - Настройки: `settings.STT_OPENAI_API_KEY: str = ""`, `settings.STT_OPENAI_BASE_URL: str = ""` (пусто → берём из `LLM_FALLBACKS`, провайдер с `proxyapi` в `base_url`, тот же ключ), `settings.STT_MODELS: str = "gpt-4o-mini-transcribe,gpt-4o-transcribe"` (через запятую, по порядку), `settings.STT_YANDEX_API_KEY: str = ""`, `settings.STT_YANDEX_FOLDER_ID: str = ""`, `settings.STT_PROMPT: str` (см. ниже).

- [ ] **Step 1: Write the failing test** — `bot/tests/test_speech.py`

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_speech.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.speech'`. (Если `pytest.mark.asyncio` не подхватывается — сверить с `tests/test_registration_invite.py`, там уже используется без доп. настройки в этом проекте.)

- [ ] **Step 3: Add settings to `bot/app/config.py`** (рядом с `LLM_*`):

```python
    # --- Распознавание речи для домашки (голосовые/аудио) ---
    # Основной путь — OpenAI напрямую (пусто = не настроено, пропускаем).
    STT_OPENAI_API_KEY: str = ""
    STT_OPENAI_BASE_URL: str = ""
    # Запасной путь при пустых STT_OPENAI_*: первый провайдер из LLM_FALLBACKS,
    # чей base_url содержит "proxyapi" — на проде это единственный провайдер,
    # который реально пропускает /audio/transcriptions (Cloudflare-воркер
    # основного провайдера отвечает 403, проверено 2026-09-24).
    STT_MODELS: str = "gpt-4o-mini-transcribe,gpt-4o-transcribe"
    STT_YANDEX_API_KEY: str = ""
    STT_YANDEX_FOLDER_ID: str = ""
```

- [ ] **Step 4: Write `bot/app/speech.py`**

```python
"""Распознавание речи для домашних заданий, присланных голосом.

Каскад: OpenAI (свой ключ, если задан) → proxyapi-провайдер из LLM_FALLBACKS
(запасной провайдер основного LLM-каскада — единственный, кто на проде
реально пропускает /audio/transcriptions, Cloudflare-воркер основного
провайдера отвечает 403) → опционально Yandex SpeechKit.

Промпт-подсказка обязателен: без контекста «вставь is или are» Whisper
слышит «из Ильяр» — с контекстом распознаёт дословно (проверено на проде
2026-09-24).
"""
from __future__ import annotations

import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

STT_CONTEXT_PROMPT = (
    "Школьник диктует домашнее задание по-русски вперемешку с английскими "
    "словами и фразами. Английские слова и предложения пиши латиницей, "
    "например: is, are, am, my friends happy, Present Simple."
)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _openai_provider() -> tuple[str, str] | None:
    """(base_url, api_key) для основного OpenAI-пути, либо None."""
    if settings.STT_OPENAI_API_KEY and settings.STT_OPENAI_BASE_URL:
        return settings.STT_OPENAI_BASE_URL, settings.STT_OPENAI_API_KEY
    raw = (settings.LLM_FALLBACKS or "").strip()
    if not raw:
        return None
    try:
        fallbacks = json.loads(raw)
    except Exception:
        logger.warning("speech: LLM_FALLBACKS содержит невалидный JSON")
        return None
    if not isinstance(fallbacks, list):
        return None
    for item in fallbacks:
        if not isinstance(item, dict):
            continue
        base_url = str(item.get("base_url", "")).strip()
        api_key = str(item.get("api_key", "")).strip()
        if base_url and api_key and "proxyapi" in base_url.lower():
            return base_url, api_key
    return None


async def _try_openai_models(audio_bytes: bytes, filename: str, mime_type: str) -> str | None:
    provider = _openai_provider()
    if provider is None:
        return None
    base_url, api_key = provider
    models = [m.strip() for m in settings.STT_MODELS.split(",") if m.strip()]
    for model in models:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    base_url.rstrip("/") + "/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (filename, audio_bytes, mime_type)},
                    data={"model": model, "prompt": STT_CONTEXT_PROMPT},
                )
        except Exception:
            logger.warning("speech: сбой запроса к %s (%s)", base_url, model, exc_info=True)
            continue
        if resp.status_code != 200:
            logger.warning("speech: %s (%s) ответил %s", base_url, model, resp.status_code)
            continue
        text = (resp.json() or {}).get("text", "").strip()
        if text:
            return text
    return None


async def _try_yandex(audio_bytes: bytes) -> str | None:
    if not (settings.STT_YANDEX_API_KEY and settings.STT_YANDEX_FOLDER_ID):
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
                params={"folderId": settings.STT_YANDEX_FOLDER_ID, "lang": "ru-RU"},
                headers={"Authorization": f"Api-Key {settings.STT_YANDEX_API_KEY}"},
                content=audio_bytes,
            )
    except Exception:
        logger.warning("speech: сбой запроса к Yandex SpeechKit", exc_info=True)
        return None
    if resp.status_code != 200:
        logger.warning("speech: Yandex SpeechKit ответил %s", resp.status_code)
        return None
    text = (resp.json() or {}).get("result", "").strip()
    return text or None


async def transcribe(audio_bytes: bytes, filename: str, mime_type: str) -> str | None:
    """Текст голосового сообщения. None — ни один провайдер не справился."""
    text = await _try_openai_models(audio_bytes, filename, mime_type)
    if text:
        return text
    return await _try_yandex(audio_bytes)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_speech.py -v`
Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/speech.py bot/app/config.py bot/tests/test_speech.py
git commit -m "feat(bot): каскад распознавания речи для голосовых ДЗ (OpenAI → proxyapi → Yandex)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Подробный разбор по пунктам + критик с перегенерацией

**Files:**
- Modify: `bot/app/homework.py`
- Test: `bot/tests/test_homework_tutor.py` (уже существует — прочитать перед правкой, дополнить в его стиле, не создавать новый файл)

**Interfaces:**
- Consumes: `app.llm_gateway.get_gateway()`, `ROLE_REASONING`, `ROLE_VISION`, `ROLE_CRITIC`
- Produces (публичные имена — переиспользуются в Task 3/4/5, не переименовывать):
  - `homework.explain_homework_text(task_text: str) -> str | None` — сигнатура не меняется, промпт внутри становится подробнее.
  - `homework.explain_homework_image(image_bytes: bytes, content_type: str, note: str = "") -> str | None` — сигнатура не меняется.
  - `homework._critic_check(reply: str, kind: str) -> dict | None` — новая: `{"ok": bool, "issues": list[str]}`, `kind` — `"explain"` или `"check"` (разный набор проверок).
  - `homework._CRITIC_SCHEMA: dict` — JSON-схема для `_critic_check`.

- [ ] **Step 1: Read current file and existing tests first**

Run: `cd /Users/grigory/Dymova-english/bot && cat app/homework.py && cat tests/test_homework_tutor.py`

Понять точный текущий промпт и покрытие тестами, прежде чем править — файл уже содержит `_homework_system_prompt`, `_homework_user_prompt`, `_homework_text_user_prompt`, `_FORMAT_TEMPLATE`, `_strip_markdown`, `_format_tutor_reply`, `_finalize_tutor_reply`. Все эти приватные помощники остаются, меняется только текст промптов и добавляется критик-проверка внутри `explain_homework_text`/`explain_homework_image`.

- [ ] **Step 2: Write the failing test** — дополнить `bot/tests/test_homework_tutor.py`:

```python
from unittest.mock import AsyncMock, patch

from app import homework


def test_homework_system_prompt_requires_per_item_breakdown():
    prompt = homework._homework_system_prompt()
    # Подробный разбор по каждому пункту — обязательное требование владельца,
    # проверяем, что промпт явно его формулирует, а не полагается на общую
    # структуру «правило → пример → план».
    assert "каждый пункт" in prompt.lower() or "каждого пункта" in prompt.lower()


_CRITIC_OK = {"ok": True, "issues": []}
_CRITIC_BAD = {"ok": False, "issues": ["в примере дан прямой ответ по заданию ученика"]}


@pytest.mark.asyncio
async def test_explain_homework_text_passes_through_when_critic_ok():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.complete = AsyncMock(return_value="📘 Правило\nТекст\n\n❓ Попробуй?")
        gw.structured = AsyncMock(return_value=_CRITIC_OK)
        result = await homework.explain_homework_text("I ... nine")
    assert result is not None
    assert gw.complete.await_count == 1  # перегенерации не было


@pytest.mark.asyncio
async def test_explain_homework_text_regenerates_once_when_critic_flags_issue():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.complete = AsyncMock(side_effect=[
            "📘 Правило\nI am nine — готовый ответ дан\n\n❓ Попробуй?",
            "📘 Правило\nТекст без готового ответа\n\n❓ Попробуй?",
        ])
        gw.structured = AsyncMock(side_effect=[_CRITIC_BAD, _CRITIC_OK])
        result = await homework.explain_homework_text("I ... nine")
    assert gw.complete.await_count == 2  # одна перегенерация
    assert "готовый ответ дан" not in result


@pytest.mark.asyncio
async def test_explain_homework_text_returns_first_reply_if_regeneration_also_flagged():
    """Критик не блокирует ответ даже после неудачной перегенерации — молчание
    хуже неидеального разбора (тот же принцип, что у общего критика чата)."""
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.complete = AsyncMock(side_effect=["первый вариант", "второй вариант"])
        gw.structured = AsyncMock(side_effect=[_CRITIC_BAD, _CRITIC_BAD])
        result = await homework.explain_homework_text("задание")
    assert result is not None
    assert gw.complete.await_count == 2


@pytest.mark.asyncio
async def test_explain_homework_text_works_without_critic_available():
    """gateway.structured вернул None (критик недоступен) — ответ всё равно
    уходит, критик необязателен, как в app/critic.py."""
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.complete = AsyncMock(return_value="разбор")
        gw.structured = AsyncMock(return_value=None)
        result = await homework.explain_homework_text("задание")
    assert result == homework._finalize_tutor_reply("разбор")
    assert gw.complete.await_count == 1


@pytest.mark.asyncio
async def test_critic_check_returns_structured_verdict():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.structured = AsyncMock(return_value=_CRITIC_BAD)
        verdict = await homework._critic_check("текст разбора", kind="explain")
    assert verdict == _CRITIC_BAD
    gw.structured.assert_awaited_once()
    call = gw.structured.await_args
    assert call.args[0] == homework.ROLE_CRITIC if hasattr(homework, "ROLE_CRITIC") else True
```

Добавить `import pytest` в начало файла, если его там ещё нет (проверить перед вставкой).

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_homework_tutor.py -v`
Expected: FAIL — `AttributeError: module 'app.homework' has no attribute '_critic_check'` (и первый тест на текст промпта может упасть тоже — это ожидаемо, промпт ещё не переписан).

- [ ] **Step 4: Rewrite the system prompt in `bot/app/homework.py`** — заменить тело `_homework_system_prompt()`:

```python
def _homework_system_prompt() -> str:
    return (
        "Ты — Фокси, педагог-наставник, который профессионально помогает "
        "школьнику с домашним заданием (английский язык и другие школьные "
        "предметы). Главное правило: не давай готовых ответов и не решай "
        "задание за него — учи выполнять его самостоятельно, ни один пункт "
        "не оставляй без разбора.\n"
        "Структура каждого ответа:\n"
        "1) Назови тему и правило, которое проверяет задание, и объясни его "
        "простыми словами.\n"
        "2) Разбери КАЖДЫЙ пункт задания по отдельности (если пункт один — "
        "один разбор): какое правило применить именно здесь, на что "
        "обратить внимание в этом конкретном пункте, какой первый шаг "
        "сделать. Готового ответа для пункта не давай — только куда "
        "смотреть и с чего начать.\n"
        "3) Придумай ОДНО похожее задание (другие слова и числа, НЕ из "
        "задания ученика) и реши его пошагово целиком, комментируя, почему "
        "делается именно так. Один пример — не несколько: длинная череда "
        "примеров утомляет и не помогает.\n"
        "4) Дай план из 2–4 шагов, как ученику решить СВОЁ задание.\n"
        "5) Заверши вопросом: предложи ученику попробовать и написать, что "
        "получилось.\n"
        "Если фото нечитаемо целиком или частично (размыто, обрезано, не "
        "видно часть строк) — НЕ отказывайся и не выдумывай, что там "
        "написано: честно скажи, какую часть не видно, и попроси переснять "
        "именно её или надиктовать голосовым сообщением.\n"
        "Язык примера: если задание по английскому — пример и его решение "
        "приводи на английском (It will be rainy in London tomorrow.), а "
        "объяснения шагов — по-русски. По остальным предметам пример — на "
        "русском.\n"
        "Тон: добрый и поддерживающий, на «ты», язык понятный ребёнку "
        "7–15 лет. Отвечай по-русски.\n"
        "Оформление ответа (важно — читает ребёнок в мессенджере):\n"
        "- разбивай ответ на короткие абзацы по 1–3 предложения, между "
        "частями — пустая строка;\n"
        "- каждую часть начинай с эмодзи-заголовка: 📘 правило, 🔎 разбор "
        "пункта (по одному на каждый пункт задания, нумеруй: 🔎 Пункт 1, "
        "🔎 Пункт 2…), ✏️ пример с решением, ✅ план для твоего задания, "
        "❓ вопрос в конце;\n"
        "- шаги нумеруй просто: 1) 2) 3), списки — через дефис;\n"
        "- НИКАКОГО markdown: без **, ##, _, `, без заголовков #, без "
        "таблиц. Только чистый текст, абзацы и эмодзи."
    )
```

(Формат-шаблон `_FORMAT_TEMPLATE` и функции `_homework_user_prompt`/`_homework_text_user_prompt` не трогать в этом шаге — они дают модели образец для блока «✏️ Похожий пример», который не изменился; пункт «🔎 разбор» модель формирует по системному промпту.)

- [ ] **Step 5: Add the critic and wire it into both explain functions** — в `bot/app/homework.py`:

```python
from app.llm_gateway import ROLE_CRITIC, ROLE_REASONING, get_gateway
```

(заменить текущий `from app.llm_gateway import ROLE_REASONING, get_gateway` на строку выше).

Добавить перед `async def explain_homework_text`:

```python
_CRITIC_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["ok", "issues"],
}

_CRITIC_PROMPT = {
    "explain": (
        "Ты — придирчивый методист языковой школы. Проверь разбор "
        "домашнего задания для ученика. Ответ ok=false, если хотя бы одно "
        "верно:\n"
        "- в разборе (в правиле, в пункте, в плане) прямо назван готовый "
        "ответ ИЛИ решение задания ученика — не придуманного примера, а "
        "именно его собственного;\n"
        "- есть фактическая ошибка в правиле или примере;\n"
        "- разобран не каждый пункт задания, часть пропущена;\n"
        "- придуманный пример совпадает с одним из пунктов задания ученика "
        "(должен быть ДРУГИМ, не из задания).\n"
        "В issues — короткий список конкретных проблем (по-русски), пустой "
        "список, если ok=true."
    ),
    "check": (
        "Ты — придирчивый методист языковой школы. Проверь ответ на "
        "проверку решённого школьником задания. Ответ ok=false, если хотя "
        "бы одно верно:\n"
        "- в ответе прямо назван правильный вариант вместо ученика — по "
        "любому пункту, где отмечена ошибка;\n"
        "- есть фактическая ошибка в оценке (верно/неверно перепутаны);\n"
        "- проверен не каждый пункт присланного решения.\n"
        "В issues — короткий список конкретных проблем (по-русски), пустой "
        "список, если ok=true."
    ),
}


async def _critic_check(reply: str, kind: str) -> dict | None:
    """Проверка ответа тьютора перед отправкой. None — критик недоступен,
    вызывающий код должен работать и без него (как app/critic.score)."""
    gateway = get_gateway()
    if not gateway.enabled:
        return None
    messages = [
        {"role": "system", "content": _CRITIC_PROMPT[kind]},
        {"role": "user", "content": f"ОТВЕТ ТЬЮТОРА:\n{reply}"},
    ]
    try:
        return await gateway.structured(
            ROLE_CRITIC, messages, _CRITIC_SCHEMA, name="homework_critic"
        )
    except Exception:
        return None


async def _with_critic_pass(
    produce, kind: str, *, regen_note_field: str = "note"
) -> str | None:
    """Один прогон + критик + при замечаниях одна перегенерация с этими
    замечаниями в промпте. Критик никогда не блокирует ответ: если и вторая
    попытка не понравилась критику, отправляем её как есть — молчание хуже
    неидеального разбора (тот же принцип, что у app/critic.py)."""
    reply = await produce(extra_note="")
    if not reply:
        return None
    verdict = await _critic_check(_strip_markdown(reply), kind)
    if verdict is None or verdict.get("ok", True):
        return _finalize_tutor_reply(reply)
    issues = "; ".join(verdict.get("issues") or [])
    note = f"Замечания методиста, обязательно исправь: {issues}"
    retry = await produce(extra_note=note)
    return _finalize_tutor_reply(retry or reply)
```

Заменить тело `explain_homework_text`:

```python
async def explain_homework_text(task_text: str) -> str | None:
    """Разбор задания, присланного текстом. None — модель не смогла помочь."""

    async def produce(extra_note: str) -> str | None:
        note = f" Дополнительная заметка: {extra_note}." if extra_note else ""
        messages = [
            {"role": "system", "content": _homework_system_prompt()},
            {"role": "user", "content": _homework_text_user_prompt(task_text) + note},
        ]
        return await get_gateway().complete(
            ROLE_REASONING, messages, temperature=0.3, max_tokens=1500
        )

    return await _with_critic_pass(produce, kind="explain")
```

Заменить тело `explain_homework_image`:

```python
async def explain_homework_image(
    image_bytes: bytes, content_type: str, note: str = ""
) -> str | None:
    """Разбор фотографии задания. None — модель не смогла помочь."""
    encoded = base64.b64encode(image_bytes).decode("ascii")

    async def produce(extra_note: str) -> str | None:
        combined_note = " ".join(n for n in (note, extra_note) if n)
        messages = [
            {"role": "system", "content": _homework_system_prompt()},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _homework_user_prompt(combined_note)},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                    },
                ],
            },
        ]
        return await get_gateway().vision(messages, temperature=0.2, max_tokens=1500)

    return await _with_critic_pass(produce, kind="explain")
```

(`max_tokens` поднят с 1200 до 1500 — подробный разбор по пунктам длиннее прежнего цельного ответа.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_homework_tutor.py tests/test_homework.py tests/test_homework_routing_report.py -v`
Expected: все PASS. (Существующие тесты на `_strip_markdown`/`_format_tutor_reply`/маршрутизацию не должны сломаться — они не завязаны на конкретный текст промпта.)

- [ ] **Step 7: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/homework.py bot/tests/test_homework_tutor.py
git commit -m "feat(bot): подробный разбор ДЗ по каждому пункту + критик с одной перегенерацией

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Режим «Проверь моё решение»

**Files:**
- Modify: `bot/app/homework.py`
- Test: `bot/tests/test_homework_tutor.py` (дополнить)

**Interfaces:**
- Consumes: `homework._with_critic_pass`, `homework._critic_check`, `homework._finalize_tutor_reply` (Task 2)
- Produces: `homework.check_homework_image(image_bytes: bytes, content_type: str, note: str = "") -> str | None`

- [ ] **Step 1: Write the failing test** — дополнить `bot/tests/test_homework_tutor.py`:

```python
def test_check_homework_system_prompt_forbids_giving_correct_answer():
    prompt = homework._check_homework_system_prompt()
    assert "не называй" in prompt.lower() or "не давай правильный" in prompt.lower()


@pytest.mark.asyncio
async def test_check_homework_image_returns_finalized_reply():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.vision = AsyncMock(return_value="🔎 Пункт 1\nВерно!\n\n🔎 Пункт 2\nПосмотри на подлежащее — оно во множественном числе.")
        gw.structured = AsyncMock(return_value={"ok": True, "issues": []})
        result = await homework.check_homework_image(b"fake-image-bytes", "image/jpeg")
    assert result is not None
    assert "Пункт 1" in result
    gw.vision.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_homework_image_regenerates_when_critic_flags_leaked_answer():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.vision = AsyncMock(side_effect=[
            "Правильный вариант — are, ты написал is",
            "Посмотри на подлежащее — множественное число, какой глагол ему нужен?",
        ])
        gw.structured = AsyncMock(side_effect=[
            {"ok": False, "issues": ["назван правильный ответ вместо ученика"]},
            {"ok": True, "issues": []},
        ])
        result = await homework.check_homework_image(b"bytes", "image/jpeg")
    assert gw.vision.await_count == 2
    assert "are" not in result or "Правильный вариант" not in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_homework_tutor.py -v`
Expected: FAIL — `AttributeError: module 'app.homework' has no attribute 'check_homework_image'`

- [ ] **Step 3: Add to `bot/app/homework.py`** — после `explain_homework_image`:

```python
def _check_homework_system_prompt() -> str:
    return (
        "Ты — Фокси, педагог-наставник. Ученик прислал фото УЖЕ решённого "
        "им домашнего задания — твоя задача проверить, а не решить заново. "
        "Главное правило: НЕ называй правильный ответ или правильный "
        "вариант ни по одному пункту, даже если в пункте есть ошибка.\n"
        "Разбери фото по пунктам (если пункт один — один разбор):\n"
        "- пункт решён верно → напиши «Верно!» и коротко похвали;\n"
        "- пункт решён с ошибкой → напиши, что здесь есть ошибка, и дай "
        "наводящую подсказку, на что обратить внимание (например: «Посмотри "
        "на подлежащее — оно во множественном числе, какой глагол ему "
        "нужен?»), но НЕ говори, какой ответ правильный;\n"
        "- если не можешь разобрать почерк или фото частично нечитаемо — "
        "честно скажи, какую часть не видно, и попроси переснять именно "
        "её или продиктовать голосом, не выдумывай, что там написано.\n"
        "Оформление: начинай каждый пункт с 🔎 Пункт N, короткие абзацы, "
        "между пунктами пустая строка, в конце один вопрос-подбадривание "
        "❓. НИКАКОГО markdown: без **, ##, `, без таблиц. По-русски, на "
        "«ты», тон доброжелательный, язык понятный ребёнку 7–15 лет."
    )


def _check_homework_user_prompt(note: str) -> str:
    extra = f" Дополнительная заметка: {note}." if note else ""
    return (
        "На фото — уже решённое учеником домашнее задание. Проверь каждый "
        "пункт: верно или есть ошибка. НЕ называй правильный ответ ни по "
        "одному пункту с ошибкой — только наводящая подсказка, куда "
        "смотреть."
        f"{extra}"
    )


async def check_homework_image(
    image_bytes: bytes, content_type: str, note: str = ""
) -> str | None:
    """Проверка решённого задания по фото. Правильный ответ не называется
    ни при каких обстоятельствах. None — модель не смогла помочь."""
    encoded = base64.b64encode(image_bytes).decode("ascii")

    async def produce(extra_note: str) -> str | None:
        combined_note = " ".join(n for n in (note, extra_note) if n)
        messages = [
            {"role": "system", "content": _check_homework_system_prompt()},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _check_homework_user_prompt(combined_note)},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                    },
                ],
            },
        ]
        return await get_gateway().vision(messages, temperature=0.2, max_tokens=1200)

    return await _with_critic_pass(produce, kind="check")
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_homework_tutor.py -v`
Expected: все PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/homework.py bot/tests/test_homework_tutor.py
git commit -m "feat(bot): режим «Проверь моё решение» — по фото, без готового ответа

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Хранение — `homework_requests` + CRM

**Files:**
- Modify: `bot/app/crm_store.py`
- Modify: `bot/app/crm_ingest.py`
- Test: `bot/tests/test_homework_storage.py`

**Interfaces:**
- Consumes: `crm_store._tx`, `crm_store._now`, `crm_store.get_conn`, `crm_store.get_or_create_conversation`, `crm_store.upsert_customer_for_identity` (уже есть)
- Produces:
  - `crm_store.record_homework_request(*, platform: str, user_id: str, customer_id: int | None = None, conversation_id: int | None, channel: str, mode: str, input_type: str, image_path: str = "", audio_transcript: str = "", task_text: str = "", reply: str = "", critic_notes: str = "") -> int` — возвращает id новой записи. `mode` — `"explain" | "check"`. `input_type` — `"text" | "image" | "voice"`. `customer_id` — из `crm_ctx["customer_id"]` (возвращает `crm_ingest.ingest_inbound`), чтобы в админке список заявок показывал имя клиента, а не голый `user_id`.
  - `crm_store.list_homework_requests(mode: str | None = None, date_from: str | None = None, date_to: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]` — каждая запись дополнена `customer_name`/`customer_phone` (LEFT JOIN customers, как у `list_callback_requests`).
  - `crm_store.get_homework_request(request_id: int) -> dict | None` — тот же LEFT JOIN.
  - `crm_ingest.ingest_inbound(..., payload: dict | None = None)` — новый необязательный параметр, прокидывается в `crm_store.add_message(..., payload=payload)`.
  - `homework.save_homework_image(image_bytes: bytes, ext: str = "jpg") -> str` (в `app/homework.py`) — сохраняет файл в `data/homework/`, возвращает относительный путь вида `homework/<uuid>.jpg`.

- [ ] **Step 1: Write the failing test** — `bot/tests/test_homework_storage.py`

```python
"""Хранилище обращений за помощью с ДЗ: своя таблица + общая переписка CRM."""
import pytest

from app import crm_store
from app.homework import save_homework_image


@pytest.fixture(autouse=True)
def fresh_db():
    crm_store.reset()
    yield
    crm_store.reset()


def test_record_and_get_homework_request():
    req_id = crm_store.record_homework_request(
        platform="telegram", user_id="tg:1", conversation_id=None,
        channel="telegram", mode="explain", input_type="text",
        task_text="I ... nine", reply="📘 Правило...",
    )
    item = crm_store.get_homework_request(req_id)
    assert item["mode"] == "explain"
    assert item["input_type"] == "text"
    assert item["task_text"] == "I ... nine"
    assert item["created_at"]


def test_homework_request_shows_customer_name_via_join():
    customer_id = crm_store.upsert_customer_for_identity("telegram", "tg:9", name="Анна Петрова")
    req_id = crm_store.record_homework_request(
        platform="telegram", user_id="tg:9", customer_id=customer_id, conversation_id=None,
        channel="telegram", mode="explain", input_type="text", task_text="a", reply="r",
    )
    item = crm_store.get_homework_request(req_id)
    assert item["customer_name"] == "Анна Петрова"
    assert crm_store.list_homework_requests()[0]["customer_name"] == "Анна Петрова"


def test_list_homework_requests_filters_by_mode():
    crm_store.record_homework_request(
        platform="telegram", user_id="tg:1", conversation_id=None,
        channel="telegram", mode="explain", input_type="text", task_text="a", reply="r",
    )
    crm_store.record_homework_request(
        platform="max", user_id="42", conversation_id=None,
        channel="max", mode="check", input_type="image", image_path="homework/x.jpg", reply="r2",
    )
    only_check = crm_store.list_homework_requests(mode="check")
    assert len(only_check) == 1
    assert only_check[0]["mode"] == "check"
    assert len(crm_store.list_homework_requests()) == 2


def test_list_homework_requests_filters_by_date_range():
    crm_store.record_homework_request(
        platform="telegram", user_id="tg:1", conversation_id=None,
        channel="telegram", mode="explain", input_type="text", task_text="a", reply="r",
    )
    future_only = crm_store.list_homework_requests(date_from="2099-01-01")
    assert future_only == []


def test_save_homework_image_writes_file_under_data_homework(tmp_path, monkeypatch):
    monkeypatch.setattr("app.homework.HOMEWORK_IMAGE_DIR", str(tmp_path / "homework"))
    rel_path = save_homework_image(b"fake-jpeg-bytes", ext="jpg")
    assert rel_path.startswith("homework/") and rel_path.endswith(".jpg")
    full = tmp_path / rel_path.split("/", 1)[1]
    assert full.exists()
    assert full.read_bytes() == b"fake-jpeg-bytes"


def test_ingest_inbound_stores_payload():
    ctx = crm_store  # noqa: F841 — просто проверяем сигнатуру ниже
    from app import crm_ingest

    result = crm_ingest.ingest_inbound(
        "telegram", "tg:1", "[фото] задание",
        external_event_id="evt-1",
        payload={"image_path": "homework/abc.jpg"},
    )
    assert result is not None
    messages = crm_store.get_messages(result["conversation_id"])
    assert messages[0]["payload_json"] and "abc.jpg" in messages[0]["payload_json"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_homework_storage.py -v`
Expected: FAIL — `AttributeError: module 'app.crm_store' has no attribute 'record_homework_request'`

- [ ] **Step 3: Add table to `bot/app/crm_store.py`** — в `_SCHEMA`, перед `CREATE TABLE IF NOT EXISTS crm_meta`:

```sql
CREATE TABLE IF NOT EXISTS homework_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    user_id TEXT NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    conversation_id INTEGER REFERENCES crm_conversations(id),
    channel TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT 'explain',
    input_type TEXT NOT NULL DEFAULT 'text',
    image_path TEXT NOT NULL DEFAULT '',
    audio_transcript TEXT NOT NULL DEFAULT '',
    task_text TEXT NOT NULL DEFAULT '',
    reply TEXT NOT NULL DEFAULT '',
    critic_notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_homework_requests_created ON homework_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_homework_requests_mode ON homework_requests(mode, created_at);
```

- [ ] **Step 4: Add functions to `bot/app/crm_store.py`** — рядом с `list_callback_requests`/`get_callback_request`:

```python
def record_homework_request(
    *, platform: str, user_id: str, conversation_id: int | None, channel: str,
    mode: str, input_type: str, customer_id: int | None = None, image_path: str = "",
    audio_transcript: str = "", task_text: str = "", reply: str = "",
    critic_notes: str = "",
) -> int:
    conn = get_conn()
    now = _now()
    with _tx(conn):
        cur = conn.execute(
            "INSERT INTO homework_requests (platform, user_id, customer_id, conversation_id,"
            " channel, mode, input_type, image_path, audio_transcript, task_text, reply,"
            " critic_notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (platform, user_id, customer_id, conversation_id, channel, mode, input_type,
             image_path, audio_transcript, task_text[:4000], reply[:8000],
             critic_notes[:2000], now),
        )
    return int(cur.lastrowid)


_HOMEWORK_SELECT = (
    "SELECT h.*, c.name AS customer_name, c.phone AS customer_phone"
    " FROM homework_requests h LEFT JOIN customers c ON c.id = h.customer_id"
)


def get_homework_request(request_id: int) -> dict | None:
    row = get_conn().execute(
        _HOMEWORK_SELECT + " WHERE h.id = ?", (request_id,)
    ).fetchone()
    return dict(row) if row else None


def list_homework_requests(
    mode: str | None = None, date_from: str | None = None, date_to: str | None = None,
    limit: int = 50, offset: int = 0,
) -> list[dict]:
    sql = _HOMEWORK_SELECT
    where: list[str] = []
    params: list = []
    if mode:
        where.append("h.mode = ?")
        params.append(mode)
    if date_from:
        where.append("h.created_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("h.created_at <= ?")
        params.append(date_to)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY h.id DESC LIMIT ? OFFSET ?"
    params.extend([max(1, min(int(limit), 200)), max(0, int(offset))])
    return _rows(get_conn().execute(sql, params))
```

(Сверить сигнатуру `_rows` перед вставкой — в других функциях этого файла она принимает готовый cursor, например `_rows(conn.execute(sql, params))`.)

- [ ] **Step 5: Extend `ingest_inbound` in `bot/app/crm_ingest.py`** — добавить параметр и прокинуть его:

```python
def ingest_inbound(
    channel: str,
    external_user_id: str,
    text: str,
    external_event_id: str | None = None,
    external_message_id: str | None = None,
    name: str = "",
    first_name: str = "",
    last_name: str = "",
    username: str = "",
    phone: str = "",
    payload: dict | None = None,
) -> dict | None:
```

И в теле, в вызове `crm_store.add_message(...)`, добавить `payload=payload` последним именованным аргументом.

- [ ] **Step 6: Add image storage to `bot/app/homework.py`** — в начало файла:

```python
import uuid
from pathlib import Path

HOMEWORK_IMAGE_DIR = "data/homework"


def save_homework_image(image_bytes: bytes, ext: str = "jpg") -> str:
    """Сохраняет фото задания на диск. Возвращает относительный путь вида
    "homework/<uuid>.<ext>" — так же, как ссылки на другие данные в /app/data."""
    directory = Path(HOMEWORK_IMAGE_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    (directory / filename).write_bytes(image_bytes)
    return f"homework/{filename}"
```

(Импорты `uuid`, `Path` — если `base64`/`re` уже импортированы в файле, добавить новые рядом, не дублировать.)

- [ ] **Step 7: Run tests**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_homework_storage.py tests/test_crm_ingest.py tests/test_crm_store.py -v`
Expected: все PASS.

- [ ] **Step 8: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/crm_store.py bot/app/crm_ingest.py bot/app/homework.py bot/tests/test_homework_storage.py
git commit -m "feat(bot): таблица homework_requests, хранение фото на диске, payload в CRM-сообщениях

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Голосовые и «проверь» в Telegram и MAX

**Files:**
- Modify: `bot/app/main.py`
- Modify: `bot/app/memory.py`
- Modify: `bot/app/max_client.py`
- Test: `bot/tests/test_homework_voice_routing.py`

**Interfaces:**
- Consumes: `app.speech.transcribe` (Task 1), `homework.explain_homework_text/image`, `homework.check_homework_image`, `homework.save_homework_image` (Task 2-4), `crm_store.record_homework_request`, `crm_ingest.ingest_inbound(..., payload=...)` (Task 4)
- Produces:
  - `Conversation.homework_check_context: bool = False` (в `app/memory.py`, сериализуется как `awaiting_homework`)
  - `max_client.MaxClient.download_file(url: str, max_bytes: int) -> bytes | None` — новый метод, качает вложение MAX по прямой ссылке.
  - `main._looks_like_check_request(text: str) -> bool` — распознаёт «проверь»/«провер» в подписи к фото.

- [ ] **Step 1: Read the exact current code around the insertion points before editing**

Run: `cd /Users/grigory/Dymova-english/bot && grep -n "Пока не умею читать голосовые\|_TELEGRAM_MEDIA_FIELDS\|if not text:\s*$" app/main.py`

Строки могли сдвинуться от прошлых сессий — найти актуальные номера перед правкой.

- [ ] **Step 2: Write the failing test** — `bot/tests/test_homework_voice_routing.py`

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_homework_voice_routing.py -v`
Expected: FAIL — `AttributeError: module 'app.main' has no attribute '_looks_like_check_request'`

- [ ] **Step 4: Add `homework_check_context` to `bot/app/memory.py`** — рядом с `awaiting_homework: bool = False`:

```python
    # Последний ответ был разбором задания — если следующим придёт фото,
    # это уже решение ученика, его нужно проверять, а не объяснять заново.
    homework_check_context: bool = False
```

И в `from_dict`, рядом со строкой `awaiting_homework=d.get("awaiting_homework", False),`:

```python
        homework_check_context=d.get("homework_check_context", False),
```

- [ ] **Step 5: Add `download_file` to `bot/app/max_client.py`** — по аналогии с `telegram_client.download_file`:

```python
    async def download_file(self, url: str, max_bytes: int) -> bytes | None:
        """Скачивает вложение MAX по прямой ссылке из payload.url. None — не
        удалось или файл больше лимита."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream("GET", url) as response:
                    if response.status_code != 200:
                        logger.warning("max: скачивание вложения ответило %s", response.status_code)
                        return None
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > max_bytes:
                            logger.warning("max: вложение больше лимита %s байт", max_bytes)
                            return None
                    return bytes(chunks)
        except Exception:
            logger.warning("max: сбой скачивания вложения", exc_info=True)
            return None
```

(Проверить, что `httpx` уже импортирован в файле — если нет, добавить `import httpx` в шапку рядом с существующими импортами.)

- [ ] **Step 6: Add helpers and handlers to `bot/app/main.py`**

Импорты — добавить рядом с `from app import homework`:

```python
from app import speech
```

Константа рядом с `MAX_HOMEWORK_IMAGE_BYTES`:

```python
# Голосовое до 5 минут — примерно 20 МБ в ogg/opus с запасом.
MAX_HOMEWORK_AUDIO_BYTES = 20 * 1024 * 1024

_CHECK_STEM_RE = re.compile(r"\bпровер", re.IGNORECASE)


def _looks_like_check_request(text: str) -> bool:
    """«Проверь», «проверка», «провери» — просьба проверить решение, а не
    объяснить задание заново."""
    return bool(_CHECK_STEM_RE.search(text or ""))
```

(Проверить, что `re` уже импортирован в main.py — почти наверняка да, используется повсеместно.)

Новый обработчик голосовых Telegram — добавить рядом с `_handle_telegram_photo`:

```python
async def _handle_telegram_voice(message: dict, chat_id, telegram) -> None:
    """Голосовое/аудио с заданием: скачиваем, распознаём, разбираем тем же
    тьютором, что и текст."""
    media = message.get("voice") or message.get("audio") or {}
    file_id = media.get("file_id")
    if not file_id:
        return
    mime_type = str(media.get("mime_type") or "audio/ogg")
    sender = message.get("from") or {}
    voice_message_id = str(message.get("message_id") or "") or None
    crm_ctx = crm_ingest.ingest_inbound(
        TELEGRAM_PLATFORM, f"tg:{chat_id}", "[голосовое]",
        external_event_id=voice_message_id,
        external_message_id=voice_message_id,
        first_name=str(sender.get("first_name") or ""),
        last_name=str(sender.get("last_name") or ""),
        username=str(sender.get("username") or ""),
    )
    download = getattr(telegram, "download_file", None)
    if not callable(download):
        await telegram.send_message(
            chat_id, "Пока не могу скачать голосовое здесь. Напишите, пожалуйста, текстом."
        )
        return
    audio = await download(file_id, MAX_HOMEWORK_AUDIO_BYTES)
    if not audio:
        await telegram.send_message(
            chat_id, "Не получилось скачать голосовое. Попробуйте ещё раз или напишите текстом."
        )
        return
    text = await _reply_while_alive(
        telegram, chat_id, lambda: speech.transcribe(audio, "voice.ogg", mime_type)
    )
    if not text:
        await telegram.send_message(
            chat_id,
            "Не расслышала голосовое 🙏 Попробуйте ещё раз при тишине — или "
            "напишите задание текстом.",
        )
        return
    await telegram.send_message(chat_id, f"Услышал: «{text}»")
    explanation = await _reply_while_alive(
        telegram, chat_id, lambda: homework.explain_homework_text(text)
    )
    explanation = explanation or HOMEWORK_TEXT_FALLBACK
    ok = await telegram.send_message(chat_id, explanation)
    crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL, ok=bool(ok))
    if crm_ctx:
        crm_store.record_homework_request(
            platform=TELEGRAM_PLATFORM, user_id=f"tg:{chat_id}",
            customer_id=crm_ctx.get("customer_id"),
            conversation_id=crm_ctx.get("conversation_id"), channel=TELEGRAM_PLATFORM,
            mode="explain", input_type="voice", audio_transcript=text,
            task_text=text, reply=explanation,
        )
    conv = get_store().get(f"tg:{chat_id}", platform=TELEGRAM_PLATFORM)
    conv.homework_check_context = True
    get_store().save(conv)
```

Вызов из диспетчера — в `_process_telegram_update`, добавить блок сразу после `if message.get("photo"): ...` и до ветки контакта (см. Step 1 — реальные номера строк):

```python
        if message.get("voice") or message.get("audio"):
            await _handle_telegram_voice(message, chat_id, telegram)
            return
```

Обновить блок фото — распознавание «проверь» и контекста «после разбора»: заменить условие вызова `_handle_telegram_photo` на:

```python
        if message.get("photo"):
            caption = str(message.get("caption") or "").strip()
            caption_intent = I.detect_intent(caption) if caption else I.HOMEWORK
            conv_for_photo = get_store().get(f"tg:{chat_id}", platform=TELEGRAM_PLATFORM)
            wants_check = _looks_like_check_request(caption) or (
                not caption and conv_for_photo.homework_check_context
            )
            if caption_intent in (I.QUESTION, I.HOMEWORK) or wants_check:
                await _handle_telegram_photo(message, chat_id, telegram, check_mode=wants_check)
                return
```

Обновить сигнатуру и тело `_handle_telegram_photo`: добавить параметр `check_mode: bool = False`, заменить вызов `explain_homework_image` на условный выбор функции и записать `homework_requests` + сбросить/выставить `homework_check_context`:

```python
async def _handle_telegram_photo(message: dict, chat_id, telegram, check_mode: bool = False) -> None:
    """Фото задания из чата: разбор или проверка решения — тем же vision,
    что и в кабинете."""
    sizes = message.get("photo") or []
    if not isinstance(sizes, list) or not sizes:
        return
    largest = max(sizes, key=lambda item: item.get("file_size") or item.get("width") or 0)
    file_id = largest.get("file_id")
    if not file_id:
        return

    note = str(message.get("caption") or "").strip()
    photo_message_id = str(message.get("message_id") or "") or None
    sender = message.get("from") or {}
    user_id = f"tg:{chat_id}"
    download = getattr(telegram, "download_file", None)
    if not callable(download):
        await telegram.send_message(
            chat_id,
            "Вижу фото 📸 Опишите, пожалуйста, текстом, что за задание — "
            "так смогу помочь точнее.",
        )
        return
    image = await download(file_id, MAX_HOMEWORK_IMAGE_BYTES)
    if not image:
        await telegram.send_message(
            chat_id,
            "Не получилось открыть это фото. Пришлите, пожалуйста, снимок "
            "поменьше — или опишите задание текстом.",
        )
        return
    image_path = homework.save_homework_image(image, ext="jpg")
    crm_ctx = crm_ingest.ingest_inbound(
        TELEGRAM_PLATFORM, user_id, f"[фото] {note}".strip(),
        external_event_id=photo_message_id,
        external_message_id=photo_message_id,
        first_name=str(sender.get("first_name") or ""),
        last_name=str(sender.get("last_name") or ""),
        username=str(sender.get("username") or ""),
        payload={"image_path": image_path},
    )

    if check_mode:
        explanation = await _reply_while_alive(
            telegram, chat_id, lambda: homework.check_homework_image(image, "image/jpeg", note)
        )
        mode = "check"
    else:
        explanation = await _reply_while_alive(
            telegram, chat_id, lambda: homework.explain_homework_image(image, "image/jpeg", note)
        )
        mode = "explain"

    if not explanation:
        hint = (
            "Не смог разобрать фото. Напишите, пожалуйста, текстом, что "
            "именно нужно сделать, или надиктуйте голосовым — помогу "
            "разобраться."
            if not check_mode else
            "Не смог разобрать фото решения. Пришлите, пожалуйста, более "
            "чёткий снимок — так смогу проверить."
        )
        await telegram.send_message(chat_id, hint)
        return
    ok = await telegram.send_message(chat_id, explanation)
    crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL, ok=bool(ok))
    if crm_ctx:
        crm_store.record_homework_request(
            platform=TELEGRAM_PLATFORM, user_id=user_id,
            customer_id=crm_ctx.get("customer_id"),
            conversation_id=crm_ctx.get("conversation_id"), channel=TELEGRAM_PLATFORM,
            mode=mode, input_type="image", image_path=image_path,
            task_text=note, reply=explanation,
        )
    conv = get_store().get(user_id, platform=TELEGRAM_PLATFORM)
    conv.homework_check_context = not check_mode
    get_store().save(conv)
```

- [ ] **Step 7: Wire MAX audio in `bot/app/main.py`**

В `_process_update`, в ветке `message_created`, до `if not text: return` вставить обработку аудио-вложений (текст ещё пустая строка на этом этапе, если сообщение — только вложение):

```python
        body = message.get("body") or {}
        text = body.get("text", "").strip()
        attachments = body.get("attachments") or []
        audio_att = next((a for a in attachments if isinstance(a, dict) and a.get("type") == "audio"), None)
        if not text and audio_att:
            url = (audio_att.get("payload") or {}).get("url", "")
            if url:
                await _handle_max_voice(url, user_id, message, update, max_client)
            return
        if not text:
            return
```

(Заменить существующую строку `text = (message.get("body") or {}).get("text", "").strip()` на приведённый выше блок целиком — она находится сразу после определения `user_id` в ветке `message_created`; проверить точное окружение перед правкой командой из Step 1.)

Новый обработчик — рядом с `_send_max_logged`:

```python
async def _handle_max_voice(url: str, user_id: str, message: dict, update: dict, max_client) -> None:
    sender = message.get("sender") or {}
    crm_ctx = crm_ingest.ingest_inbound(
        PLATFORM, user_id, "[голосовое]",
        external_event_id=_extract_update_id(update),
        external_message_id=_max_message_external_id(message),
        name=str(sender.get("name") or ""),
        username=str(sender.get("username") or ""),
    )
    download = getattr(max_client, "download_file", None)
    if not callable(download):
        await max_client.send_message(user_id, "Пока не могу скачать голосовое здесь. Напишите текстом.")
        return
    audio = await download(url, MAX_HOMEWORK_AUDIO_BYTES)
    if not audio:
        await max_client.send_message(user_id, "Не получилось скачать голосовое. Попробуйте ещё раз или напишите текстом.")
        return
    text = await _reply_while_alive(
        max_client, user_id, lambda: speech.transcribe(audio, "voice.ogg", "audio/ogg")
    )
    if not text:
        await max_client.send_message(
            user_id, "Не расслышала голосовое 🙏 Попробуйте ещё раз или напишите задание текстом."
        )
        return
    await max_client.send_message(user_id, f"Услышал: «{text}»")
    explanation = await _reply_while_alive(
        max_client, user_id, lambda: homework.explain_homework_text(text)
    )
    explanation = explanation or HOMEWORK_TEXT_FALLBACK
    ok = await max_client.send_message(user_id, explanation)
    crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL, ok=bool(ok))
    if crm_ctx:
        crm_store.record_homework_request(
            platform=PLATFORM, user_id=user_id,
            customer_id=crm_ctx.get("customer_id"),
            conversation_id=crm_ctx.get("conversation_id"), channel=PLATFORM,
            mode="explain", input_type="voice", audio_transcript=text,
            task_text=text, reply=explanation,
        )
    conv = get_store().get(user_id, platform=PLATFORM)
    conv.homework_check_context = True
    get_store().save(conv)
```

- [ ] **Step 8: Run tests**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_homework_voice_routing.py tests/test_telegram_adapter.py tests/test_max_client.py tests/test_bot.py -v`
Expected: все PASS. Если существующие тесты на `_process_telegram_update`/`_process_update` жёстко ожидали старый ответ «Пока не умею читать голосовые» — заменить ожидание на новый путь (голос теперь обрабатывается), не удалять тест.

- [ ] **Step 9: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/main.py bot/app/memory.py bot/app/max_client.py bot/tests/test_homework_voice_routing.py
git commit -m "feat(bot): голосовые ДЗ и режим «проверь» в Telegram и MAX

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: Чат с Фокси в мини-приложении — кнопки вместо экрана, история, голос

**Files:**
- Modify: `bot/app/main.py` (новые API-ручки)
- Modify: `bot/app/tgapp/index.html`
- Modify: `bot/app/tgapp/app.js`
- Modify: `bot/app/tgapp/app.css`
- Test: `bot/tests/test_max_miniapp.py` (дополнить — там уже тесты на контракт мини-приложения) и `bot/tests/test_tgapp.py`

**Interfaces:**
- Consumes: `homework.explain_homework_image/text`, `homework.check_homework_image`, `speech.transcribe`, `crm_store.record_homework_request`, `crm_ingest.ingest_inbound(..., payload=...)`
- Produces:
  - `GET /api/miniapp/chat/history?limit=50` → `{"ok": true, "messages": [{"id", "role": "me"|"bot"|"manager", "text", "image_url": str|null, "created_at"}]}` — последние N сообщений диалога (по подписанному `identity`).
  - `POST /api/miniapp/homework/check` — как существующий `POST /api/miniapp/homework`, но режим проверки: принимает `image` (multipart), возвращает `{"ok": true, "explanation": str}`.
  - `POST /api/miniapp/homework/voice` — принимает `audio` (multipart) + необязательный `mode` (`explain`|`check`, по умолчанию `explain`), распознаёт и разбирает голосом присланное задание, возвращает `{"ok": true, "transcript": str, "explanation": str}`.

- [ ] **Step 1: Read current chat/homework code fully before editing**

Run: `cd /Users/grigory/Dymova-english/bot && grep -n "buildHomework\|SHEETS\|greetInChat\|chat-log\|#chat\b" app/tgapp/app.js app/tgapp/index.html`

Найти точные текущие номера строк и разметку (`#chat-log`, `#chat-input`, кнопка вызова менеджера) — они не совпадают с номерами, увиденными на этапе планирования, если файл менялся в прошлых сессиях.

- [ ] **Step 2: Write the failing backend test** — дополнить `bot/tests/test_max_miniapp.py` (или создать `bot/tests/test_miniapp_homework_chat.py`, если формат существующего файла для этого не подходит — решить по месту, посмотрев на существующие фикстуры авторизации, например в `tests/test_cabinet.py`):

```python
"""Кнопки помощи с ДЗ и история чата прямо в мини-приложении."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import crm_store
from app import main as main_module
from app import memory as memory_module
from app.config import settings
from tests.conftest import make_telegram_init_data

TOKEN = "123456:AA-test-token"


def auth(uid: int = 777) -> dict:
    return {
        "X-Miniapp-Init-Data": make_telegram_init_data(TOKEN, telegram_user_id=uid),
        "X-Miniapp-Platform": "telegram",
    }


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    memory_module._store = None
    crm_store.reset()
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", TOKEN, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_AUTH_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_REQUIRE_REGISTRATION", False, raising=False)
    yield
    memory_module._store = None
    crm_store.reset()


def test_chat_history_requires_signed_identity():
    client = TestClient(main_module.app)
    resp = client.get("/api/miniapp/chat/history")
    assert resp.status_code == 401


def test_chat_history_returns_past_messages_in_order():
    from app import crm_ingest

    crm_ingest.ingest_inbound("telegram", "tg:777", "первый вопрос", external_event_id="e1")
    ctx = crm_ingest.ingest_inbound("telegram", "tg:777", "второй вопрос", external_event_id="e2")
    crm_ingest.ingest_outbound(ctx, "ответ бота")
    client = TestClient(main_module.app)
    resp = client.get("/api/miniapp/chat/history", headers=auth())
    body = resp.json()
    assert body["ok"] is True
    texts = [m["text"] for m in body["messages"]]
    assert texts == ["первый вопрос", "второй вопрос", "ответ бота"]
    assert body["messages"][0]["role"] == "me"
    assert body["messages"][-1]["role"] == "bot"


def test_check_endpoint_returns_explanation():
    client = TestClient(main_module.app)
    with patch("app.homework.check_homework_image", new=AsyncMock(return_value="🔎 Пункт 1\nВерно!")):
        resp = client.post(
            "/api/miniapp/homework/check",
            files={"image": ("t.jpg", b"fake-bytes", "image/jpeg")},
            headers=auth(),
        )
    body = resp.json()
    assert body["ok"] is True
    assert "Пункт 1" in body["explanation"]


def test_voice_endpoint_transcribes_and_explains():
    client = TestClient(main_module.app)
    with patch("app.speech.transcribe", new=AsyncMock(return_value="Вставь is или are")), \
         patch("app.homework.explain_homework_text", new=AsyncMock(return_value="📘 Правило")):
        resp = client.post(
            "/api/miniapp/homework/voice",
            files={"audio": ("v.ogg", b"fake-audio", "audio/ogg")},
            headers=auth(),
        )
    body = resp.json()
    assert body["ok"] is True
    assert body["transcript"] == "Вставь is или are"
    assert "Правило" in body["explanation"]


def test_voice_endpoint_unrecognized_audio_returns_error_not_500():
    client = TestClient(main_module.app)
    with patch("app.speech.transcribe", new=AsyncMock(return_value=None)):
        resp = client.post(
            "/api/miniapp/homework/voice",
            files={"audio": ("v.ogg", b"fake-audio", "audio/ogg")},
            headers=auth(),
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_max_miniapp.py -k homework or test_miniapp_homework_chat -v` (использовать реально созданный файл теста из Step 2).
Expected: FAIL — 404 на новые ручки.

- [ ] **Step 4: Add endpoints to `bot/app/main.py`** — рядом с существующим `POST /api/miniapp/homework`:

```python
@app.get("/api/miniapp/chat/history")
async def miniapp_chat_history(request: Request, limit: int = 50) -> dict:
    """История диалога для чата мини-приложения: подгружается при открытии,
    в отличие от поллинга новых исходящих (см. /api/miniapp/messages)."""
    identity = _identity_from_request(request)
    if identity is None:
        return JSONResponse(
            {"ok": False, "error": "Нужна авторизация внутри Telegram или MAX"},
            status_code=401,
        )
    conv = crm_store.find_conversation(identity.platform, identity.user_id)
    if conv is None:
        return {"ok": True, "messages": []}
    limit = max(1, min(int(limit), 100))
    rows = crm_store.get_messages(conv["id"], limit=limit)
    messages = []
    for m in rows:
        image_url = None
        try:
            payload = json.loads(m.get("payload_json") or "{}")
            if payload.get("image_path"):
                image_url = f"/api/miniapp/homework/image/{payload['image_path'].split('/', 1)[1]}"
        except Exception:
            pass
        role = "me" if m["direction"] == "in" else ("manager" if m["sender_type"] == "manager" else "bot")
        messages.append({
            "id": m["id"], "role": role, "text": m["text"],
            "image_url": image_url, "created_at": m["created_at"],
        })
    return {"ok": True, "messages": messages}


@app.get("/api/miniapp/homework/image/{filename}")
async def miniapp_homework_image(request: Request, filename: str) -> FileResponse:
    """Миниатюры фото задания в истории чата. Только по подписанному
    initData — на фото могут быть личные данные ребёнка."""
    identity = _identity_from_request(request)
    if identity is None:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    safe_name = Path(filename).name  # без произвольных путей вроде "../.."
    path = Path(homework.HOMEWORK_IMAGE_DIR) / safe_name
    if not path.exists():
        return JSONResponse({"detail": "not found"}, status_code=404)
    return FileResponse(str(path))


@app.post("/api/miniapp/homework/check")
async def api_homework_check(
    request: Request,
    note: str = Form(default=""),
    init_data: str = Form(default=""),
    image: UploadFile | None = File(default=None),
) -> dict:
    identity = _identity_from_request(request, init_data=init_data)
    access = _miniapp_access_state(identity)
    if access["locked"]:
        return JSONResponse({"ok": False, "error": access["message"]}, status_code=403)
    if image is None or not image.filename:
        return JSONResponse({"detail": "Нужна фотография решения"}, status_code=400)
    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        return JSONResponse({"detail": "Файл должен быть в формате изображения"}, status_code=400)
    image_bytes = await image.read(MAX_HOMEWORK_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_HOMEWORK_IMAGE_BYTES:
        return JSONResponse({"detail": "Фото слишком большое — пришлите снимок до 8 МБ"}, status_code=413)
    if not image_bytes:
        return JSONResponse({"detail": "Пустой файл"}, status_code=400)
    explanation = await homework.check_homework_image(image_bytes, content_type, note)
    if not explanation:
        explanation = "Не удалось разобрать фото. Попробуйте снять его при хорошем свете."
    image_path = homework.save_homework_image(image_bytes, ext="jpg")
    crm_ctx = None
    if identity is not None:
        crm_ctx = crm_ingest.ingest_inbound(
            identity.platform, identity.user_id, f"[фото решения] {note}".strip(),
            external_event_id=f"miniapp-hw-check:{uuid.uuid4().hex}",
            payload={"image_path": image_path},
        )
        crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL)
        crm_store.record_homework_request(
            platform=identity.platform, user_id=identity.user_id,
            customer_id=crm_ctx.get("customer_id") if crm_ctx else None,
            conversation_id=crm_ctx.get("conversation_id") if crm_ctx else None,
            channel=identity.platform, mode="check", input_type="image",
            image_path=image_path, task_text=note, reply=explanation,
        )
    return {"ok": True, "explanation": explanation}


@app.post("/api/miniapp/homework/voice")
async def api_homework_voice(
    request: Request,
    mode: str = Form(default="explain"),
    init_data: str = Form(default=""),
    audio: UploadFile | None = File(default=None),
) -> dict:
    identity = _identity_from_request(request, init_data=init_data)
    access = _miniapp_access_state(identity)
    if access["locked"]:
        return JSONResponse({"ok": False, "error": access["message"]}, status_code=403)
    if audio is None or not audio.filename:
        return JSONResponse({"detail": "Нужна голосовая запись"}, status_code=400)
    audio_bytes = await audio.read(MAX_HOMEWORK_AUDIO_BYTES + 1)
    if len(audio_bytes) > MAX_HOMEWORK_AUDIO_BYTES:
        return JSONResponse({"detail": "Запись слишком большая — до 20 МБ"}, status_code=413)
    text = await speech.transcribe(audio_bytes, audio.filename or "voice.webm",
                                   (audio.content_type or "audio/webm"))
    if not text:
        return {"ok": False, "error": "Не расслышала запись. Попробуйте ещё раз или напишите текстом."}
    explanation = await homework.explain_homework_text(text)
    if not explanation:
        explanation = homework.HOMEWORK_TEXT_FALLBACK
    crm_ctx = None
    if identity is not None:
        crm_ctx = crm_ingest.ingest_inbound(
            identity.platform, identity.user_id, f"[голосовое] {text}",
            external_event_id=f"miniapp-hw-voice:{uuid.uuid4().hex}",
        )
        crm_ingest.ingest_outbound(crm_ctx, explanation, ai_model=settings.LLM_MODEL)
        crm_store.record_homework_request(
            platform=identity.platform, user_id=identity.user_id,
            customer_id=crm_ctx.get("customer_id") if crm_ctx else None,
            conversation_id=crm_ctx.get("conversation_id") if crm_ctx else None,
            channel=identity.platform, mode="explain", input_type="voice",
            audio_transcript=text, task_text=text, reply=explanation,
        )
    return {"ok": True, "transcript": text, "explanation": explanation}
```

Добавить импорты в начало `main.py`, если их там ещё нет: `import json`, `import uuid`, `from pathlib import Path`, `from app import speech`. `HOMEWORK_TEXT_FALLBACK` уже импортируется из `app.homework` (проверить существующий `from app.homework import (...)` блок и дописать в него `HOMEWORK_TEXT_FALLBACK`, если отсутствует).

- [ ] **Step 5: Run backend tests**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_miniapp_homework_chat.py tests/test_max_miniapp.py tests/test_cabinet.py -v`
Expected: все PASS.

- [ ] **Step 6: Frontend — remove the standalone homework sheet, add in-chat buttons + history + voice recording**

Прочитать текущие `app/tgapp/index.html` (секцию `data-tab="chat"`) и `app/tgapp/app.js` (`SHEETS`, `buildHomework`, `submitHomework`, `greetInChat`, `addMessage`, `sendChat`) целиком перед правкой.

В `app.js`:
- Удалить `homework: { title: "Помощь с домашкой", build: buildHomework }` из `SHEETS` и функции `buildHomework`/`submitHomework` (их логику переносим в чат — см. ниже). Найти все места, где кнопка «📸 Помощь с домашкой» открывала этот лист (`openSheet("homework")` или похожее — искать по `"homework"` в файле), заменить на переключение вкладки чата (`goTab("chat")`), если такая кнопка есть на главном экране.
- В `greetInChat()` — заменить одноразовое приветствие на подгрузку истории:

```javascript
  function greetInChat() {
    var log = $("#chat-log");
    if (log.dataset.loaded) return;
    log.dataset.loaded = "1";
    request("/api/miniapp/chat/history")
      .then(function (data) {
        if (data && data.ok && data.messages && data.messages.length) {
          data.messages.forEach(function (m) {
            addMessage(m.role, m.text, m.image_url);
            state.chatLastId = Math.max(state.chatLastId || 0, m.id);
          });
        } else {
          addMessage("bot", "Спросите что угодно: программы, цены, расписание, как проходят занятия.");
        }
      })
      .catch(function () {
        addMessage("bot", "Спросите что угодно: программы, цены, расписание, как проходят занятия.");
      })
      .finally(startChatPolling);
  }
```

- Обновить `addMessage`, чтобы принимать необязательное фото-миниатюру:

```javascript
  function addMessage(role, text, imageUrl) {
    var log = $("#chat-log");
    var bubble = document.createElement("div");
    bubble.className = "bubble bubble--" + role;
    if (imageUrl) {
      var img = document.createElement("img");
      img.className = "bubble__thumb";
      img.src = imageUrl;
      img.alt = "";
      img.loading = "lazy";
      bubble.appendChild(img);
    }
    if (text) {
      var span = document.createElement("span");
      span.textContent = text;
      bubble.appendChild(span);
    }
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
    return bubble;
  }
```

(Проверить все существующие вызовы `addMessage(role, text)` в файле — они останутся рабочими, третий аргумент необязателен.)

- Добавить кнопки и обработчики в конце секции чата (рядом с местом, где сейчас `sendChat`/форма ввода текста — найти реальную разметку кнопки отправки в `index.html` и добавить панель кнопок над полем ввода):

```javascript
  function submitHomeworkFile(file, note, checkMode) {
    var typing = addMessage("bot", "…");
    typing.classList.add("bubble--typing");
    var form = new FormData();
    form.append("image", file);
    if (note) form.append("note", note);
    var path = checkMode ? "/api/miniapp/homework/check" : "/api/miniapp/homework";
    request(path, { method: "POST", body: form, timeout: 90000 })
      .then(function (data) {
        typing.remove();
        if (data.__status === 403) {
          addMessage("bot", data.error || "Раздел откроется после регистрации.");
          return;
        }
        addMessage("bot", data.explanation || data.error || "Не удалось разобрать задание.");
      })
      .catch(function () {
        typing.remove();
        addMessage("bot", "Нет связи. Попробуйте ещё раз.");
      });
  }

  function pickHomeworkPhoto(checkMode) {
    var input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      addMessage("me", checkMode ? "Проверь моё решение" : "Разбери задание", URL.createObjectURL(file));
      submitHomeworkFile(file, "", checkMode);
    });
    input.click();
  }

  var mediaRecorder = null;
  var mediaChunks = [];

  function startVoiceHomework() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      addMessage("bot", "Голосовые здесь не поддерживаются — напишите задание текстом.");
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      mediaChunks = [];
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.addEventListener("dataavailable", function (e) {
        if (e.data && e.data.size) mediaChunks.push(e.data);
      });
      mediaRecorder.addEventListener("stop", function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        var blob = new Blob(mediaChunks, { type: "audio/webm" });
        addMessage("me", "🎤 Голосовое сообщение");
        var typing = addMessage("bot", "…");
        typing.classList.add("bubble--typing");
        var form = new FormData();
        form.append("audio", blob, "voice.webm");
        request("/api/miniapp/homework/voice", { method: "POST", body: form, timeout: 90000 })
          .then(function (data) {
            typing.remove();
            if (data.ok) {
              addMessage("bot", "Услышал: «" + data.transcript + "»");
              addMessage("bot", data.explanation);
            } else {
              addMessage("bot", data.error || "Не расслышала запись.");
            }
          })
          .catch(function () {
            typing.remove();
            addMessage("bot", "Нет связи. Попробуйте ещё раз.");
          });
      });
      mediaRecorder.start();
      haptic("light");
      setTimeout(function () {
        if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
      }, 5 * 60 * 1000); // лимит 5 минут — тот же, что у голосовых в чате бота
    }).catch(function () {
      addMessage("bot", "Не удалось включить микрофон — проверьте разрешения браузера.");
    });
  }
```

В `bind()` — привязать новые кнопки (id согласовать с разметкой, добавленной в `index.html` на следующем шаге):

```javascript
    on("#chat-explain-btn", "click", function () { pickHomeworkPhoto(false); });
    on("#chat-check-btn", "click", function () { pickHomeworkPhoto(true); });
    on("#chat-voice-btn", "click", startVoiceHomework);
```

(Использовать null-safe `on()` — тот же приём, что уже закреплён в этом файле после ревью прошлой сессии, не `$(...).addEventListener`.)

- [ ] **Step 7: Add the button markup and CSS**

В `app/tgapp/index.html`, в секции `data-tab="chat"`, перед формой ввода текста (найти её точное текущее место):

```html
      <div class="chat-actions">
        <button type="button" id="chat-explain-btn" class="chip">📸 Разобрать задание</button>
        <button type="button" id="chat-check-btn" class="chip">✅ Проверить решение</button>
        <button type="button" id="chat-voice-btn" class="chip">🎤 Голосом</button>
      </div>
```

В `app/tgapp/app.css`, в конец файла:

```css
/* Кнопки помощи с ДЗ прямо в чате — заменяют отдельный экран (были
   бы дублирующим путём к той же функции: кнопки видны сразу, без
   перехода на другой лист). */
.chat-actions { display: flex; gap: 8px; flex-wrap: wrap; padding: 8px 16px; }
.chat-actions .chip { flex: 1 1 auto; min-width: 0; font-size: 12.5px; padding: 8px 10px;
  border-radius: 999px; border: 1px solid rgba(0,0,0,.12); background: #fff; }
.bubble__thumb { display: block; max-width: 220px; border-radius: 12px; margin-bottom: 6px; }
```

(Сверить с существующими токенами цвета/радиуса в начале `app.css`, использовать их вместо литералов, если есть подходящие переменные — как в прошлой сессии с формой регистрации.)

- [ ] **Step 8: Run frontend checks**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_tgapp.py tests/test_max_miniapp.py tests/test_maxapp_design.py -v && node --check app/tgapp/app.js`
Expected: все PASS, `node --check` без вывода. Обновить/удалить в `test_tgapp.py` любые проверки, жёстко завязанные на существование отдельного экрана `homework` (искать по `"homework"` в файле теста) — заменить на проверку новых кнопок в чате, не оставлять тест падать молча пропущенным.

- [ ] **Step 9: Commit**

```bash
cd /Users/grigory/Dymova-english
git add -p bot/app/main.py bot/app/tgapp/index.html bot/app/tgapp/app.js bot/app/tgapp/app.css bot/tests/
git commit -m "feat(bot): помощь с ДЗ прямо в чате мини-приложения — история, фото, проверка решения, голос

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: Раздел «Домашние задания» в админке

**Files:**
- Modify: `bot/app/admin_api.py`
- Modify: `bot/app/adminapp/app.js`
- Modify: `bot/app/adminapp/index.html`
- Modify: `bot/app/adminapp/app.css`
- Test: `bot/tests/test_admin_api.py`

**Interfaces:**
- Consumes: `crm_store.list_homework_requests`, `crm_store.get_homework_request` (Task 4)
- Produces:
  - `GET /admin/api/homework?mode=&date_from=&date_to=&limit=&offset=` → `{"items": [...]}`
  - `GET /admin/api/homework/{id}` → `{"item": {...}}`
  - `GET /admin/api/homework/{id}/image` → фото задания (FileResponse), гейт `_authorize`

- [ ] **Step 1: Read the requests-section pattern fully before editing**

Run: `cd /Users/grigory/Dymova-english/bot && sed -n '349,400p' app/admin_api.py && grep -n "requests\|SECTION" app/adminapp/app.js | head -40 && grep -n "nav-item\|data-section" app/adminapp/index.html`

- [ ] **Step 2: Write the failing test** — дополнить `bot/tests/test_admin_api.py`:

```python
def test_homework_list_requires_auth(client):
    resp = client.get("/admin/api/homework")
    assert resp.status_code == 401


def test_homework_list_and_detail(client, admin_headers):
    from app import crm_store

    req_id = crm_store.record_homework_request(
        platform="telegram", user_id="tg:1", conversation_id=None,
        channel="telegram", mode="explain", input_type="text",
        task_text="I ... nine", reply="📘 Правило",
    )
    resp = client.get("/admin/api/homework", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1

    detail = client.get(f"/admin/api/homework/{req_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["item"]["task_text"] == "I ... nine"


def test_homework_detail_404_for_missing(client, admin_headers):
    resp = client.get("/admin/api/homework/999999", headers=admin_headers)
    assert resp.status_code == 404
```

Использовать существующие фикстуры `client`/`admin_headers` из `test_admin_api.py` (прочитать их в Step 1, они уже определены в этом файле для других разделов — не создавать заново).

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_admin_api.py -k homework -v`
Expected: FAIL — 404 на `/admin/api/homework`.

- [ ] **Step 4: Add "homework" permission to `bot/app/admin_api.py`** — в `ROLE_PERMISSIONS`:

```python
    "admin": {"inbox", "customers", "pipeline", "reply", "ai_mode", "stats",
              "health", "broadcasts", "segments", "analytics", "export",
              "kb", "errors", "system", "requests", "homework"},
    "manager": {"inbox", "customers", "pipeline", "reply", "ai_mode", "stats",
                "health", "requests", "homework"},
```

(Не трогать `marketing` — раздел ДЗ не по их профилю.) `support`:

```python
    "support": {"inbox", "customers", "reply", "stats", "health", "requests", "homework"},
```

- [ ] **Step 5: Add endpoints** — рядом с разделом заявок:

```python
# --------- Домашние задания (homework_requests) ---------


@router.get("/homework")
async def homework_list(request: Request, mode: str = "", date_from: str = "",
                        date_to: str = "", limit: int = 50, offset: int = 0) -> dict:
    _authorize(request, "homework")
    return {
        "items": crm_store.list_homework_requests(
            mode=mode or None, date_from=date_from or None, date_to=date_to or None,
            limit=limit, offset=offset,
        )
    }


@router.get("/homework/{request_id}")
async def homework_detail(request: Request, request_id: int) -> dict:
    _authorize(request, "homework")
    item = crm_store.get_homework_request(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="homework request not found")
    return {"item": item}


@router.get("/homework/{request_id}/image")
async def homework_image(request: Request, request_id: int) -> FileResponse:
    _authorize(request, "homework")
    item = crm_store.get_homework_request(request_id)
    if item is None or not item.get("image_path"):
        raise HTTPException(status_code=404, detail="no image for this request")
    from pathlib import Path

    from app.homework import HOMEWORK_IMAGE_DIR

    filename = Path(item["image_path"]).name
    path = Path(HOMEWORK_IMAGE_DIR) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="image file missing")
    return FileResponse(str(path))
```

(Проверить, что `FileResponse` уже импортирован в `admin_api.py` — если нет, добавить `from fastapi.responses import FileResponse` в шапку.)

- [ ] **Step 6: Run backend tests**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_admin_api.py tests/test_rbac.py -v`
Expected: все PASS.

- [ ] **Step 7: Add the frontend section**

В `bot/app/adminapp/index.html` — nav-пункт сразу после пункта «Заявки» (после `<button class="nav-item" data-section="requests" data-perm="inbox">...</button>`):

```html
      <button class="nav-item" data-section="homework" data-perm="homework">
        <svg viewBox="0 0 16 16"><path d="M3 2h8l2 2v10H3z"/><path d="M6 6h6M6 9h6M6 12h4"/></svg>
        Домашние задания</button>
```

И секция страницы сразу после `<section class="page" id="page-requests" hidden>...</section>`:

```html
    <section class="page" id="page-homework" hidden>
      <div class="toolbar">
        <select id="homework-mode">
          <option value="">Любой режим</option>
          <option value="explain">Объясни</option>
          <option value="check">Проверь решение</option>
        </select>
        <input type="date" id="homework-date-from" />
        <input type="date" id="homework-date-to" />
        <button class="btn btn--ghost btn--sm" id="homework-filter-apply">Применить</button>
      </div>
      <div class="customers-list" id="homework-list"></div>
    </section>
```

В `bot/app/adminapp/app.js`:

1. В `sectionPerms` (внутри `showSection`, см. Step 1) добавить `homework: "homework",`.
2. В массив секций (`["dashboard", "inbox", "requests", "customers", ...]`, встречается дважды — в `showSection` для скрытия страниц и в обработчике клика по `nav`, если он использует тот же список) добавить `"homework"`.
3. После `if (name === "requests") loadRequests();` добавить `if (name === "homework") loadHomework();`.
4. Добавить функции в конец файла (рядом с разделом заявок):

```javascript
const HOMEWORK_MODE_LABELS = { explain: "Объясни", check: "Проверь решение" };

async function loadHomework() {
  try {
    const params = new URLSearchParams();
    const mode = $("homework-mode").value;
    const dateFrom = $("homework-date-from").value;
    const dateTo = $("homework-date-to").value;
    if (mode) params.set("mode", mode);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    params.set("limit", "100");
    const data = await api(`/admin/api/homework?${params.toString()}`);
    renderHomeworkList(data.items || []);
  } catch (err) {
    if (err.message === "unauthorized") showGate("Токен больше не подходит");
    else toast(err.message);
  }
}

$("homework-filter-apply").addEventListener("click", () => loadHomework());

function renderHomeworkList(items) {
  $("homework-list").innerHTML = items.length
    ? items.map(homeworkRowHtml).join("")
    : `<div class="empty">Обращений нет</div>`;
}

function homeworkRowHtml(h) {
  const name = h.customer_name || h.customer_phone || `Клиент #${h.customer_id || "—"}`;
  const preview = (h.task_text || h.audio_transcript || "").slice(0, 90);
  return `
    <button class="customer-row req-row" data-hw="${h.id}">
      <span class="avatar avatar--${esc(h.channel || "web")}">${esc(initials(name))}</span>
      <span class="customer-row__main">
        <span class="customer-row__name">
          <span class="muted">#${esc(h.id)}</span> ${esc(name)}
          <span class="pill">${esc(HOMEWORK_MODE_LABELS[h.mode] || h.mode)}</span>
        </span>
        <span class="customer-row__meta">
          ${channelPill(h.channel)} ${esc(fmtTime(h.created_at))}
          ${preview ? " · " + esc(preview) + (preview.length === 90 ? "…" : "") : ""}
        </span>
      </span>
    </button>`;
}

$("homework-list").addEventListener("click", (event) => {
  const row = event.target.closest("[data-hw]");
  if (row) openHomeworkRequest(Number(row.dataset.hw));
});

async function openHomeworkRequest(id) {
  if (!id) return;
  openDrawer(`Домашка #${id}`, async () => {
    try {
      const data = await api(`/admin/api/homework/${id}`);
      renderHomeworkDetail(data.item || {});
    } catch (err) {
      $("drawer-body").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
    }
  });
}

function renderHomeworkDetail(h) {
  const name = h.customer_name || h.customer_phone || `Клиент #${h.customer_id || "—"}`;
  const imageBlock = h.image_path
    ? `<img class="hw-detail__image" src="/admin/api/homework/${h.id}/image" alt="" />`
    : "";
  const transcriptBlock = h.audio_transcript
    ? `<div class="hw-detail__block"><h4>Распознанный голос</h4><p>${esc(h.audio_transcript)}</p></div>`
    : "";
  $("drawer-body").innerHTML = `
    <div class="hw-detail">
      <div class="hw-detail__meta">
        ${channelPill(h.channel)} <span class="pill">${esc(HOMEWORK_MODE_LABELS[h.mode] || h.mode)}</span>
        <span class="muted">${esc(fmtTime(h.created_at))}</span>
      </div>
      <div class="hw-detail__block"><h4>Клиент</h4><p>${esc(name)}</p></div>
      ${imageBlock}
      ${transcriptBlock}
      <div class="hw-detail__block"><h4>Задание</h4><p>${esc(h.task_text || "—")}</p></div>
      <div class="hw-detail__block"><h4>Ответ Фокси</h4><p>${esc(h.reply || "—")}</p></div>
    </div>`;
}
```

(`initials`, `channelPill`, `fmtTime`, `toast`, `showGate` — уже существуют в файле, использованы в разделе заявок; сверить точные имена и сигнатуры в Step 1 перед вставкой — если какое-то называется иначе, использовать реальное имя.)

В `bot/app/adminapp/app.css` добавить (в конец файла, сверив с существующими токенами цвета):

```css
.hw-detail__image { display: block; max-width: 100%; border-radius: 12px; margin: 8px 0 16px; }
.hw-detail__block { margin-bottom: 14px; }
.hw-detail__block h4 { margin: 0 0 4px; font-size: 12px; text-transform: uppercase; opacity: .6; }
.hw-detail__meta { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
```

- [ ] **Step 8: Run all admin checks**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_admin_api.py tests/test_adminapp.py tests/test_rbac.py -v && node --check app/adminapp/app.js`
Expected: все PASS.

- [ ] **Step 9: Commit**

```bash
cd /Users/grigory/Dymova-english
git add -p bot/app/admin_api.py bot/app/adminapp/app.js bot/app/adminapp/index.html bot/app/adminapp/app.css bot/tests/test_admin_api.py
git commit -m "feat(bot): раздел «Домашние задания» в админке

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Полная проверка, деплой, контрольный прогон на реальных заданиях

**Files:**
- Modify: `DEVLOG.md`

- [ ] **Step 1: Full test suite**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest -q --ignore=tests/benchmark`
Expected: 0 failed. Чинить реальные регрессии по существу.

- [ ] **Step 2: Review** — `superpowers:requesting-code-review` по всему диффу задач 1-7 (base — коммит перед Task 1, head — текущий; диф строить с `-- bot/`, если в диапазон попадут чужие коммиты владельца по Миру — проверить `git log`/`git diff --name-only <commit>~1..<commit> -- bot/` перед сборкой пакета для ревью, как в предыдущих сессиях).

- [ ] **Step 3: Manual test run on real assignments** (требование спеки: «контрольный прогон на наборе типовых заданий вручную с отчётом»)

Собрать 6 реальных школьных заданий (английский×2, математика×2, русский×2, разных классов), прогнать через прод (или staging-копию) в режиме «объясни» и «проверь» (для «проверь» — сфотографировать заведомо с одной ошибкой). Для каждого зафиксировать в отчёте (можно прямо в тексте DEVLOG): не дан ли готовый ответ, разобран ли каждый пункт, корректна ли подсказка при ошибке. Любое найденное нарушение принципа «без готового ответа» — блокирующий баг, не деплоить как есть, чинить промпт/критика и прогонять контрольный набор заново.

- [ ] **Step 4: Deploy**

```bash
cd /Users/grigory/Dymova-english && git push origin world-v2
```

На сервере — сначала `git status --short` (см. Global Constraints), затем:
```bash
ssh yc-user@89.169.132.104 'cd /home/yc-user/Dymova-english && git status --short'
ssh yc-user@89.169.132.104 'cd /home/yc-user/Dymova-english && git pull --ff-only origin world-v2'
ssh yc-user@89.169.132.104 'cd /home/yc-user/Dymova-english/bot && sudo docker compose up -d --build'
```

- [ ] **Step 5: Live check on prod**

```bash
curl -s https://bot.dymova-english.ru/health
ssh yc-user@89.169.132.104 'docker logs --since 3m bot-bot-1 2>&1 | grep -iE "error|traceback|exception"'
ssh yc-user@89.169.132.104 'docker exec bot-bot-1 python -c "
from app import speech
print(\"stt provider configured:\", speech._openai_provider() is not None)
"'
```

Expected: `/health` ok; ноль ошибок в логах; `stt provider configured: True` (запасной `proxyapi`-провайдер уже в `LLM_FALLBACKS` на проде, отдельный STT-ключ заводить не нужно — см. разведку).

Вручную (владелец или тестовый аккаунт): отправить боту в Telegram голосовое с диктовкой задания — должен прийти «Услышал: …» и подробный разбор по пунктам; отправить фото решённого задания с подписью «проверь» — должна прийти проверка без названного правильного ответа; открыть мини-приложение, вкладку «Фокси» — должна загрузиться история переписки, быть видны три кнопки помощи с ДЗ.

- [ ] **Step 6: DEVLOG + commit**

Дописать запись сессии в `DEVLOG.md` по образцу предыдущих (дата, ветка, что сделано, отчёт контрольного прогона из Step 3, как проверено, деплой, что проверить владельцу).

```bash
cd /Users/grigory/Dymova-english
git add DEVLOG.md
git commit -m "docs(bot): журнал — помощник по ДЗ 2.0 задеплоен (аудио, проверка решения, подробный разбор, админка)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin world-v2
```
