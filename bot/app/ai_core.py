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
        # Убираем технические скобки из заголовков документов KB.
        import re
        clean_ctx = re.sub(r"\[([^\]]+)\]\n", r"📌 \1\n", kb_context)
        return (f"Вот что могу рассказать:\n\n{clean_ctx}\n\n"
                + sales.sales_nudge(conv))
    return (
        "Хороший вопрос! Чтобы ответить точно, подскажите, пожалуйста, возраст "
        "ребёнка и удобный формат (онлайн/офлайн). А можно сразу записаться на "
        "бесплатную диагностику — администратор всё подробно расскажет. 😊"
    )


def _is_question_during_lead(conv: Conversation, text: str, intent: str) -> bool:
    """Определяет, задаёт ли пользователь вопрос вместо ответа на поле заявки.

    Если текущий шаг — ожидание конкретных данных (ФИО, дата, телефон, филиал),
    а пользователь пишет что-то похожее на вопрос — возвращаем True.
    """
    low = text.lower().strip()
    current_step = conv.lead_step or "fio_parent"

    # Явные интенты-вопросы — всегда отвечаем
    if intent in (I.COURSES, I.PRICE, I.ABOUT, I.QUESTION):
        return True

    # Вопросительные слова / знак вопроса
    question_markers = ("?", "сколько", "какие", "когда", "где ", "как ",
                        "почему", "зачем", "можно ли", "есть ли", "а что",
                        "расскажи", "подскажи", "что включ", "что входит")
    if any(m in low for m in question_markers):
        # Но не на шаге confirm — там "?" может быть уточнением данных
        if current_step != "confirm":
            return True

    return False


def _user_agrees_to_signup(conv: Conversation, text: str) -> bool:
    """Проверяет, согласился ли пользователь на запись после предложения бота.

    Возвращает True, если:
    1) Последний ответ бота содержал предложение записаться/диагностику
    2) Пользователь ответил согласием (да, давайте, хочу, и т.п.)
    """
    low = text.lower().strip(" .!?")
    agreement_words = (
        "да", "давайте", "давай", "хорошо", "хочу", "можно", "конечно",
        "ок", "окей", "ладно", "ага", "запишите", "запиши", "записать",
        "готов", "готова", "согласен", "согласна", "yes", "+",
    )
    if low not in agreement_words and not any(low.startswith(w) for w in agreement_words):
        return False

    # Проверяем, предлагал ли бот записаться в последнем сообщении
    last_bot_msgs = [m for m in conv.history if m.get("role") == "assistant"]
    if not last_bot_msgs:
        return False
    last_bot = last_bot_msgs[-1].get("content", "").lower()
    signup_cues = (
        "записать", "диагностик", "пробн", "запишу", "подобрать время",
        "удобное время", "бесплатн", "записаться", "оставить заявку",
    )
    return any(cue in last_bot for cue in signup_cues)


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
    #    но позволяем выйти к оператору или задать вопрос.
    if conv.stage == STAGE_LEAD:
        intent = I.detect_intent(text)
        if intent == I.HANDOFF:
            await hand_off(max_client, conv, reason="запрос оператора")
            return _handoff_reply()
        # Если пользователь задаёт вопрос вместо ответа на поле — отвечаем
        # через LLM и мягко продолжаем сбор (без навязчивого «возвращаемся»).
        if _is_question_during_lead(conv, text, intent):
            answer = await _consult(conv, text)
            current_step = conv.lead_step or lead_manager._next_step(conv)
            reminder = lead_manager.PROMPTS.get(current_step, "")
            if reminder:
                return answer + "\n\n" + reminder
            return answer
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

    # 5. Явное намерение записаться — запускаем сбор лида в чате.
    #    Бот также предложит кнопку мини-приложения (через main.py).
    if intent == I.WANT_SIGNUP:
        return lead_manager.start(conv, user_text=text)

    # 5b. Если бот предложил записаться в предыдущем сообщении, а клиент
    #     согласился (давайте, да, хорошо, можно, хочу) — бесшовно начинаем сбор.
    if _user_agrees_to_signup(conv, text):
        return lead_manager.start(conv, user_text=text)

    # 6. Приветствие — пропускаем через LLM для естественного ответа.
    if intent == I.GREETING:
        conv.stage = STAGE_DISCOVERY
        reply = await _consult(conv, text)
        # Если LLM вернул дежурный fallback — заменяем на тёплое приветствие.
        if "подскажите, пожалуйста, возраст" in reply.lower():
            reply = (
                "Привет! 🦊 Рад вас слышать, у нас всё отлично!\n\n"
                "Чем могу помочь? Расскажу о курсах, ценах, запишу "
                "на бесплатную диагностику — спрашивайте! 😊"
            )
        return reply

    # 6b. Конкретные вопросы про содержание (учебники/материалы/методика) —
    #     отвечаем из базы знаний (RAG + LLM), а не подбором программ.
    if any(k in text.lower() for k in ("учебник", "пособи", "умк", "материал")):
        if conv.stage not in (STAGE_DONE,):
            conv.stage = STAGE_DISCOVERY
        return await _consult(conv, text)

    # 7. Если знаем возраст и спрашивают про курсы/программы — предлагаем подбор,
    #    но только если ещё не показывали рекомендацию (иначе — через LLM).
    if intent == I.COURSES and conv.lead.age and not conv.recs_shown:
        items = recommend(kb, conv.lead.age, conv.selected_format)
        recs = format_recommendations(items)
        if recs:
            conv.stage = STAGE_DISCOVERY
            conv.recs_shown = True
            return recs + "\n\n" + sales.sales_nudge(conv)

    # 8. Во всех прочих случаях — консультативный ответ по базе знаний.
    if conv.stage not in (STAGE_DONE,):
        conv.stage = STAGE_DISCOVERY
    return await _consult(conv, text)


def _handoff_reply() -> str:
    return (
        "Конечно, сейчас подключу нашего администратора — "
        "он скоро напишет вам прямо сюда! 🙌\n\n"
        "Если вопрос срочный, можете позвонить:\n"
        "• Лихачевский: 8 993 923-23-09\n"
        "• Ракетостроителей: 8 916 732-31-69"
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
        "Привет! 🦊 Я — Фокси из языковой школы «Фоксинбург» в "
        "Долгопрудном!\n\n"
        "Помогу подобрать курс, расскажу о ценах и филиалах, "
        "запишу на бесплатную диагностику 😊\n\n"
        "Напишите, например: «Сыну 9 лет, ищем английский» — и я подберу "
        "лучшую программу!"
    )
    conv.add("assistant", reply)
    store.save(conv)
    return reply
