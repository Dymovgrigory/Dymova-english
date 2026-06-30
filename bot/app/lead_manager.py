"""Lead Manager: сбор данных для записи на пробное/диагностику и отправка в CRM.

Последовательно собирает ФИО родителя, ФИО ребёнка, возраст (или дату рождения),
телефон и филиал; проверяет корректность телефона и даты; формирует заявку и
отправляет её в BigBen CRM, после чего уведомляет администратора.
"""
from __future__ import annotations

import logging
import re

from app.bigben import BigBenClient
from app.intent import extract_age, extract_birthday, extract_phone
from app.knowledge.kb import KnowledgeBase
from app.max_client import MaxClient
from app.memory import Conversation, STAGE_DONE, STAGE_LEAD

logger = logging.getLogger(__name__)

# Порядок сбора полей и вопросы к клиенту.
STEPS = ["fio_parent", "fio_child", "birthday", "phone", "branch", "confirm"]

PROMPTS = {
    "fio_parent": "Как вас зовут (ФИО родителя)?",
    "fio_child": "А как зовут ребёнка (ФИО)?",
    "birthday": "Подскажите возраст или полную дату рождения ребёнка 🎂\n\nНапример: 9 лет или 15.03.2016",
    "phone": "По какому номеру телефона с вами связаться?",
    "branch": "Какой филиал удобнее?\n\n• Лихачевский 76к1\n• Ракетостроителей 9к3\n• Онлайн",
}


def _looks_like_name(text: str) -> bool:
    clean = text.strip()
    if len(clean) < 2:
        return False
    if any(c.isdigit() for c in clean):
        return False
    if extract_age(clean):
        return False
    if "?" in clean:
        return False
    low = clean.lower().strip(" .!?")
    _short = ("да", "давайте", "давай", "хорошо", "хочу", "можно",
              "конечно", "ок", "окей", "ладно", "ага", "yes", "+",
              "записаться", "запишите", "запиши", "записать")
    if any(low.startswith(prefix) for prefix in _short):
        return False
    _reject = ("запис", "пробн", "курс", "диагностик", "заняти",
               "english", "англ", "хочу")
    if any(w in low for w in _reject):
        return False
    return True


def _strip_name_prefix(clean: str) -> str:
    _prefixes = ("да ", "давайте ", "давай ", "хорошо ", "можно ",
                  "конечно ", "ок ", "окей ", "ладно ", "ага ",
                  "хочу ", "да, ", "давайте, ", "меня зовут ",
                  "зовут ", "имя ", "я ", "это ")
    low = clean.lower()
    for prefix in _prefixes:
        if low.startswith(prefix):
            return clean[len(prefix):].strip(" ,.-!")
    return clean


# Слово состоит из букв (рус/лат), допускаем дефис: Анна-Мария, Smith.
_NAME_WORD_RE = re.compile(r"^[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\-]*$")
_AGE_HINT_WORDS = ("лет", "год", "года", "годик", "сын", "доч", "ребен",
                   "ребён", "мальчик", "девочк", "телефон", "тел")


def _extract_leading_name(text: str) -> str:
    """Берёт начальную последовательность слов-имён, отбрасывая возраст/телефон.

    Позволяет вытащить «Иванова Анна» из «Иванова Анна, ребёнку 9» или
    «зовут Анна 8 999 ...».
    """
    clean = _strip_name_prefix(text.strip())
    if not clean:
        return ""
    words: list[str] = []
    for raw in clean.replace(",", " ").split():
        word = raw.strip(" ,.!?")
        if not word:
            continue
        if not _NAME_WORD_RE.match(word):
            break
        if any(hint in word.lower() for hint in _AGE_HINT_WORDS):
            break
        words.append(word)
        if len(words) >= 3:
            break
    candidate = " ".join(words)
    if candidate and _looks_like_name(candidate):
        return candidate[:255]
    return ""


def _extract_name_from_text(text: str) -> str:
    """Извлекает ФИО из текста, убирая слова-согласия и лишний «шум»."""
    clean = text.strip()
    if not clean:
        return ""
    name_part = _strip_name_prefix(clean)
    if _looks_like_name(name_part):
        return name_part[:255]
    return _extract_leading_name(clean)


