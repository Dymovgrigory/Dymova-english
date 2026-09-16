"""Перенос данных из Подпислона в карточку ученика BigBen.

Здесь чистая логика без сети: как из контакта Подпислона собрать поля для
CRM, как найти нужную карточку и что в ней можно трогать. Сетевые вызовы —
в `podpislon.py` (Подпислон) и `bigben_internal.py` (CRM).

Правило сопоставления задано школой: совпасть должны И фамилия с именем
ребёнка, И телефон. При нуле совпадений или неоднозначности карточка не
трогается — такие случаи уходят администратору руками.
"""
from __future__ import annotations

import re
from datetime import date

# Поля карточки ученика, куда складываем данные анкеты.
# Ключ — поле CRM, значение — как достаётся из контакта Подпислона.
CRM_FIELDS = (
    "fio", "birthday", "parentname", "parent_phone", "parent_birthday",
    "passport", "home_address", "email",
)

# Поля-даты: карточка BigBen хранит и отдаёт их как ГГГГ-ММ-ДД.
DATE_FIELDS = ("birthday", "parent_birthday")

# Телефон ученика может лежать в любом из этих полей карточки.
PHONE_FIELDS = ("parent_phone", "phone", "phone1", "main_phone")


def normalize_phone(value: object) -> str:
    """Последние 10 цифр: +7 (925) 880-33-33, 8 925…, 7925… дают одно и то же."""
    digits = "".join(c for c in str(value or "") if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else ""


def crm_date(value: object) -> str:
    """Любая запись даты → ГГГГ-ММ-ДД, как в карточке CRM. Не дата — пустая строка.

    Анкету заполняют руками: встречается «23.05. 2019», «3.5.2019», «09/04/2019».
    «0000-00-00» — так CRM показывает незаполненную дату.
    """
    text = str(value or "").strip()
    iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        year, month, day = iso.groups()
    else:
        ru = re.fullmatch(r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})", text)
        if not ru:
            return ""
        day, month, year = ru.groups()
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return ""


def normalize_name(value: object) -> str:
    """Регистр, «ё» и лишние пробелы не должны мешать совпадению."""
    return " ".join(str(value or "").lower().replace("ё", "е").split())


def _first_two_words(name: str) -> str:
    """Фамилия и имя. В CRM часто пишут с отчеством, в анкете — без."""
    return " ".join(normalize_name(name).split()[:2])


def surname_stem(value: object) -> str:
    """Фамилия без родового окончания: Ворожеева/Ворожеев, Троицкая/Троицкий."""
    word = normalize_name(value).split()[:1]
    if not word:
        return ""
    surname = word[0]
    for ending in ("ская", "ский", "цкая", "цкий", "ая", "ий", "ой", "а"):
        if surname.endswith(ending) and len(surname) > len(ending) + 2:
            return surname[: -len(ending)]
    return surname


def match_student(contact: dict, students: list[dict]) -> dict | None:
    """Карточка, у которой совпали и ребёнок, и телефон. Иначе None.

    Если ФИО ребёнка в анкете нет, подходит единственная карточка на этот
    телефон с фамилией родителя (в мужском или женском роде).

    None возвращается и когда подходящих карточек несколько: угадывать между
    ними нельзя, такой случай разбирает администратор.
    """
    child = _first_two_words(contact.get("child_fio"))
    phone = normalize_phone(contact.get("phone"))
    if not phone:
        return None

    by_phone = [
        st for st in students
        if any(normalize_phone(st.get(f)) == phone for f in PHONE_FIELDS)
    ]
    if child:
        hits = [st for st in by_phone if _first_two_words(st.get("fio")) == child]
        return hits[0] if len(hits) == 1 else None

    parent = surname_stem(contact.get("parent_last_name"))
    if not parent or len(by_phone) != 1:
        return None
    only = by_phone[0]
    return only if surname_stem(only.get("fio")) == parent else None


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
        if field in DATE_FIELDS and not crm_date(current):
            current = ""
        if current.strip("-—– ") == "":
            current = ""  # «-» в CRM ставят вместо пустого значения
        if not current:
            updates[field] = incoming
        elif not _same_value(field, current, incoming):
            conflicts[field] = (current, incoming)
    return updates, conflicts


def _same_value(field: str, current: str, incoming: str) -> bool:
    """Одно и то же, записанное по-разному, расхождением не считаем."""
    if field in DATE_FIELDS:
        return crm_date(current) == crm_date(incoming)
    if field == "fio":
        # В CRM ребёнок часто без отчества, в анкете — с ним.
        return _first_two_words(current) == _first_two_words(incoming)
    if field == "parentname":
        # В CRM у родителя часто только имя («мама Анастасия»), в анкете — полное ФИО.
        noted = set(normalize_name(current).split()) - {"мама", "папа"}
        return noted <= set(normalize_name(incoming).split())
    if field in PHONE_FIELDS:
        return normalize_phone(current) == normalize_phone(incoming)
    return normalize_name(current) == normalize_name(incoming)
