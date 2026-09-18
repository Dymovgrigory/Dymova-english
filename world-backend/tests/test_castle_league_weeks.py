"""Неделя лиги закрывается лениво, один раз, и платит за место."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.castle import league_weeks
from app.world import core
from app.world.db import get_conn


def _player_with_xp(key: str, name: str, xp: int, *, days_ago: int) -> int:
    player = core.get_or_create_player(key, name)
    moment = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
    get_conn().execute(
        "INSERT INTO xp_transactions (player_id, type, amount, source, idempotency_key, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (player["id"], "LESSON_REWARD", xp, "test", f"xp:{key}:{days_ago}:{xp}", moment),
    )
    return int(player["id"])


def test_week_start_is_monday():
    assert league_weeks.week_start(datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)) == "2026-09-14"
    assert league_weeks.week_start(datetime(2026, 9, 14, 0, 30, tzinfo=timezone.utc)) == "2026-09-14"


def test_closing_pays_by_rank_and_only_once(learn_db):
    _player_with_xp("kid-a", "Аня", 300, days_ago=9)
    _player_with_xp("kid-b", "Боря", 200, days_ago=9)

    closed = league_weeks.close_previous_week()
    assert closed == 2
    assert core.get_player("kid-a")["coins"] == league_weeks.COINS_BY_RANK[1]
    assert core.get_player("kid-b")["coins"] == league_weeks.COINS_BY_RANK[2]

    assert league_weeks.close_previous_week() == 0
    assert core.get_player("kid-a")["coins"] == league_weeks.COINS_BY_RANK[1]


def test_player_without_lessons_is_not_recorded(learn_db):
    core.get_or_create_player("kid-quiet", "Тихоня")
    league_weeks.close_previous_week()
    rows = get_conn().execute("SELECT COUNT(*) AS c FROM league_weeks").fetchone()["c"]
    assert rows == 0


def test_league_returns_trophy_history(learn_db):
    """Башня Славы показывает прошлые недели: свежие первыми, не больше восьми."""
    key = "trophy-kid"
    player_id = int(core.get_or_create_player(key, "Трофеев")["id"])
    conn = get_conn()
    for n in range(10):
        conn.execute(
            "INSERT INTO league_weeks (player_id, week_start, rank, weekly_xp, coins_awarded)"
            " VALUES (?,?,?,?,?)",
            (player_id, f"2026-07-{n + 1:02d}", (n % 5) + 1, 100 + n, 30),
        )
    from app.world import learn
    body = learn.league(key)
    history = body["history"]
    assert len(history) == 8
    assert history[0]["week_start"] == "2026-07-10"  # свежая первая
    assert history[0]["rank"] == (9 % 5) + 1
    assert all(set(row) == {"week_start", "rank", "weekly_xp", "coins_awarded"} for row in history)


def test_league_history_empty_for_newcomer(learn_db):
    key = "no-trophies"
    core.get_or_create_player(key, "Новичок")
    from app.world import learn
    assert learn.league(key)["history"] == []
