import pytest

from app import intent as I
from app import ai_core
from app.ai_core import handle_message
from app.knowledge.kb import get_kb
from app.llm import _mostly_russian
from app.memory import Conversation, STAGE_DISCOVERY, STAGE_HANDOFF, get_store
from app import sales


@pytest.mark.asyncio
async def test_lead_name_validation_rejects_non_names_and_captures_age():
    uid = "quality-lead-name"
    get_store().reset(uid)

    await handle_message(uid, "Хочу записаться на пробное")
    reply = await handle_message(uid, "7 лет")
    conv = get_store().get(uid)
    assert conv.lead_step == "fio_parent"
    assert conv.lead.fio_parent == ""
    assert conv.lead.age == "7"
    assert "имя" in reply.lower() or "похоже" in reply.lower()

    reply = await handle_message(uid, "давайте запишемся на пробное")
    conv = get_store().get(uid)
    assert conv.lead_step == "fio_parent"
    assert conv.lead.fio_parent == ""
    assert "имя" in reply.lower() or "похоже" in reply.lower()

    reply = await handle_message(uid, "Иванова Мария Петровна")
    conv = get_store().get(uid)
    assert conv.lead.fio_parent == "Иванова Мария Петровна"
    assert conv.lead_step == "fio_child"
    assert "ребёнка" in reply.lower() or "имя" in reply.lower()

    reply = await handle_message(uid, "сыну 8 лет")
    conv = get_store().get(uid)
    assert conv.lead.age == "7"
    assert conv.lead.fio_child == ""
    assert conv.lead_step == "fio_child"
    assert "имя ребёнка" in reply.lower()


@pytest.mark.asyncio
async def test_child_name_reject_captures_age_when_missing():
    uid = "quality-child-age-capture"
    get_store().reset(uid)

    await handle_message(uid, "Хочу записаться")
    await handle_message(uid, "Иванова Анна")
    reply = await handle_message(uid, "сыну 8 лет")
    conv = get_store().get(uid)

    assert conv.lead.age == "8"
    assert conv.lead.fio_child == ""
    assert conv.lead_step == "fio_child"
    assert "имя ребёнка" in reply.lower()


def test_detect_intent_routes_complaints_to_handoff():
    assert I.detect_intent("Я недовольна, нам никто не перезвонил") == I.HANDOFF
    assert I.detect_intent("Хочу поговорить с руководителем") == I.HANDOFF


@pytest.mark.asyncio
async def test_complaint_handling_interrupts_lead_flow():
    uid = "quality-complaint-lead"
    get_store().reset(uid)
    await handle_message(uid, "Хочу записаться на пробное")
    await handle_message(uid, "Иванова Анна")

    reply = await handle_message(uid, "Я недовольна, нам никто не перезвонил")
    conv = get_store().get(uid)

    assert conv.stage == STAGE_HANDOFF
    assert "руковод" in reply.lower() or "администратор" in reply.lower()
    assert "как вас зовут" not in reply.lower()
    assert "фио" not in reply.lower()


def test_build_system_prompt_includes_real_branch_addresses():
    kb = get_kb()
    conv = Conversation(user_id="quality-sales-prompt")
    prompt = sales.build_system_prompt(kb, conv, "")
    assert "Лихачевский, 76к1" in prompt
    assert "Ракетостроителей, 9к3" in prompt


def test_build_system_prompt_includes_emotional_state():
    kb = get_kb()
    conv = Conversation(user_id="quality-sales-empathy")
    conv.last_user_mood = "needs_empathy"
    conv.last_user_topic = "цены"
    prompt = sales.build_system_prompt(kb, conv, "")
    assert "настроение собеседника: needs_empathy" in prompt
    assert "последняя тема: цены" in prompt


def test_mostly_russian_guard():
    assert _mostly_russian("Here's the information you requested: Introduction to Psychology") is False
    assert _mostly_russian("Стоимость от 8 200 ₽/мес, см. My Level 2") is True


@pytest.mark.asyncio
async def test_lead_soft_exit_keeps_fields_and_switches_to_discovery():
    uid = "quality-soft-exit"
    get_store().reset(uid)
    await handle_message(uid, "Хочу записаться")
    await handle_message(uid, "Иванова Анна")
    await handle_message(uid, "Иванов Миша")
    await handle_message(uid, "9 лет")

    reply = await handle_message(uid, "я попозже напишу")
    conv = get_store().get(uid)

    assert conv.stage == STAGE_DISCOVERY
    assert conv.lead.fio_parent == "Иванова Анна"
    assert conv.lead.fio_child == "Иванов Миша"
    assert conv.lead.age == "9"
    assert conv.lead.phone == ""
    assert "телефон" not in reply.lower()
    assert "позже" in reply.lower() or "без проблем" in reply.lower()


def test_sales_nudge_is_more_empathic_when_user_is_upset():
    conv = Conversation(user_id="quality-sales-nudge")
    conv.last_user_mood = "needs_empathy"
    text = sales.sales_nudge(conv)
    assert "понимаю" in text.lower()


@pytest.mark.asyncio
async def test_objection_route_uses_llm(monkeypatch):
    uid = "quality-objection-llm"
    get_store().reset(uid)

    class FakeLLM:
        enabled = True

        def __init__(self):
            self.calls = []

        async def complete(self, messages, temperature=None):
            self.calls.append(messages)
            return "Понимаю сомнения — давайте подберём удобный вариант."

    fake = FakeLLM()
    monkeypatch.setattr(ai_core, "get_llm", lambda: fake)

    reply = await handle_message(uid, "это дорого")

    assert fake.calls, "ожидали вызов LLM для возражения"
    assert "подберём" in reply.lower()


@pytest.mark.asyncio
async def test_factual_questions_do_not_use_llm_or_invent_prices(monkeypatch):
    class FakeKB:
        def search(self, query, limit=5):
            return []

        def context_for(self, query, limit=5):
            return ""

    class FakeLLM:
        enabled = True

        async def complete(self, messages, temperature=None):
            raise AssertionError("LLM should not be called for factual questions")

    monkeypatch.setattr(ai_core, "get_kb", lambda: FakeKB())
    monkeypatch.setattr(ai_core, "get_llm", lambda: FakeLLM())

    reply = await handle_message("quality-factual", "Сколько стоит обучение?")

    assert "10500" not in reply
    assert "не хочу придумывать" in reply.lower() or "не нашёл" in reply.lower()
