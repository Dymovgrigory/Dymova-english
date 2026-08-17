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


# Кнопки запуска мини-приложения тут намеренно нет. В MAX мини-приложение
# привязывается к боту в кабинете MAX Бизнес, и кнопка запуска появляется в
# чате сама (см. dev.max.ru/docs/webapps/introduction и bot/DEPLOY.md).
# Тип кнопки «open_app» встречается в сторонних библиотеках, но в
# официальной документации Bot API его нет — гадать про формат нельзя:
# неверный тип кнопки роняет всю клавиатуру сообщения, а не одну кнопку.
# Ссылка на мини-приложение отправляется обычной link-кнопкой.


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


def _max_error_description(resp: httpx.Response) -> str:
    """Человекочитаемая причина ошибки MAX из тела ответа (code/message)."""
    try:
        payload = resp.json()
    except Exception:
        return f"HTTP {resp.status_code}"
    if isinstance(payload, dict):
        code = str(payload.get("code") or "").strip()
        message = str(payload.get("message") or payload.get("error") or "").strip()
        text = ": ".join(part for part in (code, message) if part)
        if text:
            return f"HTTP {resp.status_code}: {text}"[:300]
    return f"HTTP {resp.status_code}"


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
        body, _error = await self._request_ext(
            method, path, params=params, json_body=json_body, attempts=attempts)
        return body

    async def _request_ext(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        attempts: int = _MAX_ATTEMPTS,
    ) -> tuple[dict | None, str | None]:
        """Тот же запрос, но возвращает (тело, описание ошибки): описание
        из ответа платформы нужно CRM, чтобы менеджер видел причину
        недоставки (например, «пользователь заблокировал бота»)."""
        if not self.configured:
            logger.warning("MAX бот не настроен — %s %s не выполнен", method, path)
            return None, "MAX бот не настроен"
        url = f"{self.base}{path}"
        delay = _INITIAL_BACKOFF
        client = _http()

        for attempt in range(1, attempts + 1):
            try:
                resp = await client.request(
                    method, url, params=params, headers=self._headers(), json=json_body
                )
            except httpx.RequestError as exc:
                logger.warning(
                    "MAX %s %s сетевая ошибка, попытка %s/%s",
                    method, path, attempt, attempts, exc_info=True,
                )
                if attempt >= attempts:
                    return None, f"сетевая ошибка: {type(exc).__name__}"
                await asyncio.sleep(delay)
                delay *= 2
                continue
            except Exception as exc:
                logger.exception("MAX %s %s неожиданная ошибка", method, path)
                return None, str(exc)[:300]

            if resp.status_code == 200:
                try:
                    body = resp.json()
                except Exception:
                    # Успешный ответ без тела — это не ошибка доставки.
                    return {}, None
                return (body if isinstance(body, dict) else {}), None

            if resp.status_code == 429:
                wait = _retry_after(resp) or delay
                logger.warning("MAX %s %s лимит частоты, жду %.1fs", method, path, wait)
                if attempt >= attempts:
                    return None, "лимит частоты запросов (429)"
                await asyncio.sleep(wait)
                delay *= 2
                continue

            if 500 <= resp.status_code <= 599:
                logger.warning(
                    "MAX %s %s status=%s, попытка %s/%s",
                    method, path, resp.status_code, attempt, attempts,
                )
                if attempt >= attempts:
                    return None, f"ошибка платформы {resp.status_code}"
                await asyncio.sleep(delay)
                delay *= 2
                continue

            logger.error(
                "MAX %s %s ошибка status=%s body=%s",
                method, path, resp.status_code, resp.text[:300],
            )
            return None, _max_error_description(resp)
        return None, "send failed"

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
        ok, _external_id, _error = await self.send_message_ext(user_id, text, buttons)
        return ok

    async def send_message_ext(
        self,
        user_id: str,
        text: str,
        buttons: Optional[list[list[dict]]] = None,
    ) -> tuple[bool, str | None, str | None]:
        """Отправка с фактом доставки: (ok, id сообщения в MAX, описание ошибки).

        Id сообщения в ответе платформы нужен CRM для жизненного цикла
        доставки; описание ошибки — чтобы менеджер видел причину недоставки.
        """
        body: dict = {"text": text}
        if buttons:
            body["attachments"] = keyboard(buttons)
        result, error = await self._request_ext(
            "POST", "/messages", params={"user_id": user_id}, json_body=body
        )
        if result is None:
            return False, None, error or "send failed"
        # Формат ответа POST /messages: {"message": {... "id"/"mid" ...}} либо
        # плоское тело — берём то, что платформа реально вернула.
        container = result.get("message") if isinstance(result.get("message"), dict) else result
        external_id = None
        for key in ("id", "mid", "message_id"):
            if container.get(key):
                external_id = str(container[key])
                break
        return True, external_id, None

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
