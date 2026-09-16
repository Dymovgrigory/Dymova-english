"""Клиент API Подпислона (простая электронная подпись документов).

Базовый URL `https://podpislon.ru/integration`, авторизация заголовком
`X-Api-Key`, лимит 4 запроса в секунду на ключ.

Контракт подтверждён разведкой по живому аккаунту 2026-09-16:
- POST /                     — список документов, `ids` фильтрует по id;
- POST /get-file             — pdf документа в base64, поле `id`;
- GET  /v2/contacts/{id}      — карточка клиента, `expand=passport,custom_fields`;
- GET  /v2/templates          — шаблоны конструктора (только чтение).

Вебхуки приходят как `application/x-www-form-urlencoded` с полями EVENT,
COMPANY_ID, SIGNATURE и специфичными для события. Алгоритм SIGNATURE сервис
не документирует, поэтому событию мы не доверяем: любой пришедший FILE_ID
перепроверяется здесь же запросом под нашим ключом (см. `get_document`).

Кастомные поля контакта заведены в ЛК школы и адресуются по кодам — они
в CUSTOM_FIELDS ниже.
"""
from __future__ import annotations

import base64
import binascii
import logging
import re

import httpx

from app.config import settings
from app.platform.podpislon_sync import crm_date

logger = logging.getLogger(__name__)

BASE = "https://podpislon.ru/integration"

# Коды кастомных полей контакта в кабинете школы (ЛК → Настройки → Поля).
CUSTOM_FIELDS = {
    "child_fio": "ufc_132716a199f8c5fc18",
    "child_birthday": "ufc_1327168872c3c34197",
    "email": "ufc_132716916fda978041",
}

# Статусы документа: 15 «Отправлен», 20 «Просмотрен», 30 «Подписан».
STATUS_SIGNED = 30


class PodpislonError(Exception):
    pass


def configured() -> bool:
    return bool(settings.PODPISLON_API_KEY)


async def _request(method: str, path: str, *, json_body: dict | None = None,
                   data: dict | None = None) -> dict | list:
    if not configured():
        raise PodpislonError("PODPISLON_API_KEY не задан")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(
                method, BASE + path, json=json_body, data=data,
                headers={
                    "X-Api-Key": settings.PODPISLON_API_KEY,
                    "Accept": "application/json",
                })
    except httpx.HTTPError as exc:
        raise PodpislonError(f"сеть: {exc}") from exc
    if resp.status_code == 429:
        raise PodpislonError("429: превышен лимит 4 запроса/сек")
    if resp.status_code >= 400:
        raise PodpislonError(f"{resp.status_code}: {resp.text[:200]}")
    return resp.json()


async def get_document(file_id: int) -> dict | None:
    """Карточка документа по id. None, если такого документа у нас нет.

    Это и есть проверка подлинности вебхука: событие про чужой или
    выдуманный документ здесь не подтвердится.
    """
    items = await _request("POST", "/?page=1", json_body={"ids": [file_id]})
    for doc in items if isinstance(items, list) else []:
        if int(doc.get("id") or 0) == int(file_id):
            return doc
    return None


async def get_contact(contact_id: int) -> dict:
    """Карточка клиента вместе с паспортом и кастомными полями."""
    data = await _request(
        "GET", f"/v2/contacts/{contact_id}?expand=passport,custom_fields")
    return data if isinstance(data, dict) else {}


async def download_pdf(file_id: int) -> bytes:
    """Подписанный документ. Сервис отдаёт base64, возвращаем байты."""
    data = await _request("POST", "/get-file", data={"id": file_id})
    if not isinstance(data, dict) or not data.get("status"):
        raise PodpislonError(f"get-file вернул {str(data)[:200]}")
    try:
        return base64.b64decode(data.get("result") or "")
    except (ValueError, TypeError) as exc:
        raise PodpislonError(f"битый base64: {exc}") from exc


def is_signed(doc: dict) -> bool:
    return str(doc.get("status") or "") == str(STATUS_SIGNED)


def contact_id_of(doc: dict) -> int | None:
    """Id клиента, которому отправлен документ.

    В списке документов у клиента нет поля id: он зашит в `sid` (base64 от
    числа) и в ссылку на подпись `.../sign/pack/<id>/<код>`.
    """
    contacts = doc.get("contacts") or []
    person = contacts[0] if contacts and isinstance(contacts, list) else doc.get("contact")
    if not isinstance(person, dict):
        return None
    if str(person.get("id") or "").isdigit():
        return int(person["id"])
    try:
        decoded = base64.b64decode(str(person.get("sid") or ""), validate=True).decode()
        if decoded.isdigit():
            return int(decoded)
    except (binascii.Error, UnicodeDecodeError):
        pass
    link = re.search(r"/sign/pack/(\d+)/", str(person.get("link") or ""))
    return int(link.group(1)) if link else None


def _custom(contact: dict, key: str) -> str:
    """Значение кастомного поля по нашему коду."""
    code = CUSTOM_FIELDS[key]
    for field in contact.get("custom_fields") or []:
        if field.get("code") == code:
            return str(field.get("value") or "").strip()
    return ""


def _passport_date(value: object) -> str:
    """Дата выдачи внутри текстовой строки паспорта — по-русски, ДД.ММ.ГГГГ."""
    iso = crm_date(value)
    return ".".join(reversed(iso.split("-"))) if iso else ""


def to_crm_fields(contact: dict) -> dict:
    """Контакт Подпислона → поля карточки ученика BigBen.

    Паспорт собирается в одну строку: в CRM под него одно текстовое поле
    «Паспортные данные ученика (или родителя)».
    """
    passport = contact.get("passport") or {}
    parts = [
        str(passport.get("number") or "").strip(),
        f"выдан {str(passport.get('issued_by') or '').strip()}"
        if passport.get("issued_by") else "",
        _passport_date(passport.get("issued_at")),
        f"код подразделения {str(passport.get('issuer_code') or '').strip()}"
        if passport.get("issuer_code") else "",
    ]
    parent_fio = " ".join(x for x in (
        contact.get("last_name"), contact.get("name"), contact.get("surname"),
    ) if x)

    return {
        "fio": _custom(contact, "child_fio"),
        "birthday": crm_date(_custom(contact, "child_birthday")),
        "parentname": parent_fio.strip(),
        "parent_phone": str(contact.get("phone") or "").strip(),
        "parent_birthday": crm_date(passport.get("birth_date")),
        "passport": ", ".join(p for p in parts if p),
        "home_address": str(passport.get("address") or "").strip(),
        "email": (str(contact.get("email") or "").strip()
                  or _custom(contact, "email")),
    }
