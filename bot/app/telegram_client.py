"""Клиент Telegram Bot API.

Отвечает за то, чтобы сообщение до пользователя ДОШЛО:
- длинный ответ режется по лимиту Telegram (4096 символов) — раньше такой
  ответ отбивался 400-й ошибкой, и пользователь не получал вообще ничего;
- 429 (flood control) уважает retry_after и повторяется;
- сетевые сбои ретраятся с экспоненциальной паузой;
- поддерживаются три типа кнопок: ссылка, callback и web_app (Mini App).
  Раньше нормализация выкидывала всё, кроме ссылок, поэтому клавиатура
  выбора филиала приходила пустой и диалог упирался в тупик.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Жёсткий лимит Telegram на текст сообщения.
TELEGRAM_MAX_MESSAGE_CHARS = 4096
_MAX_SEND_ATTEMPTS = 3
_INITIAL_BACKOFF = 0.5
# Потолок ожидания при flood control: дольше держать пользователя бессмысленно.
_MAX_RETRY_AFTER = 30

# Нажатия inline-кнопок приходят отдельным типом апдейта. Без callback_query
# в этом списке ни одна кнопка бота в Telegram не работала вообще.
ALLOWED_UPDATES = ["message", "edited_message", "callback_query"]


def split_message(text: str, limit: int = TELEGRAM_MAX_MESSAGE_CHARS) -> list[str]:
    """Режет длинный текст на части по границам абзацев/строк/слов."""
    text = text or ""
    if len(text) <= limit:
        return [text] if text else []
    parts: list[str] = []
    rest = text
    while len(rest) > limit:
        window = rest[:limit]
        # Ищем ближайшую «красивую» границу с конца окна.
        for separator in ("\n\n", "\n", ". ", " "):
            cut = window.rfind(separator)
            if cut > limit // 2:
                window = rest[: cut + len(separator)]
                break
        parts.append(window.rstrip())
        rest = rest[len(window):].lstrip()
    if rest:
        parts.append(rest)
    return parts


def _normalize_button(button: dict) -> dict | None:
    """Приводит кнопку внутреннего формата к inline-кнопке Telegram."""
    text = str(button.get("text") or button.get("title") or "").strip()
    if not text:
        return None
    url = str(button.get("url", "")).strip()
    web_app_url = str(button.get("web_app") or button.get("web_app_url") or "").strip()
    payload = str(button.get("payload") or button.get("callback_data") or "").strip()
    button_type = str(button.get("type") or "").strip().lower()

    if web_app_url or button_type == "web_app":
        target = web_app_url or url
        if not target.startswith("https://"):
            # Telegram открывает Mini App только по HTTPS; иначе кнопка молча
            # не работает у пользователя.
            logger.warning("telegram: web_app кнопка без https — пропущена: %s", target)
            return None
        return {"text": text, "web_app": {"url": target}}
    if url:
        return {"text": text, "url": url}
    if payload:
        # callback_data ограничен 64 байтами.
        return {"text": text, "callback_data": payload[:64]}
    return None


def _normalize_buttons(buttons: list[list[dict]] | None) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for row in buttons or []:
        if not isinstance(row, (list, tuple)):
            continue
        normalized_row = [
            normalized
            for button in row
            if isinstance(button, dict) and (normalized := _normalize_button(button))
        ]
        if normalized_row:
            rows.append(normalized_row)
    return rows


def _client_kwargs(timeout: int = 30) -> dict:
    kwargs: dict = {"timeout": timeout}
    proxy_url = settings.TELEGRAM_PROXY_URL.strip()
    if proxy_url:
        kwargs["proxy"] = proxy_url
    return kwargs


def _retry_after(resp: Any) -> float | None:
    """Сколько ждать по требованию Telegram при 429."""
    try:
        payload = resp.json()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    params = payload.get("parameters")
    if isinstance(params, dict) and params.get("retry_after") is not None:
        try:
            return min(float(params["retry_after"]), _MAX_RETRY_AFTER)
        except (TypeError, ValueError):
            return None
    return None


class TelegramClient:
    def __init__(self) -> None:
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base = f"https://api.telegram.org/bot{self.token}" if self.token else ""

    @property
    def configured(self) -> bool:
        return bool(self.token)

    async def _post(
        self,
        method: str,
        data: dict,
        *,
        timeout: int = 30,
        attempts: int = _MAX_SEND_ATTEMPTS,
    ) -> dict | None:
        """POST к Bot API с ретраями. Возвращает result или None."""
        if not self.configured:
            logger.warning("telegram: токен не настроен — %s не выполнен", method)
            return None
        delay = _INITIAL_BACKOFF
        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(**_client_kwargs(timeout)) as client:
                    resp = await client.post(f"{self.base}/{method}", data=data)
            except Exception:
                logger.warning(
                    "telegram: %s сетевая ошибка, попытка %s/%s", method, attempt, attempts,
                    exc_info=True,
                )
                if attempt >= attempts:
                    return None
                await asyncio.sleep(delay)
                delay *= 2
                continue

            if resp.status_code == 200:
                try:
                    payload = resp.json()
                except Exception:
                    logger.error("telegram: %s вернул не-JSON", method)
                    return None
                result = payload.get("result") if isinstance(payload, dict) else None
                return result if isinstance(result, (dict, list)) else {}

            if resp.status_code == 429:
                wait = _retry_after(resp) or delay
                logger.warning("telegram: %s flood control, жду %.1fs", method, wait)
                if attempt >= attempts:
                    return None
                await asyncio.sleep(wait)
                delay *= 2
                continue

            if 500 <= resp.status_code <= 599:
                logger.warning(
                    "telegram: %s status=%s, попытка %s/%s", method, resp.status_code, attempt, attempts
                )
                if attempt >= attempts:
                    return None
                await asyncio.sleep(delay)
                delay *= 2
                continue

            logger.error(
                "telegram: %s ошибка status=%s body=%s", method, resp.status_code, resp.text[:300]
            )
            return None
        return None

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        buttons: Optional[list[list[dict]]] = None,
    ) -> bool:
        chunks = split_message(text)
        if not chunks:
            return False
        rows = _normalize_buttons(buttons)
        delivered = False
        for index, chunk in enumerate(chunks):
            data: dict[str, str] = {"chat_id": str(chat_id), "text": chunk}
            # Клавиатуру вешаем только на последнее сообщение — иначе она
            # дублируется под каждым куском длинного ответа.
            if rows and index == len(chunks) - 1:
                data["reply_markup"] = json.dumps({"inline_keyboard": rows}, ensure_ascii=False)
            result = await self._post("sendMessage", data)
            delivered = delivered or result is not None
        return delivered

    async def send_chat_action(self, chat_id: str | int, action: str = "typing") -> bool:
        """Индикатор «печатает». Не ретраим: это косметика, а не доставка."""
        result = await self._post(
            "sendChatAction", {"chat_id": str(chat_id), "action": action}, timeout=10, attempts=1
        )
        return result is not None

    async def answer_callback_query(
        self, callback_query_id: str, text: str | None = None
    ) -> bool:
        """Гасит спиннер на кнопке. Без этого клиент крутит загрузку до таймаута."""
        data: dict[str, str] = {"callback_query_id": str(callback_query_id)}
        if text:
            data["text"] = text[:200]
        result = await self._post("answerCallbackQuery", data, timeout=10, attempts=2)
        return result is not None

    async def set_webhook(self, url: str, secret: str | None = None) -> bool:
        data: dict[str, str] = {
            "url": url,
            "allowed_updates": json.dumps(ALLOWED_UPDATES, ensure_ascii=False),
        }
        if secret:
            data["secret_token"] = secret
        return await self._post("setWebhook", data, attempts=2) is not None

    async def delete_webhook(self) -> bool:
        return await self._post("deleteWebhook", {}, attempts=2) is not None

    async def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict]:
        if not self.configured:
            return []
        data: dict[str, str] = {
            "timeout": str(timeout),
            "allowed_updates": json.dumps(ALLOWED_UPDATES, ensure_ascii=False),
        }
        if offset is not None:
            data["offset"] = str(offset)
        kwargs = _client_kwargs(timeout + 15)
        kwargs["timeout"] = httpx.Timeout(timeout + 15)
        try:
            async with httpx.AsyncClient(**kwargs) as client:
                resp = await client.post(f"{self.base}/getUpdates", data=data)
            if resp.status_code != 200:
                logger.warning("Telegram getUpdates error status=%s body=%s", resp.status_code, resp.text[:300])
                return []
            payload = resp.json()
            result = payload.get("result") if isinstance(payload, dict) else None
            if isinstance(result, list):
                return result
            logger.warning("Telegram getUpdates unexpected payload: %s", payload)
        except Exception:
            logger.warning("Telegram get_updates failed", exc_info=True)
        return []


_client: TelegramClient | None = None


def get_telegram() -> TelegramClient:
    global _client
    if _client is None:
        _client = TelegramClient()
    return _client
