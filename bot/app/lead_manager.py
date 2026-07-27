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
from app.memory import Conversation, STAGE_DISCOVERY, STAGE_DONE, STAGE_LEAD
from app.slack import notify_slack

logger = logging.getLogger(__name__)

# Порядок сбора полей и вопросы к клиенту.
STEPS = ["fio_parent", "fio_child", "age", "phone", "branch", "confirm"]

PROMPTS = {
    "fio_parent": "Отлично! 😊 Давайте оформлю запись. Как вас зовут (ФИО родителя)?",
    "fio_child": "Спасибо! А как зовут ребёнка (ФИО)?",
    "age": "Сколько лет ребёнку? Можно указать возраст или дату рождения (дд.мм.гггг).",
    "phone": "По какому номеру телефона с вами связаться?",
    "branch": "Какой формат удобнее: Лихачевский, Ракетостроителей или онлайн?",
}

_NAME_RE = re.compile(r"^[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\-]*(?:\s+[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\-]*){0,2}$")


_NAME_BLOCKLIST_RE = re.compile(
    r"\bлет\b|\bгод\w*\b|\bкласс\w*\b|\bсын\w*\b|\bдоч\w*\b|\bребён\w*\b|"
    r"\bребят\w*\b|\bдавай\w*\b|\bзапиш\w*\b|\bхочу\b|\bпробн\w*\b|"
    r"\bоформ\w*\b|\bпотом\b|\bпозже\b|\bпоговор\w*\b",
    re.IGNORECASE,
)


def _looks_like_name(text: str) -> bool:
    """Отсеивает "9 лет"/"хочу записаться" и т.п. от настоящего имени.

    Раньше это была проверка подстроки ("лет" in text, "реб" in text), из-за
    чего реальные имя/фамилия вроде «Виолетта» (содержит "лет") или
    «Реброва» (содержит "реб") отклонялись как мусор — бот бесконечно
    просил повторить имя, которое повторить было невозможно. Теперь
    блок-лист матчит только целые слова/основы, а не подстроки где попало.
    """
    clean = text.strip()
    if len(clean) < 2:
        return False
    if any(ch.isdigit() for ch in clean):
        return False
    if _NAME_BLOCKLIST_RE.search(clean):
        return False
    return bool(_NAME_RE.match(clean))


def _extract_name_from_text(text: str) -> str:
    clean = text.strip()
    if not clean:
        return ""
    clean = re.sub(r"(?i)^(?:меня зовут|я\s*-\s*|это)\s+", "", clean)
    clean = re.split(r"[,.!?:;\n]", clean)[0].strip()
    if _looks_like_name(clean):
        return clean[:255]
    m = _NAME_RE.search(clean)
    if m:
        candidate = m.group(0).strip()
        if _looks_like_name(candidate):
            return candidate[:255]
    return ""


_SIGNUP_RESTATEMENT_RE = re.compile(
    r"давай|запиш|хочу|пробн|оформ", re.IGNORECASE,
)


def _name_retry_reply(text: str, field_label: str) -> str:
    """Просьба повторить имя после неудачного извлечения.

    Если человек просто снова говорит «хочу записаться» / «давайте
    запишем» вместо имени (естественная реакция сразу после приглашения
    записаться), голый повтор «Подскажите, пожалуйста, имя родителя.»
    читается как бот, который не слышит собеседника. Подтверждаем, что
    намерение услышано, и уточняем, что нужно конкретно.
    """
    if _SIGNUP_RESTATEMENT_RE.search(text.lower()):
        return f"Хорошо, уже записываю 😊 Для заявки нужно {field_label} — напишите, пожалуйста."
    return f"Подскажите, пожалуйста, {field_label}."


def start(conv: Conversation) -> str:
    conv.stage = STAGE_LEAD
    return _ask_next(conv)


def _next_step(conv: Conversation) -> str:
    lead = conv.lead
    if not lead.fio_parent:
        return "fio_parent"
    if not lead.fio_child:
        return "fio_child"
    if not lead.age and not lead.birthday:
        return "age"
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
        "Проверьте, пожалуйста, заявку:\n"
        f"• Родитель: {lead.fio_parent}\n"
        f"• Ребёнок: {lead.fio_child}\n"
        f"• Возраст/дата рождения: {when}\n"
        f"• Телефон: {lead.phone}\n"
        f"• Формат/филиал: {branch}\n\n"
        "Всё верно? Напишите «да» — и я отправлю заявку, или поправьте данные."
    )


