"""Значения веток берутся из уже существующих таблиц прогресса."""
from __future__ import annotations

from app.castle import counters
from app.world.db import get_conn


def _word(player_id: int, word: str, strength: int) -> None:
    get_conn().execute(
        "INSERT INTO word_stats (player_id, unit_id, word_en, strength) VALUES (?,?,?,?)",
        (player_id, "sp1.m1", word, strength),
    )


def _practice_session(player_id: int, session_id: str, status: str) -> None:
    """Сессия практики (`kind='practice'`), как её кладёт `builder.py` / завершает `sessions.finish`."""
    get_conn().execute(
        "INSERT INTO learn_sessions (id, player_id, node_id, kind, payload, pending, state, status, started_at)"
        " VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
        (session_id, player_id, "sp1.m1", "practice", "{}", "[]", "{}", status),
    )


def test_counts_only_learned_words(learner):
    _, player_id = learner
    _word(player_id, "cat", 2)
    _word(player_id, "dog", 5)
    _word(player_id, "fish", 1)  # ещё не выучено
    assert counters.counters(player_id)["lexicon"] == 2


def test_counts_practice_sessions(learner):
    _, player_id = learner
    for n in range(3):
        _practice_session(player_id, f"practice-{n}", "completed")
    assert counters.counters(player_id)["yard"] == 3


def test_counts_practice_without_coin_reward(learner):
    """Третья и последующие тренировки за день не начисляют монеты (§task-5), но в ветку идут."""
    _, player_id = learner
    _practice_session(player_id, "practice-no-coins", "completed")
    assert get_conn().execute(
        "SELECT COUNT(*) AS n FROM coin_transactions WHERE player_id=?", (player_id,)
    ).fetchone()["n"] == 0
    assert counters.counters(player_id)["yard"] == 1


def test_active_practice_session_not_counted(learner):
    _, player_id = learner
    _practice_session(player_id, "practice-active", "active")
    assert counters.counters(player_id)["yard"] == 0


def test_counts_top3_weeks_and_stickers(learner):
    _, player_id = learner
    get_conn().execute(
        "INSERT INTO league_weeks (player_id, week_start, rank, weekly_xp) VALUES (?,?,?,?)",
        (player_id, "2026-09-07", 2, 120),
    )
    get_conn().execute(
        "INSERT INTO league_weeks (player_id, week_start, rank, weekly_xp) VALUES (?,?,?,?)",
        (player_id, "2026-09-14", 7, 90),
    )
    get_conn().execute(
        "INSERT OR IGNORE INTO items (id, category, title_ru) VALUES ('sticker-family','collectibles','Семья')"
    )
    get_conn().execute(
        "INSERT INTO inventory (player_id, item_id, source) VALUES (?,?,?)", (player_id, "sticker-family", "lesson")
    )
    values = counters.counters(player_id)
    assert values["glory"] == 1
    assert values["stickers"] == 1


def test_streak_comes_from_learning_progress(learner):
    _, player_id = learner
    assert counters.counters(player_id)["nest"] == 0
