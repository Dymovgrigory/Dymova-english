"""SMART: модель потребности, гейт продажи и правило одного вопроса."""
from __future__ import annotations

import pytest

from app import llm_gateway, smart
from app.memory import Conversation, MemoryStore
from app.smart import (
    MAX_DISCOVERY_QUESTIONS,
    STAGE_COLD,
    STAGE_READY,
    STAGE_WARMING,
    WHO_ADULT,
    WHO_PARENT,
    NeedProfile,
    enrich_from_text,
    extract,
    mark_asked,
    next_question,
    sales_allowed,
    summary,
)


class FakeGateway:
    def __init__(self, payload):
        self.payload = payload
        self.enabled = True
        self.calls = 0

    async def structured(self, role, messages, schema, **kwargs):
        self.calls += 1
        return self.payload


@pytest.fixture
def gateway(monkeypatch):
    def install(payload):
        fake = FakeGateway(payload)
        monkeypatch.setattr(smart, "get_gateway", lambda: fake)
        return fake

    return install


# --------------------------- полнота профиля ---------------------------

def test_empty_profile_is_cold():
    assert NeedProfile().stage() == STAGE_COLD


def test_age_alone_is_not_enough_to_sell():
    """Знать возраст — ещё не значит понимать потребность."""
    profile = NeedProfile(child_age="9", who=WHO_PARENT)
    assert profile.stage() == STAGE_WARMING
    assert not sales_allowed(profile)


def test_goal_alone_is_not_enough_to_sell():
    profile = NeedProfile(goals=["начать говорить"])
    assert profile.stage() == STAGE_WARMING
    assert not sales_allowed(profile)


def test_situation_plus_purpose_unlocks_sales():
    profile = NeedProfile(child_age="9", who=WHO_PARENT, goals=["начать говорить"])
    assert profile.stage() == STAGE_READY
    assert sales_allowed(profile)


def test_pain_point_counts_as_purpose():
    """«Ребёнок не хочет заниматься» — это потребность, хоть цель и не названа."""
    profile = NeedProfile(child_age="9", pain_points=["нет мотивации"])
    assert profile.stage() == STAGE_READY


def test_adult_learner_needs_no_child_age():
    profile = NeedProfile(who=WHO_ADULT, goals=["язык для жизни за границей"])
    assert profile.stage() == STAGE_READY


def test_sales_unlocked_after_too_many_questions():
    """Анкета из пяти вопросов хуже предложения по неполным данным."""
    profile = NeedProfile(questions_asked=MAX_DISCOVERY_QUESTIONS)
    assert profile.stage() != STAGE_READY
    assert sales_allowed(profile)


def test_missing_lists_gaps_in_priority_order():
    profile = NeedProfile()
    assert profile.missing()[:2] == ["who", "purpose"]


# --------------------------- правило одного вопроса ---------------------------

def test_next_question_returns_exactly_one_question():
    question = next_question(NeedProfile())
    assert question is not None
    assert question.count("?") <= 2  # допустима естественная пара «возраст + уровень»


def test_opener_pairs_age_and_level():
    """ТЗ разрешает связку из двух близких вопросов в первой реплике."""
    question = next_question(NeedProfile())
    assert "лет" in question and "уровень" in question


def test_same_slot_is_never_asked_twice():
    """Повторный тот же вопрос — верный признак бота, который не слушает."""
    profile = NeedProfile()
    first = next_question(profile)
    mark_asked(profile, first)
    second = next_question(profile)
    assert second != first


def test_answered_slot_drops_out_of_questions():
    profile = NeedProfile(child_age="9", who=WHO_PARENT)
    question = next_question(profile)
    assert "лет" not in question  # возраст уже знаем


def test_questions_stop_after_the_limit():
    profile = NeedProfile(questions_asked=MAX_DISCOVERY_QUESTIONS)
    assert next_question(profile) is None


def test_mark_asked_records_both_slots_of_paired_opener():
    profile = NeedProfile()
    mark_asked(profile, next_question(profile))
    assert "who" in profile.asked_slots and "level" in profile.asked_slots
    assert profile.questions_asked == 1


def test_mark_asked_ignores_none():
    profile = NeedProfile()
    mark_asked(profile, None)
    assert profile.questions_asked == 0


# --------------------------- извлечение без LLM ---------------------------

def test_enrich_reads_age_and_parent():
    profile = NeedProfile()
    enrich_from_text(profile, "сыну 9 лет, ищем английский")
    assert profile.child_age == "9"
    assert profile.who == WHO_PARENT


def test_enrich_reads_adult_learner():
    profile = NeedProfile()
    enrich_from_text(profile, "хочу заниматься для себя, я взрослый")
    assert profile.who == WHO_ADULT


def test_enrich_detects_hidden_pain_point():
    """«Не хочет заниматься» — это боль, а не запрос курса."""
    profile = NeedProfile()
    enrich_from_text(profile, "ребёнок не хочет заниматься английским")
    assert "нет мотивации" in profile.pain_points


