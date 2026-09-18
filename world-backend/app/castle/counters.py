"""Текущие значения веток званий.

Считаем из таблиц, которые уже ведёт движок учёбы, а не заводим свои счётчики:
один источник правды, и пересчёт остаётся верным даже после ручных правок базы.
"""
from __future__ import annotations

from app.learning import clock, content, progress
from app.world.db import get_conn

WORD_LEARNED_STRENGTH = 2  # шкала силы слова 0..5; 2 — слово пережило пару верных ответов


def _scalar(sql: str, params: tuple) -> int:
    row = get_conn().execute(sql, params).fetchone()
    return int(row["value"]) if row else 0


def course_word_ids() -> set[str]:
    """Id всех слов учебников (фразы и грамматика в Словесник не идут)."""
    return {word.id for module in content.get_course().modules for word in module.words}


def learned_words(player_id: int, *, since: str | None = None) -> int:
    """Сколько слов учебника игрок выучил (сила >= порога); `since` — с московского дня."""
    words = course_word_ids()
    if not words:
        return 0
    marks = ",".join("?" for _ in words)
    sql = (
        f"SELECT COUNT(*) AS value FROM atom_mastery WHERE player_id=? AND strength>=?"
        f" AND atom_id IN ({marks})"
    )
    params: list = [player_id, WORD_LEARNED_STRENGTH, *sorted(words)]
    if since is not None:
        sql += " AND learned_at>=?"
        params.append(since)
    return _scalar(sql, tuple(params))


def counters(player_id: int) -> dict[str, int]:
    """Значения всех веток званий игрока на текущий момент."""
    return {
        "lexicon": learned_words(player_id),
        # Считаем по завершённым сессиям практики и испытания, а не по coin_transactions:
        # монеты за тренировку выдаются не больше двух раз в день, и core.award не пишет
        # строку в coin_transactions при нулевой сумме — по монетам третья и следующие
        # тренировки за день потерялись бы.
        "yard": _scalar(
            "SELECT COUNT(*) AS value FROM learn_sessions"
            " WHERE player_id=? AND kind IN ('practice','trial') AND status='completed'",
            (player_id,),
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
