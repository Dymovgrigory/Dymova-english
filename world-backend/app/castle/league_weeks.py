"""Итог недели в лиге.

Лига считается скользящим окном и сама ничего не сохраняет. Здесь неделя
закрывается лениво: первый заход после понедельника подводит итог прошлой недели
один раз. Внешний планировщик не нужен — на сервере его всё равно нет.

Сутки и недели считаем по Москве (см. `app.learning.clock`): понедельник недели
берётся из местной даты, а границы недели переводятся в UTC-строку той же
формы, в которой SQLite хранит `created_at`, — чтобы не дублировать смещение
часового пояса прямо в SQL.
"""
from __future__ import annotations

from datetime import date, datetime

from app.learning import clock
from app.world import core
from app.world.db import get_conn

COINS_BY_RANK = {1: 100, 2: 60, 3: 60, 4: 30, 5: 30, 6: 30, 7: 30, 8: 30, 9: 30, 10: 30}


def week_start(moment: datetime) -> str:
    """Понедельник недели (по Москве), к которой относится момент."""
    local_day = clock.local_day(moment)
    weekday = date.fromisoformat(local_day).weekday()
    return clock.add_days(local_day, -weekday)


def close_previous_week(now: datetime | None = None) -> int:
    """Подводит итог прошлой недели. Возвращает число закрытых игроков."""
    moment = now or clock.now()
    current_start = week_start(moment)
    prev_start = clock.add_days(current_start, -7)
    range_start = clock.day_start_sql(prev_start)
    range_end = clock.day_start_sql(current_start)

    conn = get_conn()
    rows = conn.execute(
        "SELECT p.id, p.external_key,"
        " COALESCE(SUM(CASE WHEN x.amount>0 AND x.created_at>=? AND x.created_at<? THEN x.amount END),0)"
        " AS weekly_xp"
        " FROM players p LEFT JOIN xp_transactions x ON x.player_id=p.id"
        " WHERE p.role='child'"
        " GROUP BY p.id HAVING weekly_xp > 0 ORDER BY weekly_xp DESC, p.id ASC",
        (range_start, range_end),
    ).fetchall()

    closed = 0
    for rank, row in enumerate(rows, start=1):
        already = conn.execute(
            "SELECT 1 FROM league_weeks WHERE player_id=? AND week_start=?",
            (row["id"], prev_start),
        ).fetchone()
        if already:
            continue
        coins = COINS_BY_RANK.get(rank, 0)
        conn.execute(
            "INSERT INTO league_weeks (player_id, week_start, rank, weekly_xp, coins_awarded)"
            " VALUES (?,?,?,?,?)",
            (row["id"], prev_start, rank, int(row["weekly_xp"]), coins),
        )
        if coins:
            core.award(
                row["external_key"], coins=coins, source=f"league:{prev_start}", type_="LEAGUE_REWARD",
                idempotency_key=f"league:{row['id']}:{prev_start}",
            )
        closed += 1
    return closed
