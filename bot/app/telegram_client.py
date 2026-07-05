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
            async with httpx.AsyncClient(timeout=30) as client:
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
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{self.base}/setWebhook", data=data)
            return resp.status_code == 200
        except Exception:
            logger.exception("Telegram set_webhook failed")
            return False

    async def delete_webhook(self) -> bool:
        if not self.configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{self.base}/deleteWebhook")
            return resp.status_code == 200
        except Exception:
            logger.exception("Telegram delete_webhook failed")
            return False


_client: TelegramClient | None = None


def get_telegram() -> TelegramClient:
    global _client
    if _client is None:
        _client = TelegramClient()
    return _client
