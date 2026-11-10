"""Persistent LMS lesson sessions for the private cabinet."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.world import core
from app.world.db import get_conn

from .catalog import unit
from .core import Challenge, grade
from .tasks import tasks_for
from . import progression

SESSION_TTL_HOURS = 2


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _public(challenge: Challenge, index: int) -> dict:
    body = {"id": challenge.id, "index": index, "kind": challenge.kind, "prompt": challenge.prompt,
            "options": list(challenge.options), "graded": True}
    if challenge.kind == "listen_choice":
        body["audio"] = challenge.prompt
    return body


def start(learner_key: str, unit_id: str) -> dict:
    selected = unit(unit_id)
    challenges = tasks_for(selected.id)
    session_id = uuid.uuid4().hex
    pending = list(range(len(challenges)))
    conn = get_conn()
    conn.execute(
        "INSERT INTO lk_learning_sessions (id,learner_key,unit_id,payload,pending) VALUES (?,?,?,?,?)",
        (session_id, learner_key, selected.id, json.dumps([c.__dict__ for c in challenges]), json.dumps(pending)),
    )
    return {"session_id": session_id, "unit": selected.__dict__,
            "challenges": [_public(c, i) for i, c in enumerate(challenges)], "graded_total": len(challenges)}


def _load(learner_key: str, session_id: str) -> dict:
    row = get_conn().execute(
        "SELECT * FROM lk_learning_sessions WHERE id=? AND learner_key=?", (session_id, learner_key)
    ).fetchone()
    if row is None:
        raise core.Conflict("learning_session_not_found")
    challenges = [Challenge(**item) for item in json.loads(row["payload"])]
    return {"row": row, "challenges": challenges, "pending": json.loads(row["pending"]),
            "state": json.loads(row["state"])}


def answer(learner_key: str, session_id: str, challenge_id: str, payload: dict) -> dict:
    session = _load(learner_key, session_id)
    challenge_index = next((i for i, c in enumerate(session["challenges"]) if c.id == challenge_id), None)
    if challenge_index is None:
        raise core.Conflict("learning_challenge_not_found")
    if challenge_index not in session["pending"]:
        raise core.Conflict("learning_challenge_done")
    conn = get_conn()
    prior = conn.execute(
        "SELECT correct, attempt_no FROM lk_learning_attempts WHERE session_id=? AND challenge_id=? ORDER BY attempt_no DESC LIMIT 1",
        (session_id, challenge_id),
    ).fetchone()
    attempt_no = int(prior["attempt_no"]) + 1 if prior else 1
    verdict = grade(session["challenges"][challenge_index], payload)
    conn.execute(
        "INSERT INTO lk_learning_attempts (session_id,learner_key,challenge_id,kind,answer,correct,attempt_no) VALUES (?,?,?,?,?,?,?)",
        (session_id, learner_key, challenge_id, session["challenges"][challenge_index].kind,
         json.dumps(payload, ensure_ascii=False), int(verdict.correct), attempt_no),
    )
    # One wrong attempt is retried in the same session; a correct answer closes it.
    if verdict.correct:
        session["pending"].remove(challenge_index)
    conn.execute("UPDATE lk_learning_sessions SET pending=? WHERE id=?",
                 (json.dumps(session["pending"]), session_id))
    skill = {"translate_choice": "vocabulary", "listen_choice": "listening", "read_true_false": "reading",
             "write": "writing", "speak": "speaking", "grammar_choice": "grammar"}.get(
                 session["challenges"][challenge_index].kind, "vocabulary")
    conn.execute(
        "INSERT INTO lk_learning_mastery (learner_key,unit_id,skill,level,attempts,correct) VALUES (?,?,?,?,?,?)"
        " ON CONFLICT(learner_key,unit_id,skill) DO UPDATE SET level=MIN(5,level+excluded.correct),"
        " attempts=attempts+excluded.attempts, correct=correct+excluded.correct, updated_at=datetime('now')",
        (learner_key, session["row"]["unit_id"], skill, int(verdict.correct), 1, int(verdict.correct)),
    )
    return {"correct": verdict.correct, "attempt_no": attempt_no,
            "remaining": len(session["pending"]), "solution": None if verdict.correct else "Попробуй ещё раз"}


def finish(learner_key: str, session_id: str) -> dict:
    session = _load(learner_key, session_id)
    if session["pending"]:
        raise core.Conflict("learning_session_not_complete")
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) AS total, COALESCE(SUM(correct),0) AS correct FROM lk_learning_attempts WHERE session_id=?", (session_id,)).fetchone()
    total, correct = int(row["total"]), int(row["correct"])
    result = {"session_id": session_id, "unit_id": session["row"]["unit_id"],
              "accuracy": round(correct / total, 3) if total else 1.0,
              "attempts": total, "correct": correct, "points": correct * 5}
    result["rank"] = progression.add_points(learner_key, f"learning:{session_id}", session["row"]["unit_id"], correct * 5)
    conn.execute("UPDATE lk_learning_sessions SET status='completed',finished_at=?,result=? WHERE id=?",
                 (_now(), json.dumps(result), session_id))
    return result