def test_enrich_detects_fear_of_speaking():
    profile = NeedProfile()
    enrich_from_text(profile, "она всё понимает, но боится говорить и стесняется")
    assert "страх говорить" in profile.pain_points


def test_enrich_detects_exam_goal():
    profile = NeedProfile()
    enrich_from_text(profile, "нужно подготовиться к ОГЭ")
    assert "подготовка к экзамену" in profile.goals


def test_enrich_reads_grade_and_format():
    profile = NeedProfile()
    enrich_from_text(profile, "дочь в 5 классе, удобнее онлайн")
    assert profile.child_grade == "5"
    assert profile.preferred_format == "онлайн"


def test_enrich_does_not_overwrite_known_values():
    profile = NeedProfile(child_age="9")
    enrich_from_text(profile, "а брату 14 лет")
    assert profile.child_age == "9"


def test_enrich_ignores_implausible_age():
    profile = NeedProfile()
    enrich_from_text(profile, "жду уже 0 лет")
    assert profile.child_age == ""


# --------------------------- merge ---------------------------

def test_merge_adds_without_erasing():
    """Пустое поле из свежего разбора не должно стирать давний факт."""
    profile = NeedProfile(child_age="9", goals=["начать говорить"])
    profile.merge(NeedProfile(preferred_format="онлайн"))
    assert profile.child_age == "9"
    assert profile.goals == ["начать говорить"]
    assert profile.preferred_format == "онлайн"


def test_merge_deduplicates_lists():
    profile = NeedProfile(pain_points=["страх говорить"])
    profile.merge(NeedProfile(pain_points=["страх говорить", "нет мотивации"]))
    assert profile.pain_points == ["страх говорить", "нет мотивации"]


def test_merge_keeps_question_counters():
    """Счётчик вопросов принадлежит диалогу, а не результату разбора."""
    profile = NeedProfile(questions_asked=2, asked_slots=["who"])
    profile.merge(NeedProfile(questions_asked=0))
    assert profile.questions_asked == 2
    assert profile.asked_slots == ["who"]


# --------------------------- извлечение через LLM ---------------------------

async def test_extract_reads_structured_answer(gateway):
    gateway({
        "who": "parent",
        "child_age": "9",
        "goals": ["начать говорить"],
        "pain_points": ["страх говорить"],
    })
    profile = await extract([{"role": "user", "content": "сыну 9, боится говорить"}])
    assert profile.who == WHO_PARENT
    assert profile.child_age == "9"
    assert profile.pain_points == ["страх говорить"]


async def test_extract_survives_wrong_types(gateway):
    """Модели регулярно шлют строку там, где в схеме массив."""
    gateway({"who": "parent", "child_age": 9, "goals": "начать говорить", "pain_points": []})
    profile = await extract([{"role": "user", "content": "x"}])
    assert profile.child_age == "9"
    assert profile.goals == ["начать говорить"]


async def test_extract_returns_empty_profile_when_model_fails(gateway):
    gateway(None)
    assert await extract([{"role": "user", "content": "x"}]) == NeedProfile()


async def test_extract_skips_llm_without_history(gateway):
    fake = gateway({"who": "parent", "child_age": "9", "goals": [], "pain_points": []})
    assert await extract([]) == NeedProfile()
    assert fake.calls == 0


async def test_extract_ignores_unknown_fields(gateway):
    gateway({"who": "parent", "child_age": "9", "goals": [], "pain_points": [],
             "favourite_colour": "синий"})
    profile = await extract([{"role": "user", "content": "x"}])
    assert profile.child_age == "9"


# --------------------------- хранение ---------------------------

def test_profile_survives_save_and_load():
    store = MemoryStore(db_path=":memory:")
    conv = store.get("u1", platform="max")
    conv.need.child_age = "9"
    conv.need.goals.append("начать говорить")
    store.save(conv)
    store._data.clear()

    loaded = store.get("u1", platform="max")
    assert loaded.need.child_age == "9"
    assert loaded.need.goals == ["начать говорить"]
    # Гейт продажи считается по восстановленному профилю, а не заново с нуля:
    # после перезапуска бот не должен снова допрашивать вернувшегося клиента.
    assert sales_allowed(loaded.need) is True


def test_old_record_without_need_key_still_loads():
    """Записи, сделанные до появления SMART, не должны ронять загрузку."""
    from app.memory import _conv_from_dict

    conv = _conv_from_dict({"user_id": "u1", "platform": "max", "stage": "discovery"})
    assert conv.need == NeedProfile()


def test_summary_lists_only_known_facts():
    profile = NeedProfile(child_age="9", who=WHO_PARENT, goals=["начать говорить"])
    text = summary(profile)
    assert "возраст ученика: 9" in text
    assert "расписание" not in text


def test_summary_of_empty_profile_is_empty():
    assert summary(NeedProfile()) == ""


def test_conversation_default_profile_is_independent():
    """Общий мутабельный дефолт разлил бы данные одного клиента в чужой диалог."""
    first, second = Conversation(user_id="a"), Conversation(user_id="b")
    first.need.goals.append("x")
    assert second.need.goals == []
