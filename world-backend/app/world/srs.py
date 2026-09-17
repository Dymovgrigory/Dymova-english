"""Интервальные повторения слов (система Лейтнера).

Сила слова 0–5 живёт в word_stats. Верный ответ поднимает силу и отодвигает
срок следующего показа, ошибка — опускает силу и возвращает слово почти сразу.
«Двор тренировки» берёт слова, у которых срок уже наступил.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .db import get_conn

# Индекс — сила слова 0..5. Слабое слово возвращается завтра, крепкое — через месяц.
INTERVALS_DAYS = (1, 1, 3, 7, 14, 30)
MAX_STRENGTH = len(INTERVALS_DAYS) - 1
DUE_LIMIT = 20


def interval_days(strength: int) -> int:
    return INTERVALS_DAYS[max(0, min(MAX_STRENGTH, int(strength)))]


def _today() -> datetime:
    return datetime.now(timezone.utc)


def _due_date(strength: int) -> str:
    return (_today() + timedelta(days=interval_days(strength))).strftime("%Y-%m-%d")


def touch(player_id: int, unit_id: str, word_en: str, *, correct: bool) -> int:
    """Обновляет силу слова и срок следующего повторения. Возвращает новую силу."""
    if not word_en or unit_id == "practice":
        return 0
    conn = get_conn()
    row = conn.execute(
        "SELECT strength FROM word_stats WHERE player_id=? AND unit_id=? AND word_en=?",
        (player_id, unit_id, word_en),
    ).fetchone()
    old = int(row["strength"]) if row else 0
    strength = max(0, min(MAX_STRENGTH, old + (1 if correct else -1)))
    conn.execute(
        "INSERT INTO word_stats (player_id, unit_id, word_en, correct_count, wrong_count,"
        " strength, due_at) VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(player_id, unit_id, word_en) DO UPDATE SET"
        " correct_count=word_stats.correct_count+excluded.correct_count,"
        " wrong_count=word_stats.wrong_count+excluded.wrong_count,"
        " strength=excluded.strength,"
        " due_at=excluded.due_at,"
        " updated_at=datetime('now')",
        (player_id, unit_id, word_en, 1 if correct else 0, 0 if correct else 1,
         strength, _due_date(strength)),
    )
    return strength


def due_words(player_id: int, limit: int = DUE_LIMIT) -> list[dict]:
    """Слова, чей срок повторения наступил: сначала самые слабые и самые просроченные."""
    rows = get_conn().execute(
        "SELECT unit_id, word_en, strength, due_at FROM word_stats"
        " WHERE player_id=? AND due_at IS NOT NULL AND date(due_at)<=date('now')"
        " ORDER BY strength ASC, due_at ASC LIMIT ?",
        (player_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def review_count(player_id: int) -> int:
    return int(get_conn().execute(
        "SELECT COUNT(*) AS n FROM word_stats"
        " WHERE player_id=? AND due_at IS NOT NULL AND date(due_at)<=date('now')",
        (player_id,),
    ).fetchone()["n"])
