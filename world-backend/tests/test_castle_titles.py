"""Звания выдаются один раз, вместе с монетами, и одно можно носить."""
from __future__ import annotations

import pytest

from app.castle import counters, titles, tracks
from app.world import core
from app.world.db import get_conn
from app.world.core import Conflict


FAKE_WORDS = {f"sp1.m1.w{n}" for n in range(60)}  # фикстурного курса мало для порога 50


@pytest.fixture(autouse=True)
def _wide_course(monkeypatch: pytest.MonkeyPatch):
    real = counters.course_word_ids()
    monkeypatch.setattr(counters, "course_word_ids", lambda: real | FAKE_WORDS)


def _learn_words(player_id: int, count: int) -> None:
    """Отмечает `count` слов выученными (сила 3, как после пары верных ответов)."""
    for atom_id in sorted(FAKE_WORDS)[:count]:
        get_conn().execute(
            "INSERT INTO atom_mastery (player_id, atom_id, strength, correct_count, wrong_count,"
            " due_at, updated_at, learned_at) VALUES (?,?,3,3,0,'2026-09-18','2026-09-18T10:00:00','2026-09-18')",
            (player_id, atom_id),
        )


def test_sync_awards_level_and_coins_once(learner):
    key, player_id = learner
    coins_before = core.get_player(key)["coins"]
    _learn_words(player_id, 10)

    first = titles.sync(key)
    assert [item["track"] for item in first] == ["lexicon"]
    assert first[0]["level"] == 1
    assert first[0]["coins"] == 25
    assert core.get_player(key)["coins"] == coins_before + 25

    assert titles.sync(key) == []
    assert core.get_player(key)["coins"] == coins_before + 25


def test_sync_jumps_two_levels_and_pays_for_both(learner):
    key, player_id = learner
    coins_before = core.get_player(key)["coins"]
    _learn_words(player_id, 50)
    new = titles.sync(key)
    assert new[0]["level"] == 2
    assert new[0]["coins"] == 25 + 50
    assert core.get_player(key)["coins"] == coins_before + 75


def test_state_lists_all_tracks(learner):
    key, player_id = learner
    state = titles.state(player_id)
    assert [row["track"] for row in state] == ["lexicon", "yard", "nest", "glory", "stickers"]
    assert all(row["level"] == 0 for row in state)
    assert all(row["worn"] is False for row in state)


def test_wear_switches_single_title(learner):
    key, player_id = learner
    _learn_words(player_id, 10)
    titles.sync(key)
    state = titles.wear(player_id, "lexicon")
    assert [row["worn"] for row in state if row["track"] == "lexicon"] == [True]
    assert sum(1 for row in state if row["worn"]) == 1


def test_cannot_wear_title_without_level(learner):
    _, player_id = learner
    with pytest.raises(Conflict):
        titles.wear(player_id, "glory")


def test_state_keeps_level_when_value_drops(learner):
    """Оборвалась серия дней (nest) — звание 3 уровня не отбирается,
    а следующая цель считается от него, а не от нулевого сырого значения."""
    _, player_id = learner
    get_conn().execute(
        "INSERT INTO titles (player_id, track, level) VALUES (?,?,?)",
        (player_id, "nest", 3),
    )
    state = titles.state(player_id)
    nest = next(row for row in state if row["track"] == "nest")
    assert nest["level"] == 3
    assert nest["value"] == 0
    assert nest["next_threshold"] == tracks.TRACKS["nest"].thresholds[3]


def test_state_next_threshold_none_at_max_level(learner):
    """На пятом уровне следующей цели уже нет."""
    _, player_id = learner
    get_conn().execute(
        "INSERT INTO titles (player_id, track, level) VALUES (?,?,?)",
        (player_id, "nest", 5),
    )
    state = titles.state(player_id)
    nest = next(row for row in state if row["track"] == "nest")
    assert nest["level"] == 5
    assert nest["next_threshold"] is None
