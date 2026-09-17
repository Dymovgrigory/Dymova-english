"""Монеты за урок, за отсутствие ошибок, за цель дня и за тренировку — с дневным потолком."""
from __future__ import annotations

from app.learning import sessions
from app.world.db import get_conn
from tests.lesson_helpers import right_answer, stored, wrong_answer


def _finish_lesson(key: str, node_id: str, *, wrong: int = 0) -> dict:
    """Проходит урок целиком. Первые `wrong` оцениваемых вопросов сначала отвечает неверно.

    Неверный ответ возвращает вопрос в очередь ошибок, поэтому сразу после него даётся
    верный — так урок дойдёт до конца, а счётчик ошибок останется ненулевым.
    """
    started = sessions.start(key, node_id, allow_speak=False)
    session_id = started["session_id"]
    payload = stored(session_id)
    mistakes_left = wrong
    for index, challenge in enumerate(payload):
        if mistakes_left and challenge["graded"]:
            sessions.answer(key, session_id, index, wrong_answer(challenge))
            mistakes_left -= 1
        sessions.answer(key, session_id, index, right_answer(challenge))
    return sessions.finish(key, session_id)


def test_perfect_lesson_pays_bonus(learner, learn_course):
    key, _ = learner
    result = _finish_lesson(key, "sp1.m1.n1")
    assert result["coins_breakdown"]["lesson"] == 5
    assert result["coins_breakdown"]["perfect"] == 3
    assert result["coins"] == sum(result["coins_breakdown"].values())


def test_lesson_with_mistake_has_no_perfect_bonus(learner, learn_course):
    key, _ = learner
    result = _finish_lesson(key, "sp1.m1.n1", wrong=1)
    assert result["coins_breakdown"].get("perfect", 0) == 0


def test_daily_goal_pays_once_per_day(learner, learn_course):
    key, player_id = learner
    first = _finish_lesson(key, "sp1.m1.n1")
    second = _finish_lesson(key, "sp1.m1.n2")
    goal_payments = [r["coins_breakdown"].get("daily_goal", 0) for r in (first, second)]
    assert sum(1 for payment in goal_payments if payment == 10) <= 1
    rows = get_conn().execute(
        "SELECT COUNT(*) AS c FROM coin_transactions WHERE player_id=? AND type='DAILY_GOAL_REWARD'",
        (player_id,),
    ).fetchone()["c"]
    assert rows <= 1


def test_practice_pays_three_coins_twice_a_day(learner, learn_course):
    key, _ = learner
    # тренировка собирается из уже виденных атомов, поэтому сначала два обычных урока
    _finish_lesson(key, "sp1.m1.n1")
    _finish_lesson(key, "sp1.m1.n2")
    payouts = []
    for _ in range(3):
        result = _finish_lesson(key, sessions.PRACTICE_NODE)
        payouts.append(result["coins_breakdown"].get("practice", 0))
    assert payouts[0] == 3 and payouts[1] == 3
    assert payouts[2] == 0  # третья тренировка за день монет не приносит


def test_finish_is_idempotent_for_coins(learner, learn_course):
    key, player_id = learner
    started = sessions.start(key, "sp1.m1.n1", allow_speak=False)
    for index, challenge in enumerate(stored(started["session_id"])):
        sessions.answer(key, started["session_id"], index, right_answer(challenge))
    first = sessions.finish(key, started["session_id"])
    again = sessions.finish(key, started["session_id"])
    assert again == first
    paid = get_conn().execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM coin_transactions WHERE player_id=?",
        (player_id,),
    ).fetchone()["total"]
    assert paid == first["coins"]
