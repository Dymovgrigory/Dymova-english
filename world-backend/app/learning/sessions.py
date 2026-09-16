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
        return {"correct": True, "typo": False, "skipped": skipped, "solution": None,
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
        "requeued": requeued,
        "remaining": len(session["pending"]),
    }


def finish(external_key: str, session_id: str, *, now: datetime | None = None) -> dict:
    moment = now or clock.now()
    player_id = _player_id(external_key)
    session = _load(player_id, session_id)
    if session["status"] == "completed":
        return session["result"]
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

    coins = reward.coins
    completes = kind != PRACTICE_NODE and reward.passed
    if kind == "module_test" and reward.passed and node_id not in progress.completed_nodes(player_id):
        coins += progress.COINS_MODULE_TEST_FIRST
    award = core.award(
        external_key, xp=reward.xp, coins=coins, source=node_id, type_="LESSON_REWARD",
        idempotency_key=f"v2:{session_id}",
    )
    if completes:
        progress.complete_node(player_id, node_id, stars=reward.stars, accuracy=accuracy, now=moment)
    day = progress.record_activity(player_id, reward.xp, now=moment)
    goal = progress.get_profile(player_id)["daily_goal_xp"]
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
        "player": {k: award["player"][k] for k in ("xp", "coins", "level")},
    }
    get_conn().execute(
        "UPDATE learn_sessions SET status='completed', finished_at=?, result=? WHERE id=?",
        (clock.to_iso(moment), json.dumps(result, ensure_ascii=False), session_id),
    )
    return result
