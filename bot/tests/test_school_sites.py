"""Занятия на базе гимназии 13 и школы 14: цена 8 000 ₽, расписание — у администратора.

Разбор прода 29.09: на вопросы про гимназию 13 бот отвечал общим списком групп
филиалов и ценой 9 000 ₽ — оба ответа неверны для этих площадок.
"""
import pytest

from app import ai_core, school_sites
from app import memory as memory_module
from app.config import settings


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    memory_module._store = None
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", False, raising=False)
    monkeypatch.setattr(settings, "IDENTIFICATION_REQUIRED", False, raising=False)
    yield
    memory_module._store = None


@pytest.mark.parametrize("text", [
    "Занятия на базе 13 гимназии Долгопрудный",
    "Можно узнать прайс на занятия в Гимназии 13?",
    "Добрый день! Хотелось бы узнать о расписании занятий по китайскому языку в гимназии 13 Долгопрудный",
    "сколько стоит в 14 школе",
    "занятия в школе №14",
    "а в 14-й школе есть английский?",
])
def test_detects_school_site(text):
    assert school_sites.mentions_school_site(text)


@pytest.mark.parametrize("text", [
    "Сколько стоит английский?",
    "Мой сын учится в 13 классе",
    "Ребёнку 14 лет, есть группа?",
    "Где находится филиал на Лихачевском?",
])
def test_ignores_other_texts(text):
    assert not school_sites.mentions_school_site(text)


@pytest.fixture
def handed_off(monkeypatch):
    calls = []

    async def fake_hand_off(client, conv, reason=""):
        calls.append(reason)

    monkeypatch.setattr(ai_core, "hand_off", fake_hand_off)
    return calls


@pytest.mark.asyncio
async def test_price_question_gets_8000_and_admin_for_schedule(handed_off):
    reply = await ai_core.handle_message("s1", "Можно узнать прайс на занятия в Гимназии 13?", platform="max")
    assert "8 000" in reply
    assert "9 000" not in reply
    assert "администратор" in reply
    assert handed_off, "администратор должен получить вопрос про расписание"


@pytest.mark.asyncio
async def test_schedule_question_is_not_answered_with_group_list(handed_off):
    reply = await ai_core.handle_message(
        "s2", "Какое расписание занятий по китайскому в гимназии 13?", platform="max"
    )
    assert "Вот актуальные группы" not in reply
    assert "администратор" in reply
    assert handed_off


@pytest.mark.asyncio
async def test_plain_mention_also_answered(handed_off):
    reply = await ai_core.handle_message("s3", "Занятия на базе 13 гимназии Долгопрудный", platform="max")
    assert "8 000" in reply
    assert handed_off


@pytest.mark.asyncio
async def test_regular_price_question_unchanged(handed_off):
    reply = await ai_core.handle_message("s4", "Сколько стоит английский для ребёнка 8 лет?", platform="max")
    assert "8 000" not in reply
    assert not handed_off


def test_kb_knows_school_site_price():
    from app.knowledge.kb import get_kb

    hits = get_kb().search("сколько стоит в гимназии 13", limit=5)
    assert any("8 000" in doc.text for doc in hits)
