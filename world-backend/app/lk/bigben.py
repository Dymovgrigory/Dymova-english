"""Клиент BigBen Public API v1 для ЛК.

Использует BIGBEN_PUBLIC_API_KEY (тот же ключ, что и у платформенного слоя бота).
Список учеников кэшируется в памяти с TTL — ЛК ищет детей по номеру телефона
родителя; CRM остаётся мастером данных (ТЗ §3).
"""
from __future__ import annotations

import logging
import os
import time

import httpx

log = logging.getLogger("world.lk.bigben")

BASE_URL = os.environ.get(
    "BIGBEN_PUBLIC_API_BASE", "https://platformapi.bigbencrm.ru/api/public/v1"
).strip()
API_KEY = os.environ.get("BIGBEN_PUBLIC_API_KEY", "").strip()

CACHE_TTL_SEC = 15 * 60
_students_cache: tuple[float, list[dict]] | None = None
_lessons_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}


class BigBenUnavailable(Exception):
    pass


def configured() -> bool:
    return bool(API_KEY)


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=20.0,
    )


def _iter_pages(client: httpx.Client, path: str, params: dict | None = None) -> list[dict]:
    params = dict(params or {})
    params.setdefault("per_page", 100)
    page = 1
    out: list[dict] = []
    while True:
        params["page"] = page
        r = client.get(path, params=params)
        if r.status_code == 429:
            retry_after = float(r.headers.get("Retry-After", "5"))
            time.sleep(max(1.0, retry_after))
            continue
        if r.status_code >= 400:
            raise BigBenUnavailable(f"BigBen {path}: HTTP {r.status_code}")
        payload = r.json()
        data = payload.get("data") or []
        out.extend(data)
        total = (payload.get("meta") or {}).get("total", len(data))
        if page * params["per_page"] >= total or not data:
            return out
        page += 1


def list_students(*, force: bool = False) -> list[dict]:
    """Все ученики CRM (кэш 15 мин). Каждый: id, fio, phone, active_groups."""
    global _students_cache
    if not configured():
        return []
    now = time.monotonic()
    if not force and _students_cache and now - _students_cache[0] < CACHE_TTL_SEC:
        return _students_cache[1]
    with _client() as client:
        students = _iter_pages(client, "/students")
    _students_cache = (now, students)
    return students


def students_by_phone(phone_e164: str) -> list[dict]:
    """Ученики, чей телефон совпадает с нормализованным номером родителя.

    Телефон ребёнка в CRM при отсутствии телефона родителя считается
    телефоном родителя (решение владельца, ТЗ §7).
    """
    digits = "".join(ch for ch in phone_e164 if ch.isdigit())
    out = []
    for s in list_students():
        raw = (s.get("phone") or "").strip()
        s_digits = "".join(ch for ch in raw if ch.isdigit())
        if s_digits.startswith("8"):
            s_digits = "7" + s_digits[1:]
        if len(s_digits) == 10:
            s_digits = "7" + s_digits
        if s_digits and s_digits == digits:
            out.append(s)
    return out


def lessons(date_from: str, date_to: str) -> list[dict]:
    """Занятия окном дат (кэш 10 мин).

    Каждое: id, date (YYYY-MM-DD), starts_at/ends_at (ISO UTC), group
    {id, caption}, filial {id, caption}. Педагогов и тем в публичном API нет.
    """
    if not configured():
        return []
    key = (date_from, date_to)
    now = time.monotonic()
    cached = _lessons_cache.get(key)
    if cached and now - cached[0] < 600:
        return cached[1]
    with _client() as client:
        items = _iter_pages(client, "/lessons", {"from": date_from, "to": date_to})
    _lessons_cache[key] = (now, items)
    # не держим больше 20 окон
    while len(_lessons_cache) > 20:
        _lessons_cache.pop(next(iter(_lessons_cache)))
    return items


def groups_by_ids(group_ids: set[int]) -> dict[int, dict]:
    """{group_id: {id, caption}} для подписей групп в профилях."""
    out: dict[int, dict] = {}
    if not configured() or not group_ids:
        return out
    with _client() as client:
        groups = _iter_pages(client, "/groups")
    for g in groups:
        gid = g.get("id")
        if gid in group_ids:
            out[gid] = {"id": gid, "caption": g.get("caption", "")}
    return out


def invalidate_cache() -> None:
    global _students_cache
    _students_cache = None
    _lessons_cache.clear()


def create_lead(name: str, phone: str, comment: str = "", source: str = "Личный кабинет") -> int | None:
    """Заявка в BigBen (POST /leads, public API v1). Возвращает id лида."""
    import uuid

    body = {"name": name[:255], "phone": phone[:50], "source": source[:255], "comment": comment[:800]}
    with _client() as client:
        r = client.post("/leads", json=body, headers={"Idempotency-Key": uuid.uuid4().hex})
    if r.status_code >= 400:
        raise BigBenUnavailable(f"BigBen /leads: HTTP {r.status_code}")
    data = (r.json() or {}).get("data") or {}
    return data.get("id")
