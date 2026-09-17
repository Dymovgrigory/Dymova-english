"""Текущие значения веток званий.

Считаем из таблиц, которые уже ведёт движок учёбы, а не заводим свои счётчики:
один источник правды, и пересчёт остаётся верным даже после ручных правок базы.
"""
from __future__ import annotations

from app.learning import clock, progress
from app.world.db import get_conn

WORD_LEARNED_STRENGTH = 2  # шкала силы слова 0..5; 2 — слово пережило пару верных ответов
PRACTICE_REWARD_TYPE = "PRACTICE_REWARD"


def _scalar(sql: str, params: tuple) -> int:
    row = get_conn().execute(sql, params).fetchone()
    return int(row["value"]) if row else 0


def counters(player_id: int) -> dict[str, int]:
    """Значения всех веток званий игрока на текущий момент."""
    return {
        "lexicon": _scalar(
            "SELECT COUNT(*) AS value FROM word_stats WHERE player_id=? AND strength>=?",
            (player_id, WORD_LEARNED_STRENGTH),
        ),
        "yard": _scalar(
            "SELECT COUNT(*) AS value FROM coin_transactions WHERE player_id=? AND type=?",
            (player_id, PRACTICE_REWARD_TYPE),
        ),
        "nest": progress.streak_days(player_id, now=clock.now()),
        "glory": _scalar(
            "SELECT COUNT(*) AS value FROM league_weeks WHERE player_id=? AND rank<=3",
            (player_id,),
        ),
        "stickers": _scalar(
            "SELECT COUNT(*) AS value FROM inventory WHERE player_id=? AND item_id LIKE 'sticker-%'",
            (player_id,),
        ),
    }
