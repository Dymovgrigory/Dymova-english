"""Клиент MAX Bot API.

Документация: https://dev.max.ru/docs-api
Авторизация — заголовок `Authorization: {access_token}` (без префикса Bearer).
Базовый домен с июля 2026 — platform-api2.max.ru.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import urllib.parse
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def link_button(text: str, url: str) -> dict:
    return {"type": "link", "text": text, "url": url}


def callback_button(text: str, payload: str) -> dict:
    return {"type": "callback", "text": text, "payload": payload}


def keyboard(rows: list[list[dict]]) -> list[dict]:
    """Собирает attachment inline-клавиатуры из строк кнопок."""
    return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]


class MaxClient:
    def __init__(self) -> None:
        self.token = settings.MAX_BOT_TOKEN
        self.base = settings.MAX_BOT_API_URL.rstrip("/")
        self.bot_user_id: str | None = None
        self.bot_username: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict:
        return {"Authorization": self.token, "Content-Type": "application/json"}

    async def get_bot_info(self) -> Optional[dict]:
        if not self.configured:
            return None
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{self.base}/me", headers=self._headers())
            if resp.status_code == 200:
                return resp.json()
            logger.error("MAX /me error status=%s body=%s", resp.status_code, resp.text[:300])
        except Exception:
            logger.exception("MAX /me failed")
        return None

    async def ensure_bot_identity(self) -> bool:
        if self.bot_user_id or self.bot_username:
            return True
        info = await self.get_bot_info()
        if not info:
            return False
        user = info.get("user") if isinstance(info, dict) else info
        if not isinstance(user, dict):
            return False
        user_id = user.get("user_id") or user.get("id")
        username = user.get("username") or user.get("name")
        if user_id:
            self.bot_user_id = str(user_id)
        if username:
            self.bot_username = str(username).lstrip("@").lower()
        return bool(self.bot_user_id or self.bot_username)

    async def send_message(
        self,
        user_id: str,
        text: str,
        buttons: Optional[list[list[dict]]] = None,
    ) -> bool:
        if not self.configured:
            logger.warning("MAX бот не настроен — сообщение не отправлено")
            return False
        params = {"user_id": user_id}
        body: dict = {"text": text}
        if buttons:
            body["attachments"] = keyboard(buttons)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base}/messages",
                    params=params,
                    headers=self._headers(),
                    json=body,
                )
            if resp.status_code == 200:
                return True
            logger.error("MAX send error status=%s body=%s", resp.status_code, resp.text[:300])
        except Exception:
            logger.exception("MAX send failed")
        return False

    async def send_to_chat(
        self,
        chat_id: int | str,
        text: str,
        buttons: Optional[list[list[dict]]] = None,
    ) -> bool:
        if not self.configured:
            logger.warning("MAX бот не настроен — сообщение в чат не отправлено")
            return False
        params = {"chat_id": chat_id}
        body: dict = {"text": text}
        if buttons:
            body["attachments"] = keyboard(buttons)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base}/messages",
                    params=params,
                    headers=self._headers(),
                    json=body,
                )
            if resp.status_code == 200:
                return True
            logger.error("MAX send chat error status=%s body=%s", resp.status_code, resp.text[:300])
        except Exception:
            logger.exception("MAX send_to_chat failed")
        return False

    async def answer_callback(self, callback_id: str, notification: Optional[str] = None) -> bool:
        if not self.configured:
            return False
        params = {"callback_id": callback_id}
        body: dict = {}
        if notification:
            body["notification"] = notification
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base}/answers",
                    params=params,
                    headers=self._headers(),
                    json=body,
                )
            return resp.status_code == 200
        except Exception:
            logger.exception("MAX answer_callback failed")
            return False

    async def set_webhook(self, url: str, secret: Optional[str] = None) -> bool:
        """Подписывает бота на webhook (subscription)."""
        if not self.configured:
            return False
        body = {"url": url}
        if secret:
            body["secret"] = secret
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base}/subscriptions",
                    headers=self._headers(),
                    json=body,
                )
            return resp.status_code == 200
        except Exception:
            logger.exception("MAX set_webhook failed")
            return False

    def verify_init_data(self, init_data: str) -> Optional[dict]:
        """Проверяет подпись initData из MAX Mini App и возвращает user.id."""
        if not self.token or not init_data:
            return None
        parsed = urllib.parse.parse_qs(init_data)
        received_hash = parsed.pop("hash", [None])[0]
        if not received_hash:
            return None
        data_pairs = []
        for key in sorted(parsed.keys()):
            for value in sorted(parsed[key]):
                data_pairs.append(f"{key}={value}")
        data_check_string = "\n".join(data_pairs)
        secret = hmac.new(b"WebAppData", self.token.encode(), hashlib.sha256).digest()
        computed = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed, received_hash):
            return None
        try:
            user = json.loads(parsed.get("user", ["{}"])[0])
            return {"user_id": str(user.get("id"))}
        except Exception:
            return None


_client: MaxClient | None = None


def get_max() -> MaxClient:
    global _client
    if _client is None:
        _client = MaxClient()
    return _client
