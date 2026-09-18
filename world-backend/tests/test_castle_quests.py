"""Задания Беседки: дневные и недельные на таблицах v2, награда один раз за окно."""
from __future__ import annotations

import pytest

from app.castle import counters, league_weeks, quests
from app.learning import clock
from app.world import core
from app.world.core import Conflict
from app.world.db import get_conn

FAKE_WORDS = {f"sp1.m1.w{n}" for n in range(60)}


@pytest.fixture(autouse=True)
def _wide_course(monkeypatch: pytest.MonkeyPatch):
    real = counters.course_word_ids()
    monkeypatch.setattr(counters, "course_word_ids", lambda: real | FAKE_WORDS)


def _lesson(player_id: int, name: str, *, day: str | None = None) -> None:
    get_conn().execute(
        "INSERT INTO learn_sessions (id, player_id, node_id, kind, payload, pending, state, status, started_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (f"ls-{name}-{player_id}", player_id, "sp1.m1.w1", "words", "{}", "[]", "{}", "completed",
         f"{day or clock.local_day(clock.now())}T12:00:00"),
    )


def _perfect_node(player_id: int) -> None:
    get_conn().execute(
        "INSERT INTO node_progress (player_id, node_id, stars, best_accuracy, completed_at)"
        " VALUES (?,?,?,?,?)",
        (player_id, "sp1.m1.w1", 3, 1.0, f"{clock.local_day(clock.now())}T12:00:00"),
    )


def test_empty_state(learner):
    key, _ = learner
    data = quests.quests(key)
    assert [q["id"] for q in data["daily"]] == ["xp-goal", "lesson-1", "perfect-1"]
    assert [q["id"] for q in data["weekly"]] == ["week-lessons", "week-practice", "week-words"]
    assert all(not q["done"] and not q["claimed"] for q in data["daily"] + data["weekly"])
    assert data["weekly"][1]["spot"] == "yard"


def test_daily_lesson_and_claim_once(learner):
    key, player_id = learner
    _lesson(player_id, "a")
    data = quests.quests(key)
    lesson = next(q for q in data["daily"] if q["id"] == "lesson-1")
    assert lesson["done"] and lesson["claimable"] and lesson["coins"] == 5

    before = core.get_player(key)["coins"]
    assert quests.claim(key, "lesson-1", "day")["coins_delta"] == 5
    assert core.get_player(key)["coins"] == before + 5
    # повтор — без монет
    assert quests.claim(key, "lesson-1", "day")["coins_delta"] == 0
    assert core.get_player(key)["coins"] == before + 5
    assert next(q for q in quests.quests(key)["daily"] if q["id"] == "lesson-1")["claimed"]


def test_claim_not_done_rejected(learner):
    key, _ = learner
    with pytest.raises(Conflict):
        quests.claim(key, "week-lessons", "week")


def test_daily_goal_quest_uses_profile_goal(learner):
    key, player_id = learner
    from app.learning import progress
    progress.record_activity(player_id, 20, now=clock.now())  # цель в профиле = 20
    data = quests.quests(key)
    goal = next(q for q in data["daily"] if q["id"] == "xp-goal")
    assert goal["done"] and goal["target"] == 20


def test_perfect_lesson_quest(learner):
    key, player_id = learner
    _perfect_node(player_id)
    perfect = next(q for q in quests.quests(key)["daily"] if q["id"] == "perfect-1")
    assert perfect["done"]


def test_weekly_words_and_claim(learner):
    key, player_id = learner
    for atom_id in sorted(FAKE_WORDS)[:25]:
        get_conn().execute(
            "INSERT INTO atom_mastery (player_id, atom_id, strength, correct_count, wrong_count,"
            " due_at, updated_at, learned_at) VALUES (?,?,3,3,0,'2026-09-18','2026-09-18T10:00:00',?)",
            (player_id, atom_id, league_weeks.week_start(clock.now())),
        )
    words = next(q for q in quests.quests(key)["weekly"] if q["id"] == "week-words")
    assert words["done"] and words["coins"] == 20
    assert quests.claim(key, "week-words", "week")["coins_delta"] == 20


def test_weekly_lessons_count(learner):
    key, player_id = learner
    for n in range(5):
        _lesson(player_id, f"w{n}")
    quest = next(q for q in quests.quests(key)["weekly"] if q["id"] == "week-lessons")
    assert quest["done"]
