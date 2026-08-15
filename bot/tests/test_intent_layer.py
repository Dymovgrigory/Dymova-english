"""Намерение: ключевые слова плюс разбор по смыслу.

Два уровня проверяются раздельно. Первый — детерминированный: он обязан
понимать отрицание, иначе «я не хочу записываться» запускает сбор заявки у
человека, который от неё отказался. Второй — модельный: он подключается
только там, где первый ничего не понял, и не имеет права ни перебивать
уверенный разбор, ни выдумывать метки.
"""
from __future__ import annotations

import asyncio

import pytest

from app import ai_core, intent as I, intent_ai
from app.memory import Conversation, get_store


@pytest.fixture(autouse=True)
def _fresh_store():
    get_store()._data.clear()


# ------------------------- отрицание -------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Я не хочу записываться, просто спрашиваю про цены",
        "Пока не готов записаться",
        "Ещё не решил, записываться ли",
    ],
)
def test_refusal_is_not_a_signup(text):
    assert I.detect_intent(text) != I.WANT_SIGNUP


@pytest.mark.parametrize(
    "text",
    [
        "Хочу записаться",
        "Как записаться на пробное?",
        "Запишите меня на английский",
        "Не подскажете, как записаться?",
    ],
)
def test_real_signup_still_works(text):
    assert I.detect_intent(text) == I.WANT_SIGNUP


async def test_refusal_does_not_start_the_lead_form():
    """Сквозная проверка: анкету человеку не навязывают."""
    uid = "negation-live"
    reply = await ai_core.handle_message(uid, "Я не хочу записываться, просто спрашиваю про цены")
    assert get_store().get(uid).stage != "lead"
    assert "как вас зовут" not in reply.lower()


# ------------------------- модельный слой -------------------------


def test_prompt_separates_browsing_from_signup():
    """«Ищу занятия для дочки» — это не заявка.

    Модельный слой однажды классифицировал присматривающегося родителя как
    want_signup, и бот начинал оформление заявки человеку, который просто
    интересовался. Промпт обязан явно разделять эти случаи — тест сторожит
    эту границу от случайного вычитания при правках промпта.
    """
    assert "присматривается" in intent_ai._PROMPT
    assert "НЕ want_signup" in intent_ai._PROMPT


# ------------------------- возражения из брендбука -------------------------


@pytest.mark.parametrize(
    "text,key",
    [
        ("Мы, наверное, начнём попозже", "попозже"),
        ("Нам ещё рано, ему бы сначала по-русски научиться", "рано"),
        ("Он не хочет заниматься английским", "не хочет"),
        ("Ребёнок отказывается ходить на занятия", "не хочет"),
        ("Нам не подходит расписание", "расписание"),
        ("Нет удобного времени у групп", "расписание"),
    ],
)
def test_brandbook_objections_are_recognised(text, key):
    assert I.detect_objection(text) == key


def test_refusal_is_still_not_an_objection():
    """«Я не хочу записываться» — отказ, а не «ребёнок не хочет»."""
    assert I.detect_objection("Я не хочу записываться, просто спрашиваю") != "не хочет"


def test_new_objection_keys_have_answers():
    """Каждый распознаваемый ключ обязан иметь ответ в базе знаний."""
    from app.knowledge.kb import get_kb

    kb = get_kb()
    for key in ("попозже", "не хочет", "расписание", "рано"):
        assert kb.objection(key), key


# ------------------------- приветствие + вопрос -------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Здравствуйте! Сколько стоит английский для ребёнка?", I.PRICE),
        ("Привет, а где вы находитесь?", I.CONTACTS),
        ("Добрый день, ищу курс английского для сына", I.COURSES),
        ("Здравствуйте", I.GREETING),
        ("Привет!", I.GREETING),
        ("Здравствуйте, я пока не хочу записываться", I.GREETING),
    ],
)
def test_greeting_does_not_swallow_the_question(text, expected):
    """Приветствие не должно глушить содержательную часть сообщения."""
    assert I.detect_intent(text) == expected



