"""Внутренний API пульта владельца (platformapi.bigbencrm.ru/public/api).

Публичный API v1 не умеет создавать карточку ученика — только лида,
демо-урок и зачисление существующего ученика. Поэтому создание/поиск
карточки делаем через внутренний API пульта (Bearer-токен из localStorage
пульта владельца, срок жизни токена ~год; хранится в BIGBEN_INTERNAL_TOKEN).

Эндпоинты подсмотрены в живом пульте (перехват XHR формы «Добавить ученика»):
- GET  /public/api/user/students?search=<строка>&per_page=N — поиск;
- POST /public/api/user/students — создание карточки.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE = "https://platformapi.bigbencrm.ru/public/api"


class BigBenInternalError(Exception):
    pass


def configured() -> bool:
    return bool(settings.BIGBEN_INTERNAL_TOKEN)


async def _request(method: str, path: str, json_body: dict | None = None) -> dict:
    if not configured():
        raise BigBenInternalError("BIGBEN_INTERNAL_TOKEN не задан")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(
                method, BASE + path, json=json_body,
                headers={"Authorization": f"Bearer {settings.BIGBEN_INTERNAL_TOKEN}"})
    except httpx.HTTPError as exc:
        raise BigBenInternalError(f"сеть: {exc}") from exc
    if resp.status_code >= 400:
        raise BigBenInternalError(f"{resp.status_code}: {resp.text[:200]}")
    return resp.json()


def _digits(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())[-10:]


async def find_student_by_phone(phone: str) -> dict | None:
    """Карточка ученика по телефону (его или родителя). None, если не найден."""
    digits = _digits(phone)
    if not digits:
        return None
    data = await _request("GET", f"/user/students?search={digits}&per_page=10")
    for st in data.get("data") or []:
        for field in ("phone", "parent_phone", "main_phone", "phone1"):
            if _digits(str(st.get(field) or "")) == digits:
                return st
    return None


async def create_student(*, fio: str, phone: str, parentname: str = "",
                         parent_phone: str = "", filial_id: int | None = None,
                         birthday: str = "", comment: str = "") -> dict:
    """Создаёт карточку ученика. Возвращает {"id": ..., "fio": ...}."""
    body = {
        "fio": fio.strip(),
        "filial_id": filial_id,
        "important_comment": (comment or "")[:500],
        "parentname": parentname.strip(),
        "parent_phone": parent_phone,
        "parent_gender": "",
        "birthday": birthday or "",
        "ages": None,
        "phone": phone,
        "email": "",
        "home_address": "",
        "passport": "",
    }
    data = await _request("POST", "/user/students", json_body=body)
    student = data.get("data") or {}
    if not student.get("id"):
        raise BigBenInternalError(f"неожиданный ответ создания: {data!r}"[:200])
    return student


async def find_or_create_student(**kwargs) -> dict:
    """Дедупликация по телефону: существующая карточка или новая."""
    found = await find_student_by_phone(kwargs.get("phone", ""))
    if found:
        return found
    parent_phone = kwargs.get("parent_phone", "")
    if parent_phone and parent_phone != kwargs.get("phone"):
        found = await find_student_by_phone(parent_phone)
        if found:
            return found
    return await create_student(**kwargs)
