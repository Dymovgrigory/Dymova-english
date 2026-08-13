"""Карточка клиента: единый взгляд на разрозненные источники.

Профиль ничего не хранит — он собирает. Поэтому проверяем именно сборку:
что поля берутся из канонического места, что заявка и SMART-профиль не
спорят друг с другом, и что температура лида считается по поступкам, а не
по длине переписки.
"""
from __future__ import annotations

from app import profile
from app.memory import STAGE_HANDOFF, Conversation, Lead
from app.profile import TEMP_COLD, TEMP_HOT, TEMP_WARM, UserProfile
from app.smart import STAGE_READY, NeedProfile


def _conv(**kwargs) -> Conversation:
    conv = Conversation(user_id="profile-test")
    for key, value in kwargs.items():
        setattr(conv, key, value)
    return conv


# ------------------------- сборка -------------------------


def test_profile_collects_from_both_sources():
    conv = _conv(
        lead=Lead(fio_parent="Иванова Анна", fio_child="Иванов Миша", age="9"),
        selected_branch="Лихачевский",
    )
    conv.need = NeedProfile(
        level="начальный",
        goals=["заговорить"],
        pain_points=["боится ошибаться"],
        preferred_format="группа",
    )
    card = UserProfile.of(conv)

    assert card.name == "Иванова Анна"
    assert card.child_name == "Миша"
    assert card.child_age == "9"
    assert card.english_level == "начальный"
    assert card.goals == ["заговорить"]
    assert card.pain_points == ["боится ошибаться"]
    assert card.preferred_format == "группа"
    assert card.location == "Лихачевский"


def test_need_profile_wins_over_stale_lead_age():
    """Возраст из разговора свежее, чем возраст из старой заявки."""
    conv = _conv(lead=Lead(age="7"))
    conv.need = NeedProfile(child_age="9")
    assert UserProfile.of(conv).child_age == "9"


def test_empty_conversation_gives_empty_profile():
    card = UserProfile.of(_conv())
    assert card.known() == {}
    assert card.lead_temperature == TEMP_COLD


def test_known_returns_only_filled_fields():
    """Известное ФИО родителя — это ещё и ответ на вопрос, кто решает."""
    conv = _conv(lead=Lead(fio_parent="Иванова Анна"))
    known = UserProfile.of(conv).known()
    assert known == {"name": "Иванова Анна", "decision_maker": "parent"}


def test_last_objection_becomes_an_objection():
    """Возражение, пойманное старым кодом, тоже часть картины."""
    conv = _conv(last_objection="дорого")
    assert UserProfile.of(conv).objections == ["дорого"]


def test_profile_does_not_mutate_the_sources():
    conv = _conv()
    conv.need = NeedProfile(goals=["заговорить"])
    card = UserProfile.of(conv)
    card.goals.append("сдать экзамен")
    assert conv.need.goals == ["заговорить"]


# ------------------------- температура -------------------------


def test_left_phone_is_hot():
    assert profile.temperature(_conv(lead=Lead(phone="+79990000000"))) == TEMP_HOT


def test_submitted_lead_is_hot():
    assert profile.temperature(_conv(lead_submitted=True)) == TEMP_HOT


def test_clear_need_with_chosen_course_is_hot():
    conv = _conv(selected_course="Английский для школьников")
    conv.need = _ready_profile()
    assert profile.temperature(conv) == TEMP_HOT


def test_clear_need_without_a_course_is_only_warm():
    conv = _conv()
    conv.need = _ready_profile()
    assert profile.temperature(conv) == TEMP_WARM


def test_silent_visitor_is_cold():
    assert profile.temperature(_conv()) == TEMP_COLD


def test_objection_cools_a_warming_lead():
    conv = _conv()
    conv.need = NeedProfile(who="родитель", child_age="9", objections=["дорого"])
    assert profile.temperature(conv) == TEMP_COLD


def test_objection_does_not_cool_someone_who_left_a_phone():
    """«А не дорого ли?» после заявки — уточнение, а не отказ."""
    conv = _conv(lead=Lead(phone="+79990000000"))
    conv.need = NeedProfile(objections=["дорого"])
    assert profile.temperature(conv) == TEMP_HOT


# ------------------------- сводка для администратора -------------------------


def test_lead_summary_gives_the_human_the_whole_picture():
    conv = _conv(
        lead=Lead(fio_parent="Иванова Анна", phone="+79990000000", fio_child="Иванов Миша"),
        stage=STAGE_HANDOFF,
        selected_course="Английский для школьников",
    )
    conv.need = NeedProfile(
        child_age="9",
        goals=["заговорить"],
        pain_points=["боится ошибаться"],
        objections=["дорого"],
    )
    summary = profile.lead_summary(conv)

    assert "+79990000000" in summary
    assert "Миша" in summary
    assert "заговорить" in summary
    assert "боится ошибаться" in summary
    assert "дорого" in summary
    assert "Английский для школьников" in summary
    assert "Температура:" in summary


def test_lead_summary_survives_an_empty_conversation():
    summary = profile.lead_summary(_conv())
    assert "ЗАЯВКА" in summary
    assert "Температура" in summary


def _ready_profile() -> NeedProfile:
    ready = NeedProfile(
        who="родитель",
        child_age="9",
        level="начальный",
        goals=["заговорить"],
        motivations=["хочет в поездку"],
    )
    assert ready.stage() == STAGE_READY, "профиль-фикстура должен быть полным"
    return ready
