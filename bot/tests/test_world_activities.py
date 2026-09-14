"""Активности World: серверные сессии челленджа, проверка ответов, награда."""
import json

import pytest

from app.world import activities, core
from app.world.db import get_conn, reset_for_tests


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    core.get_or_create_player("child-1", "Мария")
    yield
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def test_start_returns_questions_without_answers():
    session = activities.start("child-1", "vocabulary-challenge-1", seed=1)
    assert session["total"] == 5
    assert len(session["questions"]) == 5
    for i, q in enumerate(session["questions"]):
        assert q["index"] == i
        assert len(q["options"]) == 4
        assert "correct_index" not in q
        assert "example_ru" not in q


def test_start_keeps_answers_on_server():
    session = activities.start("child-1", "vocabulary-challenge-1", seed=1)
    row = get_conn().execute(
        "SELECT payload FROM activity_sessions WHERE id=?", (session["session_id"],)
    ).fetchone()
    payload = json.loads(row["payload"])
    assert all("correct_index" in q for q in payload["questions"])


def test_start_unknown_activity():
    with pytest.raises(core.NotFound):
        activities.start("child-1", "no-such-activity")


def _correct_index(session_id: str, index: int) -> int:
    row = get_conn().execute(
        "SELECT payload FROM activity_sessions WHERE id=?", (session_id,)
    ).fetchone()
    return json.loads(row["payload"])["questions"][index]["correct_index"]


def test_answer_correct_and_wrong():
    s = activities.start("child-1", "vocabulary-challenge-1", seed=3)
    sid = s["session_id"]
    right = _correct_index(sid, 0)
    r = activities.answer("child-1", sid, 0, right)
    assert r["correct"] is True
    assert r["correct_index"] == right
    assert r["answered"] == 1 and r["total"] == 5
    assert r["example_ru"]

    wrong = (_correct_index(sid, 1) + 1) % 4
    r2 = activities.answer("child-1", sid, 1, wrong)
    assert r2["correct"] is False
    assert r2["correct_index"] == _correct_index(sid, 1)


def test_answer_twice_on_same_question_conflicts():
    s = activities.start("child-1", "vocabulary-challenge-1", seed=3)
    activities.answer("child-1", s["session_id"], 0, 0)
    with pytest.raises(core.Conflict):
        activities.answer("child-1", s["session_id"], 0, 1)


def test_answer_out_of_range_question():
    s = activities.start("child-1", "vocabulary-challenge-1", seed=3)
    with pytest.raises(core.NotFound):
        activities.answer("child-1", s["session_id"], 99, 0)


def test_answer_in_foreign_session_is_not_found():
    core.get_or_create_player("child-2", "Пётр")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=3)
    with pytest.raises(core.NotFound):
        activities.answer("child-2", s["session_id"], 0, 0)


def _answer_all(sid: str, *, correct: bool) -> None:
    for i in range(5):
        right = _correct_index(sid, i)
        activities.answer("child-1", sid, i, right if correct else (right + 1) % 4)


def test_finish_awards_xp_and_coins_from_config():
    from app.world import config
    core.start_quest("child-1", "first-day-at-foxinburg")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=5)
    _answer_all(s["session_id"], correct=False)
    r = activities.finish("child-1", s["session_id"])
    assert r["score"] == 0 and r["total"] == 5 and r["perfect"] is False
    assert r["xp_delta"] == config.XP_REWARDS["vocabulary_challenge"]
    assert r["coins_delta"] == config.COIN_REWARDS["vocabulary_challenge"]


def test_finish_perfect_run_adds_bonus():
    from app.world import config
    core.start_quest("child-1", "first-day-at-foxinburg")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=6)
    _answer_all(s["session_id"], correct=True)
    r = activities.finish("child-1", s["session_id"])
    assert r["score"] == 5 and r["perfect"] is True
    assert r["xp_delta"] == (config.XP_REWARDS["vocabulary_challenge"]
                             + config.PERFECT_BONUS["xp"])
    assert r["coins_delta"] == (config.COIN_REWARDS["vocabulary_challenge"]
                                + config.PERFECT_BONUS["coins"])


def test_finish_is_idempotent():
    core.start_quest("child-1", "first-day-at-foxinburg")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=7)
    _answer_all(s["session_id"], correct=True)
    first = activities.finish("child-1", s["session_id"])
    second = activities.finish("child-1", s["session_id"])
    assert second["xp_delta"] == first["xp_delta"]
    assert second["player"]["xp"] == first["player"]["xp"]
    rows = get_conn().execute(
        "SELECT COUNT(*) c FROM xp_transactions WHERE type='ACTIVITY_REWARD'"
    ).fetchone()
    assert rows["c"] == 1


def test_finish_requires_all_answers():
    s = activities.start("child-1", "vocabulary-challenge-1", seed=8)
    activities.answer("child-1", s["session_id"], 0, 0)
    with pytest.raises(core.Conflict):
        activities.finish("child-1", s["session_id"])


def test_finish_advances_quest_step():
    core.start_quest("child-1", "first-day-at-foxinburg")
    core.advance_quest_step("child-1", "first-day-at-foxinburg", "visit", "school-hub")
    core.advance_quest_step("child-1", "first-day-at-foxinburg", "talk", "foxi")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=9)
    _answer_all(s["session_id"], correct=True)
    r = activities.finish("child-1", s["session_id"])
    assert r["quest"]["step"] == 3 and r["quest"]["all_steps_done"] is True


def test_finish_without_matching_quest_step_still_awards():
    core.start_quest("child-1", "first-day-at-foxinburg")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=10)
    _answer_all(s["session_id"], correct=True)
    r = activities.finish("child-1", s["session_id"])
    assert r["quest"] is None
    assert r["xp_delta"] > 0