async def test_refine_is_skipped_without_a_model():
    assert await intent_ai.refine("хотелось бы уже начать заниматься") is None


async def test_refine_is_skipped_for_short_messages(monkeypatch):
    monkeypatch.setattr(intent_ai, "get_gateway", lambda: _Gateway({}))
    assert await intent_ai.refine("а как?") is None


async def test_refine_returns_a_confident_label(monkeypatch):
    gateway = _Gateway({"intent": I.WANT_SIGNUP, "confidence": 0.9})
    monkeypatch.setattr(intent_ai, "get_gateway", lambda: gateway)
    result = await intent_ai.refine("хотелось бы уже начать, только не знаю с чего")
    assert result == I.WANT_SIGNUP


async def test_low_confidence_changes_nothing(monkeypatch):
    gateway = _Gateway({"intent": I.WANT_SIGNUP, "confidence": 0.2})
    monkeypatch.setattr(intent_ai, "get_gateway", lambda: gateway)
    assert await intent_ai.refine("хотелось бы уже начать, только не знаю с чего") is None


async def test_invented_label_is_rejected(monkeypatch):
    """Модель не может придумать маршрут, которого нет."""
    gateway = _Gateway({"intent": "buy_a_car", "confidence": 1.0})
    monkeypatch.setattr(intent_ai, "get_gateway", lambda: gateway)
    assert await intent_ai.refine("хотелось бы уже начать, только не знаю с чего") is None


async def test_broken_model_answer_is_survivable(monkeypatch):
    monkeypatch.setattr(intent_ai, "get_gateway", lambda: _Gateway(None, error=True))
    assert await intent_ai.refine("хотелось бы уже начать, только не знаю с чего") is None


async def test_context_is_passed_to_the_model(monkeypatch):
    gateway = _Gateway({"intent": I.PRICE, "confidence": 0.8})
    monkeypatch.setattr(intent_ai, "get_gateway", lambda: gateway)
    history = [{"role": "assistant", "content": "Сколько лет ребёнку?"}]
    await intent_ai.refine("а это вообще во сколько обойдётся?", history)
    joined = " ".join(m["content"] for m in gateway.seen)
    assert "Сколько лет ребёнку?" in joined


# ------------------------- связка с ядром -------------------------


async def test_keyword_intent_is_not_sent_to_the_model(monkeypatch):
    """За понятные сообщения платить незачем — модель не вызывается."""
    called = []

    async def spy(*args, **kwargs):
        called.append(args)
        return None

    monkeypatch.setattr(intent_ai, "refine", spy)
    conv = Conversation(user_id="intent-core")
    assert await ai_core._detect_intent(conv, "Сколько стоит абонемент?") == I.PRICE
    assert called == []


async def test_unclear_message_goes_to_the_model(monkeypatch):
    async def fake_refine(text, history=None, vault=None):
        return I.WANT_SIGNUP

    monkeypatch.setattr(intent_ai, "refine", fake_refine)
    conv = Conversation(user_id="intent-core-2")
    result = await ai_core._detect_intent(conv, "хотелось бы уже начать, только не знаю с чего")
    assert result == I.WANT_SIGNUP


async def test_slow_model_does_not_hold_up_the_answer(monkeypatch):
    async def slow_refine(text, history=None, vault=None):
        await asyncio.sleep(5)
        return I.WANT_SIGNUP

    monkeypatch.setattr(intent_ai, "refine", slow_refine)
    monkeypatch.setattr(ai_core, "INTENT_TIMEOUT_SEC", 0.05)
    conv = Conversation(user_id="intent-core-3")
    result = await ai_core._detect_intent(conv, "хотелось бы уже начать, только не знаю с чего")
    assert result == I.QUESTION


class _Gateway:
    """Шлюз, возвращающий заранее заданный разбор."""

    enabled = True

    def __init__(self, result, error: bool = False):
        self._result = result
        self._error = error
        self.seen: list[dict] = []

    async def structured(self, role, messages, schema, **kwargs):
        self.seen = messages
        if self._error:
            raise RuntimeError("провайдер недоступен")
        return self._result
