"""Задания Беседки: три дневных и три недельных, награды монетами.

Таблицы v2: уроки — learn_sessions (всё, кроме practice/trial), «без ошибок» —
node_progress с best_accuracy=1, XP дня — daily_activity, новые слова недели —
atom_mastery.learned_at. Каждое задание ведёт в своё здание (spot) — Беседка
раздаёт работу остальным зданиям замка.
"""
from __future__ import annotations

from app.learning import clock, progress
from app.world import core
from app.world.core import Conflict, NotFound
from app.world.db import get_conn

from . import counters, league_weeks

DAILY = (
    # (id, название, цель, монет, здание, ссылка)
    ("xp-goal", "Выполни цель дня", None, 5, "school", "/learn"),  # цель из профиля
    ("lesson-1", "Пройди урок", 1, 5, "school", "/learn"),
    ("perfect-1", "Урок без ошибок", 1, 5, "school", "/learn"),
)

WEEKLY = (
    ("week-lessons", "5 уроков за неделю", 5, 30, "school", "/learn"),
    ("week-practice", "3 тренировки за неделю", 3, 20, "yard", "/practice"),
    ("week-words", "25 новых слов за неделю", 25, 20, "lexicon", "/words"),
)

_TYPE = "QUEST_V2"


def _claimed(player_id: int, window: str) -> set[str]:
    prefix = f"quest-v2:{player_id}:{window}:"
    rows = get_conn().execute(
        "SELECT idempotency_key FROM coin_transactions WHERE player_id=? AND type=? AND idempotency_key LIKE ?",
        (player_id, _TYPE, f"{prefix}%"),
    ).fetchall()
    return {str(r["idempotency_key"])[len(prefix):].removesuffix(":coins") for r in rows}


def _pack(qid: str, title: str, progress_value: int, target: int, coins: int,
          spot: str, href: str, period: str, claimed: set[str]) -> dict:
    done = progress_value >= target
    return {
        "id": qid,
        "period": period,
        "title_ru": title,
        "progress": min(progress_value, target),
        "target": target,
        "coins": coins,
        "done": done,
        "claimed": qid in claimed,
        "claimable": done and qid not in claimed,
        "spot": spot,
        "href": href,
    }


def quests(external_key: str) -> dict:
    player = core.get_player(external_key)
    player_id = int(player["id"])
    now = clock.now()
    today = clock.local_day(now)
    week = league_weeks.week_start(now)
    conn = get_conn()

    xp_today = int(
        conn.execute(
            "SELECT COALESCE(xp,0) AS xp FROM daily_activity WHERE player_id=? AND day=?",
            (player_id, today),
        ).fetchone()["xp"]
        if conn.execute(
            "SELECT COUNT(*) AS n FROM daily_activity WHERE player_id=? AND day=?", (player_id, today)
        ).fetchone()["n"]
        else 0
    )
    goal = int(progress.get_profile(player_id)["daily_goal_xp"])

    lessons_today = int(conn.execute(
        "SELECT COUNT(*) AS n FROM learn_sessions WHERE player_id=? AND status='completed'"
        " AND kind NOT IN ('practice','trial') AND substr(started_at,1,10)=?",
        (player_id, today),
    ).fetchone()["n"])
    perfect_today = int(conn.execute(
        "SELECT COUNT(*) AS n FROM node_progress WHERE player_id=? AND best_accuracy>=1"
        " AND substr(completed_at,1,10)=?",
        (player_id, today),
    ).fetchone()["n"])

    lessons_week = int(conn.execute(
        "SELECT COUNT(*) AS n FROM learn_sessions WHERE player_id=? AND status='completed'"
        " AND kind NOT IN ('practice','trial') AND substr(started_at,1,10)>=?",
        (player_id, week),
    ).fetchone()["n"])
    practice_week = int(conn.execute(
        "SELECT COUNT(*) AS n FROM learn_sessions WHERE player_id=? AND status='completed'"
        " AND kind IN ('practice','trial') AND substr(started_at,1,10)>=?",
        (player_id, week),
    ).fetchone()["n"])
    words_week = counters.learned_words(player_id, since=week)

    daily_claimed = _claimed(player_id, today)
    weekly_claimed = _claimed(player_id, week)

    daily_progress = {"xp-goal": xp_today, "lesson-1": lessons_today, "perfect-1": perfect_today}
    weekly_progress = {"week-lessons": lessons_week, "week-practice": practice_week, "week-words": words_week}

    return {
        "daily": [
            _pack(qid, title, daily_progress[qid], target if target is not None else goal,
                  coins, spot, href, "day", daily_claimed)
            for qid, title, target, coins, spot, href in DAILY
        ],
        "weekly": [
            _pack(qid, title, weekly_progress[qid], target, coins, spot, href, "week", weekly_claimed)
            for qid, title, target, coins, spot, href in WEEKLY
        ],
    }


def claim(external_key: str, quest_id: str, period: str) -> dict:
    player = core.get_player(external_key)
    player_id = int(player["id"])
    data = quests(external_key)
    pool = data["daily"] if period == "day" else data["weekly"] if period == "week" else None
    if pool is None:
        raise NotFound(f"period {period!r}")
    quest = next((q for q in pool if q["id"] == quest_id), None)
    if quest is None:
        raise NotFound(f"quest {quest_id!r}")
    if not quest["done"]:
        raise Conflict("quest not complete")
    if quest["claimed"]:
        return {"quest_id": quest_id, "ok": True, "coins_delta": 0}  # двойное нажатие

    now = clock.now()
    window = clock.local_day(now) if period == "day" else league_weeks.week_start(now)
    result = core.award(
        external_key, coins=int(quest["coins"]), source=f"quest:{quest_id}", type_=_TYPE,
        idempotency_key=f"quest-v2:{player_id}:{window}:{quest_id}",
    )
    return {"quest_id": quest_id, "ok": True, "coins_delta": result["coins_delta"]}
