"""Идентификация клиента по номеру телефона (спека approach-1, разделы 2/6).

Сценарий: в начале диалога бот просит поделиться номером (в Telegram —
нативная кнопка request_contact, в MAX кнопки такого типа нет — просим
номер текстом). По номеру ищем ученика в read-model BigBen:

- не нашёлся — номер сохраняется в лид, человек считается новым;
- нашёлся один ученик — спрашиваем имя ребёнка и сверяем нечётко
  («Маша» = «Мария»);
- нашлось несколько (один родитель, несколько детей) — показываем список
  и ждём выбора номером или именем.

При совпадении диалог привязывается к ученику (conv.student_id) и считается
зарегистрированным: анкета для существующего клиента не нужна.
"""
from __future__ import annotations

import json
import logging
import re

from app.config import settings
from app.memory import Conversation
from app.platform import bb_store

logger = logging.getLogger(__name__)

STATE_AWAIT_CONTACT = "await_contact"
STATE_AWAIT_CHILD_NAME = "await_child_name"
STATE_AWAIT_CHILD_CHOICE = "await_child_choice"
_PENDING = (STATE_AWAIT_CHILD_NAME, STATE_AWAIT_CHILD_CHOICE)

SHARE_BUTTON_TEXT = "📞 Поделиться номером"
SHARE_BUTTON_PAYLOAD = "share:phone"

ASK_CONTACT = (
    "Чтобы я могла найти вас в системе школы (расписание, баланс, домашние "
    "задания) — или быстрее оформить заявку, если вы у нас впервые, — "
    "поделитесь, пожалуйста, номером телефона: кнопкой ниже или просто "
    "отправьте номер сообщением."
)
ASK_CONTACT_AGAIN = (
    "Пока не вижу номер 🙈 Поделитесь, пожалуйста, номером телефона — "
    "кнопкой ниже или текстом, например +7 900 123-45-67. Без него я "
    "не смогу ни найти вас в базе, ни передать заявку администратору."
)
ASK_PHONE_TEXT_MAX = (
    "Отправьте, пожалуйста, номер телефона текстом, например "
    "+7 900 123-45-67 — я проверю его в базе школы."
)
START_PROMPT = (
    "Здравствуйте! Я Фокси, консультант языковой школы «Фоксинбург» в "
    "Долгопрудном 😊\n\n" + ASK_CONTACT
)
NEW_LEAD_REPLY = (
    "Спасибо! Такого номера в базе школы пока нет — видимо, вы у нас "
    "впервые. С удовольствием всё расскажу!"
)
ASK_CHILD_NAME = (
    "Нашла этот номер в базе школы! Подскажите, как зовут вашего ребёнка?"
)
IDENTIFIED_REPLY = "Отлично, я вас нашла: {fio}. Чем помочь? 😊"
NAME_MISMATCH_REPLY = (
    "По этому номеру такого имени не нашла — значит, оформим вас как нового "
    "клиента. Номер я сохранила!"
)

# Уменьшительные формы ↔ полные имена. Словарь намеренно маленький: только
# частые детские имена, незнакомые сравниваются как есть.
_DIMINUTIVES = {
    "маша": "мария", "даша": "дарья", "саша": "александр", "катя": "екатерина",
    "настя": "анастасия", "лена": "елена", "ваня": "иван", "петя": "петр",
    "миша": "михаил", "дима": "дмитрий", "костя": "константин", "оля": "ольга",
    "таня": "татьяна", "юля": "юлия", "леша": "алексей", "женя": "евгений",
    "вова": "владимир", "соня": "софья", "варя": "варвара", "аня": "анна",
    "поля": "полина", "вика": "виктория", "тема": "артем", "витя": "виктор",
    "рита": "маргарита", "гоша": "георгий", "стас": "станислав",
}
# Альтернативные полные формы, которые должны считаться одним именем.
_EQUIVALENT = {"софья": "софия", "наталия": "наталья", "пётр": "петр"}


def normalize_phone(phone: str) -> str:
    """Приводит номер к виду +7XXXXXXXXXX по последним 10 цифрам."""
    digits = "".join(c for c in (phone or "") if c.isdigit())[-10:]
    return f"+7{digits}" if digits else ""


def needs_gate(conv: Conversation) -> bool:
    """True, если диалог обязан сначала пройти идентификацию по номеру."""
    if not settings.IDENTIFICATION_REQUIRED:
        return False
    if conv.student_id:
        return False
    if conv.identify_state in _PENDING:
        return True
    return not conv.lead.phone


def start_prompt(conv: Conversation) -> str:
    """Приветствие нового диалога при включённой идентификации."""
    conv.identify_state = STATE_AWAIT_CONTACT
    return START_PROMPT


def gate_reply(conv: Conversation) -> str:
    """Ответ на сообщение без номера, когда идентификация обязательна."""
    conv.identify_state = STATE_AWAIT_CONTACT
    return ASK_CONTACT if not conv.history else ASK_CONTACT_AGAIN


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower().replace("ё", "е"))


def _canonical(name: str) -> str:
    name = _normalize_name(name)
    name = _DIMINUTIVES.get(name, name)
    return _EQUIVALENT.get(name, name)


