"""Главное обещание ТЗ: бот не продаёт, пока не понял потребность.

Тесты идут через handle_message, то есть проверяют поведение целиком, а не
внутренности SMART (для них есть test_smart.py). LLM в тестах отключена —
это делает проверки детерминированными и заодно доказывает, что запрет
ранней продажи не держится на одном лишь тексте промпта.
"""
from __future__ import annotations

import pytest

from app import sales, smart
from app.ai_core import handle_message
from app.memory import Conversation, get_store
from app.smart import NeedProfile

# Признак продажи — именно призыв к действию, а не упоминание слова.
# Проверять по подстроке «пробн» нельзя: она встречается в самих данных
# прайса («Пробный урок — 1 125 ₽»), и цена в ответ на вопрос о цене —
# это не преждевременная продажа.
SALES_CTA = (
    "запишу вас",
    "запишу на",
    "записать вас",
    "запишитесь",
    "хотите записаться",
    "предлагаю записаться",
    "приходите на диагностик",
    "оставьте заявк",
    "начать с бесплатной диагностики",
    "подберём время для бесплатной диагностики",
    "запишу на бесплатную диагностику",
)


def _looks_like_sales(text: str) -> bool:
    return any(phrase in text.lower() for phrase in SALES_CTA)


@pytest.fixture(autouse=True)
def _fresh_store():
    """Каждый тест начинает с чистого диалога."""
    get_store()._data.clear()


async def test_greeting_does_not_offer_diagnostics():
    """Раньше на «здравствуйте» бот сразу звал на бесплатную диагностику."""
    reply = await handle_message("early-greet", "Здравствуйте")
    assert not _looks_like_sales(reply)


async def test_greeting_asks_about_the_learner():
    reply = await handle_message("early-greet2", "Здравствуйте")
    assert "?" in reply


async def test_bare_price_question_does_not_pitch():
    """«Сколько стоит?» — не повод предлагать пробное занятие."""
    reply = await handle_message("early-price", "Сколько стоит английский?")
    assert not _looks_like_sales(reply)
    assert "?" in reply


async def test_hidden_need_is_not_answered_with_a_course_offer():
    """«Ребёнок не хочет заниматься» — это проблема, а не запрос курса."""
    uid = "early-hidden"
    reply = await handle_message(uid, "Ребёнок не хочет заниматься английским")

    assert not _looks_like_sales(reply)
    profile = get_store().get(uid).need
    assert "нет мотивации" in profile.pain_points


async def test_fear_of_speaking_is_recorded_as_pain_point():
    uid = "early-fear"
    await handle_message(uid, "Дочь всё понимает, но боится говорить на уроке")
    profile = get_store().get(uid).need
    assert "страх говорить" in profile.pain_points


async def test_bot_does_not_repeat_the_same_question():
    """Повторный один и тот же вопрос — признак бота, который не слушает."""
    uid = "early-repeat"
    first = await handle_message(uid, "Здравствуйте")
    second = await handle_message(uid, "Сколько стоит?")
    assert first != second


async def test_question_count_is_capped():
    """Пять вопросов подряд — это анкета, а не разговор."""
    profile = NeedProfile()
    asked = []
    for _ in range(smart.MAX_DISCOVERY_QUESTIONS + 3):
        question = smart.next_question(profile)
        if question is None:
            break
        asked.append(question)
        smart.mark_asked(profile, question)
    assert len(asked) <= smart.MAX_DISCOVERY_QUESTIONS


async def test_age_from_message_unlocks_nothing_by_itself():
    """Знать возраст мало: цель по-прежнему неизвестна, продавать рано."""
    uid = "early-age"
    await handle_message(uid, "Сыну 9 лет")
    profile = get_store().get(uid).need
    assert profile.child_age == "9"
    assert not smart.sales_allowed(profile)


async def test_situation_plus_goal_unlocks_the_offer():
    uid = "early-ready"
    await handle_message(uid, "Сыну 9 лет, хотим чтобы он начал говорить по-английски")
    profile = get_store().get(uid).need
    assert smart.sales_allowed(profile)


# ---------------------- системный промпт ----------------------

def test_prompt_forbids_offer_while_need_unknown():
    from app.knowledge.kb import get_kb

    conv = Conversation(user_id="p1")
    prompt = sales.build_system_prompt(get_kb(), conv, "")
    assert "НЕ предлагай курс" in prompt
    assert "потребность ещё не ясна" in prompt


