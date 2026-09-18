"""Значения веток берутся из уже существующих таблиц прогресса."""
from __future__ import annotations

from app.castle import counters
from app.learning import mastery
from app.world.db import get_conn


def _word(player_id: int, atom_id: str, strength: int, *, learned_at: str | None = "2026-09-18") -> None:
    """Атом в atom_mastery с заданной силой (как пишет mastery.record)."""
    get_conn().execute(
        "INSERT INTO atom_mastery (player_id, atom_id, strength, correct_count, wrong_count, due_at, updated_at, learned_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (player_id, atom_id, strength, strength, 0, "2026-09-18", "2026-09-18T10:00:00", learned_at if strength >= 2 else None),
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
    _word(player_id, "sp1.m1.cat", 2)
    _word(player_id, "sp1.m1.dog", 5)
    _word(player_id, "sp1.m1.mum", 1)  # ещё не выучено
    assert counters.counters(player_id)["lexicon"] == 2


def test_counts_only_word_atoms(learner):
    """Фразы и грамматика в Словесник не идут — только слова учебника."""
    _, player_id = learner
    _word(player_id, "sp1.m1.cat", 3)
    _word(player_id, "sp1.m1.p1", 5)  # фраза из того же модуля
    assert counters.counters(player_id)["lexicon"] == 1


def test_learned_at_marks_first_crossing(learner):
    """mastery.record ставит learned_at один раз — при первом достижении порога."""
    _, player_id = learner
    mastery.record(player_id, "sp1.m1.cat", correct=True)   # 0 → 1, порога нет
    row = get_conn().execute(
        "SELECT learned_at FROM atom_mastery WHERE player_id=? AND atom_id=?",
        (player_id, "sp1.m1.cat"),
    ).fetchone()
    assert row["learned_at"] is None
    mastery.record(player_id, "sp1.m1.cat", correct=True)   # 1 → 2, порог взят
    row = get_conn().execute(
        "SELECT learned_at FROM atom_mastery WHERE player_id=? AND atom_id=?",
        (player_id, "sp1.m1.cat"),
    ).fetchone()
    first = row["learned_at"]
    assert first is not None
    mastery.record(player_id, "sp1.m1.cat", correct=False)  # 2 → 1
    mastery.record(player_id, "sp1.m1.cat", correct=True)   # 1 → 2 повторно
    row = get_conn().execute(
        "SELECT learned_at FROM atom_mastery WHERE player_id=? AND atom_id=?",
        (player_id, "sp1.m1.cat"),
    ).fetchone()
    assert row["learned_at"] == first  # дата первого взятия порога не перезаписывается


def test_counts_trial_as_practice(learner):
    """Испытание дня (`kind='trial'`) растёт в ветку Тренера наравне с тренировкой."""
    _, player_id = learner
    get_conn().execute(
        "INSERT INTO learn_sessions (id, player_id, node_id, kind, payload, pending, state, status, started_at)"
        " VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
        ("trial-1", player_id, "trial", "trial", "{}", "[]", "{}", "completed"),
    )
    assert counters.counters(player_id)["yard"] == 1


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
