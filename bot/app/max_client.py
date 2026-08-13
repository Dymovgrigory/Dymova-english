"""Клиент MAX Bot API.

Документация: https://dev.max.ru/docs-api
Авторизация — заголовок `Authorization: {access_token}` (без префикса Bearer).
Передача токена query-параметром платформой больше не поддерживается.

Базовый домен — `platform-api2.max.ru`. Старый `botapi.max.ru` выведён из
эксплуатации (срок миграции — 19.07.2026). Новый домен обслуживается
сертификатом Минцифры, которого нет в стандартном списке доверенных: если
на хосте он не установлен, укажите путь к нему в `MAX_CA_BUNDLE`
(см. DEPLOY.md), иначе все запросы упадут на проверке TLS.

Доставка сообщений здесь так же обязательна, как в Telegram-клиенте, поэтому
транспорт устроен одинаково: переиспользуемое соединение, ретраи сетевых
сбоев и 5xx, уважение к 429 с Retry-After.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import urllib.parse
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_INITIAL_BACKOFF = 0.5
# Дольше держать пользователя в ожидании бессмысленно — лучше честный фолбэк.
_MAX_RETRY_AFTER = 30.0
_REQUEST_TIMEOUT = 30.0


def link_button(text: str, url: str) -> dict:
    return {"type": "link", "text": text, "url": url}


def callback_button(text: str, payload: str) -> dict:
    return {"type": "callback", "text": text, "payload": payload}


def keyboard(rows: list[list[dict]]) -> list[dict]:
    """Собирает attachment inline-клавиатуры из строк кнопок."""
    return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]


_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    """Общий клиент с keep-alive.

    Раньше на каждый вызов создавался новый AsyncClient: соединение и TLS-
    рукопожатие устанавливались заново для каждого сообщения.
    """
    global _client
    if _client is None or _client.is_closed:
        verify: object = True
        bundle = (getattr(settings, "MAX_CA_BUNDLE", "") or "").strip()
        if bundle:
            verify = bundle
        _client = httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            verify=verify,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _client


async def close_http() -> None:
    """Закрывает общий клиент (вызывается при остановке приложения)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _retry_after(resp: httpx.Response) -> float | None:
    """Сколько ждать по требованию платформы при 429."""
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return min(float(header), _MAX_RETRY_AFTER)
        except (TypeError, ValueError):
            pass
    try:
        payload = resp.json()
    except Exception:
        return None
    if isinstance(payload, dict):
        for key in ("retry_after", "retryAfter"):
            if payload.get(key) is not None:
                try:
                    return min(float(payload[key]), _MAX_RETRY_AFTER)
                except (TypeError, ValueError):
                    return None
    return None


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

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        attempts: int = _MAX_ATTEMPTS,
    ) -> dict | None:
        """Запрос к MAX API с ретраями. Возвращает тело ответа или None."""
        if not self.configured:
            logger.warning("MAX бот не настроен — %s %s не выполнен", method, path)
            return None
        url = f"{self.base}{path}"
        delay = _INITIAL_BACKOFF
        client = _http()

        for attempt in range(1, attempts + 1):
            try:
                resp = await client.request(
                    method, url, params=params, headers=self._headers(), json=json_body
                )
            except httpx.RequestError:
                logger.warning(
                    "MAX %s %s сетевая ошибка, попытка %s/%s",
                    method, path, attempt, attempts, exc_info=True,
                )
                if attempt >= attempts:
                    return None
                await asyncio.sleep(delay)
                delay *= 2
                continue
            except Exception:
                logger.exception("MAX %s %s неожиданная ошибка", method, path)
                return None

            if resp.status_code == 200:
                try:
                    body = resp.json()
                except Exception:
                    # Успешный ответ без тела — это не ошибка доставки.
                    return {}
                return body if isinstance(body, dict) else {}

            if resp.status_code == 429:
                wait = _retry_after(resp) or delay
                logger.warning("MAX %s %s лимит частоты, жду %.1fs", method, path, wait)
                if attempt >= attempts:
                    return None
                await asyncio.sleep(wait)
                delay *= 2
                continue

            if 500 <= resp.status_code <= 599:
                logger.warning(
                    "MAX %s %s status=%s, попытка %s/%s",
                    method, path, resp.status_code, attempt, attempts,
                )
                if attempt >= attempts:
                    return None
                await asyncio.sleep(delay)
                delay *= 2
                continue

            logger.error(
                "MAX %s %s ошибка status=%s body=%s",
                method, path, resp.status_code, resp.text[:300],
            )
            return None
        return None

    async def get_bot_info(self) -> Optional[dict]:
        return await self._request("GET", "/me")

    async def ensure_bot_identity(self) -> bool:
        if self.bot_user_id and self.bot_username:
            return True
        info = await self.get_bot_info()
        if not info:
            return False
        user_id = info.get("user_id")
        username = info.get("username")
        if isinstance(info.get("user"), dict):
            user = info["user"]
            user_id = user.get("id") or user_id
            username = user.get("username") or username
        if user_id is not None:
            self.bot_user_id = str(user_id)
        if username:
            self.bot_username = str(username)
        return bool(self.bot_user_id and self.bot_username)

    async def send_message(
        self,
        user_id: str,
        text: str,
        buttons: Optional[list[list[dict]]] = None,
    ) -> bool:
        body: dict = {"text": text}
        if buttons:
            body["attachments"] = keyboard(buttons)
        result = await self._request(
            "POST", "/messages", params={"user_id": user_id}, json_body=body
        )
        return result is not None

    async def send_to_chat(
        self,
        chat_id: int,
        text: str,
        buttons: Optional[list[list[dict]]] = None,
    ) -> bool:
        return await self.send_message(str(chat_id), text, buttons)

    async def answer_callback(self, callback_id: str, notification: Optional[str] = None) -> bool:
        body: dict = {}
        if notification:
            body["notification"] = notification
        # Ответ на нажатие гасит спиннер у пользователя: ретраить его дольше
        # одной повторной попытки бессмысленно, клиент к тому времени сдастся.
        result = await self._request(
            "POST", "/answers", params={"callback_id": callback_id},
            json_body=body, attempts=2,
        )
        return result is not None

    async def set_webhook(self, url: str, secret: Optional[str] = None) -> bool:
        """Подписывает бота на webhook (subscription)."""
        body: dict = {"url": url}
        if secret:
            body["secret"] = secret
        result = await self._request("POST", "/subscriptions", json_body=body, attempts=2)
        return result is not None

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


_max: MaxClient | None = None


def get_max() -> MaxClient:
    global _max
    if _max is None:
        _max = MaxClient()
    return _max


def reset_max() -> None:
    """Сброс между тестами и после смены конфигурации."""
    global _max
    _max = None
