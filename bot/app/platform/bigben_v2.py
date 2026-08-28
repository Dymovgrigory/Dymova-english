"""Асинхронный клиент публичного API BigBen CRM v1.

Документация: https://developers.bigbencrm.ru
Base URL: https://platformapi.bigbencrm.ru/api/public/v1

Принципы:
- единая точка доступа к API (никаких разрозненных fetch по проекту);
- Bearer-авторизация, скоупы read/write проверяются на стороне API;
- пагинация per_page<=100, обход страниц до meta.total;
- 429 → ждём Retry-After и повторяем; 5xx/сетевые → экспоненциальный backoff;
- write-методы требуют заголовок Idempotency-Key (UUID, 24ч окно дедупа);
- деньги: API отдаёт копейки целыми (amount_kopecks, balance_kopecks);
  вебхук payment.received — рубли (другая семантика, не путать!).
"""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

MAX_PER_PAGE = 100
MAX_RETRIES = 5
DEFAULT_TIMEOUT = 20.0


class BigBenError(Exception):
    """Ошибка API BigBen с кодом и HTTP-статусом."""

    def __init__(self, message: str, *, status: int = 0, code: str = "", details: Any = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details


class BigBenRateLimited(BigBenError):
    pass


@dataclass
class Page:
    data: list[dict]
    total: int
    page: int
    per_page: int


@dataclass
class BigBenV2Client:
    base_url: str = ""
    api_key: str = ""
    timeout: float = DEFAULT_TIMEOUT
    _client: httpx.AsyncClient | None = field(default=None, repr=False)

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    async def _session(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def _request(self, method: str, path: str, *, params: dict | None = None,
                       json_body: dict | None = None, idempotency_key: str | None = None) -> Any:
        if not self.configured:
            raise BigBenError("BigBen public API не сконфигурирован", code="not_configured")
        headers: dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        session = await self._session()
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await session.request(method, path, params=params, json=json_body, headers=headers)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                await self._sleep_backoff(attempt)
                continue
            if resp.status_code == 429:
                retry_after = _retry_after(resp)
                logger.warning("bigben v2: 429 rate limit, ждём %ss (attempt %d)", retry_after, attempt)
                await asyncio.sleep(retry_after)
                continue
            if resp.status_code >= 500:
                last_exc = BigBenError(f"HTTP {resp.status_code}", status=resp.status_code, code="server_error")
                await self._sleep_backoff(attempt)
                continue
            if resp.status_code >= 400:
                raise _map_error(resp)
            return resp.json()
        if isinstance(last_exc, BigBenError):
            raise last_exc
        raise BigBenError(f"BigBen API недоступен после {MAX_RETRIES} попыток: {last_exc}", code="unavailable")

    @staticmethod
    async def _sleep_backoff(attempt: int) -> None:
        await asyncio.sleep(min(2 ** attempt, 30) + random.uniform(0, 0.5))

    async def _iter_pages(self, path: str, params: dict | None = None):
        """Генератор постраничной выборки до meta.total."""
        params = dict(params or {})
        params.setdefault("per_page", MAX_PER_PAGE)
        page = 1
        while True:
            params["page"] = page
            payload = await self._request("GET", path, params=params)
            data = payload.get("data", [])
            meta = payload.get("meta", {})
            yield Page(data=data, total=meta.get("total", len(data)),
                       page=meta.get("page", page), per_page=meta.get("per_page", params["per_page"]))
            if page * params["per_page"] >= meta.get("total", 0) or not data:
                return
            page += 1

    async def list_all(self, path: str, params: dict | None = None) -> list[dict]:
        items: list[dict] = []
        async for p in self._iter_pages(path, params):
            items.extend(p.data)
        return items

    # --- Справочники ---
    async def filials(self) -> list[dict]:
        return await self.list_all("/filials")

    async def subjects(self) -> list[dict]:
        return await self.list_all("/subjects")

    async def programs(self) -> list[dict]:
        return await self.list_all("/programs")

    async def levels(self) -> list[dict]:
        return await self.list_all("/levels")

    # --- Группы и расписание ---
    async def groups(self, *, updated_since: str | None = None) -> list[dict]:
        params = {"updated_since": updated_since} if updated_since else None
        return await self.list_all("/groups", params)

    async def lessons(self, date_from: str, date_to: str, *, updated_since: str | None = None) -> list[dict]:
        params: dict[str, Any] = {"from": date_from, "to": date_to}
        if updated_since:
            params["updated_since"] = updated_since
        return await self.list_all("/lessons", params)

    # --- Ученики ---
    async def students(self, *, updated_since: str | None = None) -> list[dict]:
        params = {"updated_since": updated_since} if updated_since else None
        return await self.list_all("/students", params)

    async def student(self, student_id: int) -> dict:
        payload = await self._request("GET", f"/students/{student_id}")
        return payload.get("data", payload)

    # --- Платежи ---
    async def payments(self, *, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
        params: dict[str, Any] = {}
        if date_from:
            params["from"] = date_from
        if date_to:
            params["to"] = date_to
        return await self.list_all("/payments", params or None)

    # --- Запись (скоуп write) ---
    async def create_lead(self, *, name: str, phone: str, source: str = "api",
                          comment: str | None = None, funnel_id: int | None = None,
                          idempotency_key: str | None = None) -> dict:
        body: dict[str, Any] = {"name": name, "phone": phone, "source": source}
        if comment:
            body["comment"] = comment[:800]
        if funnel_id:
            body["funnel_id"] = funnel_id
        payload = await self._request(
            "POST", "/leads", json_body=body,
            idempotency_key=idempotency_key or uuid.uuid4().hex,
        )
        return payload.get("data", payload)

    async def create_demo_lesson(self, *, group_id: int, lesson_id: int,
                                 user_id: int | None = None, lead_id: int | None = None,
                                 idempotency_key: str | None = None) -> dict:
        if not user_id and not lead_id:
            raise BigBenError("Нужен user_id или lead_id", code="validation_failed")
        body: dict[str, Any] = {"group_id": group_id, "lesson_id": lesson_id}
        if user_id:
            body["user_id"] = user_id
        if lead_id:
            body["lead_id"] = lead_id
        payload = await self._request(
            "POST", "/demo-lessons", json_body=body,
            idempotency_key=idempotency_key or uuid.uuid4().hex,
        )
        return payload.get("data", payload)

    async def enroll_group(self, student_id: int, group_id: int,
                           idempotency_key: str | None = None) -> dict:
        payload = await self._request(
            "POST", f"/students/{student_id}/groups", json_body={"group_id": group_id},
            idempotency_key=idempotency_key or uuid.uuid4().hex,
        )
        return payload.get("data", payload)


def _retry_after(resp: httpx.Response) -> float:
    try:
        return max(1.0, float(resp.headers.get("Retry-After", "5")))
    except ValueError:
        return 5.0


def _map_error(resp: httpx.Response) -> BigBenError:
    code = ""
    message = resp.text[:300]
    details = None
    try:
        err = resp.json().get("error", {})
        code = err.get("code", "")
        message = err.get("message", message)
        details = err.get("fields") or err.get("details")
    except Exception:
        pass
    if resp.status_code == 401:
        code = code or "unauthorized"
    if resp.status_code == 403:
        code = code or "insufficient_scope"
    if resp.status_code == 422:
        code = code or "validation_failed"
    return BigBenError(message, status=resp.status_code, code=code, details=details)


_client: BigBenV2Client | None = None


def get_bigben_v2() -> BigBenV2Client:
    """Singleton-клиент; конфигурация из env (BIGBEN_PUBLIC_API_*)."""
    global _client
    if _client is None:
        _client = BigBenV2Client(
            base_url=settings.BIGBEN_PUBLIC_API_BASE,
            api_key=settings.BIGBEN_PUBLIC_API_KEY,
        )
    return _client
