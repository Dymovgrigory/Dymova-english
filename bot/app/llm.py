"""Провайдер-агностичный клиент LLM (OpenAI-совместимый Chat Completions).

Поддерживает каскад провайдеров: основной (LLM_API_KEY / LLM_BASE_URL /
LLM_MODEL) и запасные через LLM_FALLBACKS. При временных ошибках делает
ретраи с экспоненциальной паузой, затем переходит к следующему провайдеру.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS_PER_PROVIDER = 3
_INITIAL_BACKOFF = 0.25


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    api_key: str
    model: str

    @property
    def label(self) -> str:
        return f"{self.base_url.rstrip('/')}::{self.model}"


_client: httpx.AsyncClient | None = None
_http_client: httpx.AsyncClient | None = None

_FILLER_RE = re.compile(
    r"\b(?:indeed|actually|basically|really|just|well|so|like|you know)\b",
    re.IGNORECASE,
)


def _clean_response(text: str) -> str:
    text = _FILLER_RE.sub("", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" ,;")


def _mostly_russian(text: str) -> bool:
    if len(text.split()) <= 3:
        return True
    latin = sum(1 for ch in text if "A" <= ch <= "Z" or "a" <= ch <= "z")
    cyr = sum(1 for ch in text if "А" <= ch <= "я" or ch in "Ёё")
    return not (latin and latin > cyr * 1.25)


def _build_provider_configs() -> list[ProviderConfig]:
    providers: list[ProviderConfig] = [
        ProviderConfig(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
        )
    ]
    raw = (settings.LLM_FALLBACKS or "").strip()
    if raw:
        try:
            fallbacks = json.loads(raw)
        except Exception:
            logger.exception("LLM_FALLBACKS содержит невалидный JSON")
            fallbacks = []
        if isinstance(fallbacks, list):
            for item in fallbacks:
                if not isinstance(item, dict):
                    continue
                providers.append(
                    ProviderConfig(
                        base_url=str(item.get("base_url", "")).strip(),
                        api_key=str(item.get("api_key", "")).strip(),
                        model=str(item.get("model", "")).strip(),
                    )
                )
    return [p for p in providers if p.base_url and p.api_key and p.model]


def _provider_headers(provider: ProviderConfig) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter" in provider.base_url.lower():
        headers["HTTP-Referer"] = "https://dymova-english.ru"
        headers["X-Title"] = "Foxinburg MAX Bot"
    return headers


async def _get_client() -> httpx.AsyncClient:
    global _client, _http_client
    client = _client or _http_client
    if client is None:
        client = httpx.AsyncClient(timeout=settings.LLM_TIMEOUT)
    _client = client
    _http_client = client
    return client


async def _complete_with_provider(
    client: httpx.AsyncClient,
    provider: ProviderConfig,
    messages: list[dict],
    temperature: float,
) -> str | None:
    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": provider.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": settings.LLM_MAX_TOKENS,
    }
    headers = _provider_headers(provider)
    delay = _INITIAL_BACKOFF

    for attempt in range(1, _MAX_ATTEMPTS_PER_PROVIDER + 1):
        try:
            resp = await client.post(url, headers=headers, json=payload)
        except httpx.RequestError:
            logger.warning(
                "LLM provider=%s attempt=%s network/timeout error",
                provider.label,
                attempt,
                exc_info=True,
            )
            if attempt < _MAX_ATTEMPTS_PER_PROVIDER:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            return None
        except Exception:
            logger.exception("LLM provider=%s attempt=%s unexpected error", provider.label, attempt)
            if attempt < _MAX_ATTEMPTS_PER_PROVIDER:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            return None

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                logger.exception("LLM provider=%s invalid JSON", provider.label)
                return None
            choices = data.get("choices") or []
            if not choices:
                logger.error("LLM provider=%s returned no choices", provider.label)
                return None
            content = choices[0].get("message", {}).get("content", "")
            reply = _clean_response(content or "").strip() or None
            if reply and not _mostly_russian(reply):
                logger.warning("LLM provider=%s returned mostly-English text", provider.label)
                return None
            if reply:
                logger.info("LLM provider=%s success", provider.label)
            return reply

        if resp.status_code == 429 or 500 <= resp.status_code <= 599:
            logger.warning(
                "LLM provider=%s attempt=%s retryable status=%s body=%s",
                provider.label,
                attempt,
                resp.status_code,
                resp.text[:300],
            )
            if attempt < _MAX_ATTEMPTS_PER_PROVIDER:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            return None

        logger.error(
            "LLM provider=%s non-retryable status=%s body=%s",
            provider.label,
            resp.status_code,
            resp.text[:300],
        )
        return None

    return None


class LLMClient:
    def __init__(self) -> None:
        self.providers = _build_provider_configs()

    @property
    def enabled(self) -> bool:
        return bool(self.providers)

    async def complete(self, messages: list[dict], temperature: float | None = None) -> str | None:
        if not self.enabled:
            return None
        client = await _get_client()
        target_temperature = settings.LLM_TEMPERATURE if temperature is None else temperature
        for provider in self.providers:
            reply = await _complete_with_provider(client, provider, messages, target_temperature)
            if reply:
                return reply
        logger.error("LLM cascade exhausted all providers")
        return None


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


__all__ = ["get_llm", "_clean_response", "_mostly_russian"]
