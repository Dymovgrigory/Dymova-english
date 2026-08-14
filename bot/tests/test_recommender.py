"""Подбор программы: что предложить, с какой уверенностью и почему.

Главное свойство движка — умение промолчать. Предложить «хоть что-нибудь»
человеку, о котором мы почти ничего не знаем, — это и есть тот самый
преждевременный каталог, ради ухода от которого всё затевалось.
"""
from __future__ import annotations

import pytest

from app import emotion, recommender
from app.ai_core import handle_message
from app.knowledge.kb import get_kb
from app.memory import Conversation, Lead, get_store
from app.recommender import NEXT_ASK, NEXT_DIAGNOSTIC, NEXT_LEAD
from app.smart import NeedProfile


@pytest.fixture(autouse=True)
def _fresh_store():
    get_store()._data.clear()


def _conv(**kwargs) -> Conversation:
    conv = Conversation(user_id="rec-test")
    need = kwargs.pop("need", None)
    for key, value in kwargs.items():
        setattr(conv, key, value)
    if need is not None:
        conv.need = need
    return conv


def _informed_need() -> NeedProfile:
    return NeedProfile(
        who="родитель",
        child_age="9",
        level="начальный",
        goals=["заговорить"],
        motivations=["поездка"],
        preferred_format="группа",
    )


# ------------------------- когда предлагать нечего -------------------------


def test_nothing_is_suggested_to_a_stranger():
    assert recommender.suggest(get_kb(), _conv()) is None


def test_age_alone_is_not_enough_for_a_confident_offer():
    """Возраст — это ещё не потребность, и уверенность должна это отражать."""
    conv = _conv(need=NeedProfile(child_age="9"))
    pick = recommender.suggest(get_kb(), conv)
    assert pick is None or pick.confidence < 0.6


# ------------------------- когда есть что предложить -------------------------


def test_informed_profile_gets_a_program():
    pick = recommender.suggest(get_kb(), _conv(need=_informed_need()))
    assert pick is not None
    assert pick.program
    assert 0 < pick.confidence <= 1


def test_age_outside_the_range_is_not_offered():
    """Программу «3-6 лет» нельзя предлагать пятнадцатилетнему."""
    need = _informed_need()
    need.child_age = "15"
    pick = recommender.suggest(get_kb(), _conv(need=need))
    assert pick is not None
    assert "3-6" not in pick.program


def test_reason_quotes_what_the_person_said():
    pick = recommender.suggest(get_kb(), _conv(need=_informed_need()))
    assert "ребёнку 9" in pick.reason
    assert "заговорить" in pick.reason


def test_offer_text_has_program_and_one_call_to_action():
    pick = recommender.suggest(get_kb(), _conv(need=_informed_need()))
    text = pick.as_text()
    assert pick.program in text
    assert text.count("?") <= 1


# ------------------------- следующий шаг -------------------------


def test_next_action_is_a_question_while_the_gate_is_closed():
    conv = _conv(need=NeedProfile(child_age="9", preferred_format="группа"))
    pick = recommender.suggest(get_kb(), conv)
    if pick is not None:
        assert pick.next_best_action == NEXT_ASK


def test_upset_person_is_never_pushed_to_the_diagnostic():
    conv = _conv(need=_informed_need(), last_user_mood=emotion.ANGRY)
    pick = recommender.suggest(get_kb(), conv)
    assert pick is None or pick.next_best_action == NEXT_ASK


def test_person_with_a_phone_goes_to_the_lead():
    conv = _conv(need=_informed_need(), lead=Lead(phone="+79990000000"))
    pick = recommender.suggest(get_kb(), conv)
    assert pick.next_best_action == NEXT_LEAD


def test_confident_pick_invites_to_the_diagnostic():
    pick = recommender.suggest(get_kb(), _conv(need=_informed_need()))
    assert pick.next_best_action == NEXT_DIAGNOSTIC
    assert "диагностик" in pick.as_text()


# ------------------------- сквозной путь -------------------------


async def test_course_question_gets_a_reasoned_pick_not_a_catalogue():
    uid = "rec-live"
    store = get_store()
    conv = store.get(uid)
    conv.need = _informed_need()
    conv.lead.age = "9"
    store.save(conv)

    reply = await handle_message(uid, "Какие у вас есть программы?")

    assert "Судя по тому, что вы рассказали" in reply
    assert store.get(uid).recommended_program


async def test_pick_is_remembered_for_the_next_message():
    uid = "rec-live-2"
    store = get_store()
    conv = store.get(uid)
    conv.need = _informed_need()
    store.save(conv)

    await handle_message(uid, "Какие программы есть?")
    remembered = store.get(uid).recommended_program

    assert remembered
    assert store.get(uid).recommended_program == remembered