def start(conv: Conversation, user_text: str = "") -> str:
    """Начинает сбор лида. Если user_text содержит ФИО — сразу записывает."""
    conv.stage = STAGE_LEAD
    # Попробуем извлечь ФИО из текста пользователя
    if user_text and not conv.lead.fio_parent:
        name = _extract_name_from_text(user_text)
        if name:
            conv.lead.fio_parent = name
    return _ask_next(conv)


def _next_step(conv: Conversation) -> str:
    lead = conv.lead
    if not lead.fio_parent:
        return "fio_parent"
    if not lead.fio_child:
        return "fio_child"
    if not lead.birthday and not lead.age:
        return "birthday"
    if not lead.phone:
        return "phone"
    if not lead.branch and not conv.selected_branch:
        return "branch"
    return "confirm"


def _ask_next(conv: Conversation) -> str:
    step = _next_step(conv)
    conv.lead_step = step
    if step == "confirm":
        return _confirmation_text(conv)
    return PROMPTS[step]


def _confirmation_text(conv: Conversation) -> str:
    lead = conv.lead
    branch = lead.branch or conv.selected_branch or "—"
    when = lead.birthday or (f"{lead.age} лет" if lead.age else "—")
    return (
        "Проверьте, пожалуйста, заявку:\n\n"
        f"• Родитель: {lead.fio_parent}\n"
        f"• Ребёнок: {lead.fio_child}\n"
        f"• Дата рождения: {when}\n"
        f"• Телефон: {lead.phone}\n"
        f"• Филиал: {branch}\n\n"
        "Всё верно? Напишите «да» — и я отправлю заявку, или поправьте данные."
    )


async def step(
    conv: Conversation,
    text: str,
    kb: KnowledgeBase,
    bigben: BigBenClient,
    max_client: MaxClient,
) -> tuple[str, bool]:
    """Обрабатывает шаг сбора лида. Возвращает (ответ, submitted)."""
    current = conv.lead_step or _next_step(conv)
    lead = conv.lead
    clean = text.strip()

    # На каждом шаге подбираем «лишние» данные, которые клиент дал вперёд/вперемешку
    # (телефон, дату, возраст, филиал) — чтобы не терять их и не переспрашивать.
    if current not in ("fio_parent", "fio_child"):
        _opportunistic_fill(conv, clean, kb)

    if current == "fio_parent":
        name = _extract_name_from_text(clean)
        if not name:
            return (
                "Кажется, это не похоже на имя 😊 Напишите, пожалуйста, как вас зовут (имя и фамилия)."
            ), False
        lead.fio_parent = name

    elif current == "fio_child":
        name = _extract_name_from_text(clean)
        if not name:
            age = extract_age(clean)
            if age and not lead.age:
                lead.age = age
            return "Напишите, пожалуйста, имя ребёнка.", False
        lead.fio_child = name

    elif current == "birthday":
        birthday = extract_birthday(clean)
        if birthday:
            lead.birthday = birthday
        else:
            age = extract_age(clean)
            if not age and clean.isdigit() and 1 <= len(clean) <= 2:
                age = clean
            if age:
                lead.age = age
            else:
                return ("Пожалуйста, укажите возраст или дату рождения в "
                        "формате дд.мм.гггг 😊\n\nНапример: 9 лет или 15.03.2016"), False

    elif current == "phone":
        phone = extract_phone(clean)
        if not phone:
            # Клиент мог прислать не телефон, а другое поле (дата/возраст) —
            # оно уже подхвачено выше, поэтому не ругаемся, а мягко переспрашиваем.
            if extract_birthday(clean):
                prefix = "Дату рождения записал ✅ "
            elif extract_age(clean):
                prefix = "Возраст записал ✅ "
            else:
                prefix = ""
            return (prefix + "Остался телефон — напишите, пожалуйста, в формате "
                    "+7XXXXXXXXXX или 8XXXXXXXXXX, и я оформлю заявку."), False
        lead.phone = phone

    elif current == "branch":
        lead.branch = _match_branch(kb, clean) or clean[:255]
        conv.selected_branch = lead.branch

    elif current == "confirm":
        if _is_yes(clean):
            return await _submit(conv, bigben, max_client), True
        if _is_no(clean):
            # пользователь хочет поправить — сбрасываем шаг и переспрашиваем
            conv.lead_step = ""
            return ("Хорошо, что нужно поправить? Напишите, например: "
                    "«телефон 89991234567» или просто новое значение."), False
        # пытаемся обновить поля из свободного текста
        _opportunistic_fill(conv, clean, kb)
        return _confirmation_text(conv), False

    return _ask_next(conv), False


