"""AI Core: оркестратор «мышления» бота.

Перед каждым ответом проходит цикл принятия решения:
  что хочет пользователь → какая цель → какая информация нужна → где её найти →
  нужно ли уточнять / продавать / записывать / передавать человеку → ответ.

Соединяет распознавание намерения, память, поиск по базе знаний, продажи,
подбор курса, сбор лида и передачу администратору.
"""
from __future__ import annotations

import logging
import re

from app import intent as I
from app import registration
from app.bigben import get_bigben
from app.course_selector import format_recommendations, recommend
from app.config import settings
from app.knowledge.kb import get_kb
from app.llm import get_llm
from app.max_client import get_max
from app.memory import (
    Conversation,
    STAGE_DISCOVERY,
    STAGE_DONE,
    STAGE_HANDOFF,
    STAGE_LEAD,
    STAGE_OBJECTION,
    get_store,
)
from app import sales
from app import lead_manager
from app.admin_router import hand_off

logger = logging.getLogger(__name__)


def _capture_entities(conv: Conversation, text: str) -> None:
    """Опортунистически вытаскиваем возраст/телефон/формат из любого сообщения."""
    age = I.extract_age(text)
    if age and not conv.lead.age:
        conv.lead.age = age
    phone = I.extract_phone(text)
    if phone and not conv.lead.phone:
        conv.lead.phone = phone
    low = text.lower()
    if "онлайн" in low and not conv.selected_format:
        conv.selected_format = "Онлайн"
    elif ("офлайн" in low or "оффлайн" in low) and not conv.selected_format:
        conv.selected_format = "Офлайн"


def _wants_manager(text: str) -> bool:
    low = text.lower()
    return any(word in low for word in ("руковод", "директор", "администрат", "начальник"))


def _drop_trailing_question(text: str) -> str:
    stripped = text.rstrip()
    if stripped.endswith("?"):
        stripped = stripped[:-1].rstrip()
        cut = max(stripped.rfind("."), stripped.rfind("!"), stripped.rfind("…"))
        if cut >= 0:
            stripped = stripped[: cut + 1]
        elif stripped:
            stripped += "."
    return stripped


def _handoff_followup_reply(conv: Conversation, text: str) -> str:
    if _wants_manager(text):
        return (
            "Понимаю, сейчас подключу руководителя или администратора — "
            "он скоро ответит. Если срочно, можно позвонить: 8 993 923-23-09 "
            "(Лихачевский) или 8 916 732-31-69 (Ракетостроителей)."
        )
    variants = [
        "Я уже передал ваш вопрос администратору — он скоро ответит. Если нужно что-то ещё, напишите, я помогу. 😊",
        "Вопрос уже у администратора, он скоро подключится. Если хотите, могу пока подсказать по курсам или расписанию. 😊",
    ]
    return variants[len(conv.history) % len(variants)]


async def _consult_with_context(conv: Conversation, text: str, kb_context: str) -> str:
    kb = get_kb()
    llm = get_llm()
    if llm.enabled:
        system = sales.build_system_prompt(kb, conv, kb_context)
        messages = [{"role": "system", "content": system}]
        history_turns = max(0, int(getattr(settings, "LLM_HISTORY_TURNS", 8)))
        messages.extend(conv.history[-history_turns:])
        reply = await llm.complete(messages)
        if reply:
            return reply
    if kb_context:
        return f"Вот что у меня есть по вашему вопросу:\n\n{kb_context}\n\n" + sales.sales_nudge(conv)
    return (
        "Хороший вопрос! Чтобы ответить точно, подскажите, пожалуйста, возраст "
        "ребёнка и удобный формат (онлайн/офлайн). А можно сразу записаться на "
        "бесплатную диагностику — администратор всё подробно расскажет. 😊"
    )


async def _consult(conv: Conversation, text: str) -> str:
    """Свободный консультативный ответ, основанный на базе знаний (RAG-lite)."""
    kb = get_kb()
    kb_context = kb.context_for(text, limit=5)
    return await _consult_with_context(conv, text, kb_context)


async def handle_message(user_id: str, text: str) -> str:
    """Главная точка входа: принимает сообщение пользователя, возвращает ответ бота."""
    store = get_store()
    kb = get_kb()
    conv = store.get(user_id)
    conv.add("user", text)
    _capture_entities(conv, text)

    if not registration.is_registered(conv):
        if conv.stage != registration.STAGE_REGISTRATION:
            reply = registration.start_registration(conv)
        else:
            reply, _done = await registration.handle_registration_step(
                conv, text, get_bigben()
            )
        conv.add("assistant", reply)
        store.save(conv)
        return reply

    reply = await _route(conv, text, kb)

    conv.add("assistant", reply)
    store.save(conv)
    return reply


