"""Провайдер-агностичный клиент LLM (OpenAI-совместимый Chat Completions).

По умолчанию работает с OpenRouter и бесплатными моделями, но через переменные
окружения (LLM_BASE_URL / LLM_MODEL / LLM_API_KEY) легко переключается на Groq,
локальный Ollama или любой другой OpenAI-совместимый эндпоинт.

Если ключ не задан, клиент возвращает None — вызывающий код переходит на
ответы по правилам, поэтому бот остаётся работоспособным без LLM.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_INITIAL_BACKOFF = 0.25
_MAX_ATTEMPTS_PER_PROVIDER = 3


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    api_key: str
    model: str

    @property
    def label(self) -> str:
        host = urlparse(self.base_url).netloc or self.base_url
        return f"{host}::{self.model}"


_http_client: httpx.AsyncClient | None = None
_client: "LLMClient" | None = None


def _build_providers() -> list[ProviderConfig]:
    providers: list[ProviderConfig] = [
        ProviderConfig(
            base_url=settings.LLM_BASE_URL.strip(),
            api_key=settings.LLM_API_KEY.strip(),
            model=settings.LLM_MODEL.strip(),
        )
    ]
    raw = (settings.LLM_FALLBACKS or "").strip()
    if raw:
        try:
            items = json.loads(raw)
        except Exception:
            logger.exception("LLM_FALLBACKS contains invalid JSON")
            items = []
        if isinstance(items, list):
            for item in items:
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


async def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=settings.LLM_TIMEOUT)
    return _http_client


class LLMClient:
    def __init__(self) -> None:
        self.providers = _build_providers()
        self.vision_model = settings.VISION_MODEL

    @property
    def enabled(self) -> bool:
        return bool(self.providers)

    def _headers(self, provider: ProviderConfig) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        host = urlparse(provider.base_url).netloc.lower()
        if "openrouter.ai" in host:
            headers["HTTP-Referer"] = "https://dymova-english.ru"
            headers["X-Title"] = "Foxinburg MAX Bot"
        return headers

    async def _complete_once(
        self,
        provider: ProviderConfig,
        model: str,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str | None:
        if not self.enabled:
            return None
        client = await _get_http_client()
        url = f"{provider.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            "max_tokens": settings.LLM_MAX_TOKENS if max_tokens is None else max_tokens,
        }
        delay = _INITIAL_BACKOFF
        for attempt in range(1, _MAX_ATTEMPTS_PER_PROVIDER + 1):
            try:
                resp = await client.post(url, headers=self._headers(provider), json=payload)
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
                    logger.exception("LLM provider=%s invalid JSON response", provider.label)
                    return None
                choices = data.get("choices") or []
                if not choices:
                    logger.error("LLM provider=%s returned no choices", provider.label)
                    return None
                content = choices[0].get("message", {}).get("content", "")
                reply = _clean_response(content)
                if reply:
                    logger.info("LLM provider=%s model=%s succeeded", provider.label, model)
                return reply or None

            if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                logger.warning(
                    "LLM provider=%s model=%s attempt=%s retryable status=%s body=%s",
                    provider.label,
                    model,
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
                "LLM provider=%s model=%s non-retryable status=%s body=%s",
                provider.label,
                model,
                resp.status_code,
                resp.text[:300],
            )
            return None
        return None

    async def _complete_with_fallbacks(
        self,
        messages: list[dict],
        model: str | None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        apply_russian_guard: bool = False,
    ) -> str | None:
        if not self.enabled:
            return None
        for provider in self.providers:
            provider_model = provider.model if model is None else model
            reply = await self._complete_once(
                provider,
                provider_model,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if not reply:
                continue
            if apply_russian_guard and not _mostly_russian(reply):
                logger.warning(
                    "LLM provider=%s model=%s reply looks non-Russian, retrying once",
                    provider.label,
                    provider_model,
                )
                retry = await self._complete_once(
                    provider,
                    provider_model,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if retry and _mostly_russian(retry):
                    return retry
                if retry:
                    logger.warning(
                        "LLM provider=%s model=%s still non-Russian after retry",
                        provider.label,
                        provider_model,
                    )
                continue
            return reply
        logger.error("LLM cascade exhausted all providers for model=%s", model or "provider-model")
        return None

    async def complete(self, messages: list[dict], temperature: float | None = None) -> str | None:
        return await self._complete_with_fallbacks(
            messages,
            None,
            temperature=temperature,
            apply_russian_guard=True,
        )

    async def complete_vision(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str | None:
        return await self._complete_with_fallbacks(
            messages,
            self.vision_model,
            temperature=temperature,
            max_tokens=max_tokens,
            apply_russian_guard=False,
        )


def _mostly_russian(text: str) -> bool:
    cyr = len(re.findall(r"[А-Яа-яЁё]", text or ""))
    lat = len(re.findall(r"[A-Za-z]", text or ""))
    total = cyr + lat
    if total < 8:
        return True
    return (cyr / total) >= 0.35


# Паттерны мусорных токенов LLM (заголовки чата Llama, роли).
_JUNK_TOKENS = re.compile(
    r"<\|(?:end_header_id|start_header_id|eot_id|begin_of_text|im_start|im_end)[^>]*\|>",
)
# Китайские/японские/корейские иероглифы — Llama иногда вставляет.
_CJK_RE = re.compile(r"[一-鿿㐀-䶿぀-ゟ゠-ヿ]+")

# Английские слова-вставки, которые модель иногда роняет в русский текст
# («Цена indeed важна»). Удаляем как отдельные слова, не трогая бренды
# (My Level, Hippo, Foxinburg) и фактические латинские токены.
_EN_FILLER = re.compile(
    r"\b(?:indeed|actually|however|basically|literally|obviously|honestly|"
    r"frankly|anyway|essentially|certainly|definitely|absolutely|seriously|"
    r"really|kind of|sort of|you know|i mean|well|okay|sure)\b",
    re.IGNORECASE,
)


def _clean_response(text: str) -> str:
    """Strip LLM artifacts: chat header tokens, CJK characters, extra whitespace."""
    if not text:
        return ""
    # Remove special tokens
    text = _JUNK_TOKENS.sub("", text)
    # Remove CJK characters (replace with space to avoid broken words like "нымиами")
    text = _CJK_RE.sub(" ", text)
    # Вырезаем английские слова-вставки только если текст в основном русский
    # (чтобы не трогать ответы, которые легитимно содержат английский).
    if _mostly_russian(text):
        text = _EN_FILLER.sub("", text)
        # подчищаем пунктуацию, оставшуюся после удаления слова: «Цена , важна»
        text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    # Remove lines that are just "assistant" or "user" (role leaks)
    lines = text.split("\n")
    cleaned = [ln for ln in lines if ln.strip().lower() not in ("assistant", "user", "system")]
    text = "\n".join(cleaned)
    # Collapse multiple blank lines to max 1
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()



def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
