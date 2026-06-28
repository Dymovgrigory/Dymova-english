"""Распознавание намерения клиента и извлечение сущностей.

Сначала пытаемся понять намерение по ключевым словам (быстро и предсказуемо).
LLM используется уже на этапе формулирования ответа — здесь нам важна
маршрутизация: приветствие, вопрос о цене, подбор курса, возражение, запрос
оператора, передача контактных данных и т.д.
"""
from __future__ import annotations

import re

# --- намерения ---
GREETING = "greeting"
PRICE = "price"
COURSES = "courses"
CONTACTS = "contacts"
ABOUT = "about"
WANT_SIGNUP = "want_signup"
OBJECTION = "objection"
HANDOFF = "handoff"
QUESTION = "question"

# Приветствие проверяем отдельным regex по границам слов: короткие токены вроде
# «ку»/«hi» иначе ложно срабатывают внутри слов («ребёнку», «уроки»).
_GREETING_RE = re.compile(
    r"\b(привет\w*|здравств\w*|здравуй\w*|здравейте|хелло\w*|hello|hi|hey|ку)\b"
    r"|добрый день|добрый вечер|доброе утро",
    re.IGNORECASE,
)

_PATTERNS: list[tuple[str, list[str]]] = [
    (HANDOFF, ["оператор", "администратор", "менеджер", "жалоб", "директор",
               "возврат", "договор", "претензи", "живой человек", "человек",
               "позвоните мне", "перезвоните"]),
    (WANT_SIGNUP, ["запис", "записать", "пробн", "хочу учиться", "хочу заниматься",
                   "хочу на курс", "оставить заявку", "забронир", "диагностик",
                   "хочу попробовать", "хочу записаться"]),
    (PRICE, ["сколько стоит", "стоимость", "цена", "цены", "почем", "прайс",
             "сколько за", "дорого ли", "оплат"]),
    (COURSES, ["курс", "программ", "какие занятия", "направлен", "немецк",
               "китайск", "английск", "чтени", "грамматик", "летн", "академи",
               "онлайн", "оффлайн", "офлайн", "группа", "уровень"]),
    (CONTACTS, ["адрес", "филиал", "где наход", "как добраться", "телефон",
                "контакт", "режим работы", "часы работы", "как с вами связаться"]),
    (ABOUT, ["о школе", "о вас", "кто вы", "методик", "лицензи", "преподавател",
             "педагог", "отзыв", "результат", "почему вы", "преимуществ"]),
]

_OBJECTIONS = {
    "дорого": ["дорого", "дороговато", "не по карману", "дешевле", "скидк"],
    "подумаю": ["подумаю", "посоветуюсь", "не уверен", "позже", "может быть",
                "надо подумать", "обсужу"],
    "далеко": ["далеко", "неудобно ехать", "нет рядом", "другой город", "не близко"],
}

_PHONE_RE = re.compile(r"(?:\+7|8|7)?[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
_AGE_RE = re.compile(r"(\d{1,2})\s*(?:лет|год|года|годик)")
_AGE_CHILD_RE = re.compile(r"(?:сын|доч|реб[её]нк|мальчик|девочк|ему|ей)\D{0,12}?(\d{1,2})")
_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_RU_RE = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b")


def detect_objection(text: str) -> str | None:
    low = text.lower()
    for key, words in _OBJECTIONS.items():
        if any(w in low for w in words):
            return key
    return None


def detect_intent(text: str) -> str:
    low = text.lower().strip()
    if detect_objection(low):
        return OBJECTION
    if _GREETING_RE.search(low):
        return GREETING
    for intent, words in _PATTERNS:
        if any(w in low for w in words):
            return intent
    return QUESTION


def extract_phone(text: str) -> str | None:
    m = _PHONE_RE.search(text)
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(0))
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10:
        return "+7" + digits
    if len(digits) < 10:
        return None
    return "+" + digits


def extract_age(text: str) -> str | None:
    m = _AGE_RE.search(text.lower())
    if m:
        return m.group(1)
    m = _AGE_CHILD_RE.search(text.lower())
    if m:
        return m.group(1)
    return None


def extract_birthday(text: str) -> str | None:
    """Возвращает дату в формате yyyy-mm-dd, если найдена и валидна."""
    m = _DATE_RE.search(text)
    if m:
        return _validate_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _DATE_RU_RE.search(text)
    if m:
        return _validate_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def _validate_date(year: int, month: int, day: int) -> str | None:
    import datetime

    try:
        d = datetime.date(year, month, day)
    except ValueError:
        return None
    if d.year < 1990 or d > datetime.date.today():
        return None
    return d.isoformat()
