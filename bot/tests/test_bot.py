"""Тесты логики бота (без сети: LLM/MAX/BigBen не сконфигурированы)."""
import pytest

from app import intent as I
from app.ai_core import handle_message, handle_start
from app.course_selector import recommend
from app.knowledge.kb import get_kb
from app.memory import STAGE_DONE, STAGE_HANDOFF, STAGE_LEAD, get_store


# ---------- извлечение сущностей ----------

def test_extract_phone_variants():
    assert I.extract_phone("мой телефон 8 999 123-45-67") == "+79991234567"
    assert I.extract_phone("+7 (916) 732 31 69") == "+79167323169"
    assert I.extract_phone("позвоните вечером") is None


def test_extract_age():
    assert I.extract_age("сыну 9 лет") == "9"
    assert I.extract_age("ребёнку 5") == "5"
    assert I.extract_age("хочу английский") is None


def test_extract_birthday():
    assert I.extract_birthday("дата 2016-05-01") == "2016-05-01"
    assert I.extract_birthday("01.05.2016") == "2016-05-01"
    assert I.extract_birthday("32.13.2016") is None


def test_intents():
    assert I.detect_intent("Здравствуйте") == I.GREETING
    assert I.detect_intent("Сколько стоит обучение?") == I.PRICE
    assert I.detect_intent("хочу записаться на пробное") == I.WANT_SIGNUP
    assert I.detect_intent("зарегистрироваться") == I.REGISTER
    assert I.detect_intent("соедините с администратором") == I.HANDOFF
    assert I.detect_intent("это дорого для нас") == I.OBJECTION


# ---------- база знаний ----------

def test_kb_search_finds_relevant():
    kb = get_kb()
    docs = kb.search("сколько стоит немецкий")
    assert docs, "должны найтись документы"
    assert any("Немецкий" in d.title or "немец" in d.text.lower() for d in docs)


def test_kb_branches_loaded():
    kb = get_kb()
    assert len(kb.branches) == 2


# ---------- подбор курса ----------

def test_recommend_by_age():
    kb = get_kb()
    items = recommend(kb, "5")
    assert items
    assert any("дошкол" in p.get("name", "").lower() for p in items)


# ---------- диалоговые сценарии ----------

@pytest.mark.asyncio
async def test_greeting_does_not_dump_info():
    uid = "test-greet"
    get_store().reset(uid)
    reply = await handle_message(uid, "Здравствуйте")
    assert "Фоксинбург" in reply or "Здравствуйте" in reply
    # приветствие не должно вываливать прайс
    assert "8 200" not in reply


@pytest.mark.asyncio
async def test_signup_flow_collects_and_submits():
    uid = "test-signup"
    get_store().reset(uid)
    await handle_message(uid, "Хочу записаться на пробное")
    conv = get_store().get(uid)
    assert conv.stage == STAGE_LEAD

    await handle_message(uid, "Иванова Анна")
    await handle_message(uid, "Иванов Миша")
    await handle_message(uid, "9 лет")
    await handle_message(uid, "+79991234567")
    await handle_message(uid, "Лихачевский")
    # шаг подтверждения
    conv = get_store().get(uid)
    assert conv.lead.fio_parent == "Иванова Анна"
    assert conv.lead.fio_child == "Иванов Миша"
    assert conv.lead.phone == "+79991234567"
    assert conv.lead.age == "9"


@pytest.mark.asyncio
async def test_registration_request_starts_registration():
    uid = "test-register-request"
    get_store().reset(uid)
    reply = await handle_message(uid, "зарегистрироваться")
    conv = get_store().get(uid)
    assert conv.stage != STAGE_DONE
    assert "познаком" in reply.lower() or "зовут" in reply.lower()


@pytest.mark.asyncio
async def test_handoff_request():
    uid = "test-handoff"
    get_store().reset(uid)
    reply = await handle_message(uid, "позовите администратора, у меня жалоба")
    conv = get_store().get(uid)
    assert conv.stage == STAGE_HANDOFF
    assert "администратор" in reply.lower()


@pytest.mark.asyncio
async def test_objection_handling():
    uid = "test-obj"
    get_store().reset(uid)
    reply = await handle_message(uid, "это дорого")
    assert any(w in reply.lower() for w in ("рассрочк", "маткапитал", "диагностик", "год"))


@pytest.mark.asyncio
async def test_invalid_phone_reprompt():
    uid = "test-phone"
    get_store().reset(uid)
    await handle_message(uid, "Записаться")
    await handle_message(uid, "Анна")
    await handle_message(uid, "Миша")
    await handle_message(uid, "7")
    reply = await handle_message(uid, "не помню номер")
    assert "номер" in reply.lower() or "телефон" in reply.lower()
