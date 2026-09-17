"""Профиль, статусы пути, награды, серия дней, сундук."""
from datetime import datetime, timezone

import pytest

from app.learning import progress
from app.learning.errors import Conflict, NotFound, ProfileRequired
from app.world import core

NOW = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)


def test_stars_and_rewards():
    assert [progress.stars_for(a) for a in (0.5, 0.6, 0.8, 0.95, 1.0)] == [0, 1, 2, 3, 3]
    assert progress.session_reward("words", 0.8, wrong=2) == progress.Reward(xp=10, coins=5, stars=0, passed=True)
    assert progress.session_reward("grammar", 1.0, wrong=0).xp == 15
    assert progress.session_reward("module_test", 0.85, wrong=2) == progress.Reward(xp=20, coins=5, stars=2, passed=True)
    assert progress.session_reward("module_test", 0.5, wrong=7).passed is False


def test_profile_required_and_validation(learn_db, learn_course):
    pid = core.get_or_create_player("kid-profile", "Оля")["id"]
    with pytest.raises(ProfileRequired):
        progress.get_profile(pid)
    with pytest.raises(NotFound):
        progress.set_profile(pid, learn_course, book_id="sp1", module_id="sp3.m1", daily_goal_xp=20)
    with pytest.raises(Conflict):
        progress.set_profile(pid, learn_course, book_id="sp1", module_id="sp1.m1", daily_goal_xp=15)
    saved = progress.set_profile(pid, learn_course, book_id="sp1", module_id="sp1.m2", daily_goal_xp=30)
    assert saved == {"book_id": "sp1", "module_id": "sp1.m2", "daily_goal_xp": 30}
    assert progress.get_profile(pid) == saved


def test_statuses_start_at_profile_module(learn_db, learn_course):
    pid = core.get_or_create_player("kid-path", "Лёша")["id"]
    profile = progress.set_profile(pid, learn_course, book_id="sp1", module_id="sp1.m2", daily_goal_xp=20)
    statuses = progress.node_statuses(learn_course, pid, "sp1", profile)
    assert {statuses[f"sp1.m1.n{i}"] for i in range(1, 7)} == {"open"}
    assert statuses["sp1.m2.n1"] == "current"
    assert statuses["sp1.m2.n2"] == "locked"
    assert set(progress.node_statuses(learn_course, pid, "sp3", profile).values()) == {"locked"}

    progress.complete_node(pid, "sp1.m2.n1", stars=0, accuracy=0.9, now=NOW)
    statuses = progress.node_statuses(learn_course, pid, "sp1", profile)
    assert statuses["sp1.m2.n1"] == "completed" and statuses["sp1.m2.n2"] == "current"


def test_higher_book_opens_after_all_module_tests(learn_db, learn_course):
    pid = core.get_or_create_player("kid-up", "Дима")["id"]
    profile = progress.set_profile(pid, learn_course, book_id="sp1", module_id="sp1.m1", daily_goal_xp=20)
    progress.complete_node(pid, "sp1.m1.n6", stars=2, accuracy=0.85, now=NOW)
    assert set(progress.node_statuses(learn_course, pid, "sp3", profile).values()) == {"locked"}
    progress.complete_node(pid, "sp1.m2.n5", stars=1, accuracy=0.7, now=NOW)
    statuses = progress.node_statuses(learn_course, pid, "sp3", profile)
    assert statuses["sp3.m1.n1"] == "current" and statuses["sp3.m1.n2"] == "locked"


def test_lower_books_are_open_for_older_pupils(learn_db, learn_course):
    pid = core.get_or_create_player("kid-older", "Катя")["id"]
    profile = progress.set_profile(pid, learn_course, book_id="sp3", module_id="sp3.m1", daily_goal_xp=10)
    assert set(progress.node_statuses(learn_course, pid, "sp1", profile).values()) == {"open"}
    assert progress.node_statuses(learn_course, pid, "sp3", profile)["sp3.m1.n1"] == "current"


def test_complete_node_keeps_best_result(learn_db, learn_course):
    pid = core.get_or_create_player("kid-best", "Саша")["id"]
    progress.complete_node(pid, "sp1.m1.n6", stars=3, accuracy=0.96, now=NOW)
    progress.complete_node(pid, "sp1.m1.n6", stars=1, accuracy=0.61, now=NOW)
    assert progress.completed_nodes(pid)["sp1.m1.n6"] == {"stars": 3, "best_accuracy": 0.96}


def test_next_node(learn_course):
    assert progress.next_node_id(learn_course, "sp1.m1.n6") == "sp1.m2.n1"
    assert progress.next_node_id(learn_course, "sp1.m2.n5") is None


def test_streak_uses_moscow_days(learn_db):
    pid = core.get_or_create_player("kid-streak", "Нина")["id"]
    late_evening = datetime(2026, 9, 16, 20, 30, tzinfo=timezone.utc)   # 23:30 МСК 16-го
    after_midnight = datetime(2026, 9, 16, 21, 30, tzinfo=timezone.utc)  # 00:30 МСК 17-го
    assert progress.record_activity(pid, 10, now=late_evening) == {"today_xp": 10, "streak_days": 1}
    assert progress.record_activity(pid, 15, now=after_midnight) == {"today_xp": 15, "streak_days": 2}
    assert progress.record_activity(pid, 5, now=after_midnight) == {"today_xp": 20, "streak_days": 2}
    next_evening = datetime(2026, 9, 17, 18, 0, tzinfo=timezone.utc)
    assert progress.streak_days(pid, now=next_evening) == 2
    after_gap = datetime(2026, 9, 19, 9, 0, tzinfo=timezone.utc)
    assert progress.streak_days(pid, now=after_gap) == 0
    assert progress.today_xp(pid, now=after_gap) == 0


def test_open_chest(learner, learn_course):
    key, pid = learner
    with pytest.raises(Conflict):
        progress.open_chest(key, learn_course, "sp1.m1.n4")
    with pytest.raises(Conflict):
        progress.open_chest(key, learn_course, "sp1.m1.n1")
    for node_id in ("sp1.m1.n1", "sp1.m1.n2", "sp1.m1.n3"):
        progress.complete_node(pid, node_id, stars=0, accuracy=1.0, now=NOW)
    before = core.get_player(key)["coins"]
    result = progress.open_chest(key, learn_course, "sp1.m1.n4")
    assert result["coins"] == progress.COINS_CHEST
    assert core.get_player(key)["coins"] == before + progress.COINS_CHEST
    assert progress.node_statuses(learn_course, pid, "sp1", progress.get_profile(pid))["sp1.m1.n5"] == "current"
    with pytest.raises(Conflict):
        progress.open_chest(key, learn_course, "sp1.m1.n4")
