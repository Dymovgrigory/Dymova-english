"""Перенос данных из Подпислона в карточку ученика BigBen.

Здесь чистая логика без сети: как из контакта Подпислона собрать поля для
CRM, как найти нужную карточку и что в ней можно трогать. Сетевые вызовы —
в `podpislon.py` (Подпислон) и `bigben_internal.py` (CRM).

Правило сопоставления задано школой: совпасть должны И фамилия с именем
ребёнка, И телефон. При нуле совпадений или неоднозначности карточка не
трогается — такие случаи уходят администратору руками.
"""
from __future__ import annotations

# Поля карточки ученика, куда складываем данные анкеты.
# Ключ — поле CRM, значение — как достаётся из контакта Подпислона.
CRM_FIELDS = (
    "fio", "birthday", "parentname", "parent_phone", "parent_birthday",
    "passport", "home_address", "email",
)

# Телефон ученика может лежать в любом из этих полей карточки.
PHONE_FIELDS = ("parent_phone", "phone", "phone1", "main_phone")


def normalize_phone(value: object) -> str:
    """Последние 10 цифр: +7 (925) 880-33-33, 8 925…, 7925… дают одно и то же."""
    digits = "".join(c for c in str(value or "") if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else ""


def normalize_name(value: object) -> str:
    """Регистр, «ё» и лишние пробелы не должны мешать совпадению."""
    return " ".join(str(value or "").lower().replace("ё", "е").split())


def _first_two_words(name: str) -> str:
    """Фамилия и имя. В CRM часто пишут с отчеством, в анкете — без."""
    return " ".join(normalize_name(name).split()[:2])


def match_student(contact: dict, students: list[dict]) -> dict | None:
    """Карточка, у которой совпали и ребёнок, и телефон. Иначе None.

    None возвращается и когда подходящих карточек несколько: угадывать между
    ними нельзя, такой случай разбирает администратор.
    """
    child = _first_two_words(contact.get("child_fio"))
    phone = normalize_phone(contact.get("phone"))
    if not child or not phone:
        return None

    hits = [
        st for st in students
        if _first_two_words(st.get("fio")) == child
        and any(normalize_phone(st.get(f)) == phone for f in PHONE_FIELDS)
    ]
    return hits[0] if len(hits) == 1 else None


def missing_fields(student: dict, data: dict) -> tuple[dict, dict]:
    """Что дозаполнить и что разошлось.

    Возвращает (обновления, расхождения). Заполняем только пустые поля:
    непустое значение в CRM мог поставить администратор руками, и затирать
    его автоматикой нельзя. Расхождения возвращаются, чтобы о них сообщить.
    """
    updates: dict[str, str] = {}
    conflicts: dict[str, tuple[str, str]] = {}
    for field in CRM_FIELDS:
        incoming = str(data.get(field) or "").strip()
        if not incoming:
            continue
        current = str(student.get(field) or "").strip()
        if not current:
            updates[field] = incoming
        elif current != incoming:
            conflicts[field] = (current, incoming)
    return updates, conflicts
