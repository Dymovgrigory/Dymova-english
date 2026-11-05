"""Внутренний API пульта BigBen (platformapi.bigbencrm.ru/public/api) для ЛК.

Тот же API, через который работает пульт lk.bigbencrm.ru и бот создаёт карточки учеников.
Нужен ЛК для двух вещей, которых нет в публичном API v1:
- «Данные для входа» ученика: в карточке поля phone + password_raw (ученик)
  и parent_phone + parent_password (родитель). Пульт сохраняет их через
  PUT /user/students/{id} (разведка бандла пульта и карточки 2026-11-05);
- создание карточки ученика: POST /user/students (как при записи в группу с сайта/бота).

Токен — BIGBEN_INTERNAL_TOKEN (Bearer из пульта владельца), тот же, что у бота.
"""
from __future__ import annotations

import hmac
import logging
import os

import httpx

log = logging.getLogger("world.lk.bigben_internal")

BASE = os.environ.get("BIGBEN_INTERNAL_BASE", "https://platformapi.bigbencrm.ru/public/api").strip()
PHONE_FIELDS = ("phone", "main_phone", "phone1", "parent_phone")


class BigBenInternalError(Exception):
    pass


def _token() -> str:
    return os.environ.get("BIGBEN_INTERNAL_TOKEN", "").strip()


def configured() -> bool:
    return bool(_token())


def _request(method: str, path: str, json_body: dict | None = None) -> dict:
    if not configured():
        raise BigBenInternalError("BIGBEN_INTERNAL_TOKEN не задан")
    try:
        with httpx.Client(timeout=15) as client:
            r = client.request(method, BASE + path, json=json_body, headers={
                "Authorization": f"Bearer {_token()}",
                # без этих заголовков пульт на ошибку отвечает редиректом на страницу входа
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            })
    except httpx.HTTPError as exc:
        raise BigBenInternalError(f"сеть: {exc}") from exc
    if r.status_code >= 400:
        raise BigBenInternalError(f"HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError as exc:
        raise BigBenInternalError("не JSON") from exc


def digits10(phone: str) -> str:
    d = "".join(c for c in str(phone or "") if c.isdigit())
    return d[-10:] if len(d) >= 10 else ""


def find_students_by_phone(phone: str) -> list[dict]:
    """Все карточки, где этот номер — телефон ученика или родителя (в семье бывает несколько детей)."""
    d = digits10(phone)
    if not d:
        return []
    data = _request("GET", f"/user/students?search={d}&per_page=50")
    rows = data.get("data") or []
    return [st for st in rows if isinstance(st, dict) and not st.get("deleted")
            and any(digits10(st.get(f)) == d for f in PHONE_FIELDS)]


def _same(a: str, b: str) -> bool:
    return bool(a) and bool(b) and hmac.compare_digest(str(a).encode(), str(b).encode())


def check_login(phone: str, password: str) -> list[dict]:
    """Карточки, к которым подходят телефон и пароль из «Данных для входа».

    Пара ученика: phone (или main_phone) + password_raw. Пара родителя: parent_phone + parent_password.
    Возвращает все карточки с этим номером, если пароль подошёл хотя бы к одной; иначе [].
    """
    d = digits10(phone)
    students = find_students_by_phone(phone)
    ok = False
    for st in students:
        if (digits10(st.get("phone")) == d or digits10(st.get("main_phone")) == d) and _same(password, st.get("password_raw")):
            ok = True
        if digits10(st.get("parent_phone")) == d and _same(password, st.get("parent_password")):
            ok = True
    return students if ok else []


def create_student(*, fio: str, phone: str, parentname: str, comment: str = "", birthday: str = "") -> dict:
    body = {
        "fio": fio.strip(), "filial_id": None, "important_comment": (comment or "")[:500],
        "parentname": parentname.strip(), "parent_phone": phone, "parent_gender": "",
        "birthday": birthday or "", "ages": None, "phone": phone, "email": "",
        "home_address": "", "passport": "",
    }
    data = _request("POST", "/user/students", body)
    st = data.get("data") or {}
    if not st.get("id"):
        raise BigBenInternalError("карточка не создана")
    return st


def set_login_data(student_id: int, phone: str, password: str) -> None:
    """Записать «Данные для входа»: телефон и пароль ученика и родителя (видны администратору в карточке)."""
    _request("PUT", f"/user/students/{int(student_id)}",
             {"phone": phone, "password_raw": password, "parent_phone": phone, "parent_password": password})
