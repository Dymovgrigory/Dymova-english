"""Lead Manager: сбор данных для записи на пробное/диагностику и отправка в CRM.

Последовательно собирает ФИО родителя, ФИО ребёнка, возраст (или дату рождения),
телефон и филиал; проверяет корректность телефона и даты; формирует заявку и
отправляет её в BigBen CRM, после чего уведомляет администратора.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from app.bigben import BigBenClient
from app.intent import extract_age, extract_birthday, extract_phone
from app.knowledge.kb import KnowledgeBase
from app.max_client import MaxClient
from app.memory import Conversation, Lead, STAGE_DISCOVERY, STAGE_DONE, STAGE_LEAD
from app import profile
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
    if conv.lead_submitted:
        # Предыдущая заявка уже ушла в CRM — начинаем новую с чистого листа.
        # Без этого сброса ФИО/телефон/возраст из уже отправленной заявки
        # (например, тестовые данные) продолжали подставляться в каждую
        # следующую попытку записаться: "хочу записаться" сразу прыгало на
        # экран подтверждения со старыми данными, бот выглядел так, будто
        # отвечает одно и то же независимо от разговора, а повторное "да"
        # отправляло дубликат заявки в CRM. Отмена (cancel) сюда не
        # попадает — lead_submitted остаётся False, и незавершённая заявка
        # осознанно донабирается с того же места, как обещано в тексте
        # отмены.
        conv.lead = Lead()
        conv.lead_step = ""
        conv.lead_submitted = False
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


def _confirmation_text(conv: Conversation, changed: list[tuple[str, str]] | None = None) -> str:
    """Экран подтверждения. `changed` — что именно только что поправили.

    Дословно одинаковый блок в ответ на каждую правку читается как «бот меня
    не услышал»: в реальной переписке человек дважды диктовал имя ребёнка,
    потому что подтверждение выглядело неизменившимся. Поэтому сверху
    называем внесённые изменения.
    """
    lead = conv.lead
    branch = lead.branch or conv.selected_branch or "—"
    when = lead.birthday or (f"{lead.age} лет" if lead.age else "—")
    prefix = ""
    if changed:
        listed = ", ".join(f"{label} — {value}" for label, value in changed)
        prefix = f"Готово: {listed}.\n\n"
    return (
        prefix
        + "Проверьте, пожалуйста, заявку:\n"
        f"• Родитель: {lead.fio_parent}\n"
        f"• Ребёнок: {lead.fio_child}\n"
        f"• Возраст/дата рождения: {when}\n"
        f"• Телефон: {lead.phone}\n"
        f"• Формат/филиал: {branch}\n\n"
        "Всё верно? Напишите «да» — и я отправлю заявку, или поправьте данные."
    )


# Маркер для вызывающего кода: сообщение не про заявку, на него нужно
# ответить по существу (см. pending_question). Заявка при этом не теряется.
OFF_TOPIC = "\x00off-topic"


# Отказ продолжать. Основы, а не точные слова: человек пишет «не будем»,
# «не буду», «не будете» — раньше подходило только «не буду», и фраза
# «Не будем завершать» не совпадала ни с чем, оставляя единственный выход
# словом «отмена», о котором клиент не знает.
_CANCEL_RE = re.compile(
    r"позже|попозже|потом|не\s*сейчас|передумал\w*|не\s*хочу|не\s*хотим|"
    r"отмен\w*|не\s*буд\w*|расхотел\w*|не\s*готов\w*|хватит|прекрат\w*|"
    r"\bстоп\b|не\s*нужно",
    re.IGNORECASE,
)


def _exit_reply(conv: Conversation) -> str:
    """Выход из заявки без потери уже собранного."""
    lead = conv.lead
    if lead.fio_parent or lead.fio_child or lead.phone:
        return (
            "Хорошо, к заявке вернёмся позже — отправлять не буду. Всё, что вы "
            "уже назвали, сохранится, продолжим с того же места. А пока "
            "спрашивайте что угодно про курсы, цены и филиалы 😊"
        )
    return (
        "Без проблем, вернёмся к этому позже. Если захотите продолжить, "
        "я помогу подобрать курс или запись на бесплатную диагностику."
    )


def pending_question(conv: Conversation) -> str:
    """Чем закончить ответ на посторонний вопрос, чтобы заявка не потерялась."""
    if conv.lead_step == "correcting":
        return f"{_CORRECTION_HINT}\n\n{_confirmation_text(conv)}"
    return _ask_next(conv)


_CORRECTION_HINT = (
    "Что именно поправить? Например: «телефон 89991234567», «ребёнку 10 лет», "
    "«филиал Ракетостроителей», «имя родителя: Иванова Анна» или «имя "
    "ребёнка: Миша». Или напишите «отмена», если передумали отправлять заявку."
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

    # Согласие проверяем РАНЬШЕ отказа: «не буду ничего менять, отправляйте»
    # содержит «не буду», но означает ровно противоположное.
    if current == "confirm" and _is_yes(clean):
        return await _submit(conv, bigben, max_client), True

    # Отказ работает на любом шаге, а не только на подтверждении: бросить
    # заполнение можно в любой момент, иначе анкета превращается в ловушку.
    if _CANCEL_RE.search(low):
        conv.stage = STAGE_DISCOVERY
        conv.lead_step = ""
        return _exit_reply(conv), False

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
        if _is_no(clean):
            # Пользователь хочет поправить данные — переходим в отдельный шаг
            # "correcting", где следующее сообщение ПЕРЕЗАПИШЕТ поле (а не
            # просто дополнит пустое, как _opportunistic_fill). Раньше здесь
            # только сбрасывался lead_step в "", а _opportunistic_fill в
            # ветке ниже не трогает уже заполненные телефон/возраст/дату
            # рождения — заявка бесконечно показывала неизменённые данные,
            # что бы человек ни написал.
            conv.lead_step = "correcting"
            return f"Хорошо, {_CORRECTION_HINT[0].lower()}{_CORRECTION_HINT[1:]}", False
        # Экран подтверждения прямо предлагает поправить данные, поэтому
        # свободный текст здесь трактуем как правку с ПЕРЕЗАПИСЬЮ поля.
        changed = _apply_correction(conv, clean, kb)
        if changed:
            return _confirmation_text(conv, changed), False
        # Ни «да», ни «нет», ни правка — человек спросил что-то своё.
        # Отвечать за него здесь нечем: возвращаем маркер, и вызывающий
        # отвечает по существу, а потом напоминает про заявку. Раньше тут
        # повторялся тот же экран с «сначала завершим заявку» — на живой
        # переписке это выглядело как бот, который не слышит собеседника.
        return OFF_TOPIC, False

    elif current == "correcting":
        changed = _apply_correction(conv, clean, kb)
        if changed:
            conv.lead_step = "confirm"
            return _confirmation_text(conv, changed), False
        # Поле не распознали. Возможно, это была не правка, а вопрос —
        # пусть отвечает вызывающий, подсказку про правку он добавит сам
        # (pending_question).
        return OFF_TOPIC, False

    return _ask_next(conv), False


async def _submit(conv: Conversation, bigben: BigBenClient, max_client: MaxClient) -> str:
    from app.admin_router import hand_off

    lead = conv.lead
    lead.course = conv.selected_course or lead.course
    lead.branch = lead.branch or conv.selected_branch
    source = f"MAX-бот Фоксинбург — запись ({lead.course or 'диагностика'})"

    ok = await bigben.create_lead(lead, source=source)
    conv.stage = STAGE_DONE
    conv.lead_submitted = True
    conv.lead_submitted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

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
            f"{profile.lead_summary(conv)}\n"
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


def _opportunistic_fill(conv: Conversation, text: str, kb: KnowledgeBase) -> bool:
    """Дополняет ещё пустые поля данными, случайно найденными в тексте.

    Возвращает True, если что-то реально обновили — используется на шаге
    confirm, чтобы отличить "в свободном тексте была полезная деталь" от
    "человек просто спросил что-то не по теме заявки" (см. вызов ниже).
    """
    lead = conv.lead
    updated = False
    phone = extract_phone(text)
    if phone and not lead.phone:
        lead.phone = phone
        updated = True
    birthday = extract_birthday(text)
    if birthday and not lead.birthday:
        lead.birthday = birthday
        updated = True
    age = extract_age(text)
    if age and not lead.age:
        lead.age = age
        updated = True
    branch = _match_branch(kb, text)
    if branch:
        lead.branch = branch
        conv.selected_branch = branch
        updated = True
    return updated


_PARENT_NAME_PREFIX_RE = re.compile(r"^(?:имя\s+родител[яю]|родитель)\s*[:\-]?\s*", re.IGNORECASE)
_CHILD_NAME_PREFIX_RE = re.compile(r"^(?:имя\s+реб[её]нка|реб[её]нок)\s*[:\-]?\s*", re.IGNORECASE)


_SEGMENT_SPLIT_RE = re.compile(r"[,;\n]|\s+и\s+")


def _apply_correction(
    conv: Conversation, text: str, kb: KnowledgeBase
) -> list[tuple[str, str]]:
    """Перезаписывает поля после явной просьбы «поправьте данные».

    В отличие от _opportunistic_fill (которая только дополняет ПУСТЫЕ поля,
    чтобы не затереть что-то по случайному совпадению в свободном тексте),
    здесь пользователь целенаправленно диктует новое значение в ответ на
    прямой вопрос «что нужно поправить?» — поэтому уже заполненное поле
    нужно именно перезаписать.

    Применяем ВСЕ поля, которые нашли, а не первое попавшееся: на живой
    переписке «Родитель Григорий, ребенок Аделина» обновляло только
    родителя, и имя ребёнка приходилось диктовать вторым сообщением.

    Возвращает список пар (поле, новое значение) — вызывающий показывает их
    человеку, чтобы правка была видна.
    """
    lead = conv.lead
    clean = text.strip()
    changed: list[tuple[str, str]] = []

    # Имена ищем посегментно: у каждого свой префикс («родитель …»,
    # «ребёнок …»), и в одном сообщении их может быть несколько.
    for segment in _SEGMENT_SPLIT_RE.split(clean):
        segment = segment.strip()
        if not segment:
            continue
        m = _PARENT_NAME_PREFIX_RE.match(segment)
        if m:
            name = _extract_name_from_text(segment[m.end():])
            if name and name != lead.fio_parent:
                lead.fio_parent = name
                changed.append(("родитель", name))
            continue
        m = _CHILD_NAME_PREFIX_RE.match(segment)
        if m:
            name = _extract_name_from_text(segment[m.end():])
            if name and name != lead.fio_child:
                lead.fio_child = name
                changed.append(("ребёнок", name))

    # Остальные поля однозначны по формату — их достаточно искать во всём
    # сообщении целиком.
    phone = extract_phone(clean)
    if phone and phone != lead.phone:
        lead.phone = phone
        changed.append(("телефон", phone))

    birthday = extract_birthday(clean)
    if birthday and birthday != lead.birthday:
        lead.birthday = birthday
        lead.age = ""
        changed.append(("дата рождения", birthday))
    else:
        age = extract_age(clean)
        if age and age != lead.age:
            lead.age = age
            lead.birthday = ""
            changed.append(("возраст", f"{age} лет"))

    branch = _match_branch(kb, clean)
    if branch and branch != lead.branch:
        lead.branch = branch
        conv.selected_branch = branch
        changed.append(("филиал", branch))

    # Голое имя без «родитель»/«ребёнок» намеренно НЕ трогаем: на шаге
    # подтверждения под это подошло бы любое слово вроде «Привет», и правка
    # молча затёрла бы имя ребёнка.
    return changed


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
    иначе шаблон "отправ" в _YES_RE ловит «отправляйте» внутри такой фразы
    и заявка уходит в CRM ровно вопреки прямой просьбе пользователя.
    """
    return bool(_NO_RE.search(text.lower()))