async def _submit(conv: Conversation, bigben: BigBenClient, max_client: MaxClient) -> str:
    from app.admin_router import hand_off

    lead = conv.lead
    lead.course = conv.selected_course or lead.course
    lead.branch = lead.branch or conv.selected_branch
    source = f"MAX-бот Фоксинбург — запись ({lead.course or 'диагностика'})"
    note = _lead_note(conv)
    utm = {**(conv.utm or {})}
    utm.setdefault("utm_source", "max")
    utm.setdefault("utm_medium", "bot")

    ok = await bigben.create_lead(lead, source=source, note=note, utm=utm)
    conv.stage = STAGE_DONE
    conv.lead_submitted = True

    # уведомляем администратора о новой заявке (без переключения в режим handoff)
    if max_client.configured:
        try:
            await hand_off(max_client, conv, reason="новая заявка с записи")
        except Exception:
            logger.exception("Не удалось уведомить администратора о заявке")
        # hand_off переводит этап в handoff — возвращаем DONE, чтобы бот не молчал
        conv.stage = STAGE_DONE

    if ok:
        return (
            "Готово! ✅ Заявка отправлена!\n\n"
            "Администратор в ближайшее время свяжется с вами "
            "для подтверждения. Спасибо, что выбираете Фоксинбург! 🦊"
        )
    return (
        "Заявка принята! Администратор свяжется с вами "
        "в ближайшее время для подтверждения.\n\n"
        "Если удобно, можете также позвонить нам:\n"
        "• 8 993 923-23-09 (Лихачевский)\n"
        "• 8 916 732-31-69 (Ракетостроителей)\n\n"
        "Спасибо! 🦊"
    )


def _lead_note(conv: Conversation) -> str:
    """Полный контекст для администратора: резюме + выбор + концовка диалога."""
    parts = [conv.summary()]
    if conv.selected_format:
        parts.append(f"Формат: {conv.selected_format}")
    tail = [m for m in conv.history if m.get("role") == "user"][-4:]
    if tail:
        quoted = "; ".join(m["content"][:120] for m in tail)
        parts.append(f"Реплики клиента: {quoted}")
    parts.append("Источник: MAX-бот Фоксинбург")
    return ". ".join(p for p in parts if p)


def _match_branch(kb: KnowledgeBase, text: str) -> str | None:
    low = text.lower()
    if "онлайн" in low:
        return "Онлайн"
    for b in kb.branches:
        addr = b.get("address", "").lower()
        name = b.get("name", "")
        if "лихачев" in low and "лихачев" in addr:
            return name
        if "ракето" in low and "ракето" in addr:
            return name
    return None


def _opportunistic_fill(conv: Conversation, text: str, kb: KnowledgeBase) -> None:
    lead = conv.lead
    phone = extract_phone(text)
    if phone:
        lead.phone = phone
    birthday = extract_birthday(text)
    if birthday:
        lead.birthday = birthday
    age = extract_age(text)
    if age:
        lead.age = age
    branch = _match_branch(kb, text)
    if branch:
        lead.branch = branch
        conv.selected_branch = branch


def _is_yes(text: str) -> bool:
    return text.lower().strip(" .!") in (
        "да", "верно", "всё верно", "все верно", "да, верно", "отправляйте",
        "отправить", "подтверждаю", "ок", "окей", "ага", "yes", "+",
    )


def _is_no(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in ("нет", "не верно", "неверно", "исправ", "поправ", "измен"))