def test_prompt_allows_offer_once_need_is_clear():
    from app.knowledge.kb import get_kb

    conv = Conversation(user_id="p2")
    conv.need = NeedProfile(child_age="9", who=smart.WHO_PARENT, goals=["начать говорить"])
    prompt = sales.build_system_prompt(get_kb(), conv, "")
    assert "потребность понятна" in prompt


def test_prompt_lists_what_is_already_known():
    from app.knowledge.kb import get_kb

    conv = Conversation(user_id="p3")
    conv.need = NeedProfile(child_age="9", pain_points=["страх говорить"])
    prompt = sales.build_system_prompt(get_kb(), conv, "")
    assert "возраст ученика: 9" in prompt
    assert "страх говорить" in prompt


def test_prompt_bans_canned_enthusiasm():
    """ТЗ прямо запрещает дежурные восторги без причины."""
    assert "Отличный вопрос!" in sales.SYSTEM_PROMPT
    assert "Не используй дежурные восторги" in sales.SYSTEM_PROMPT


def test_prompt_requires_honesty_about_being_ai():
    assert "ИИ-консультант" in sales.SYSTEM_PROMPT


def test_prompt_no_longer_demands_selling_in_every_reply():
    """Старая формулировка и была причиной преждевременных предложений."""
    assert "Каждый ответ мягко ведёт" not in sales.SYSTEM_PROMPT


def test_prompt_tells_model_not_to_reask_answered_slots():
    from app.knowledge.kb import get_kb

    conv = Conversation(user_id="p4")
    conv.need = NeedProfile(asked_slots=["who"])
    prompt = sales.build_system_prompt(get_kb(), conv, "")
    assert "повторно не спрашивай" in prompt


# ---------------------- призыв к действию ----------------------

def test_nudge_asks_instead_of_selling_when_need_unknown():
    conv = Conversation(user_id="n1")
    assert not _looks_like_sales(sales.sales_nudge(conv))


def test_nudge_offers_only_once_need_is_clear():
    conv = Conversation(user_id="n2")
    conv.need = NeedProfile(child_age="9", who=smart.WHO_PARENT, goals=["начать говорить"])
    assert _looks_like_sales(sales.sales_nudge(conv))


def test_nudge_marks_the_question_as_asked():
    """Иначе тот же вопрос будет задан снова следующей репликой."""
    conv = Conversation(user_id="n3")
    sales.sales_nudge(conv)
    assert conv.need.questions_asked == 1


def test_nudge_returns_nothing_when_questions_are_exhausted():
    conv = Conversation(user_id="n4")
    conv.need = NeedProfile(questions_asked=smart.MAX_DISCOVERY_QUESTIONS)
    # Лимит исчерпан — гейт открывается, и появляется мягкое предложение.
    assert _looks_like_sales(sales.sales_nudge(conv))


# ---------------------- экономия запросов ----------------------

def test_lookup_questions_do_not_trigger_llm_extraction():
    """Справочный вопрос не несёт информации о потребности."""
    assert not smart.looks_informative("Сколько стоит?")
    assert not smart.looks_informative("А где вы находитесь?")


def test_situational_messages_do_trigger_extraction():
    assert smart.looks_informative("Сыну 9 лет, боится говорить")
    assert smart.looks_informative("Ребёнок не хочет заниматься")
    assert smart.looks_informative(
        "Мы переезжаем в другую страну и нужно быстро подтянуть разговорный язык "
        "до уровня свободного общения"
    )


# ----------------- бот не здоровается по второму разу -----------------


async def test_greeting_is_said_once_not_every_time():
    """В живой переписке бот поздоровался трижды — человек решил, что его забыли."""
    uid = "greet-once"
    first = await handle_message(uid, "Привет")
    await handle_message(uid, "Сыну 9 лет")
    later = await handle_message(uid, "Привет ещё раз")

    assert "Меня зовут Фокси" in first
    assert "Меня зовут Фокси" not in later
    assert later.strip()


async def test_small_talk_does_not_get_a_greeting():
    """«В целом неплохо, ветер сильный» — это разговор, а не приветствие."""
    uid = "greet-smalltalk"
    await handle_message(uid, "Здравствуйте")
    reply = await handle_message(uid, "В целом неплохо, только ветер сильный на улице")
    assert "Чем могу помочь" not in reply
