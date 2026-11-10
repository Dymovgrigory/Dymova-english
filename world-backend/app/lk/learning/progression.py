"""LMS-only mastery and rank progression."""
from __future__ import annotations

from app.world.db import get_conn

RANKS = (
    (0, "Гость Фоксинбурга"), (50, "Ученик"), (150, "Следопыт"),
    (300, "Знаток"), (550, "Мастер"), (900, "Хранитель знаний"),
    (1400, "Герой английского"), (2200, "Легенда Фоксинбурга"),
)


def rank_for(points: int) -> dict:
    index = max(i for i, (threshold, _) in enumerate(RANKS) if points >= threshold)
    next_rank = RANKS[index + 1] if index + 1 < len(RANKS) else None
    return {"index": index + 1, "title": RANKS[index][1], "points": points,
            "next_title": next_rank[1] if next_rank else "",
            "next_points": next_rank[0] if next_rank else None}


def add_points(learner_key: str, event_key: str, source: str, points: int) -> dict:
    conn = get_conn()
    conn.execute(
        "INSERT INTO lk_learning_points (learner_key,event_key,source,points) VALUES (?,?,?,?) ON CONFLICT(event_key) DO NOTHING",
        (learner_key, event_key, source, max(0, int(points))),
    )
    row = conn.execute("SELECT COALESCE(SUM(points),0) AS points FROM lk_learning_points WHERE learner_key=?", (learner_key,)).fetchone()
    return rank_for(int(row["points"] or 0))


def summary(learner_key: str) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT COALESCE(SUM(points),0) AS points FROM lk_learning_points WHERE learner_key=?", (learner_key,)).fetchone()
    result = rank_for(int(row["points"] or 0))
    result["mastery"] = [dict(item) for item in conn.execute(
        "SELECT unit_id, skill, level, attempts, correct, updated_at FROM lk_learning_mastery WHERE learner_key=? ORDER BY unit_id, skill",
        (learner_key,)).fetchall()]
    return result
