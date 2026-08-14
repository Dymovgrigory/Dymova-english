"""Критик — последний рубеж перед человеком.

Проверяем именно контракт из ТЗ: запрещённые дежурные фразы, призыв
записаться до выявления потребности, простыня вопросов, эмодзи-россыпь,
утечка служебных маркеров и повтор предыдущей реплики. Отдельно — главное
свойство критика: он никогда не блокирует ответ. Плохая реплика лучше
молчания, поэтому «ничего не отдать» — это баг, а не строгость.
"""
from __future__ import annotations

import pytest

from app import critic, smart
from app.ai_core import _review, handle_message
from app.memory import Conversation, get_store


@pytest.fixture(autouse=True)
def _fresh_store():
    get_store()._data.clear()


def _conv(*previous_replies: str) -> Conversation:
    conv = Conversation(user_id="critic-test")
    for reply in previous_replies:
        conv.add("assistant", reply)
    return conv


# --------------------------- inspect: находки ---------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "Отличный вопрос!",
        "С удовольствием помогу!",
        "Замечательно!",
        "Это прекрасная возможность!",
        "У нас есть отличное предложение!",
    ],
)
def test_banned_enthusiasm_is_caught(phrase):
    """ТЗ перечисляет эти фразы поимённо как недопустимые."""
    issues = critic.inspect(f"{phrase} Занятия идут по вторникам.", _conv(), True)
    assert "canned_phrase" in issues


def test_canned_phrase_is_caught_mid_text():
    """Восторг в середине реплики — то же нарушение, что и в начале."""
    reply = "Понимаю вас. Отличный вопрос! Расписание гибкое."
    assert "canned_phrase" in critic.inspect(reply, _conv(), True)


def test_cta_blocked_while_need_is_unknown():
    reply = "У нас есть подходящие программы, запишитесь на пробное занятие."
    assert "premature_sales" in critic.inspect(reply, _conv(), False)


def test_same_cta_is_fine_once_need_is_clear():
    """Запрет — на преждевременность, а не на приглашение как таковое."""
    reply = "Тогда давайте запишем на диагностику, я подберу время. Запишитесь?"
    assert "premature_sales" not in critic.inspect(reply, _conv(), True)


def test_questionnaire_is_caught():
    """«Правило одного хорошего вопроса»: три вопроса подряд — это анкета."""
    reply = "Сколько лет ребёнку? Какой уровень? Когда удобно заниматься?"
    assert "too_many_questions" in critic.inspect(reply, _conv(), True)


def test_one_question_is_not_an_issue():
    reply = "А что именно даётся тяжелее всего — говорить или писать?"
    assert critic.inspect(reply, _conv(), True) == []


def test_emoji_flood_is_caught():
    reply = "Привет 😊 у нас классно 🎉 приходите 🔥 будет здорово ✨"
    assert "too_many_emoji" in critic.inspect(reply, _conv(), True)


@pytest.mark.parametrize(
    "leak",
    [
        "[UNKNOWN]",
        "{{CHILD_NAME}}",
        "{{CHILD_NAME:вин}}",
        "ЭТАП: потребность понятна",
        "КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ",
    ],
)
def test_internal_markers_never_reach_the_user(leak):
    assert "leaked_marker" in critic.inspect(f"Хорошо. {leak} Уточню.", _conv(), True)


def test_near_duplicate_of_previous_reply_is_caught():
    previous = "Понимаю. А ему тяжелее говорить или писать?"
    reply = "Понимаю! А ему тяжелее говорить или писать?"
    assert "repeats_previous" in critic.inspect(reply, _conv(previous), True)


def test_repeat_check_looks_beyond_the_last_reply():
    """Чередование двух одинаковых реплик читается так же плохо, как повтор."""
    conv = _conv(
        "Расскажите, что уже пробовали с английским?",
        "Занятия идут по будням вечером.",
    )
    reply = "Расскажите, что уже пробовали с английским?"
    assert "repeats_previous" in critic.inspect(reply, conv, True)


def test_different_reply_is_not_a_repeat():
    conv = _conv("Понимаю. А ему тяжелее говорить или писать?")
    reply = "Тогда посмотрим на формат: в группе или один на один?"
    assert "repeats_previous" not in critic.inspect(reply, conv, True)


def test_empty_reply_is_an_issue():
    assert critic.inspect("   ", _conv(), True) == ["empty"]


def test_good_reply_passes_clean():
    reply = "Понимаю. А как вам кажется, дело в самом английском или в формате?"
    assert critic.inspect(reply, _conv(), False) == []


# ---------------------------- repair: правки ----------------------------


def test_repair_removes_canned_opener_and_keeps_content():
    reply = "Отличный вопрос! Занятия идут по вторникам и четвергам."
    fixed = critic.repair(reply, ["canned_phrase"])
    assert "Отличный вопрос" not in fixed
    assert "вторникам и четвергам" in fixed
    assert fixed.startswith("Занятия")


