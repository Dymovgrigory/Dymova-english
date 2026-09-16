"""Прогресс ученика: профиль «Мой класс», статусы узлов пути, награды, серия и цель дня."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.world import core
from app.world.db import get_conn

from . import clock
from .content import Course
from .errors import Conflict, NotFound, ProfileRequired

DAILY_GOALS = (10, 20, 30)
XP_NODE = 10
XP_PERFECT_BONUS = 5
XP_PER_STAR = 10
COINS_SESSION = 5
COINS_CHEST = 30
COINS_MODULE_TEST_FIRST = 50
STAR_THRESHOLDS = (0.95, 0.80, 0.60)  # 3, 2, 1 звезда
STREAK_LOOKBACK_DAYS = 400

COMPLETED, CURRENT, OPEN, LOCKED = "completed", "current", "open", "locked"


@dataclass(frozen=True)
class Reward:
    xp: int
    coins: int
    stars: int
    passed: bool


def stars_for(accuracy: float) -> int:
    for stars, threshold in zip((3, 2, 1), STAR_THRESHOLDS):
        if accuracy >= threshold:
            return stars
    return 0


def session_reward(kind: str, accuracy: float, wrong: int) -> Reward:
    if kind == "module_test":
        stars = stars_for(accuracy)
        return Reward(xp=XP_PER_STAR * stars, coins=COINS_SESSION, stars=stars, passed=stars >= 1)
    bonus = XP_PERFECT_BONUS if wrong == 0 else 0
    return Reward(xp=XP_NODE + bonus, coins=COINS_SESSION, stars=0, passed=True)


# --- профиль -------------------------------------------------------------------------------

def get_profile(player_id: int) -> dict:
    row = get_conn().execute(
        "SELECT book_id, module_id, daily_goal_xp FROM learner_profile WHERE player_id=?", (player_id,)
    ).fetchone()
    if row is None:
        raise ProfileRequired()
    return {"book_id": row["book_id"], "module_id": row["module_id"], "daily_goal_xp": int(row["daily_goal_xp"])}


def set_profile(player_id: int, course: Course, *, book_id: str, module_id: str, daily_goal_xp: int) -> dict:
    course.book(book_id)
    if course.module(module_id).book != book_id:
        raise NotFound(f"module {module_id!r} is not in book {book_id!r}")
    if daily_goal_xp not in DAILY_GOALS:
        raise Conflict("daily_goal_xp must be one of 10, 20, 30")
    get_conn().execute(
        "INSERT INTO learner_profile (player_id, book_id, module_id, daily_goal_xp) VALUES (?,?,?,?)"
        " ON CONFLICT(player_id) DO UPDATE SET book_id=excluded.book_id, module_id=excluded.module_id,"
        " daily_goal_xp=excluded.daily_goal_xp, updated_at=datetime('now')",
        (player_id, book_id, module_id, daily_goal_xp),
    )
    return get_profile(player_id)


# --- узлы пути -----------------------------------------------------------------------------

def completed_nodes(player_id: int) -> dict[str, dict]:
    rows = get_conn().execute(
        "SELECT node_id, stars, best_accuracy FROM node_progress WHERE player_id=?", (player_id,)
    ).fetchall()
    return {r["node_id"]: {"stars": int(r["stars"]), "best_accuracy": float(r["best_accuracy"])} for r in rows}


def complete_node(player_id: int, node_id: str, *, stars: int, accuracy: float, now: datetime) -> None:
    get_conn().execute(
        "INSERT INTO node_progress (player_id, node_id, stars, best_accuracy, completed_at) VALUES (?,?,?,?,?)"
        " ON CONFLICT(player_id, node_id) DO UPDATE SET"
        " stars=CASE WHEN excluded.stars > node_progress.stars THEN excluded.stars ELSE node_progress.stars END,"
        " best_accuracy=CASE WHEN excluded.best_accuracy > node_progress.best_accuracy"
        " THEN excluded.best_accuracy ELSE node_progress.best_accuracy END",
        (player_id, node_id, stars, accuracy, clock.to_iso(now)),
    )


def _book_passed(course: Course, book_id: str, done: dict[str, dict]) -> bool:
    return all(node.id in done for _, node in course.nodes_of(book_id) if node.kind == "module_test")


def node_statuses(course: Course, player_id: int, book_id: str, profile: dict) -> dict[str, str]:
    """Статусы узлов книги.

    Книга ниже класса ученика открыта целиком. В книге ученика узлы до его модуля
    открыты, дальше путь идёт строго по порядку. Книга выше открывается, когда
    пройдены все контрольные книг между ними.
    """
    done = completed_nodes(player_id)
    sequence = course.nodes_of(book_id)
    target = course.book(book_id)
    home = course.book(profile["book_id"])
    if target.grade < home.grade:
        return {node.id: COMPLETED if node.id in done else OPEN for _, node in sequence}
    if target.grade > home.grade:
        between = [b for b in course.books if home.grade <= b.grade < target.grade]
        if not all(_book_passed(course, b.id, done) for b in between):
            return {node.id: COMPLETED if node.id in done else LOCKED for _, node in sequence}
        start = 0
    else:
        start = next(i for i, (module, _) in enumerate(sequence) if module.id == profile["module_id"])

    statuses: dict[str, str] = {}
    frontier_found = False
    for position, (_, node) in enumerate(sequence):
        if node.id in done:
            statuses[node.id] = COMPLETED
        elif position < start:
            statuses[node.id] = OPEN
        elif not frontier_found:
            statuses[node.id] = CURRENT
            frontier_found = True
        else:
            statuses[node.id] = LOCKED
    return statuses


def next_node_id(course: Course, node_id: str) -> str | None:
    module, _ = course.node(node_id)
    ids = [node.id for _, node in course.nodes_of(module.book)]
    position = ids.index(node_id)
    return ids[position + 1] if position + 1 < len(ids) else None


def assert_startable(course: Course, player_id: int, node_id: str) -> None:
    module, _ = course.node(node_id)
    status = node_statuses(course, player_id, module.book, get_profile(player_id))[node_id]
    if status == LOCKED:
        raise Conflict("node_locked")


# --- день и серия --------------------------------------------------------------------------

def record_activity(player_id: int, xp: int, *, now: datetime) -> dict:
    day = clock.local_day(now)
    get_conn().execute(
        "INSERT INTO daily_activity (player_id, day, xp, sessions) VALUES (?,?,?,1)"
        " ON CONFLICT(player_id, day) DO UPDATE SET xp=daily_activity.xp+excluded.xp,"
        " sessions=daily_activity.sessions+1",
        (player_id, day, xp),
    )
    return {"today_xp": today_xp(player_id, now=now), "streak_days": streak_days(player_id, now=now)}


def today_xp(player_id: int, *, now: datetime) -> int:
    row = get_conn().execute(
        "SELECT xp FROM daily_activity WHERE player_id=? AND day=?", (player_id, clock.local_day(now))
    ).fetchone()
    return int(row["xp"]) if row else 0


def streak_days(player_id: int, *, now: datetime) -> int:
    """Дней подряд с занятием. Серия жива, если занимались сегодня или вчера."""
    rows = get_conn().execute(
        "SELECT day FROM daily_activity WHERE player_id=? AND sessions>0 ORDER BY day DESC LIMIT ?",
        (player_id, STREAK_LOOKBACK_DAYS),
    ).fetchall()
    days = {r["day"] for r in rows}
    today = clock.local_day(now)
    cursor = today if today in days else clock.add_days(today, -1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor = clock.add_days(cursor, -1)
    return streak


# --- сундук --------------------------------------------------------------------------------

def open_chest(external_key: str, course: Course, node_id: str, *, now: datetime | None = None) -> dict:
    moment = now or clock.now()
    player_id = core.get_player(external_key)["id"]
    module, node = course.node(node_id)
    if node.kind != "chest":
        raise Conflict("not_a_chest")
    status = node_statuses(course, player_id, module.book, get_profile(player_id))[node_id]
    if status == COMPLETED:
        raise Conflict("chest_opened")
    if status == LOCKED:
        raise Conflict("node_locked")
    award = core.award(
        external_key, coins=COINS_CHEST, source=node_id, type_="CHEST_REWARD",
        idempotency_key=f"v2:chest:{player_id}:{node_id}",
    )
    complete_node(player_id, node_id, stars=0, accuracy=1.0, now=moment)
    return {"coins": COINS_CHEST, "next_node_id": next_node_id(course, node_id), "player": award["player"]}
