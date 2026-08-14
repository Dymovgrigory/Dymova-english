"""Качество ответов бота: валидация полей заявки, язык рекомендации, расписание.

Каждый тест — воспроизведение реальной продовой переписки, где бот
ответил не в попад.
"""
import pytest

from app import cabinet
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


# --- Род Фокси# --- Род Фокси ------------------------------------------------------------------

def test_foxi_gender_is_pinned_in_prompt():
    from app.sales import SYSTEM_PROMPT

    assert "МУЖСКОГО рода" in SYSTEM_PROMPT
    assert "я понял" in SYSTEM_PROMPT


# --- Тест уровня: 10 заданий, картинки, сбор предложения ----------------------

def test_level_test_has_ten_varied_questions():
    from app import leveltest

    assert len(leveltest.QUESTIONS) == 10
    types = {q["type"] for q in leveltest.QUESTIONS}
    assert {"choice", "picture", "order"} <= types
    # Картинки — это SVG, а не системные emoji.
    for q in leveltest.QUESTIONS:
        if q["type"] == "picture":
            assert q["art"].startswith("<svg")


def test_level_test_public_hides_answers_but_shows_art():
    from app import leveltest

    for q in leveltest.public_questions():
        assert "answer" not in q
    assert any("art" in q for q in leveltest.public_questions())


def test_level_test_order_question_grading():
    from app import leveltest

    order_q = next(q for q in leveltest.QUESTIONS if q["type"] == "order")
    good = leveltest.grade({order_q["id"]: list(order_q["answer"])})
    assert good["details"][5]["correct"] is True
    bad = leveltest.grade({order_q["id"]: [0, 1, 2]})
    assert bad["details"][5]["correct"] is False


def test_level_test_thresholds():
    from app import leveltest

    all_right = {q["id"]: q["answer"] for q in leveltest.QUESTIONS}
    assert leveltest.grade(all_right)["level"] == "B1+"
    assert leveltest.grade({})["level"] == "A0–A1"


# --- Две формы записи ---------------------------------------------------------

def test_two_signup_sheets_exist():
    from app import main as main_module

    js = (main_module._TGAPP_DIR / "app.js").read_text(encoding="utf-8")
    html = (main_module._TGAPP_DIR / "index.html").read_text(encoding="utf-8")
    # «Записаться на занятия» — форма с выбором направления; «на диагностику» —
    # отдельный лист, где уровень определяет методист, а не анкета.
    assert 'diagnostic: { title: "Запись на диагностику"' in js
    assert 'data-sheet="diagnostic"' in html
    assert "Записаться на занятия" in html
    assert "Методист определит уровень" in js
    assert "Подготовка к школе" in js and "Репетитор (1–4 классы)" in js
    # Кнопка подбора — «Оставить заявку», а не «Записаться на это».
    assert "Записаться на это" not in js
    assert "Оставить заявку" in js


def test_picker_age_ranges_by_audience():
    from app import main as main_module

    js = (main_module._TGAPP_DIR / "app.js").read_text(encoding="utf-8")
    # Ребёнку 3–10, подростку 11–17, себе — без ползунка.
    assert '["Ребёнку", 3, 10]' in js
    assert '["Подростку", 11, 17]' in js
    assert '["Себе", 0, 0]' in js
    # Ползунок не перезапрашивает подбор на каждый пиксель.
    assert "schedulePicker" in js
