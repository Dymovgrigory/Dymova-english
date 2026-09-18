"""Испытание дня во Дворе: 5 слов на время, +5 монет, раз в день, в ветку Тренера."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.castle import counters
from app.learning import mastery, sessions
from app.world import core
from app.world.db import get_conn
from tests.lesson_helpers import right_answer, stored

WORDS = ["sp1.m1.cat", "sp1.m1.dog", "sp1.m1.mum", "sp1.m1.dad", "sp1.m1.hello"]


def _seed_words(player_id: int) -> None:
    """Пять слов «уже видели» — испытанию есть из чего собрать план."""
    for atom_id in WORDS:
        mastery.record(player_id, atom_id, correct=True)


def _finish_trial(key: str, *, slow: bool = False, wrong_first: bool = False) -> dict:
    start = sessions.start(key, "trial", allow_speak=False)
    assert start["kind"] == "trial"
    assert len(start["challenges"]) == 5
    stored_challenges = stored(start["session_id"])  # start прячет решения — берём из payload
    queue = list(range(5))
    answered = 0
    while queue:
        index = queue.pop(0)
        answer = right_answer(stored_challenges[index])
        if wrong_first and answered == 0:
            sessions.answer(key, start["session_id"], index, _wrong(stored_challenges[index]), response_ms=800)
        result = sessions.answer(
            key, start["session_id"], index, answer,
            response_ms=16_000 if slow and answered == 0 else 800,
        )
        if result["requeued"]:
            queue.append(index)
        answered += 1
    return sessions.finish(key, start["session_id"])


def _wrong(challenge: dict) -> dict:
    solution = challenge["solution"]
    if solution["kind"] == "choice":
        return {"index": solution["index"] + 1 if solution["index"] == 0 else 0}
    if solution["kind"] == "text":
        return {"text": "zzzzzz"}
    return {"tiles": ["zzz"]}


def test_trial_plan_is_five_words(learner):
    key, player_id = learner
    _seed_words(player_id)
    start = sessions.start(key, "trial", allow_speak=False)
    assert start["kind"] == "trial"
    assert len(start["challenges"]) == 5


def test_fast_trial_pays_once_a_day(learner):
    key, player_id = learner
    _seed_words(player_id)
    first = _finish_trial(key)
    assert first["trial_passed"] is True
    assert first["coins_breakdown"]["trial"] == 5
    coins = core.get_player(key)["coins"]
    # вторая попытка в тот же день — без монет за испытание
    # (другие источники, например цель дня, могут добавить свои)
    second = _finish_trial(key)
    assert "trial" not in second["coins_breakdown"]
    assert core.get_player(key)["coins"] == coins + second["coins"]


def test_slow_answer_fails_trial_but_retry_allowed(learner):
    key, player_id = learner
    _seed_words(player_id)
    failed = _finish_trial(key, slow=True)
    assert failed["trial_passed"] is False
    assert failed["coins_breakdown"].get("trial") is None
    # провал не сжигает дневную награду: следующая быстрая попытка платит
    passed = _finish_trial(key)
    assert passed["coins_breakdown"]["trial"] == 5


def test_wrong_first_try_fails_trial(learner):
    key, player_id = learner
    _seed_words(player_id)
    result = _finish_trial(key, wrong_first=True)
    assert result["trial_passed"] is False


def test_trial_counts_to_yard_track(learner):
    key, player_id = learner
    _seed_words(player_id)
    _finish_trial(key)
    assert counters.counters(player_id)["yard"] == 1


def test_trial_without_words_is_rejected(learner):
    key, _ = learner
    try:
        sessions.start(key, "trial", allow_speak=False)
    except Exception as exc:
        assert "nothing_to_practice" in str(exc)
    else:
        raise AssertionError("без выученных слов испытание не должно собираться")


def test_practice_status_endpoint(learner):
    from main import app

    key, player_id = learner
    _seed_words(player_id)
    with TestClient(app) as client:
        head = {"X-World-Player": key}
        body = client.get("/api/v2/practice/status", headers=head).json()
        assert body == {"trial_done_today": False, "trial_available": True}
        _finish_trial(key)
        body = client.get("/api/v2/practice/status", headers=head).json()
        assert body["trial_done_today"] is True
