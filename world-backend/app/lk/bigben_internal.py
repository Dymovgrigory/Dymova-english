"""Внутренний API пульта BigBen (platformapi.bigbencrm.ru/public/api) для ЛК.

Тот же API, через который работает пульт lk.bigbencrm.ru и бот создаёт карточки учеников.
Нужен ЛК для двух вещей, которых нет в публичном API v1:
- «Данные для входа» ученика: в карточке поля phone + password_raw (ученик)
  и parent_phone + parent_password (родитель). Пульт сохраняет их через
  PUT /user/students/{id} (разведка бандла пульта и карточки 2026-11-05);
- создание карточки ученика: POST /user/students (как при записи в группу с сайта/бота).

Доступ (2026-11-05, чтобы вход в ЛК не зависел от срока жизни токена):
- основной путь — учётная запись сотрудника пульта (BIGBEN_LK_LOGIN / BIGBEN_LK_PASSWORD):
  ЛК сам входит в пульт (POST auth/login, как форма входа lk.bigbencrm.ru), продлевает
  сессию (POST auth/refresh) и при ответе 401 входит заново — токен обновляется без людей;
- запасной — постоянный BIGBEN_INTERNAL_TOKEN (тот же, что у бота).
"""
from __future__ import annotations

import hmac
import logging
import os
import threading
import time
from datetime import datetime, timezone

import httpx

log = logging.getLogger("world.lk.bigben_internal")

BASE = os.environ.get("BIGBEN_INTERNAL_BASE", "https://platformapi.bigbencrm.ru/public/api").strip()
PHONE_FIELDS = ("phone", "main_phone", "phone1", "parent_phone")


class BigBenInternalError(Exception):
    pass


HEADERS = {
    # без этих заголовков пульт на ошибку отвечает редиректом на страницу входа
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}
_session: dict = {"token": "", "refresh": "", "expires": 0.0}
_lock = threading.Lock()


def _login_creds() -> tuple[str, str]:
    return (os.environ.get("BIGBEN_LK_LOGIN", "").strip(), os.environ.get("BIGBEN_LK_PASSWORD", ""))


def _static_token() -> str:
    return os.environ.get("BIGBEN_INTERNAL_TOKEN", "").strip()


def configured() -> bool:
    login, password = _login_creds()
    return bool((login and password) or _static_token())


def _parse_exp(value) -> float:
    if not value:
        return time.time() + 12 * 3600
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time() + 12 * 3600


def _auth_post(client: httpx.Client, path: str, body: dict) -> dict:
    r = client.post(BASE + "/" + path, json=body, headers=HEADERS)
    if r.status_code >= 400:
        raise BigBenInternalError(f"{path}: HTTP {r.status_code}")
    data = r.json()
    data = data.get("data", data) if isinstance(data, dict) else {}
    if not isinstance(data, dict) or not data.get("token"):
        raise BigBenInternalError(f"{path}: нет токена в ответе")
    return data


def _new_session(client: httpx.Client) -> None:
    """Вход в пульт учётной записью сотрудника; сначала пробуем продлить сессию."""
    if _session["refresh"]:
        try:
            d = _auth_post(client, "auth/refresh", {"refreshToken": _session["refresh"]})
            _session.update(token=d["token"], expires=_parse_exp(d.get("expiresAt")))
            return
        except (BigBenInternalError, httpx.HTTPError, ValueError) as exc:
            log.info("bigben: продление сессии не удалось (%s), входим заново", exc)
    login, password = _login_creds()
    d = _auth_post(client, "auth/login", {"identifier": login, "password": password, "remember": True})
    _session.update(token=d["token"], refresh=d.get("refreshToken") or "", expires=_parse_exp(d.get("expiresAt")))
    log.info("bigben: вошли в пульт, сессия до %s", datetime.fromtimestamp(_session["expires"], timezone.utc))


def _bearer(client: httpx.Client, force: bool = False) -> str:
    login, password = _login_creds()
    if not (login and password):
        return _static_token()
    with _lock:
        if force or not _session["token"] or _session["expires"] - time.time() < 600:
            _new_session(client)
        return _session["token"]


def _request(method: str, path: str, json_body: dict | None = None) -> dict:
    if not configured():
        raise BigBenInternalError("нет доступа к пульту BigBen (BIGBEN_LK_LOGIN/BIGBEN_LK_PASSWORD или BIGBEN_INTERNAL_TOKEN)")
    try:
        with httpx.Client(timeout=15) as client:
            r = client.request(method, BASE + path, json=json_body,
                               headers={**HEADERS, "Authorization": f"Bearer {_bearer(client)}"})
            if r.status_code == 401 and all(_login_creds()):
                # токен отозван или истёк раньше срока — входим заново и повторяем один раз
                r = client.request(method, BASE + path, json=json_body,
                                   headers={**HEADERS, "Authorization": f"Bearer {_bearer(client, force=True)}"})
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


def health() -> dict:
    """Проверка доступа к пульту (для мониторинга): ок/ошибка без персональных данных."""
    try:
        _request("GET", "/user/students?per_page=1")
        return {"ok": True, "mode": "login" if all(_login_creds()) else "token"}
    except BigBenInternalError as exc:
        return {"ok": False, "error": str(exc)[:80]}


def _group_item(g) -> dict | None:
    if isinstance(g, int) or (isinstance(g, str) and g.isdigit()):
        return {"id": int(g), "caption": ""}
    if isinstance(g, dict):
        gid = g.get("id") or g.get("group_id")
        if gid and str(gid).isdigit():
            cap = g.get("caption") or g.get("name") or g.get("title") or g.get("group_name") or ""
            return {"id": int(gid), "caption": str(cap)}
    return None


def student_groups(student_id: int) -> list[dict]:
    """Активные группы ученика из карточки пульта (публичный API v1 их не отдаёт)."""
    data = _request("GET", f"/user/students/{int(student_id)}")
    st = data.get("data", data) if isinstance(data, dict) else {}
    raw = st.get("active_groups") if isinstance(st, dict) else None
    if isinstance(raw, dict):
        raw = list(raw.values())
    out, seen = [], set()
    for g in raw or []:
        item = _group_item(g)
        if item and item["id"] not in seen:
            seen.add(item["id"])
            out.append(item)
    return out
