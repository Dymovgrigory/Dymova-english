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
