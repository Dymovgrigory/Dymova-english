"""Карточка клиента: данные диалога и точное сопоставление с учениками BigBen.

Раньше номер, названный клиентом в чате, оставался в диалоге, а админка
искала ученика BigBen только по телефону карточки — из 128 карточек телефон
был у 8, и почти везде значилось «ученик не найден» (разбор прода 30.09).

Правила:
1. Сопоставление ТОЛЬКО по номеру: это любой из телефонов карточки ученика
   (свой, родителя, второй родитель). Имён для догадок не используем: у
   родителя в BigBen чаще всего записано одно имя («Ольга»), а в мессенджере
   он подписан как угодно. Нет номера — нет связи, и бот просит номер.
2. Все ученики на этом номере — братья и сёстры одной семьи — связываются
   вместе.
3. Заполняем ТОЛЬКО пустые поля: что менеджер поправил руками, остаётся.
"""
from __future__ import annotations

import logging

from app import crm_ingest, crm_store
from app.memory import Conversation
from app.platform import bb_cards, bb_store

logger = logging.getLogger(__name__)

STUDENT_TAG = "ученик школы"
FORMER_STUDENT_TAG = "бывший ученик"


def sync_conversation(conv: Conversation) -> int | None:
    """Переносит ФИО, ребёнка, возраст и телефон из диалога в карточку."""
    lead = conv.lead
    fields = {
        "name": lead.fio_parent,
        "child_name": lead.fio_child,
        "child_age": lead.age or lead.birthday,
        "phone": lead.phone,
    }
    if not any(fields.values()):
        return None
    channel = crm_ingest._channel_for_user(conv.user_id)
    customer_id = crm_store.upsert_customer_for_identity(channel, conv.user_id, **fields)
    enrich_from_bigben(customer_id)
    return customer_id


def _public_api_students(phone: str) -> list[dict]:
    """Запасной путь: справочник карточек ещё не синхронизирован (нет токена
    пульта) — берём учеников из публичного API v1, там только ФИО и email."""
    return [
        {"id": r["id"], "fio": r["fio"], "parentname": "", "age": "", "email": r.get("email", ""),
         "filial": "", "is_active": True, "archived": False, "groups": [], "phones": [],
         "debt_rub": 0, "balance_rub": 0, "important_comment": "", "birthday": ""}
        for r in bb_store.find_students_by_phone(phone)
    ]


def students_for_phone(phone: str) -> list[dict]:
    """Все ученики BigBen с этим номером (точное совпадение)."""
    phone = (phone or "").strip()
    if not phone:
        return []
    if bb_cards.count():
        return bb_cards.find_by_phone(phone)
    return _public_api_students(phone)


def _unique(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen


def enrich_from_bigben(customer_id: int) -> list[dict]:
    """Дописывает пустые поля карточки из BigBen и ставит тег."""
    customer = crm_store.get_customer(customer_id)
    if customer is None:
        return []
    students = students_for_phone(customer.get("phone") or "")
    if not students:
        return []
    crm_store.fill_customer_empty(
        customer_id,
        name=", ".join(_unique([s["parentname"] for s in students])),
        child_name=", ".join(_unique([s["fio"] for s in students])),
        child_age=", ".join(_unique([s["age"] for s in students])),
        email=next((s["email"] for s in students if s["email"]), ""),
    )
    crm_store.set_customer_metadata(customer_id, "bb_student_ids", [s["id"] for s in students])
    current = any(not s["archived"] for s in students)
    crm_store.assign_tag(customer_id, STUDENT_TAG if current else FORMER_STUDENT_TAG)
    return students


def bigben_status(customer_id: int) -> dict:
    """Что знаем про связь карточки с BigBen — и почему, если не знаем."""
    customer = crm_store.get_customer(customer_id)
    if customer is None:
        return {"reason": "no_customer", "students": []}
    phone = (customer.get("phone") or "").strip()
    if not phone:
        return {"reason": "no_phone", "students": []}
    students = students_for_phone(phone)
    if students:
        return {"reason": "linked", "students": students}
    return {"reason": "phone_not_in_bigben", "students": []}


def _all_conversations() -> list[Conversation]:
    from app.memory import get_store

    return get_store().all_conversations()


def backfill() -> dict:
    """Разовый проход по всем диалогам и карточкам (после выкладки на прод)."""
    synced = failed = 0
    for conv in _all_conversations():
        try:
            if sync_conversation(conv):
                synced += 1
        except Exception:
            failed += 1
            logger.exception("customer_sync: сбой переноса user=%s", conv.user_id)
    enriched = 0
    for row in crm_store.get_conn().execute(
        "SELECT id FROM customers WHERE phone != '' AND status != 'archived'"
    ).fetchall():
        if enrich_from_bigben(int(row["id"])):
            enriched += 1
    return {"synced": synced, "failed": failed, "enriched": enriched}
