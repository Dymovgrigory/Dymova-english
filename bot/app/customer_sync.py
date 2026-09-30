"""Карточка клиента: данные диалога и сопоставление с учениками BigBen.

Раньше номер, названный клиентом в чате, оставался в диалоге, а админка
искала ученика BigBen только по телефону карточки — из 128 карточек телефон
был у 8, и почти везде значилось «ученик не найден» (разбор прода 30.09).

Правило одно: заполняем ТОЛЬКО пустые поля. Всё, что менеджер поправил
руками, остаётся как есть.
"""
from __future__ import annotations

import logging

from app import crm_ingest, crm_store, identify
from app.memory import Conversation
from app.platform import bb_store

logger = logging.getLogger(__name__)

STUDENT_TAG = "ученик школы"
MAX_CANDIDATES = 5


def _digits10(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())[-10:]


def _hint(phone: str) -> str:
    """Подсказка для менеджера: номер целиком в списке кандидатов не светим."""
    tail = _digits10(phone)[-4:]
    return f"…{tail}" if tail else ""


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


def _students_for(customer: dict) -> list[dict]:
    """Ученики по телефону карточки и по ручной привязке менеджера."""
    found: dict[int, dict] = {}
    phone = (customer.get("phone") or "").strip()
    if phone:
        for row in bb_store.find_students_by_phone(phone):
            found[row["id"]] = row
    for student_id in (customer.get("metadata") or {}).get("bb_linked_ids", []):
        row = _student_by_id(int(student_id))
        if row:
            found.setdefault(row["id"], row)
    return list(found.values())


def _student_by_id(student_id: int) -> dict | None:
    rows = bb_store._rows("SELECT * FROM bb_students WHERE id = ?", (student_id,))
    return dict(rows[0]) if rows else None


def enrich_from_bigben(customer_id: int) -> list[dict]:
    """Дописывает пустые поля карточки из BigBen и ставит тег «ученик школы»."""
    customer = crm_store.get_customer(customer_id)
    if customer is None:
        return []
    students = _students_for(customer)
    if not students:
        return []
    fios = [s["fio"] for s in students if s.get("fio")]
    email = next((s["email"] for s in students if s.get("email")), "")
    crm_store.fill_customer_empty(
        customer_id, child_name=", ".join(fios), email=email
    )
    crm_store.set_customer_metadata(customer_id, "bb_student_ids", [s["id"] for s in students])
    crm_store.assign_tag(customer_id, STUDENT_TAG)
    return students


def bigben_status(customer_id: int) -> dict:
    """Что знаем про связь карточки с BigBen — и почему, если не знаем."""
    customer = crm_store.get_customer(customer_id)
    if customer is None:
        return {"reason": "no_customer", "students": []}
    students = _students_for(customer)
    if students:
        return {"reason": "linked", "students": students}
    if not (customer.get("phone") or "").strip():
        return {"reason": "no_phone", "students": []}
    return {"reason": "phone_not_in_bigben", "students": []}


def bb_candidates(customer_id: int, limit: int = MAX_CANDIDATES) -> list[dict]:
    """Возможные ученики по имени ребёнка/родителя — для ручной привязки."""
    customer = crm_store.get_customer(customer_id)
    if customer is None:
        return []
    names = [n for n in (customer.get("child_name"), customer.get("name")) if n]
    tokens = {t for n in names for t in n.split() if len(t) >= 2}
    if not tokens:
        return []
    linked = {s["id"] for s in _students_for(customer)}
    scored: list[tuple[int, dict]] = []
    for row in bb_store._rows("SELECT * FROM bb_students"):
        if row["id"] in linked or not row["fio"]:
            continue
        score = sum(1 for t in tokens if identify.name_matches(t, row["fio"]))
        if score:
            scored.append((score, dict(row)))
    scored.sort(key=lambda item: (-item[0], item[1]["fio"]))
    return [
        {"id": r["id"], "fio": r["fio"], "email": r.get("email", ""),
         "phone_hint": _hint(r.get("phone", "")), "score": score}
        for score, r in scored[:limit]
    ]


def link_bigben(customer_id: int, student_id: int, actor: str = "admin") -> bool:
    """Ручная привязка карточки к ученику BigBen: дополняет пустые поля."""
    customer = crm_store.get_customer(customer_id)
    student = _student_by_id(int(student_id))
    if customer is None or student is None:
        return False
    linked = list((customer.get("metadata") or {}).get("bb_linked_ids", []))
    if student["id"] not in linked:
        linked.append(student["id"])
    crm_store.set_customer_metadata(customer_id, "bb_linked_ids", linked)
    crm_store.fill_customer_empty(
        customer_id, phone=student.get("phone", ""), email=student.get("email", ""),
        child_name=student.get("fio", ""),
    )
    crm_store.audit(actor, "link_bigben", "customer", customer_id,
                    after={"bb_student_id": student["id"]})
    enrich_from_bigben(customer_id)
    return True


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
