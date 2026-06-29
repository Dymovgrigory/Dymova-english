"""Тесты логики бота (без сети: LLM/MAX/BigBen не сконфигурированы)."""
import pytest

from app import intent as I
from app.ai_core import handle_message, handle_start, parse_utm
from app.bigben import build_params
from app.course_selector import recommend
from app.knowledge.kb import get_kb
from app.memory import Lead, STAGE_DONE, STAGE_HANDOFF, STAGE_LEAD, get_store


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
    assert I.detect_intent("Как дела?") == I.GREETING
    assert I.detect_intent("Сколько стоит обучение?") == I.PRICE
    assert I.detect_intent("Хочу узнать точную цену") == I.PRICE
    assert I.detect_intent("Что умеешь?") == I.ABOUT
    assert I.detect_intent("хочу записаться на пробное") == I.WANT_SIGNUP
    assert I.detect_intent("соедините с администратором") == I.HANDOFF
    assert I.detect_intent("это дорого для нас") == I.OBJECTION


def test_greeting_not_false_positive():
    # «ку» внутри «ребёнку» не должно распознаваться как приветствие
    assert I.detect_intent("По каким учебникам занимаетесь? Ребёнку 9 лет") != I.GREETING
    assert I.detect_intent("ку") == I.GREETING


def test_kb_has_textbooks():
    kb = get_kb()
    docs = kb.search("по каким учебникам английский My Level")
    assert docs
    assert any("My Level" in (d.title + d.text) for d in docs)


# ---------- цикл улучшения (insights) ----------

def test_insights_log_and_summarize(tmp_path, monkeypatch):
    from app import insights
    from app.config import settings

    monkeypatch.setattr(settings, "INSIGHTS_FILE", str(tmp_path / "insights.jsonl"))
    insights.log_gap("Есть ли парковка у филиала?", reason="no_kb", score=0.0, user_id="u1")
    insights.log_gap("есть ли парковка у филиала", reason="no_kb", score=0.1, user_id="u2")
    insights.log_gap("Можно ли оплатить картой?", reason="low_score", score=0.2, user_id="u1")

    s = insights.summarize(days=30, top=10)
    assert s["total_weak_answers"] == 3
    # две формулировки про парковку схлопываются в одну тему с count=2 и 2 юзерами
    top = s["gaps"][0]
    assert top["count"] == 2
    assert top["users"] == 2
    assert "digest" not in s
    assert "парков" in insights.digest(days=30).lower()


def test_digest_schedule_timing():
    from datetime import datetime, timedelta, timezone

    from app import scheduler
    from app.config import settings

    tz = timezone(timedelta(hours=settings.DIGEST_TZ_OFFSET))
    # за час до 21:00 -> примерно 3600 секунд
    before = datetime(2026, 6, 28, 20, 0, 0, tzinfo=tz)
    assert abs(scheduler._seconds_until_next_run(before) - 3600) < 2
    # после 21:00 -> переносится на следующий день (близко к 24ч)
    after = datetime(2026, 6, 28, 21, 30, 0, tzinfo=tz)
    assert scheduler._seconds_until_next_run(after) > 23 * 3600


def test_admin_commands(monkeypatch):
    from app import main
    from app.config import settings

    monkeypatch.setattr(settings, "ADMIN_MAX_IDS", "555,777")
    # /myid доступна всем
    assert "555" in main._admin_command("/myid", "555")
    assert "обычный" in main._admin_command("/myid", "111")
    # отчёт: админу — дайджест, обычному пользователю — None (как обычный вопрос)
    assert main._admin_command("/отчёт", "111") is None
    assert main._admin_command("/отчёт", "555").startswith("🛠 Админ-панель")


# ---------- UTM / атрибуция заявки ----------

def test_parse_utm_query_string():
    utm = parse_utm("utm_source=vk&utm_campaign=spring&foo=bar")
    assert utm == {"utm_source": "vk", "utm_campaign": "spring"}


def test_parse_utm_short_token():
    assert parse_utm("vk") == {"utm_source": "vk", "utm_medium": "referral"}
    assert parse_utm("") == {}


def test_build_params_includes_utm_and_contacts():
    lead = Lead(
        fio_parent="Иванова Анна", fio_child="Иванов Миша", phone="+79991234567",
        email="a@b.ru", city="Долгопрудный", course="Английский",
    )
    params = build_params(
        lead, source="MAX мини-приложение", note="заметка",
        utm={"utm_source": "vk", "utm_medium": "miniapp", "unknown": "x"},
    )
    assert params["email"] == "a@b.ru"
    assert params["city"] == "Долгопрудный"
    assert params["utm_source"] == "vk"
    assert params["utm_medium"] == "miniapp"
    assert "unknown" not in params
    assert params["user_note"] == "заметка"


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
    assert "?" in reply


@pytest.mark.asyncio
async def test_smalltalk_answers_with_next_step():
    uid = "test-smalltalk"
    get_store().reset(uid)
    reply = await handle_message(uid, "Как дела?")
    assert "сразу помогаю" in reply.lower() or "всё отлично" in reply.lower()
    assert "?" in reply


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

    reply = await handle_message(uid, "да")
    conv = get_store().get(uid)
    assert conv.stage == STAGE_DONE
    assert "заявк" in reply.lower()


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
