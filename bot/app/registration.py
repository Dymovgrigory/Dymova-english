"""Registration gate: обязательная регистрация перед доступом к боту.

Новый пользователь обязан пройти регистрацию (ФИО родителя → имя ребёнка →
дата рождения ребёнка → телефон) перед тем, как ему откроются все возможности
бота (подбор курса, ДЗ, консультация и т.д.).

После регистрации данные отправляются как лид в BigBen CRM.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from app.bigben import BigBenClient
from app.config import settings
from app.intent import extract_age, extract_birthday, extract_phone
from app.memory import Conversation, STAGE_REGISTRATION

logger = logging.getLogger(__name__)

# Шаги регистрации в строгом порядке.
REG_STEPS = ["fio_parent", "fio_child", "birthday", "phone"]

REG_RESUME = "Вернёмся к анкете. "

REG_PROMPTS = {
    "fio_parent": "Как вас зовут? (ФИО родителя)",
    "fio_child": "Как зовут вашего ребёнка? (имя)",
    "birthday": (
        "Укажите дату рождения или возраст ребёнка 🎂\n\n"
        "Например: 9 лет или 15.03.2016"
    ),
    "phone": "Ваш номер телефона для связи?",
}

REG_WELCOME = (
    "Привет! 🦊 Я — Фокси из языковой школы «Фоксинбург» в Долгопрудном!\n\n"
    "Чтобы начать — давайте познакомимся. "
    "Это займёт буквально минутку, а потом я смогу помочь вам "
    "с подбором курса, ценами и записью на бесплатную диагностику 😊\n\n"
)

REG_COMPLETE = (
    "Спасибо за регистрацию! ✅ Теперь все возможности бота открыты для вас 🦊\n\n"
    "Чем могу помочь? Расскажу о курсах, ценах, запишу на бесплатную "
    "диагностику — спрашивайте! 😊"
)

# Regex: слово из букв (рус/лат), допускаем дефис.
_NAME_WORD_RE = re.compile(r"^[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\-]*$")


# Слова, которые человек пишет вместо имени. Раньше проходило что угодно без
# цифр и знака вопроса — в CRM попадали карточки «Привет» и «Тест».
_NAME_STOPWORDS = {
    "привет", "здравствуй", "здравствуйте", "добрый", "доброе", "день", "вечер",
    "утро", "тест", "test", "проверка", "да", "нет", "ок", "окей", "ok", "хорошо",
    "давай", "давайте", "не", "знаю", "никак", "хз", "спасибо", "пока", "бот",
    "админ", "asdf", "qwerty", "фыва", "йцукен", "ааа", "ясно", "понятно",
    "меня", "зовут", "имя", "ребенок", "ребёнок", "мама", "папа", "сын", "дочь",
}

_VOWELS = set("аеёиоуыэюяaeiouy")


def _looks_like_name(text: str) -> bool:
    """Отличает настоящее имя от «Привет», «ааа» и «фффф».

    Идеального детектора не существует, поэтому берём то, что ловит реальный
    мусор без ложных срабатываний на именах: слово из букв, хотя бы одна
    гласная, минимум две разные буквы и не из списка дежурных ответов.
    """
    clean = text.strip()
    if len(clean) < 2 or "?" in clean:
        return False
    if any(c.isdigit() for c in clean):
        return False
    words = clean.split()
    if not words or len(words) > 3:
        return False
    for word in words:
        if not _NAME_WORD_RE.match(word):
            return False
        low = word.lower().strip("-")
        if low in _NAME_STOPWORDS:
            return False
        if len(set(low)) < 2:
            return False
        if not (_VOWELS & set(low)):
            return False
    return True


def _extract_name(text: str) -> str:
    """Extract a name from user text (strip common prefixes)."""
    _prefixes = (
        "меня зовут ", "зовут ", "имя ", "я ", "это ",
        "да ", "давайте ", "давай ", "хорошо ",
    )
    clean = text.strip()
    low = clean.lower()
    for prefix in _prefixes:
        if low.startswith(prefix):
            clean = clean[len(prefix):].strip(" ,.-!")
            break
    # Take first 1-3 word-like tokens
    words: list[str] = []
    for raw in clean.replace(",", " ").split():
        word = raw.strip(" ,.!?")
        if not word:
            continue
        if not _NAME_WORD_RE.match(word):
            break
        words.append(word)
        if len(words) >= 3:
            break
    candidate = " ".join(words)
    if candidate and _looks_like_name(candidate):
        return candidate[:255]
    return ""


def _plausible_age(value: str) -> bool:
    """Возраст ученика. «0» и «150» — это не возраст, а опечатка или шутка."""
    try:
        age = int(str(value).strip())
    except (TypeError, ValueError):
        return False
    return 1 <= age <= 99


def _plausible_birthday(iso_date: str) -> bool:
    """Дата рождения в пределах живого человека, а не 1899 год."""
    try:
        born = date.fromisoformat(iso_date)
    except (TypeError, ValueError):
        return False
    today = date.today()
    if born > today:
        return False
    return (today.year - born.year) <= 100


def _current_step(conv: Conversation) -> str:
    """Determine which registration step is needed next."""
    lead = conv.lead
    if not lead.fio_parent:
        return "fio_parent"
    if not lead.fio_child:
        return "fio_child"
    if not lead.birthday and not lead.age:
        return "birthday"
    if not lead.phone:
        return "phone"
    return "done"


def start_registration(conv: Conversation) -> str:
    """Начинает регистрацию. Возвращает приветствие и первый вопрос.

    Приветствие звучит один раз за разговор. Раньше анкета перезапускалась
    с полного «Привет! Я Фокси…» каждый раз, когда этап уходил в сторону, —
    в живом диалоге человек услышал это знакомство трижды и решил, что бот
    его не помнит.
    """
    conv.stage = STAGE_REGISTRATION
    conv.registration_step = "fio_parent"
    step = _current_step(conv)
    if step == "done":
        conv.registered = True
        return REG_COMPLETE
    conv.registration_step = step
    if _already_greeted(conv):
        return REG_RESUME + REG_PROMPTS[step]
    return REG_WELCOME + REG_PROMPTS[step]


def _already_greeted(conv: Conversation) -> bool:
    """Здоровались ли мы в этом разговоре."""
    marker = REG_WELCOME.split("!")[0]
    return any(
        marker in (m.get("content") or "")
        for m in (getattr(conv, "history", None) or [])
        if m.get("role") == "assistant"
    )


async def handle_registration_step(
    conv: Conversation, text: str, bigben: BigBenClient
) -> tuple[str, bool]:
    """Process one step of registration.

    Returns (reply_text, is_complete).
    """
    step = conv.registration_step or _current_step(conv)
    lead = conv.lead
    clean = text.strip()

    if step == "fio_parent":
        name = _extract_name(clean)
        if not name:
            return "Напишите, пожалуйста, ваше имя и фамилию 😊", False
        lead.fio_parent = name

    elif step == "fio_child":
        name = _extract_name(clean)
        if not name:
            return "Напишите, пожалуйста, как зовут ребёнка.", False
        lead.fio_child = name

    elif step == "birthday":
        birthday = extract_birthday(clean)
        if birthday and _plausible_birthday(birthday):
            lead.birthday = birthday
        else:
            age = extract_age(clean)
            if not age and clean.isdigit() and 1 <= len(clean) <= 2:
                age = clean
            if age and not _plausible_age(age):
                age = ""
            if age:
                lead.age = age
            else:
                return (
                    "Пожалуйста, укажите возраст или дату рождения ребёнка 😊\n\n"
                    "Например: 9 лет или 15.03.2016"
                ), False

    elif step == "phone":
        phone = extract_phone(clean)
        if not phone:
            return (
                "Напишите, пожалуйста, номер телефона в формате "
                "+7XXXXXXXXXX или 8XXXXXXXXXX 📱"
            ), False
        lead.phone = phone

    # Move to next step
    next_step = _current_step(conv)
    if next_step == "done":
        conv.registered = True
        conv.registration_step = ""
        # Send lead to CRM
        await _submit_registration(conv, bigben)
        return REG_COMPLETE, True

    conv.registration_step = next_step
    return REG_PROMPTS[next_step], False


async def _submit_registration(conv: Conversation, bigben: BigBenClient) -> None:
    """Submit registration data as a lead to BigBen CRM."""
    lead = conv.lead
    source = "MAX-бот Фоксинбург — регистрация"
    note = (
        f"Регистрация в боте. "
        f"Родитель: {lead.fio_parent}. "
        f"Ребёнок: {lead.fio_child}. "
        f"{'Дата рождения: ' + lead.birthday if lead.birthday else 'Возраст: ' + (lead.age or '—')}. "
        f"Телефон: {lead.phone}."
    )
    utm = {**(conv.utm or {})}
    utm.setdefault("utm_source", "max")
    utm.setdefault("utm_medium", "bot")

    try:
        await bigben.create_lead(lead, source=source, note=note, utm=utm)
        logger.info("registration: lead submitted for user=%s", conv.user_id)
    except Exception:
        logger.exception("registration: failed to submit lead for user=%s", conv.user_id)


def is_registered(conv: Conversation) -> bool:
    """Check if user has completed registration.

    If REGISTRATION_REQUIRED is disabled, everyone is considered registered.
    """
    if not settings.REGISTRATION_REQUIRED:
        return True
    return conv.registered
