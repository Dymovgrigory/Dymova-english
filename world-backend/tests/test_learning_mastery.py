"""Сила атомов (Лейтнер 0–5) и сроки повторения."""
from datetime import datetime, timedelta, timezone

from app.learning import mastery
from app.world import core

NOW = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)


def _pid() -> int:
    return core.get_or_create_player("kid-mastery", "Петя")["id"]


def test_correct_answers_grow_strength_up_to_cap(learn_db):
    pid = _pid()
    values = [mastery.record(pid, "sp1.m1.cat", correct=True, now=NOW) for _ in range(7)]
    assert values == [1, 2, 3, 4, 5, 5, 5]


def test_wrong_answer_lowers_strength_and_makes_atom_due_today(learn_db):
    pid = _pid()
    mastery.record(pid, "sp1.m1.cat", correct=True, now=NOW)
    assert mastery.due_atoms(pid, limit=10, now=NOW) == []
    assert mastery.record(pid, "sp1.m1.cat", correct=False, now=NOW) == 0
    assert mastery.record(pid, "sp1.m1.cat", correct=False, now=NOW) == 0
    assert mastery.due_atoms(pid, limit=10, now=NOW) == ["sp1.m1.cat"]


def test_due_after_interval_passes(learn_db):
    pid = _pid()
    for _ in range(3):
        mastery.record(pid, "sp1.m1.dog", correct=True, now=NOW)  # сила 3 → 7 дней
    assert mastery.due_atoms(pid, limit=10, now=NOW + timedelta(days=6)) == []
    assert mastery.due_atoms(pid, limit=10, now=NOW + timedelta(days=7)) == ["sp1.m1.dog"]


def test_due_orders_weak_first_and_respects_exclude_and_limit(learn_db):
    pid = _pid()
    past = NOW - timedelta(days=40)
    for _ in range(4):
        mastery.record(pid, "strong", correct=True, now=past)
    mastery.record(pid, "weak", correct=False, now=past)
    mastery.record(pid, "mid", correct=True, now=past)
    assert mastery.due_atoms(pid, limit=10, now=NOW) == ["weak", "mid", "strong"]
    assert mastery.due_atoms(pid, limit=10, exclude={"weak"}, now=NOW) == ["mid", "strong"]
    assert mastery.due_atoms(pid, limit=1, now=NOW) == ["weak"]


def test_strengths_and_weakest(learn_db):
    pid = _pid()
    mastery.record(pid, "a", correct=True, now=NOW)
    mastery.record(pid, "a", correct=True, now=NOW)
    mastery.record(pid, "b", correct=True, now=NOW)
    assert mastery.strengths(pid, ["a", "b", "c"]) == {"a": 2, "b": 1}
    assert mastery.weakest(pid, ["a", "b", "c"], 2) == ["c", "b"]
    assert mastery.weakest_seen(pid, 5) == ["b", "a"]
