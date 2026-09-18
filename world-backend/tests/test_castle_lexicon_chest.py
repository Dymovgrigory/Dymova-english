"""Сундук слов: каждые 25 выученных слов — монеты и украшение, один раз на сундук."""
from __future__ import annotations

import pytest

from app.castle import catalog, counters, lexicon_chest
from app.world import core
from app.world.core import Conflict
from app.world.db import get_conn

FAKE_WORDS = {f"sp1.m1.w{n}" for n in range(60)}


@pytest.fixture(autouse=True)
def _wide_course(monkeypatch: pytest.MonkeyPatch):
    real = counters.course_word_ids()
    monkeypatch.setattr(counters, "course_word_ids", lambda: real | FAKE_WORDS)


def _learn(player_id: int, count: int) -> None:
    for atom_id in sorted(FAKE_WORDS)[:count]:
        get_conn().execute(
            "INSERT INTO atom_mastery (player_id, atom_id, strength, correct_count, wrong_count,"
            " due_at, updated_at, learned_at) VALUES (?,?,3,3,0,'2026-09-18','2026-09-18T10:00:00','2026-09-18')",
            (player_id, atom_id),
        )


def test_status_progress_and_ready(learner):
    _, player_id = learner
    assert lexicon_chest.status(player_id) == {
        "words": 0, "per_chest": 25, "opened": 0, "ready": 0, "progress": 0,
    }
    _learn(player_id, 30)
    assert lexicon_chest.status(player_id) == {
        "words": 30, "per_chest": 25, "opened": 0, "ready": 1, "progress": 5,
    }


def test_open_grants_coins_and_decor_once(learner):
    key, player_id = learner
    _learn(player_id, 26)
    before = core.get_player(key)["coins"]

    result = lexicon_chest.open(key)
    assert result["coins"] == 30
    assert result["item_id"] is not None
    assert result["item_id"] in {
        item.id for item in catalog.ITEMS.values() if item.kind == "decor"
    }
    assert core.get_player(key)["coins"] == before + 30
    owned_row = get_conn().execute(
        "SELECT source FROM castle_owned WHERE player_id=? AND item_id=?",
        (player_id, result["item_id"]),
    ).fetchone()
    assert owned_row["source"] == "lexicon-chest"

    # повторный вызов возвращает уже выданное, монеты не капают второй раз
    again = lexicon_chest.open(key)
    assert again == result
    assert core.get_player(key)["coins"] == before + 30
    assert lexicon_chest.status(player_id)["opened"] == 1


def test_open_without_ready_is_rejected(learner):
    key, _ = learner
    _learn(_, 24)
    with pytest.raises(Conflict):
        lexicon_chest.open(key)


def test_all_decor_owned_gives_bigger_coins(learner):
    key, player_id = learner
    _learn(player_id, 25)
    conn = get_conn()
    for item in catalog.ITEMS.values():
        if item.kind == "decor":
            conn.execute(
                "INSERT OR IGNORE INTO castle_owned (player_id, item_id, anchor, source) VALUES (?,?,?,?)",
                (player_id, item.id, item.anchor, "shop"),
            )
    before = core.get_player(key)["coins"]
    result = lexicon_chest.open(key)
    assert result["item_id"] is None
    assert result["coins"] == 60
    assert core.get_player(key)["coins"] == before + 60


def test_second_chest_after_fifty_words(learner):
    key, player_id = learner
    _learn(player_id, 50)
    first = lexicon_chest.open(key)
    assert lexicon_chest.status(player_id)["ready"] == 1
    second = lexicon_chest.open(key)
    assert second["item_id"] != first["item_id"]  # два сундука не дают одну вещь дважды
    assert lexicon_chest.status(player_id)["opened"] == 2
