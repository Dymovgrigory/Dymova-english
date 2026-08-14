"""Эмоциональный слой: главное последствие — кому нельзя ничего предлагать.

ТЗ формулирует требование одной фразой: «Если человек раздражён — не
рекламируй». Поэтому здесь проверяется не столько точность распознавания,
сколько поведение: недовольный человек не получает предложений ни через
промпт, ни через заготовки, ни через движок продажи.
"""
from __future__ import annotations

import pytest

from app import emotion, sales
from app.ai_core import handle_message
from app.knowledge.kb import get_kb
from app.memory import Conversation, get_store
from app.smart import NeedProfile


@pytest.fixture(autouse=True)
def _fresh_store():
    get_store()._data.clear()


# ------------------------- распознавание -------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Мне никто не перезвонил, сколько можно?",
        "Это уже претензия, а не вопрос",
        "Верните деньги за прошлый месяц",
        "Меня раздражает такое отношение",
        "ДА СКОЛЬКО МОЖНО ЖДАТЬ ОТВЕТА",
        "Ответьте наконец!!",
    ],
)
def test_anger_is_recognized(text):
    assert emotion.detect(text) == emotion.ANGRY


@pytest.mark.parametrize(
    "text",
    [
        "Мы уже всё пробовали, ничего не помогает",
        "У меня опустились руки",
        "Он терпеть не может английский",
    ],
)
def test_discouragement_is_recognized(text):
    assert emotion.detect(text) == emotion.DISCOURAGED


@pytest.mark.parametrize(
    "text",
    [
        "Переживаю, что он отстаёт от класса",
        "Боюсь, что не справится",
        "Сомневаюсь, что группа ему подойдёт",
    ],
)
def test_anxiety_is_recognized(text):
    assert emotion.detect(text) == emotion.ANXIOUS


def test_confusion_is_recognized():
    assert emotion.detect("Не понимаю, чем группа отличается") == emotion.CONFUSED


def test_short_caps_is_not_shouting():
    """«ОК» капсом — не крик, а привычка печатать."""
    assert emotion.detect("ОК") != emotion.ANGRY


def test_plain_question_is_curious():
    assert emotion.detect("А сколько стоит абонемент?") == emotion.CURIOUS


def test_neutral_statement_is_neutral():
    assert emotion.detect("Сыну девять лет") == emotion.NEUTRAL


# ------------------------- инерция состояния -------------------------


def test_anger_does_not_evaporate_on_the_next_message():
    """Недовольство не проходит от того, что следующая реплика спокойнее."""
    assert emotion.detect("Хорошо", previous=emotion.ANGRY) == emotion.ANGRY


def test_thanks_after_anger_returns_to_neutral_not_cheer():
    assert emotion.detect("Спасибо", previous=emotion.ANGRY) == emotion.NEUTRAL


def test_thanks_in_a_calm_dialogue_is_warm():
    assert emotion.detect("Спасибо!", previous=emotion.NEUTRAL) == emotion.WARM


def test_empty_message_keeps_the_previous_state():
    assert emotion.detect("", previous=emotion.ANXIOUS) == emotion.ANXIOUS


# ------------------------- последствия -------------------------


def test_offer_is_forbidden_to_an_upset_person():
    assert not emotion.allows_offer(emotion.ANGRY)
    assert not emotion.allows_offer(emotion.DISCOURAGED)
    assert not emotion.allows_offer(emotion.CONFUSED)


def test_offer_is_allowed_in_a_calm_dialogue():
    assert emotion.allows_offer(emotion.NEUTRAL)
    assert emotion.allows_offer(emotion.ANXIOUS)
    assert emotion.allows_offer(emotion.WARM)


def test_offer_gate_needs_both_conditions():
    """Понятная потребность не отменяет запрета для раздражённого человека."""
    conv = Conversation(user_id="gate")
    conv.need = _ready_profile()
    assert sales.offer_allowed(conv)
    conv.last_user_mood = emotion.ANGRY
    assert not sales.offer_allowed(conv)


def test_prompt_tells_the_model_not_to_advertise():
    conv = Conversation(user_id="prompt-angry")
    conv.need = _ready_profile()
    conv.last_user_mood = emotion.ANGRY
    prompt = sales.build_system_prompt(get_kb(), conv, "")
    assert "не рекламируй" in prompt
    assert "ЭТАП: потребность понятна" not in prompt


def test_nudge_is_silent_for_an_upset_person():
    conv = Conversation(user_id="nudge-angry")
    conv.need = _ready_profile()
    conv.last_user_mood = emotion.ANGRY
    assert sales.sales_nudge(conv) == ""


def test_nudge_still_invites_a_calm_person():
    conv = Conversation(user_id="nudge-calm")
    conv.need = _ready_profile()
    assert "диагностик" in sales.sales_nudge(conv)


def test_opening_acknowledges_the_emotion():
    assert emotion.opening(emotion.ANGRY).startswith("Извините")
    assert emotion.opening(emotion.NEUTRAL) == ""


# ------------------------- сквозной путь -------------------------


async def test_complaint_gets_no_advertising():
    uid = "angry-live"
    reply = await handle_message(uid, "Мне никто не перезвонил, сколько можно ждать?")
    low = reply.lower()
    for pitch in ("запишитесь", "запишу вас", "приходите на диагностик", "пробное занятие"):
        assert pitch not in low
    assert get_store().get(uid).last_user_mood == emotion.ANGRY


async def test_mood_survives_into_the_next_message():
    uid = "angry-live-2"
    await handle_message(uid, "Это уже претензия, никто не отвечает")
    await handle_message(uid, "Ну так что?")
    assert get_store().get(uid).last_user_mood == emotion.ANGRY


def _ready_profile() -> NeedProfile:
    return NeedProfile(
        who="родитель",
        child_age="9",
        level="начальный",
        goals=["заговорить"],
        motivations=["поездка"],
    )
