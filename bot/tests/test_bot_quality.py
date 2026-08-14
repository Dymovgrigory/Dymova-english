"""Качество ответов бота: валидация полей заявки, язык рекомендации, расписание.

Каждый тест — воспроизведение реальной продовой переписки, где бот
ответил не в попад.
"""
import pytest

from app import cabinet, importer
from app import intent as I
from app import lead_manager
from app import recommender
from app import memory as memory_module
from app.config import settings
from app.knowledge.kb import get_kb
from app.memory import Conversation, STAGE_LEAD, get_store


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    memory_module._store = None
    monkeypatch.setattr(settings, "MINIAPP_REQUIRE_REGISTRATION", False, raising=False)
    yield
    memory_module._store = None


# --- Имена: разговорный мусор не должен становиться ФИО ---------------------

@pytest.mark.parametrize("junk", [
    "Как дела",
    "Что расскажешь",
    "Меня зовут что расскажешь",
    "Привет",
    "Спасибо большое",
    "Сколько стоит",
])
def test_junk_is_not_a_name(junk):
    assert lead_manager._looks_like_name(
        lead_manager._extract_name_from_text(junk) or ""
    ) is False or lead_manager._extract_name_from_text(junk) == ""


@pytest.mark.parametrize("name", ["Григорий", "Аделина", "Иванова Анна", "Виолетта", "Реброва"])
def test_real_names_still_pass(name):
    assert lead_manager._extract_name_from_text(name) == name


# --- Телефон: все цифры одинаковые — не номер --------------------------------

def test_all_same_digit_phone_rejected():
    assert I.extract_phone("+79999999999") is None
    assert I.extract_phone("8 999 123 45 67") == "+79991234567"


# --- Возраст: «99 лет» не возраст ребёнка -------------------------------------

@pytest.mark.asyncio
async def test_implausible_age_rejected():
    conv = Conversation(user_id="u1")
    conv.stage = STAGE_LEAD
    conv.lead.fio_parent = "Григорий"
    conv.lead.fio_child = "Аделина"
    conv.lead_step = "age"
    reply, _ = await lead_manager.step(conv, "99 лет", get_kb(), None, None)
    assert conv.lead.age == ""
    assert "не возраст" in reply.lower() or "не понял" in reply.lower()


@pytest.mark.asyncio
async def test_plausible_age_accepted():
    conv = Conversation(user_id="u2")
    conv.stage = STAGE_LEAD
    conv.lead.fio_parent = "Григорий"
    conv.lead.fio_child = "Аделина"
    conv.lead_step = "age"
    await lead_manager.step(conv, "9 лет", get_kb(), None, None)
    assert conv.lead.age == "9"


# --- Вопрос посреди анкеты — не значение поля ---------------------------------

@pytest.mark.asyncio
async def test_question_mid_form_is_off_topic():
    conv = Conversation(user_id="u3")
    conv.stage = STAGE_LEAD
    conv.lead.fio_parent = "Григорий"
    conv.lead.fio_child = "Аделина"
    conv.lead.age = "9"
    conv.lead.phone = "+79991234567"
    conv.lead_step = "branch"
    reply, _ = await lead_manager.step(conv, "Как ты записал мое имя?", get_kb(), None, None)
    assert reply == lead_manager.OFF_TOPIC
    # Поле филиала при этом не заполнено вопросом.
    assert conv.lead.branch == ""


# --- Рекомендация: китайский не должен предлагать английский дошкольникам -----

def test_chinese_request_never_recommends_english_preschool():
    kb = get_kb()
    conv = Conversation(user_id="u4")
    conv.need.child_age = "6"
    conv.add("user", "Хотим китайский с нуля для дочери, ей 6")
    pick = recommender.suggest(kb, conv)
    if pick is not None:
        text = (pick.program + " " + " ".join(pick.alternatives)).lower()
        assert "дошкол" not in text or "китайск" in text


def test_english_request_keeps_age_programs():
    kb = get_kb()
    conv = Conversation(user_id="u5")
    conv.need.child_age = "6"
    conv.add("user", "Хотим английский для дочери, ей 6")
    # Английский — язык по умолчанию: возрастные программы не отсеиваются.
    programs = recommender._filter_by_language(
        recommender._candidates(kb), recommender._language_of(recommender.UserProfile.of(conv), conv)
    )
    assert any("дошкол" in p["name"].lower() for p in programs)


# --- Расписание в чате ----------------------------------------------------------

@pytest.mark.asyncio
async def test_schedule_reply_from_import():
    from app.ai_core import _schedule_reply

    store = get_store()
    conv = store.get("u6", platform="max")
    conv.lead.fio_child = "Маша"
    conv.lead.phone = "8 926 111 22 33"
    store.save(conv)

    importer.import_schedule(
        store,
        filename="schedule.csv",
        rows=[{"Ученик": "Маша", "Телефон": "89261112233", "День": "понедельник",
               "Время": "17:30", "Программа": "Kids", "Педагог": "Анна", "Филиал": "Лихачёвский"}],
        mapping={"student": "Ученик", "phone": "Телефон", "weekday": "День",
                 "time": "Время", "program": "Программа", "teacher": "Педагог",
                 "filial": "Филиал"},
        actor="test",
    )

    class FakeMax:
        configured = False

        async def send_message(self, *a, **kw):
            return False

    reply = await _schedule_reply(conv, FakeMax())
    assert reply is not None
    assert "понедельник" in reply
    assert "17:30" in reply
    assert "Расписание на" in reply


@pytest.mark.asyncio
async def test_schedule_reply_without_import_is_none_for_stranger():
    from app.ai_core import _schedule_reply

    conv = Conversation(user_id="u7", platform="max")

    class FakeMax:
        configured = False

    # Ни выгрузки, ни заявки — отвечает обычный путь (база знаний).
    assert await _schedule_reply(conv, FakeMax()) is None


# --- Род Фокси ------------------------------------------------------------------

def test_foxi_gender_is_pinned_in_prompt():
    from app.sales import SYSTEM_PROMPT

    assert "МУЖСКОГО рода" in SYSTEM_PROMPT
    assert "я понял" in SYSTEM_PROMPT
