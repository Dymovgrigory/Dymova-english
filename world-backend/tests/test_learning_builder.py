"""Сборка сессии по типу узла, полосе и повторению."""
from datetime import timedelta

import pytest

from app.learning import builder, clock, mastery
from app.learning.errors import Conflict

@pytest.fixture()
def pid(learn_db, learn_course):
    from app.world import core

    return core.get_or_create_player("kid-builder", "Ваня")["id"]


SESSION_NODES = [
    "sp1.m1.n1", "sp1.m1.n2", "sp1.m1.n3", "sp1.m1.n5", "sp1.m1.n6",
    "sp1.m2.n1", "sp1.m2.n2", "sp1.m2.n4", "sp1.m2.n5",
    "sp3.m1.n1", "sp3.m1.n2", "sp3.m1.n3", "sp3.m1.n5", "sp3.m1.n6",
]


def _graded(plan):
    return [c for c in plan.challenges if c.graded]


def _assert_layout(plan):
    items = plan.challenges
    speak = sum(c.type == "speak" for c in items)
    assert speak <= builder.MAX_SPEAK
    for i, ch in enumerate(items):
        if i and ch.graded and items[i - 1].graded and ch.atom_id:
            assert ch.atom_id != items[i - 1].atom_id, (plan.node_id, i)
        if i >= builder.MAX_SAME_TYPE_RUN:
            window = items[i - builder.MAX_SAME_TYPE_RUN: i + 1]
            assert len({c.type for c in window}) > 1, (plan.node_id, i, ch.type)
        if ch.graded and ch.atom_id:
            later_teach = [c for c in items[i + 1:] if not c.graded and c.atom_id == ch.atom_id]
            assert not later_teach, (plan.node_id, i)


@pytest.mark.parametrize("node_id", SESSION_NODES)
def test_layout_rules_hold_for_many_seeds(learn_course, node_id):
    for seed in range(40):
        plan = builder.build_session(learn_course, node_id, player_id=None, seed=seed, allow_speak=True)
        assert plan.node_id == node_id and _graded(plan)
        _assert_layout(plan)
        quiet = builder.build_session(learn_course, node_id, player_id=None, seed=seed, allow_speak=False)
        assert all(c.type != "speak" for c in quiet.challenges)


def test_words_node_teaches_then_practises(learn_course):
    plan = builder.build_session(learn_course, "sp1.m1.n1", player_id=None, seed=7, allow_speak=False)
    teach = [c.atom_id for c in plan.challenges if c.type == "teach_word"]
    assert sorted(teach) == ["sp1.m1.cat", "sp1.m1.dad", "sp1.m1.mum"]
    graded = _graded(plan)
    assert len(graded) == 10
    assert graded[-1].type == "match_pairs" or any(c.type == "match_pairs" for c in graded)
    assert all(c.type != "read_word_pick_image" for c in plan.challenges)


def test_phonics_node_reads_only_decodable_words(learn_course):
    for seed in range(10):
        plan = builder.build_session(learn_course, "sp1.m1.n3", player_id=None, seed=seed, allow_speak=False)
        types = [c.type for c in plan.challenges]
        assert types.count("teach_grapheme") == 5
        assert types.count("letter_sound") == 5 and types.count("sound_letter") == 5
        reading = {c.atom_id for c in plan.challenges if c.type in ("blend_sounds", "read_word_pick_image")}
        assert reading and reading <= {"sp1.m1.cat", "sp1.m1.dad"}
        assert len(_graded(plan)) >= 12


def test_grammar_node(learn_course):
    plan = builder.build_session(learn_course, "sp3.m1.n3", player_id=None, seed=3, allow_speak=False)
    assert plan.challenges[0].type == "teach_rule"
    types = [c.type for c in plan.challenges]
    assert types.count("grammar_pick") == 4
    assert "build_phrase" in types
    assert 8 <= len(_graded(plan)) <= 12


def test_module_test_has_no_teaching_and_fixed_size(learn_course):
    for node_id in ("sp1.m1.n6", "sp1.m2.n5", "sp3.m1.n6"):
        plan = builder.build_session(learn_course, node_id, player_id=None, seed=11, allow_speak=True)
        assert all(c.graded for c in plan.challenges)
        assert len(plan.challenges) == builder.TEST_SIZE


def test_review_size(learn_course):
    plan = builder.build_session(learn_course, "sp3.m1.n5", player_id=None, seed=2, allow_speak=True)
    assert len(_graded(plan)) == builder.REVIEW_SIZE


def test_same_seed_same_session(learn_course):
    a = builder.build_session(learn_course, "sp3.m1.n1", player_id=None, seed=42, allow_speak=True)
    b = builder.build_session(learn_course, "sp3.m1.n1", player_id=None, seed=42, allow_speak=True)
    assert [c.to_dict() for c in a.challenges] == [c.to_dict() for c in b.challenges]


def test_chest_has_no_session(learn_course):
    with pytest.raises(Conflict):
        builder.build_session(learn_course, "sp1.m1.n4", player_id=None, seed=1, allow_speak=True)


def test_due_atoms_from_other_modules_are_mixed_in(pid, learn_course):
    past = clock.now() - timedelta(days=3)
    mastery.record(pid, "sp1.m1.cat", correct=False, now=past)
    plan = builder.build_session(learn_course, "sp1.m2.n1", player_id=pid, seed=5, allow_speak=True)
    mixed = [c for c in plan.challenges if c.atom_id == "sp1.m1.cat"]
    assert len(mixed) == 1 and mixed[0].type != "speak"
    test = builder.build_session(learn_course, "sp1.m2.n5", player_id=pid, seed=5, allow_speak=True)
    assert all(c.atom_id != "sp1.m1.cat" for c in test.challenges)


def test_practice_uses_weak_atoms_or_refuses(pid, learn_course):
    with pytest.raises(Conflict):
        builder.build_practice(learn_course, pid, seed=1, allow_speak=True)
    for atom_id in ("sp1.m1.cat", "sp1.m1.dad", "sp1.m1.mum", "sp1.m1.dog", "sp1.m1.sun", "sp1.m1.p2"):
        mastery.record(pid, atom_id, correct=True)
    plan = builder.build_practice(learn_course, pid, seed=1, allow_speak=True)
    assert plan.kind == "practice" and len(plan.challenges) == 6
    assert all(c.graded for c in plan.challenges)
    _assert_layout(plan)