async def _route(conv: Conversation, text: str, kb) -> str:
    max_client = get_max()
    bigben = get_bigben()

    # 1. Если уже идёт сбор данных для заявки — продолжаем его,
    #    но позволяем выйти к оператору.
    if conv.stage == STAGE_LEAD:
        if I.detect_intent(text) == I.HANDOFF:
            await hand_off(max_client, conv, reason="запрос оператора")
            return _handoff_reply()
        reply, _submitted = await lead_manager.step(conv, text, kb, bigben, max_client)
        return reply

    # 2. Уже передан администратору — не перебиваем, но подтверждаем.
    if conv.stage == STAGE_HANDOFF:
        return _handoff_followup_reply(conv, text)

    intent = I.detect_intent(text)

    # 3. Запрос живого человека / нестандартная ситуация.
    if intent == I.HANDOFF:
        await hand_off(max_client, conv, reason="запрос оператора")
        return _handoff_reply()

    # 4. Возражение — отрабатываем по сценарию и подталкиваем к диагностике.
    if intent == I.OBJECTION:
        conv.stage = STAGE_OBJECTION
        key = I.detect_objection(text) or "подумаю"
        if get_llm().enabled:
            return await _consult_with_context(conv, text, sales.handle_objection(kb, key))
        return sales.handle_objection(kb, key)

    # 5. Явное намерение открыть кабинет — запускаем регистрацию.
    if intent == I.REGISTER:
        return registration.start_registration(conv)

    # 6. Явное намерение записаться — запускаем сбор лида.
    if intent == I.WANT_SIGNUP:
        return lead_manager.start(conv)

    # 7. Приветствие — короткое, человеческое, без простыни про школу.
    if intent == I.GREETING and len(conv.history) <= 2:
        conv.stage = STAGE_DISCOVERY
        return (
            "Здравствуйте! 🦊 Рады видеть вас в школе «Фоксинбург».\n"
            "Подскажите, для кого подбираете занятия и сколько лет ребёнку — "
            "помогу выбрать подходящую программу. Или сразу запишу на бесплатную "
            "диагностику. 😊"
        )

    # 8. Если знаем возраст и спрашивают про курсы/программы — предлагаем подбор.
    if intent == I.COURSES and conv.lead.age:
        items = recommend(kb, conv.lead.age, conv.selected_format)
        recs = format_recommendations(items)
        if recs:
            conv.stage = STAGE_DISCOVERY
            return recs + "\n\n" + sales.sales_nudge(conv)

    # 9. Во всех прочих случаях — консультативный ответ по базе знаний.
    if conv.stage not in (STAGE_DONE,):
        conv.stage = STAGE_DISCOVERY
    return await _consult(conv, text)


def _handoff_reply() -> str:
    return (
        "Конечно, подключаю администратора — он скоро напишет вам здесь. 🙌\n"
        "Если вопрос срочный, можно позвонить: 8 993 923-23-09 "
        "(Лихачевский) или 8 916 732-31-69 (Ракетостроителей)."
    )


async def handle_start(user_id: str) -> str:
    """Ответ на команду /start или событие bot_started."""
    store = get_store()
    conv = store.get(user_id)
    if not registration.is_registered(conv):
        reply = registration.start_registration(conv)
        conv.add("assistant", reply)
        store.save(conv)
        return reply
    if conv.is_returning():
        reply = (
            "Привет! С возвращением! 🦊 Я помню ваш прошлый диалог и помогу "
            "продолжить с того места, где остановились."
        )
        conv.add("assistant", reply)
        store.save(conv)
        return reply
    conv.stage = STAGE_DISCOVERY
    reply = (
        "Привет! 🦊 Я — консультант языковой школы «Фоксинбург» в "
        "Долгопрудном. Помогу подобрать курс, расскажу о ценах, филиалах и "
        "запишу на бесплатную диагностику.\n\n"
        "С чего начнём? Можете написать, например: «Сыну 9 лет, ищем английский»."
    )
    conv.add("assistant", reply)
    store.save(conv)
    return reply


__all__ = [
    "handle_message",
    "handle_start",
    "_consult_with_context",
    "_drop_trailing_question",
    "_handoff_followup_reply",
    "_wants_manager",
]