def test_repair_strips_leaked_markers():
    fixed = critic.repair("Уточню у администратора. [UNKNOWN]", ["leaked_marker"])
    assert "[UNKNOWN]" not in fixed
    assert "Уточню у администратора" in fixed


def test_repair_keeps_two_emoji_and_drops_the_rest():
    reply = "Привет 😊 у нас классно 🎉 приходите 🔥 будет здорово ✨"
    fixed = critic.repair(reply, ["too_many_emoji"])
    assert len(critic._EMOJI_RE.findall(fixed)) == critic.MAX_EMOJI


def test_repair_never_returns_empty_text():
    """Реплика целиком из нарушения — всё равно не повод отдать пустоту."""
    assert critic.repair("Замечательно!", ["canned_phrase"]).strip()


def test_repair_leaves_unfixable_issues_to_the_caller():
    reply = "Запишитесь на пробное занятие."
    assert critic.repair(reply, ["premature_sales"]) == reply


def test_needs_rewrite_only_for_unfixable():
    assert not critic.needs_rewrite(["canned_phrase", "too_many_emoji"])
    assert critic.needs_rewrite(["premature_sales"])
    assert critic.needs_rewrite(["too_many_questions"])


def test_feedback_is_plain_russian_not_codes():
    note = critic.feedback(["premature_sales", "too_many_questions"])
    assert "premature_sales" not in note
    assert "записаться" in note and "вопрос" in note


def test_feedback_is_empty_for_unknown_issue():
    assert critic.feedback(["something_new"]) == ""


# ------------------------- _review: поведение целиком -------------------------


async def test_review_cleans_fixable_issue_without_llm():
    conv = _conv()
    reply = await _review(conv, "Когда занятия?", "Отличный вопрос! По вторникам.")
    assert "Отличный вопрос" not in reply
    assert "вторникам" in reply


async def test_review_returns_original_when_rewrite_unavailable():
    """LLM выключена — критик не может переписать, но и молчать не имеет права."""
    conv = _conv()
    reply = "Запишитесь на пробное занятие."
    assert await _review(conv, "Сколько стоит?", reply) == reply


async def test_review_never_returns_empty():
    conv = _conv()
    original = "Замечательно! 😊🎉🔥✨"
    assert (await _review(conv, "Привет", original)).strip()


async def test_review_accepts_a_better_rewrite(monkeypatch):
    conv = _conv()
    conv.need = smart.NeedProfile()

    async def fake_ask(messages, vault):
        return "Расскажите, для кого подбираете занятия?"

    monkeypatch.setattr("app.ai_core._ask", fake_ask)
    monkeypatch.setattr("app.ai_core.get_llm", lambda: _EnabledLLM())

    reply = await _review(conv, "Есть курсы?", "Запишитесь на пробное занятие.")
    assert "Запишитесь" not in reply
    assert "Расскажите" in reply


async def test_review_keeps_original_when_rewrite_is_no_better(monkeypatch):
    """Модель вполне может переписать в те же грабли — тогда версия не нужна."""
    conv = _conv()

    async def fake_ask(messages, vault):
        return "Тогда запишитесь на пробное занятие прямо сейчас."

    monkeypatch.setattr("app.ai_core._ask", fake_ask)
    monkeypatch.setattr("app.ai_core.get_llm", lambda: _EnabledLLM())

    original = "Запишитесь на пробное занятие."
    assert await _review(conv, "Есть курсы?", original) == original


async def test_review_survives_rewrite_failure(monkeypatch):
    conv = _conv()

    async def boom(messages, vault):
        raise RuntimeError("провайдер недоступен")

    monkeypatch.setattr("app.ai_core._ask", boom)
    monkeypatch.setattr("app.ai_core.get_llm", lambda: _EnabledLLM())

    original = "Запишитесь на пробное занятие."
    assert await _review(conv, "Есть курсы?", original) == original


class _EnabledLLM:
    enabled = True


# --------------------------- сквозной путь ---------------------------


async def test_live_dialogue_never_leaks_markers_or_canned_phrases():
    """Критик стоит в основном пути, а не только в юнит-тестах."""
    for text in ("Здравствуйте", "Сколько стоит?", "Ребёнку 9 лет"):
        reply = await handle_message("critic-live", text)
        assert reply.strip()
        assert critic._LEAK_RE.search(reply) is None
        assert critic._CANNED_RE.search(reply) is None


def test_repair_leaves_no_hole_where_a_token_was():
    """Вырезанный токен оставлял «А сколько лет ?» — дыру перед знаком."""
    fixed = critic.repair("А сколько лет {{CHILD_NAME}}?", ["leaked_marker"])
    assert fixed == "А сколько лет?"
