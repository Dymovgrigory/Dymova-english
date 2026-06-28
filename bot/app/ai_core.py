"""AI Core: оркестратор «мышления» бота.

Перед каждым ответом проходит цикл принятия решения:
  что хочет пользователь → какая цель → какая информация нужна → где её найти →
  нужно ли уточнять / продавать / записывать / передавать человеку → ответ.

Соединяет распознавание намерения, память, поиск по базе знаний, продажи,
подбор курса, сбор лида и передачу администратору.
"""
from __future__ import annotations

import logging
from urllib.parse import parse_qs

from app import insights
from app import intent as I
from app.bigben import get_bigben
from app.config import settings
from app.course_selector import format_recommendations, recommend
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

_UTM_KEYS = (
    "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "utm_content", "fbclid", "fbp", "fbc",
)


def parse_utm(start_param: str) -> dict:
    """Разбирает нагрузку deep-link в UTM-метки.

    Поддерживает строку запроса («utm_source=vk&utm_campaign=spring») и
    короткое значение («vk» → utm_source=vk, utm_medium=referral).
    """
    raw = (start_param or "").strip()
    if not raw:
        return {}
    if "=" in raw:
        parsed = parse_qs(raw.lstrip("?"), keep_blank_values=False)
        utm = {k: v[0][:300] for k, v in parsed.items() if k in _UTM_KEYS and v}
        if utm:
            return utm
    token = raw[:300]
    return {"utm_source": token, "utm_medium": "referral"}


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


async def _consult(conv: Conversation, text: str) -> str:
    """Свободный консультативный ответ, основанный на базе знаний (RAG-lite)."""
    kb = get_kb()
    llm = get_llm()
    kb_context = kb.context_for(text, limit=5)

    # Цикл улучшения: если база знаний почти не покрывает вопрос — фиксируем пробел.
    score = kb.best_score(text)
    if score < settings.INSIGHTS_MIN_SCORE:
        insights.log_gap(
            text,
            reason="no_kb" if not kb_context else "low_score",
            score=score,
            user_id=conv.user_id,
        )

    if llm.enabled:
        system = sales.build_system_prompt(kb, conv, kb_context)
        messages = [{"role": "system", "content": system}]
        messages.extend(conv.history[-8:])
        reply = await llm.complete(messages)
        if reply:
            return reply

    # Fallback без LLM — отдаём найденные факты + мягкий призыв.
    if kb_context:
        return (f"Вот что у меня есть по вашему вопросу:\n\n{kb_context}\n\n"
                + sales.sales_nudge(conv))
    return (
        "Хороший вопрос! Чтобы ответить точно, подскажите, пожалуйста, возраст "
        "ребёнка и удобный формат (онлайн/офлайн). А можно сразу записаться на "
        "бесплатную диагностику — администратор всё подробно расскажет. 😊"
    )


async def handle_message(user_id: str, text: str) -> str:
    """Главная точка входа: принимает сообщение пользователя, возвращает ответ бота."""
    store = get_store()
    kb = get_kb()
    conv = store.get(user_id)
    conv.add("user", text)
    _capture_entities(conv, text)

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
        return ("Я уже передал ваш вопрос администратору — он скоро ответит. "
                "Если нужно что-то ещё, напишите, я помогу. 😊")

    intent = I.detect_intent(text)

    # 3. Запрос живого человека / нестандартная ситуация.
    if intent == I.HANDOFF:
        await hand_off(max_client, conv, reason="запрос оператора")
        return _handoff_reply()

    # 4. Возражение — отрабатываем по сценарию и подталкиваем к диагностике.
    if intent == I.OBJECTION:
        conv.stage = STAGE_OBJECTION
        key = I.detect_objection(text) or "подумаю"
        return sales.handle_objection(kb, key)

    # 5. Явное намерение записаться — запускаем сбор лида.
    if intent == I.WANT_SIGNUP:
        return lead_manager.start(conv)

    # 6. Приветствие — короткое, человеческое, без простыни про школу.
    if intent == I.GREETING and len(conv.history) <= 2:
        conv.stage = STAGE_DISCOVERY
        return (
            "Здравствуйте! 🦊 Рады видеть вас в школе «Фоксинбург».\n"
            "Подскажите, для кого подбираете занятия и сколько лет ребёнку — "
            "помогу выбрать подходящую программу. Или сразу запишу на бесплатную "
            "диагностику. 😊"
        )

    # 6b. Конкретные вопросы про содержание (учебники/материалы/методика) —
    #     отвечаем из базы знаний (RAG + LLM), а не подбором программ.
    if any(k in text.lower() for k in ("учебник", "пособи", "умк", "материал")):
        if conv.stage not in (STAGE_DONE,):
            conv.stage = STAGE_DISCOVERY
        return await _consult(conv, text)

    # 7. Если знаем возраст и спрашивают про курсы/программы — предлагаем подбор.
    if intent == I.COURSES and conv.lead.age:
        items = recommend(kb, conv.lead.age, conv.selected_format)
        recs = format_recommendations(items)
        if recs:
            conv.stage = STAGE_DISCOVERY
            return recs + "\n\n" + sales.sales_nudge(conv)

    # 8. Во всех прочих случаях — консультативный ответ по базе знаний.
    if conv.stage not in (STAGE_DONE,):
        conv.stage = STAGE_DISCOVERY
    return await _consult(conv, text)


def _handoff_reply() -> str:
    return (
        "Конечно, подключаю администратора — он скоро напишет вам здесь. 🙌\n"
        "Если вопрос срочный, можно позвонить: 8 993 923-23-09 "
        "(Лихачевский) или 8 916 732-31-69 (Ракетостроителей)."
    )


async def handle_start(user_id: str, start_param: str = "") -> str:
    """Ответ на команду /start или событие bot_started.

    start_param — необязательная нагрузка deep-link (например
    «utm_source=vk&utm_campaign=spring» или просто «vk»), из которой
    извлекаются UTM-метки для атрибуции заявки в CRM.
    """
    store = get_store()
    conv = store.reset(user_id)
    conv.stage = STAGE_DISCOVERY
    if start_param:
        conv.utm = parse_utm(start_param)
    reply = (
        "Здравствуйте! 🦊 Я — консультант языковой школы «Фоксинбург» в "
        "Долгопрудном. Помогу подобрать курс, расскажу о ценах, филиалах и "
        "запишу на бесплатную диагностику.\n\n"
        "С чего начнём? Можете написать, например: «Сыну 9 лет, ищем английский»."
    )
    conv.add("assistant", reply)
    store.save(conv)
    return reply
