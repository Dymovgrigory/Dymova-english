"""Жизненный цикл сессии: старт → ответы с очередью ошибок → финиш и награда."""
from datetime import timedelta

import pytest

from app.learning import clock, sessions
from app.learning.errors import Conflict, Gone
from app.world import core
from app.world.db import get_conn
from tests.lesson_helpers import right_answer, stored, wrong_answer


def play(key: str, started: dict, *, wrong_first: int = 0) -> list[dict]:
    payload = stored(started["session_id"])
    replies = []
    queue = list(range(len(payload)))
    mistakes_left = wrong_first
    while queue:
        index = queue.pop(0)
        challenge = payload[index]
        if challenge["graded"] and mistakes_left:
            mistakes_left -= 1
            reply = sessions.answer(key, started["session_id"], index, wrong_answer(challenge))
            if reply["requeued"]:
                queue.append(index)
        else:
            reply = sessions.answer(key, started["session_id"], index, right_answer(challenge))
        replies.append(reply)
    return replies


def test_start_hides_solutions(learner):
    key, _ = learner
    started = sessions.start(key, "sp1.m1.n1", allow_speak=False, seed=1)
    assert started["kind"] == "words" and started["graded_total"] == 10
    assert all("solution" not in c for c in started["challenges"])


def test_locked_node_cannot_start(learner):
    key, _ = learner
    with pytest.raises(Conflict, match="node_locked"):
        sessions.start(key, "sp1.m1.n2", allow_speak=False, seed=1)


def test_full_lesson_with_mistake_requeues_and_rewards(learner):
    key, pid = learner
    xp_before = core.get_player(key)["xp"]
    started = sessions.start(key, "sp1.m1.n1", allow_speak=False, seed=3)
    replies = play(key, started, wrong_first=1)
    assert sum(1 for r in replies if r["requeued"]) == 1
    wrong = next(r for r in replies if not r["correct"])
    assert wrong["solution"]
    wrong_challenge = next(c for c in stored(started["session_id"]) if c["graded"])
    if wrong_challenge["solution"]["kind"] == "choice":
        assert wrong["solution_index"] == wrong_challenge["solution"]["index"]
    result = sessions.finish(key, started["session_id"])
    assert result["xp"] == 10 and result["coins"] == 5
    assert result["accuracy"] == pytest.approx(0.9)
    assert result["mistakes"] == 1
    assert result["node_completed"] is True and result["next_node_id"] == "sp1.m1.n2"
    assert result["streak_days"] == 1 and result["today_xp"] == 10
    assert result["daily_goal_xp"] == 20 and result["goal_reached"] is False
    assert core.get_player(key)["xp"] == xp_before + 10
    attempts = get_conn().execute("SELECT COUNT(*) AS n FROM attempts WHERE player_id=?", (pid,)).fetchone()["n"]
    assert attempts == 11

    again = sessions.finish(key, started["session_id"])
    assert again == result
    assert core.get_player(key)["xp"] == xp_before + 10


def test_perfect_lesson_bonus_and_goal(learner):
    key, _ = learner
    started = sessions.start(key, "sp1.m1.n1", allow_speak=False, seed=4)
    play(key, started)
    first = sessions.finish(key, started["session_id"])
    assert first["xp"] == 15 and first["accuracy"] == 1.0
    started = sessions.start(key, "sp1.m1.n2", allow_speak=False, seed=4)
    play(key, started)
    second = sessions.finish(key, started["session_id"])
    assert second["today_xp"] == 30 and second["goal_reached"] is True


def test_finish_too_early_and_double_answer(learner):
    key, _ = learner
    started = sessions.start(key, "sp1.m1.n1", allow_speak=False, seed=5)
    payload = stored(started["session_id"])
    with pytest.raises(Conflict, match="session_not_complete"):
        sessions.finish(key, started["session_id"])
    sessions.answer(key, started["session_id"], 0, right_answer(payload[0]))
    with pytest.raises(Conflict, match="challenge_done"):
        sessions.answer(key, started["session_id"], 0, right_answer(payload[0]))


def test_expired_session(learner):
    key, _ = learner
    started = sessions.start(key, "sp1.m1.n1", allow_speak=False, seed=6)
    later = clock.now() + sessions.SESSION_TTL + timedelta(minutes=1)
    with pytest.raises(Gone):
        sessions.answer(key, started["session_id"], 0, {}, now=later)


def test_failed_module_test_does_not_complete_node(learner, learn_course):
    key, pid = learner
    from app.learning import progress

    for node_id in ("sp1.m1.n1", "sp1.m1.n2", "sp1.m1.n3", "sp1.m1.n4", "sp1.m1.n5"):
        progress.complete_node(pid, node_id, stars=0, accuracy=1.0, now=clock.now())
    started = sessions.start(key, "sp1.m1.n6", allow_speak=False, seed=7)
    replies = play(key, started, wrong_first=8)
    assert not any(r["requeued"] for r in replies)
    result = sessions.finish(key, started["session_id"])
    assert result["passed"] is False and result["stars"] == 0 and result["xp"] == 0
    assert result["node_completed"] is False
    assert "sp1.m1.n6" not in progress.completed_nodes(pid)


def test_passed_module_test_gives_first_pass_bonus(learner):
    key, pid = learner
    from app.learning import progress

    for node_id in ("sp1.m1.n1", "sp1.m1.n2", "sp1.m1.n3", "sp1.m1.n4", "sp1.m1.n5"):
        progress.complete_node(pid, node_id, stars=0, accuracy=1.0, now=clock.now())
    started = sessions.start(key, "sp1.m1.n6", allow_speak=False, seed=8)
    play(key, started)
    result = sessions.finish(key, started["session_id"])
    assert result["stars"] == 3 and result["xp"] == 30
    assert result["coins"] == progress.COINS_SESSION + progress.COINS_MODULE_TEST_FIRST


def test_speak_can_be_skipped(learner):
    key, _ = learner
    for seed in range(30):
        started = sessions.start(key, "sp1.m1.n1", allow_speak=True, seed=seed)
        payload = stored(started["session_id"])
        speak = [i for i, c in enumerate(payload) if c["type"] == "speak"]
        if speak:
            break
    else:
        pytest.skip("no speak challenge generated")
    reply = sessions.answer(key, started["session_id"], speak[0], {"skip": True})
    assert reply["skipped"] is True and reply["requeued"] is False


def test_check_pair_answers_instantly_without_finishing_challenge(learner):
    key, _ = learner
    for seed in range(40):
        started = sessions.start(key, "sp1.m1.n1", allow_speak=False, seed=seed)
        payload = stored(started["session_id"])
        index = next((i for i, c in enumerate(payload) if c["type"] == "match_pairs"), None)
        if index is not None:
            break
    pairs = payload[index]["solution"]["pairs"]
    left, right = pairs[0]
    assert sessions.check_pair(key, started["session_id"], index, left, right) == {"correct": True}
    wrong_right = pairs[1][1]
    assert sessions.check_pair(key, started["session_id"], index, left, wrong_right) == {"correct": False}
    # проверка пары не закрывает задание и не пишет попыток
    reply = sessions.answer(key, started["session_id"], index, {"pairs": pairs})
    assert reply["correct"] is True
    with pytest.raises(Conflict, match="not_pairs"):
        sessions.check_pair(key, started["session_id"], 0, left, right)
