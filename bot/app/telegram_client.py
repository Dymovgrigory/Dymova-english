"""Клиент Telegram Bot API."""
from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _normalize_buttons(buttons: list[list[dict]] | None) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for row in buttons or []:
        normalized_row: list[dict] = []
        for button in row:
            if not isinstance(button, dict):
                continue
            url = str(button.get("url", "")).strip()
            text = str(button.get("text") or button.get("title") or "").strip()
            if not url or not text:
                continue
            normalized_row.append({"text": text, "url": url})
        if normalized_row:
            rows.append(normalized_row)
    return rows


def _client_kwargs(timeout: int = 30) -> dict:
    kwargs: dict = {"timeout": timeout}
    proxy_url = settings.TELEGRAM_PROXY_URL.strip()
    if proxy_url:
        kwargs["proxy"] = proxy_url
    return kwargs


class TelegramClient:
    def __init__(self) -> None:
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base = f"https://api.telegram.org/bot{self.token}" if self.token else ""

    @property
    def configured(self) -> bool:
        return bool(self.token)

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        buttons: Optional[list[list[dict]]] = None,
    ) -> bool:
        if not self.configured:
            logger.warning("Telegram bot token not configured — message not sent")
            return False
        data: dict[str, str] = {"chat_id": str(chat_id), "text": text}
        rows = _normalize_buttons(buttons)
        if rows:
            data["reply_markup"] = json.dumps({"inline_keyboard": rows}, ensure_ascii=False)
        try:
            async with httpx.AsyncClient(**_client_kwargs()) as client:
                resp = await client.post(f"{self.base}/sendMessage", data=data)
            if resp.status_code == 200:
                return True
            logger.error("Telegram sendMessage error status=%s body=%s", resp.status_code, resp.text[:300])
        except Exception:
            logger.exception("Telegram send_message failed")
        return False

    async def set_webhook(self, url: str, secret: str | None = None) -> bool:
        if not self.configured:
            return False
        data: dict[str, str] = {"url": url}
        if secret:
            data["secret_token"] = secret
        try:
            async with httpx.AsyncClient(**_client_kwargs()) as client:
                resp = await client.post(f"{self.base}/setWebhook", data=data)
            return resp.status_code == 200
        except Exception:
            logger.exception("Telegram set_webhook failed")
            return False

    async def delete_webhook(self) -> bool:
        if not self.configured:
            return False
        try:
            async with httpx.AsyncClient(**_client_kwargs()) as client:
                resp = await client.post(f"{self.base}/deleteWebhook")
            return resp.status_code == 200
        except Exception:
            logger.exception("Telegram delete_webhook failed")
            return False

    async def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict]:
        if not self.configured:
            return []
        data: dict[str, str] = {
            "timeout": str(timeout),
            "allowed_updates": json.dumps(["message"], ensure_ascii=False),
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
