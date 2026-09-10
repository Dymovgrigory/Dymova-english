"""Внутренний API пульта владельца (platformapi.bigbencrm.ru/public/api).

Публичный API v1 не умеет создавать карточку ученика — только лида,
демо-урок и зачисление существующего ученика. Поэтому создание/поиск
карточки делаем через внутренний API пульта (Bearer-токен из localStorage
пульта владельца, срок жизни токена ~год; хранится в BIGBEN_INTERNAL_TOKEN).

Он же — единственный способ записать деньги: v1 платежи только читает.

Эндпоинты подсмотрены в живом пульте (перехват XHR формы «Добавить ученика»)
и подтверждены разведкой контракта 2026-09-10:
- GET  /public/api/user/students?search=<строка>&per_page=N — поиск;
- POST /public/api/user/students — создание карточки;
- POST /public/api/user/payments — счёт ученика (виден как оплата в v1);
- POST /public/api/user/incomes — поступление в кассу.
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
                headers={
                    "Authorization": f"Bearer {settings.BIGBEN_INTERNAL_TOKEN}",
                    # Без этих заголовков пульт на ошибку валидации отвечает
                    # 302 на страницу входа вместо JSON — сбой выглядит как
                    # успех с пустым телом.
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                })
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


# --- Деньги: счёт (начисление) и доход (касса) ---
#
# Public API v1 платежи только читает. Пульт умеет их создавать:
#   POST /user/payments — счёт ученика (user_id, group_id, type, summ,
#     bycard, date). Именно эта запись видна как оплата в Public API v1;
#     внутреннее поле summ_paid CRM для признания оплаты не использует
#     (у платежей, заведённых самим пультом, оно тоже 0.00).
#   POST /user/incomes — поступление в кассу (type_id, summ, bycard,
#     filial_id); связывается со счётом через user_payment_id.
#
# Коды подтверждены на живых данных школы:
#   bycard: 0 — наличные, 4 — из приложения (онлайн), 7 — расчётный счёт,
#           10 — другое;
#   type_id (доход): 1 — оплата обучения, 2 — продажа УМК, 10 — внесение
#           наличных, 11 — другое, 12 — орг. взнос.

async def create_payment(*, user_id: int, group_id: int, summ: int,
                         bycard: int, date: str, comment: str = "",
                         type_: int = 0) -> dict:
    """Счёт ученика. Возвращает {"payment_id": ...}."""
    body = {"user_id": user_id, "group_id": group_id, "type": type_,
            "summ": summ, "bycard": bycard, "date": date}
    if comment:
        body["comment"] = comment[:500]
    data = await _request("POST", "/user/payments", json_body=body)
    if not data.get("payment_id"):
        raise BigBenInternalError(f"счёт не создан: {data!r}"[:200])
    return data


async def create_income(*, type_id: int, summ: int, bycard: int,
                        filial_id: int, user_payment_id: int | None = None,
                        comment: str = "") -> dict:
    """Поступление в кассу. Возвращает карточку дохода с id.

    Поле date запрос не принимает: без привязки к счёту доход датируется
    моментом создания, а с `user_payment_id` — наследует дату счёта.
    Поэтому доход пишем сразу после подтверждения оплаты, не задним числом.

    ВАЖНО: `user_payment_id` не передавать. Привязка к счёту делает доход
    зависимым — отмена счёта каскадно отменяет и доход
    (cancel_reason: «Удаление счёта»), и деньги молча исчезают из кассы.
    """
    body: dict = {"type_id": type_id, "summ": summ, "bycard": bycard,
                  "filial_id": filial_id}
    if user_payment_id:
        body["user_payment_id"] = user_payment_id
    if comment:
        body["comment"] = comment[:500]
    data = await _request("POST", "/user/incomes", json_body=body)
    income = data.get("data") or {}
    if not income.get("id"):
        raise BigBenInternalError(f"доход не создан: {data!r}"[:200])
    return income
