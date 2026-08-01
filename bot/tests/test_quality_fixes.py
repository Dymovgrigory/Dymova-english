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
async def test_factual_questions_do_not_invent_prices(monkeypatch):
    """Новый контракт (сессия 36): при пустом KB бот НЕ уходит мгновенно к
    администратору — сначала спрашивает LLM (с живым веб-поиском). Но цифры
    выдумывать всё равно запрещено: если LLM не нашёл подтверждённых данных,
    он отвечает [UNKNOWN], и только тогда включается handoff."""
    class FakeKB:
        branches = []

        def search(self, query, limit=5):
            return []

        def search_scored(self, query, limit=5):
            return []

        def context_for(self, query, limit=5):
            return ""

    class FakeLLM:
        enabled = True
        calls = 0

        async def complete(self, messages, temperature=None):
            self.calls += 1
            return "[UNKNOWN] точных данных по стоимости в источниках нет."

    async def fake_search_web(query, limit=4):
        return []

    fake_llm = FakeLLM()
    monkeypatch.setattr(ai_core, "get_kb", lambda: FakeKB())
    monkeypatch.setattr(ai_core, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(ai_core, "search_web", fake_search_web)

    uid = "quality-factual"
    # Возраст уже известен — обходит уточняющий вопрос про курс/возраст
    # (см. test_bare_price_question_asks_clarifying_question_instead_of_giving_up).
    store = get_store()
    conv = store.get(uid)
    conv.lead.age = "9"
    store.save(conv)

    reply = await handle_message(uid, "Сколько стоит обучение?")

    assert fake_llm.calls == 1, "ожидали ровно один вызов LLM для фактического вопроса"
    assert "10500" not in reply
    assert "администратор" in reply.lower()


@pytest.mark.asyncio
async def test_bare_price_question_asks_clarifying_question_instead_of_giving_up():
    """Раньше голый "Сколько стоит?" без курса/возраста находил по
    ключевым словам нерелевантный документ, LLM честно отказывался
    называть цену по слабому контексту, и это перехватывалось как "не
    знаю" — шаблонная передача администратору, хотя цены для конкретных
    курсов есть в базе знаний. Теперь бот сначала уточняет курс/возраст,
    как это сделал бы живой менеджер."""
    reply = await handle_message("quality-price-clarify", "Сколько стоит?")

    assert "администратор" not in reply.lower()
    assert "курс" in reply.lower() or "возраст" in reply.lower()


@pytest.mark.asyncio
async def test_price_question_naming_a_course_skips_the_clarifying_loop():
    """Без учёта упоминания курса в самом сообщении "сколько стоит
    английский для ребёнка?" получал бы тот же уточняющий вопрос
    бесконечно: цифры в тексте нет (conv.lead.age не установится), а
    conv.selected_course нигде в кодовой базе не присваивается — тот же
    паттерн "узкое условие → одинаковый ответ навсегда", который чинили
    весь остальной сеанс."""
    uid = "quality-price-with-course"
    reply = await handle_message(uid, "сколько стоит английский для ребенка?")

    assert "для какого курса" not in reply.lower()


@pytest.mark.asyncio
async def test_uncertain_answer_retries_with_web_search(monkeypatch):
    """Если LLM ответила [UNKNOWN] по школьному/фактическому вопросу, бот
    делает вторую попытку с результатами живого веб-поиска, прежде чем
    передавать вопрос администратору (сессия 36)."""
    class FakeKB:
        branches = []

        def search(self, query, limit=5):
            return []

        def search_scored(self, query, limit=5):
            return [(0.5, None)]  # сильное покрытие — веб сразу не подключается

        def context_for(self, query, limit=5):
            return ""

    class Doc:
        def render(self):
            return "[ЕГЭ]\nКурс подготовки к ЕГЭ по английскому."

    class FakeKB2(FakeKB):
        def search_scored(self, query, limit=5):
            return [(0.5, Doc())]

    class FakeLLM:
        enabled = True
        calls = 0

        async def complete(self, messages, temperature=None):
            self.calls += 1
            if self.calls == 1:
                return "[UNKNOWN] нет актуальных данных."
            return "По данным ФИПИ, в 2026 году формат ЕГЭ по английскому не меняется."

    async def fake_search_web(query, limit=4):
        return [{"title": "ФИПИ", "url": "https://fipi.ru", "snippet": "Изменений в КИМ ЕГЭ 2026 по английскому нет."}]

    fake_llm = FakeLLM()
    monkeypatch.setattr(ai_core, "get_kb", lambda: FakeKB2())
    monkeypatch.setattr(ai_core, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(ai_core, "search_web", fake_search_web)

    uid = "quality-web-retry"
    store = get_store()
    conv = store.get(uid)
    conv.lead.age = "16"
    store.save(conv)

    reply = await handle_message(uid, "Что нового в ЕГЭ по английскому в 2026 году?")

    assert fake_llm.calls == 2, "ожидали первую попытку и веб-ретрай"
    assert "ФИПИ" in reply
    assert "администратор" not in reply.lower()