_CANCEL_RE = re.compile(
    r"позже|попозже|потом|не\s*сейчас|передумал|не\s*хочу|отмен\w*|"
    r"не\s*буду|расхотел",
    re.IGNORECASE,
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
    low = clean.lower()
    _opportunistic_fill(conv, clean, kb)

    if any(word in low for word in ("позже", "попозже", "потом", "не сейчас", "давайте позже")):
        conv.stage = STAGE_DISCOVERY
        conv.lead_step = ""
        return (
            "Без проблем, вернёмся к этому позже. Если захотите продолжить, "
            "я помогу подобрать курс или запись на бесплатную диагностику.",
            False,
        )

    if current == "fio_parent":
        age = extract_age(clean)
        if age:
            lead.age = age
            return "Подскажите, пожалуйста, имя родителя.", False
        name = _extract_name_from_text(clean)
        if not name:
            return _name_retry_reply(clean, "имя родителя"), False
        lead.fio_parent = name

    elif current == "fio_child":
        birthday = extract_birthday(clean)
        age = extract_age(clean)
        if birthday:
            lead.birthday = birthday
            return "Подскажите, пожалуйста, имя ребёнка.", False
        if age:
            if not lead.age:
                lead.age = age
            return "Подскажите, пожалуйста, имя ребёнка.", False
        name = _extract_name_from_text(clean)
        if not name:
            return _name_retry_reply(clean, "имя ребёнка"), False
        lead.fio_child = name

    elif current == "age":
        birthday = extract_birthday(clean)
        age = extract_age(clean)
        if birthday:
            lead.birthday = birthday
        elif age:
            lead.age = age
        else:
            # просто число?
            digits = "".join(c for c in clean if c.isdigit())
            if digits and len(digits) <= 2:
                lead.age = digits
            else:
                return ("Не понял возраст. Укажите числом, например «9», "
                        "или дату рождения в формате дд.мм.гггг."), False

    elif current == "phone":
        birthday = extract_birthday(clean)
        if birthday:
            lead.birthday = birthday
            conv.lead_step = "phone"
            return "Дату рождения записал. Теперь, пожалуйста, напишите телефон.", False
        phone = extract_phone(clean)
        if not phone:
            return ("Кажется, номер указан не полностью. Напишите телефон в "
                    "формате +7XXXXXXXXXX или 8XXXXXXXXXX."), False
        lead.phone = phone

    elif current == "branch":
        lead.branch = _match_branch(kb, clean) or clean[:255]
        conv.selected_branch = lead.branch

    elif current == "confirm":
        if _CANCEL_RE.search(low):
            conv.stage = STAGE_DISCOVERY
            conv.lead_step = ""
            return (
                "Хорошо, не отправляю заявку. Если передумаете — просто "
                "напишите, и мы продолжим с того же места.",
                False,
            )
        if _is_yes(clean):
            return await _submit(conv, bigben, max_client), True
        if _is_no(clean):
            # Пользователь хочет поправить данные — переходим в отдельный шаг
            # "correcting", где следующее сообщение ПЕРЕЗАПИШЕТ поле (а не
            # просто дополнит пустое, как _opportunistic_fill). Раньше здесь
            # только сбрасывался lead_step в "", а _opportunistic_fill в
            # ветке ниже не трогает уже заполненные телефон/возраст/дату
            # рождения — заявка бесконечно показывала неизменённые данные,
            # что бы человек ни написал.
            conv.lead_step = "correcting"
            return (
                "Хорошо, что нужно поправить? Например: «телефон "
                "89991234567», «ребёнку 10 лет», «филиал Ракетостроителей», "
                "«имя родителя: Иванова Анна» или «имя ребёнка: Миша». Или "
                "напишите «отмена», если передумали отправлять заявку."
            ), False
        # пытаемся обновить поля из свободного текста
        _opportunistic_fill(conv, clean, kb)
        return _confirmation_text(conv), False

    elif current == "correcting":
        if _CANCEL_RE.search(low):
            conv.stage = STAGE_DISCOVERY
            conv.lead_step = ""
            return (
                "Хорошо, не отправляю заявку. Если передумаете — просто "
                "напишите, и мы продолжим с того же места.",
                False,
            )
        if _apply_correction(conv, clean, kb):
            conv.lead_step = "confirm"
            return _confirmation_text(conv), False
        # Не смогли распознать поле — показываем текущие данные заявки
        # заново (а не голое сообщение об ошибке), чтобы человек не терял
        # из виду, что уже собрано, и мог просто написать «да».
        return (
            "Не понял, что именно поправить. Попробуйте, например: «телефон "
            "89991234567», «ребёнку 10 лет», «филиал Ракетостроителей», "
            "«имя родителя: Иванова Анна» или «имя ребёнка: Миша». Или "
            "напишите «отмена», если передумали отправлять заявку.\n\n"
            f"{_confirmation_text(conv)}"
        ), False

    return _ask_next(conv), False


async def _submit(conv: Conversation, bigben: BigBenClient, max_client: MaxClient) -> str:
    from app.admin_router import hand_off

    lead = conv.lead
    lead.course = conv.selected_course or lead.course
    lead.branch = lead.branch or conv.selected_branch
    source = f"MAX-бот Фоксинбург — запись ({lead.course or 'диагностика'})"

    ok = await bigben.create_lead(lead, source=source)
    conv.stage = STAGE_DONE

    # уведомляем администратора о новой заявке (без переключения в режим handoff)
    if max_client.configured:
        try:
            await hand_off(max_client, conv, reason="новая заявка с записи")
        except Exception:
            logger.exception("Не удалось уведомить администратора о заявке")
        # hand_off переводит этап в handoff — возвращаем DONE, чтобы бот не молчал
        conv.stage = STAGE_DONE

    if ok:
        await notify_slack(
            "Новая заявка из MAX\n\n"
            f"{conv.summary()}\n"
            f"Источник: {source}"
        )
        return (
            "Готово! ✅ Заявка отправлена, администратор свяжется с вами в "
            "ближайшее время, чтобы подобрать удобное время диагностики. "
            "Спасибо, что выбираете Фоксинбург! 🦊"
        )
    return (
        "Я сохранил вашу заявку и передал её администратору — он свяжется с "
        "вами в ближайшее время. Если удобно, можете также позвонить нам: "
        "8 993 923-23-09. Спасибо! 🦊"
    )


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
    if phone and not lead.phone:
        lead.phone = phone
    birthday = extract_birthday(text)
    if birthday and not lead.birthday:
        lead.birthday = birthday
    age = extract_age(text)
    if age and not lead.age:
        lead.age = age
    branch = _match_branch(kb, text)
    if branch:
        lead.branch = branch
        conv.selected_branch = branch


_PARENT_NAME_PREFIX_RE = re.compile(r"^(?:имя\s+родител[яю]|родитель)\s*[:\-]?\s*", re.IGNORECASE)
_CHILD_NAME_PREFIX_RE = re.compile(r"^(?:имя\s+реб[её]нка|реб[её]нок)\s*[:\-]?\s*", re.IGNORECASE)


def _apply_correction(conv: Conversation, text: str, kb: KnowledgeBase) -> bool:
    """Перезаписывает поле после явной просьбы «поправьте данные».

    В отличие от _opportunistic_fill (которая только дополняет ПУСТЫЕ поля,
    чтобы не затереть что-то по случайному совпадению в свободном тексте),
    здесь пользователь целенаправленно диктует новое значение в ответ на
    прямой вопрос «что нужно поправить?» — поэтому уже заполненное поле
    нужно именно перезаписать. Возвращает True, если что-то обновили.
    """
    lead = conv.lead
    clean = text.strip()

    m = _PARENT_NAME_PREFIX_RE.match(clean)
    if m:
        name = _extract_name_from_text(clean[m.end():])
        if name:
            lead.fio_parent = name
            return True

    m = _CHILD_NAME_PREFIX_RE.match(clean)
    if m:
        name = _extract_name_from_text(clean[m.end():])
        if name:
            lead.fio_child = name
            return True

    phone = extract_phone(clean)
    if phone:
        lead.phone = phone
        return True

    birthday = extract_birthday(clean)
    if birthday:
        lead.birthday = birthday
        lead.age = ""
        return True

    age = extract_age(clean)
    if age:
        lead.age = age
        lead.birthday = ""
        return True

    branch = _match_branch(kb, clean)
    if branch:
        lead.branch = branch
        conv.selected_branch = branch
        return True

    return False


_YES_RE = re.compile(
    r"\b(?:да|верно|подтвержда\w*|ага|угу|ок|окей|yes)\b|\bотправ\w*",
    re.IGNORECASE,
)


def _is_yes(text: str) -> bool:
    """Подтверждение на шаге confirm.

    Раньше это было точное совпадение с узким списком фраз ("да", "верно",
    "все верно", ...) — любая естественная формулировка вроде «Да, всё
    верно, отправляйте заявку» не совпадала ни с одной из них, и бот
    бесконечно повторял один и тот же текст подтверждения на любой ответ,
    не продвигая заявку. Тот же класс бага, что чинили в STAGE_HANDOFF
    (dc70d34), только на шаге оформления заявки.
    """
    low = text.lower().strip()
    if low == "+":
        return True
    if _is_no(low):
        return False
    return bool(_YES_RE.search(low))


_NO_RE = re.compile(
    r"нет|не\s*верно|неверно|исправ|поправ|измен|не\s*отправ|не\s*надо|"
    r"подожд\w*|погоди(?:те)?|\bстоп\b|\bно\b",
    re.IGNORECASE,
)


def _is_no(text: str) -> bool:
    """Отказ/просьба поправить или подождать на шаге confirm.

    Должна перекрывать отрицательные формы вроде «не отправляйте пока» —
    иначе \bотправ\w* в _YES_RE ловит «отправляйте» внутри такой фразы и
    заявка уходит в CRM ровно вопреки прямой просьбе пользователя.
    """
    return bool(_NO_RE.search(text.lower()))
