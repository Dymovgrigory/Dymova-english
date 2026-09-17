"""Сессия урока: старт, ответ на задание, финиш с наградой.

Клиент показывает задания по порядку и сам возвращает ошибочные в конец очереди
(`requeued`). Сервер хранит эталоны и множество `pending` — индексы, которые ещё
не решены верно; финиш возможен, только когда оно пусто.
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta

from app.world import core
from app.world.db import get_conn

from . import builder, challenges, clock, content, mastery, progress
from .challenges import Challenge
from .errors import Conflict, Gone, NotFound

SESSION_TTL = timedelta(hours=2)
PRACTICE_NODE = "practice"


def _player_id(external_key: str) -> int:
    return int(core.get_player(external_key)["id"])


def start(external_key: str, node_id: str, *, allow_speak: bool, seed: int | None = None,
          now: datetime | None = None) -> dict:
    moment = now or clock.now()
    player_id = _player_id(external_key)
    course = content.get_course()
    session_seed = seed if seed is not None else random.SystemRandom().randrange(1 << 30)
    progress.get_profile(player_id)
    if node_id == PRACTICE_NODE:
        plan = builder.build_practice(course, player_id, seed=session_seed, allow_speak=allow_speak)
    else:
        progress.assert_startable(course, player_id, node_id)
        plan = builder.build_session(course, node_id, player_id=player_id, seed=session_seed, allow_speak=allow_speak)

    session_id = uuid.uuid4().hex
    state = {"attempts": {}, "first_try": {}, "wrong": 0, "skipped": []}
    get_conn().execute(
        "INSERT INTO learn_sessions (id, player_id, node_id, kind, payload, pending, state, started_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (
            session_id, player_id, plan.node_id, plan.kind,
            json.dumps([c.to_dict() for c in plan.challenges], ensure_ascii=False),
            json.dumps(list(range(len(plan.challenges)))),
            json.dumps(state), clock.to_iso(moment),
        ),
    )
    return {
        "session_id": session_id,
        "node_id": plan.node_id,
        "kind": plan.kind,
        "challenges": [c.public(i) for i, c in enumerate(plan.challenges)],
        "graded_total": sum(1 for c in plan.challenges if c.graded),
    }


def _load(player_id: int, session_id: str) -> dict:
    row = get_conn().execute(
        "SELECT * FROM learn_sessions WHERE id=? AND player_id=?", (session_id, player_id)
    ).fetchone()
    if row is None:
        raise NotFound("session not found")
    return {
        "id": row["id"],
        "node_id": row["node_id"],
        "kind": row["kind"],
        "challenges": [Challenge.from_dict(c) for c in json.loads(row["payload"])],
        "pending": json.loads(row["pending"]),
        "state": json.loads(row["state"]),
        "status": row["status"],
        "started_at": clock.from_iso(row["started_at"]),
        "result": json.loads(row["result"]) if row["result"] else None,
    }


def _save(session: dict) -> None:
    get_conn().execute(
        "UPDATE learn_sessions SET pending=?, state=? WHERE id=?",
        (json.dumps(session["pending"]), json.dumps(session["state"]), session["id"]),
    )


def answer(external_key: str, session_id: str, index: int, payload: dict, *, response_ms: int | None = None,
           now: datetime | None = None) -> dict:
    moment = now or clock.now()
    player_id = _player_id(external_key)
    session = _load(player_id, session_id)
    if session["status"] != "active":
        raise Conflict("session_finished")
    if moment - session["started_at"] > SESSION_TTL:
        raise Gone("session_expired")
    if not 0 <= index < len(session["challenges"]):
        raise NotFound("challenge not found")
    if index not in session["pending"]:
        raise Conflict("challenge_done")

    challenge = session["challenges"][index]
    state = session["state"]
    if not challenge.graded or (challenge.type == "speak" and payload.get("skip") is True):
        session["pending"].remove(index)
        skipped = challenge.graded
        if skipped:
            state["skipped"].append(index)
        _save(session)
        return {"correct": True, "typo": False, "skipped": skipped, "solution": None, "solution_index": None,
                "requeued": False, "remaining": len(session["pending"])}

    verdict = challenges.grade(challenge, payload)
    key = str(index)
    attempt_no = int(state["attempts"].get(key, 0)) + 1
    state["attempts"][key] = attempt_no
    if attempt_no == 1:
        state["first_try"][key] = verdict.correct
        if challenge.atom_id:
            mastery.record(player_id, challenge.atom_id, correct=verdict.correct, now=moment)
    if not verdict.correct:
        state["wrong"] += 1
    requeued = not verdict.correct and session["kind"] != "module_test"
    if not requeued:
        session["pending"].remove(index)
    _save(session)
    get_conn().execute(
        "INSERT INTO attempts (player_id, session_id, node_id, challenge_type, atom_id, answer, correct, typo,"
        " response_ms, attempt_no, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (player_id, session_id, session["node_id"], challenge.type, challenge.atom_id,
         json.dumps(payload, ensure_ascii=False), int(verdict.correct), int(verdict.typo),
         response_ms, attempt_no, clock.to_iso(moment)),
    )
    return {
        "correct": verdict.correct,
        "typo": verdict.typo,
        "skipped": False,
        "solution": challenge.solution.get("display"),
        "solution_index": challenge.solution.get("index"),
        "requeued": requeued,
        "remaining": len(session["pending"]),
    }


def check_pair(external_key: str, session_id: str, index: int, left: str, right: str,
               *, now: datetime | None = None) -> dict:
    """Мгновенная проверка одной пары в «Найди пары»: верная пара фиксируется на клиенте.

    Задание не закрывается и попытка не пишется — итог засчитывается в answer().
    """
    moment = now or clock.now()
    session = _load(_player_id(external_key), session_id)
    if session["status"] != "active":
        raise Conflict("session_finished")
    if moment - session["started_at"] > SESSION_TTL:
        raise Gone("session_expired")
    if not 0 <= index < len(session["challenges"]):
        raise NotFound("challenge not found")
    challenge = session["challenges"][index]
    if challenge.solution.get("kind") != "pairs":
        raise Conflict("not_pairs")
    if index not in session["pending"]:
        raise Conflict("challenge_done")
    return {"correct": [left, right] in challenge.solution["pairs"]}


def finish(external_key: str, session_id: str, *, now: datetime | None = None) -> dict:
    moment = now or clock.now()
    player_id = _player_id(external_key)
    session = _load(player_id, session_id)
    # Результата может не быть, если сессию успели пометить завершённой, а сборка результата
    # упала: тогда идём обычным путём и собираем его заново — начисления идемпотентны.
    if session["status"] == "completed" and session["result"] is not None:
        return session["result"]
    replay = session["status"] == "completed"
    if session["pending"]:
        raise Conflict("session_not_complete")

    course = content.get_course()
    state = session["state"]
    kind, node_id = session["kind"], session["node_id"]
    skipped = set(state["skipped"])
    graded = [i for i, c in enumerate(session["challenges"]) if c.graded and i not in skipped]
    first_ok = sum(1 for i in graded if state["first_try"].get(str(i)))
    accuracy = round(first_ok / len(graded), 3) if graded else 1.0
    reward = progress.session_reward(kind, accuracy, state["wrong"])

    completes = kind != PRACTICE_NODE and reward.passed

    from app.castle import titles as castle_titles

    day_key = clock.local_day(moment)
    breakdown: dict[str, int] = {}
    if kind == PRACTICE_NODE:
        # created_at пишется в UTC, а сутки ученика местные: границу дня берём из clock,
        # чтобы часовой пояс задавался в одном месте.
        paid_today = get_conn().execute(
            "SELECT COUNT(*) AS c FROM coin_transactions"
            " WHERE player_id=? AND type='PRACTICE_REWARD' AND created_at>=?",
            (player_id, clock.day_start_sql(day_key)),
        ).fetchone()["c"]
        if paid_today < progress.PRACTICE_PAID_PER_DAY:
            breakdown["practice"] = progress.COINS_PRACTICE
    else:
        breakdown["lesson"] = reward.coins
        if state["wrong"] == 0:
            breakdown["perfect"] = progress.COINS_PERFECT
        if kind == "module_test" and reward.passed and node_id not in progress.completed_nodes(player_id):
            breakdown["module_test"] = progress.COINS_MODULE_TEST_FIRST

    coins = sum(breakdown.values())
    award_type = "PRACTICE_REWARD" if kind == PRACTICE_NODE else "LESSON_REWARD"
    core.award(
        external_key, xp=reward.xp, coins=coins, source=node_id, type_=award_type,
        idempotency_key=f"v2:{session_id}",
    )
    if completes:
        progress.complete_node(player_id, node_id, stars=reward.stars, accuracy=accuracy, now=moment)
    if replay:
        # Пересборка результата: день уже посчитан, повторная запись задвоила бы xp дня.
        day = {"today_xp": progress.today_xp(player_id, now=moment),
               "streak_days": progress.streak_days(player_id, now=moment)}
    else:
        day = progress.record_activity(player_id, reward.xp, now=moment)
    goal = progress.get_profile(player_id)["daily_goal_xp"]
    if day["today_xp"] >= goal:
        goal_award = core.award(
            external_key, coins=progress.COINS_DAILY_GOAL, source=day_key, type_="DAILY_GOAL_REWARD",
            idempotency_key=f"goal:{player_id}:{day_key}",
        )
        if goal_award["coins_delta"]:
            breakdown["daily_goal"] = progress.COINS_DAILY_GOAL
            coins += progress.COINS_DAILY_GOAL

    # Сессию закрываем до пересчёта званий: ветка «Тренер» считает завершённые тренировки,
    # иначе звание за эту тренировку пришло бы только со следующей.
    conn = get_conn()
    conn.execute(
        "UPDATE learn_sessions SET status='completed', finished_at=? WHERE id=?",
        (clock.to_iso(moment), session_id),
    )
    titles_gained = castle_titles.sync(external_key)
    player = core.get_player(external_key)  # снимок уже с монетами за новые звания
    result = {
        "node_id": node_id,
        "kind": kind,
        "xp": reward.xp,
        "coins": coins,
        "stars": reward.stars,
        "passed": reward.passed,
        "accuracy": accuracy,
        "mistakes": state["wrong"],
        "duration_sec": int((moment - session["started_at"]).total_seconds()),
        "streak_days": day["streak_days"],
        "today_xp": day["today_xp"],
        "daily_goal_xp": goal,
        "goal_reached": day["today_xp"] >= goal,
        "node_completed": completes,
        "next_node_id": progress.next_node_id(course, node_id) if completes else None,
        "player": {k: player[k] for k in ("xp", "coins", "level")},
        "coins_breakdown": breakdown,
        "titles_gained": titles_gained,
    }
    conn.execute(
        "UPDATE learn_sessions SET result=? WHERE id=?",
        (json.dumps(result, ensure_ascii=False), session_id),
    )
    return result