def name_matches(given: str, fio: str) -> bool:
    """Нечёткое сравнение введённого имени с ФИО ученика из CRM.

    «Маша» совпадает с «Иванова Мария», «Петя» — с «Пётр». Имя сравнивается
    с каждым словом ФИО: порядок «Фамилия Имя» в CRM не гарантирован.
    """
    given_canon = _canonical(given.split()[0] if given.split() else "")
    if not given_canon:
        return False
    for token in fio.split():
        token_canon = _canonical(token)
        if given_canon == token_canon:
            return True
        # «Мария» против «Марьяна» совпадать не должны, а вот короткий ввод
        # («Мар», «Кат») считаем опечаткой недописанного имени.
        if len(given_canon) >= 3 and token_canon.startswith(given_canon):
            return True
    return False


def _student_age(row: dict) -> str:
    """Возраст из raw_json, если CRM его отдала; иначе пусто."""
    try:
        raw = json.loads(row.get("raw_json") or "{}")
    except (TypeError, ValueError):
        return ""
    for key in ("age", "vozrast"):
        if raw.get(key):
            return str(raw[key])
    birthday = str(raw.get("birthday") or raw.get("birth_date") or "")
    match = re.match(r"(\d{4})-\d{2}-\d{2}", birthday)
    if match:
        from datetime import date
        age = date.today().year - int(match.group(1))
        if 0 < age < 100:
            return str(age)
    return ""


def _candidate_label(candidate: dict) -> str:
    age = _student_age(candidate)
    return f"{candidate['fio']} ({age} лет)" if age else candidate["fio"]


def _finish_as_student(conv: Conversation, candidate: dict) -> str:
    conv.student_id = int(candidate["id"])
    conv.identify_state = ""
    conv.identify_candidates = []
    if not conv.lead.fio_child:
        conv.lead.fio_child = candidate["fio"]
    # Ученик уже есть в CRM — анкета регистрации ему не нужна.
    conv.registered = True
    return IDENTIFIED_REPLY.format(fio=candidate["fio"])


def _finish_as_new_lead(conv: Conversation, phone: str) -> str:
    conv.lead.set_phone(normalize_phone(phone))
    conv.identify_state = ""
    conv.identify_candidates = []
    return NEW_LEAD_REPLY


def handle_contact(conv: Conversation, raw_phone: str, confirmed: bool = False) -> str:
    """Обработка присланного контакта/номера. Возвращает ответ клиенту.

    confirmed=True ставится только для нативного контакта Telegram
    (message.contact): платформа гарантирует, что номер принадлежит
    отправителю. Номер, присланный текстом, — confirmed=False.
    """
    phone = normalize_phone(raw_phone)
    if not phone:
        conv.identify_state = STATE_AWAIT_CONTACT
        return ASK_PHONE_TEXT_MAX
    conv.lead.set_phone(phone, confirmed=confirmed)
    try:
        rows = bb_store.find_students_by_phone(phone)
    except Exception:
        # Read-model недоступна — это не повод терять лид: сохраняем номер
        # и работаем как с новым клиентом.
        logger.exception("identify: ошибка поиска ученика по телефону")
        rows = []
    if not rows:
        return _finish_as_new_lead(conv, phone)
    conv.identify_candidates = [{"id": r["id"], "fio": r["fio"], "raw_json": r.get("raw_json", "{}")} for r in rows]
    if len(rows) == 1:
        conv.identify_state = STATE_AWAIT_CHILD_NAME
        return ASK_CHILD_NAME
    conv.identify_state = STATE_AWAIT_CHILD_CHOICE
    labels = "\n".join(
        f"{i}. {_candidate_label(c)}" for i, c in enumerate(conv.identify_candidates, start=1)
    )
    return (
        "По этому номеру у нас учится несколько детей. Кто из них ваш?\n"
        f"{labels}\nОтветьте номером или именем."
    )


def handle_pending(conv: Conversation, text: str) -> str | None:
    """Ответ на уточняющий вопрос идентификации. None — не наш сценарий."""
    state = conv.identify_state
    candidates = conv.identify_candidates or []
    if state == STATE_AWAIT_CHILD_NAME and candidates:
        candidate = candidates[0]
        if name_matches(text, candidate["fio"]):
            return _finish_as_student(conv, candidate)
        # Имя не совпало — по спеке считаем человека новым лидом.
        _finish_as_new_lead(conv, conv.lead.phone)
        return NAME_MISMATCH_REPLY
    if state == STATE_AWAIT_CHILD_CHOICE and candidates:
        digit = re.search(r"\d+", text or "")
        if digit:
            index = int(digit.group(0)) - 1
            if 0 <= index < len(candidates):
                return _finish_as_student(conv, candidates[index])
        for candidate in candidates:
            if name_matches(text, candidate["fio"]):
                return _finish_as_student(conv, candidate)
        labels = "\n".join(
            f"{i}. {_candidate_label(c)}" for i, c in enumerate(candidates, start=1)
        )
        return (
            "Не поняла, кого вы имеете в виду 🙈 Выберите из списка:\n"
            f"{labels}\nОтветьте номером или именем."
        )
    return None
