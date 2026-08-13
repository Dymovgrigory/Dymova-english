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


def _remaining(deadline: float | None) -> float | None:
    """Сколько секунд осталось от общего бюджета каскада."""
    if deadline is None:
        return None
    return deadline - asyncio.get_running_loop().time()


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


def _budget_seconds() -> float:
    raw = getattr(settings, "LLM_TOTAL_BUDGET_SEC", 45.0)
    try:
        return max(1.0, float(raw))
    except (TypeError, ValueError):
        return 45.0


async def _complete_with_provider(
    client: httpx.AsyncClient,
    provider: ProviderConfig,
    messages: list[dict],
    temperature: float,
    max_tokens: int | None = None,
    allow_english: bool = False,
    deadline: float | None = None,
    extra_payload: dict | None = None,
    raw: bool = False,
) -> str | None:
    """Один запрос к провайдеру с ретраями.

    `raw=True` отключает косметическую постобработку (чистку слов-паразитов и
    проверку «ответ в основном по-русски»): для JSON она разрушительна —
    вырезает `so`/`just` внутри строк и отбраковывает валидный ответ как
    «не русский», потому что ключи схемы латиницей.
    """
    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": provider.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
    }
    if extra_payload:
        payload.update(extra_payload)
    headers = _provider_headers(provider)
    delay = _INITIAL_BACKOFF

    for attempt in range(1, _MAX_ATTEMPTS_PER_PROVIDER + 1):
        remaining = _remaining(deadline)
        if remaining is not None and remaining <= 0:
            logger.warning("LLM provider=%s бюджет времени исчерпан", provider.label)
            return None
        try:
            request_timeout = (
                httpx.Timeout(min(float(settings.LLM_TIMEOUT), remaining))
                if remaining is not None
                else None
            )
            if request_timeout is None:
                resp = await client.post(url, headers=headers, json=payload)
            else:
                resp = await client.post(url, headers=headers, json=payload, timeout=request_timeout)
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
            if raw:
                return (content or "").strip() or None
            reply = _clean_response(content or "").strip() or None
            if reply and not allow_english and not _mostly_russian(reply):
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

    async def complete(
        self,
        messages: list[dict],
        temperature: float | None = None,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        extra_payload: dict | None = None,
        raw: bool = False,
        budget_scale: float = 1.0,
    ) -> str | None:
        """Каскад провайдеров с общим бюджетом времени.

        Без бюджета худший случай = провайдеры × 3 попытки × LLM_TIMEOUT,
        то есть минуты полного молчания в чате. Каскад обязан вернуть
        управление вовремя, чтобы вызывающий успел отправить фолбэк.

        `model` подменяет модель ТОЛЬКО у основного провайдера — так роль
        (быстрая/умная модель) выбирается на основном ключе, а запасные
        провайдеры остаются со своими собственными моделями, ради которых
        их и настраивали. Подставлять роль во все провайдеры нельзя: у
        запасного ключа такой модели может просто не быть.
        """
        if not self.enabled:
            return None
        client = await _get_client()
        target_temperature = settings.LLM_TEMPERATURE if temperature is None else temperature
        deadline = asyncio.get_running_loop().time() + _budget_seconds() * max(0.1, budget_scale)
        for index, provider in enumerate(self.providers):
            if _remaining(deadline) <= 0:
                logger.warning("LLM: бюджет времени исчерпан, провайдер %s пропущен", provider.label)
                break
            if model and index == 0:
                provider = ProviderConfig(
                    base_url=provider.base_url, api_key=provider.api_key, model=model
                )
            reply = await _complete_with_provider(
                client,
                provider,
                messages,
                target_temperature,
                max_tokens=max_tokens,
                allow_english=raw,
                deadline=deadline,
                extra_payload=extra_payload,
                raw=raw,
            )
            if reply:
                return reply
        logger.error("LLM cascade exhausted all providers")
        return None

    async def complete_vision(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str | None:
        """Мультимодальный запрос (текст + изображение в content-частях).

        Используется помощником по домашке: фото задания → объяснение.
        Ответ не фильтруем по языку — объяснение может цитировать задание.
        """
        if not self.enabled:
            return None
        client = await _get_client()
        # Картинки обрабатываются дольше текста — даём каскаду двойной бюджет.
        deadline = asyncio.get_running_loop().time() + _budget_seconds() * 2
        for provider in self.providers:
            if _remaining(deadline) <= 0:
                break
            reply = await _complete_with_provider(
                client, provider, messages, temperature, max_tokens=max_tokens,
                allow_english=True, deadline=deadline,
            )
            if reply:
                return reply
        logger.error("LLM vision cascade exhausted all providers")
        return None


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


__all__ = ["get_llm", "_clean_response", "_mostly_russian"]
