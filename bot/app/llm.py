"""Провайдер-агностичный клиент LLM (OpenAI-совместимый Chat Completions).

По умолчанию работает с OpenRouter и бесплатными моделями, но через переменные
окружения (LLM_BASE_URL / LLM_MODEL / LLM_API_KEY) легко переключается на Groq,
локальный Ollama или любой другой OpenAI-совместимый эндпоинт.

Если ключ не задан, клиент возвращает None — вызывающий код переходит на
ответы по правилам, поэтому бот остаётся работоспособным без LLM.
"""
from __future__ import annotations

import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.model = settings.LLM_MODEL
        self.vision_model = settings.VISION_MODEL

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # OpenRouter рекомендует указывать источник запроса.
            "HTTP-Referer": "https://dymova-english.ru",
            "X-Title": "Foxinburg MAX Bot",
        }

    async def _chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str | None:
        if not self.enabled:
            return None
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            "max_tokens": settings.LLM_MAX_TOKENS if max_tokens is None else max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
            if resp.status_code != 200:
                logger.error("LLM error status=%s body=%s", resp.status_code, resp.text[:500])
                return None
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                return None
            content = choices[0].get("message", {}).get("content", "")
            return _clean_response(content) or None
        except Exception:
            logger.exception("LLM request failed")
            return None

    async def complete(self, messages: list[dict], temperature: float | None = None) -> str | None:
        reply = await self._chat_completion(self.model, messages, temperature=temperature)
        if reply and not _mostly_russian(reply):
            logger.warning("LLM reply looks non-Russian, retrying once")
            retry = await self._chat_completion(self.model, messages, temperature=temperature)
            if retry and not _mostly_russian(retry):
                return None
            return retry
        return reply

    async def complete_vision(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str | None:
        return await self._chat_completion(
            self.vision_model, messages, temperature=temperature, max_tokens=max_tokens
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
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff]+")


def _clean_response(text: str) -> str:
    """Strip LLM artifacts: chat header tokens, CJK characters, extra whitespace."""
    if not text:
        return ""
    # Remove special tokens
    text = _JUNK_TOKENS.sub("", text)
    # Remove CJK characters (replace with space to avoid broken words like "нымиами")
    text = _CJK_RE.sub(" ", text)
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    # Remove lines that are just "assistant" or "user" (role leaks)
    lines = text.split("\n")
    cleaned = [ln for ln in lines if ln.strip().lower() not in ("assistant", "user", "system")]
    text = "\n".join(cleaned)
    # Collapse multiple blank lines to max 1
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
