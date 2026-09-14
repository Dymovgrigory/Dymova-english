"""Активности мира: серверные сессии обучающих мини-игр (§68).

Вопросы и правильные ответы хранятся на сервере; клиент получает только
формулировки и варианты, ответ проверяется здесь, награда идёт через
core.award — идемпотентно (§84, §160).
"""
from __future__ import annotations

import json
import uuid

from . import config, core, vocabulary
from .db import get_conn


def _activity(activity_id: str) -> dict:
    spec = config.ACTIVITIES.get(activity_id)
    if spec is None:
        raise core.NotFound(f"activity {activity_id!r} not found")
    return spec


def start(external_key: str, activity_id: str, seed: int | None = None) -> dict:
    """Создаёт сессию и отдаёт вопросы без правильных ответов."""
    player = core.get_player(external_key)
    spec = _activity(activity_id)
    questions = vocabulary.build_questions(spec["theme"], spec["questions"], seed)
    session_id = str(uuid.uuid4())
    get_conn().execute(
        "INSERT INTO activity_sessions (id, player_id, activity_id, payload)"
        " VALUES (?,?,?,?)",
        (session_id, player["id"], activity_id,
         json.dumps({"questions": questions}, ensure_ascii=False)),
    )
    return {
        "session_id": session_id,
        "activity_id": activity_id,
        "title_ru": spec["title_ru"],
        "total": len(questions),
        "questions": [
            {
                "index": i,
                "en": q["en"],
                "ipa": q["ipa"],
                "example_en": q["example_en"],
                "options": q["options"],
            }
            for i, q in enumerate(questions)
        ],
    }


def _load_session(external_key: str, session_id: str) -> tuple[dict, dict, dict]:
    """Возвращает (игрок, строка сессии как dict, payload). Чужая сессия — NotFound."""
    player = core.get_player(external_key)
    row = get_conn().execute(
        "SELECT * FROM activity_sessions WHERE id=? AND player_id=?",
        (session_id, player["id"]),
    ).fetchone()
    if row is None:
        raise core.NotFound(f"activity session {session_id!r} not found")
    return player, dict(row), json.loads(row["payload"])


def answer(external_key: str, session_id: str, index: int, choice: int) -> dict:
    """Сверяет ответ с серверной копией и запоминает его в сессии."""
    _player, session, payload = _load_session(external_key, session_id)
    if session["status"] == "completed":
        raise core.Conflict("activity already completed")
    questions = payload["questions"]
    if not 0 <= index < len(questions):
        raise core.NotFound(f"question {index} not found")

    answers = json.loads(session["answers"])
    if str(index) in answers:
        raise core.Conflict(f"question {index} already answered")

    question = questions[index]
    correct = int(choice) == question["correct_index"]
    answers[str(index)] = {"choice": int(choice), "correct": correct}
    get_conn().execute(
        "UPDATE activity_sessions SET answers=? WHERE id=?",
        (json.dumps(answers, ensure_ascii=False), session_id),
    )
    return {
        "index": index,
        "correct": correct,
        "correct_index": question["correct_index"],
        "example_en": question["example_en"],
        "example_ru": question["example_ru"],
        "answered": len(answers),
        "total": len(questions),
    }


def finish(external_key: str, session_id: str,
           idempotency_key: str | None = None) -> dict:
    """Закрывает сессию, начисляет награду и двигает шаг квеста.

    Награда считается сервером по config; повторный вызов ничего не
    начисляет второй раз и возвращает те же цифры (§160).
    """
    _player, session, payload = _load_session(external_key, session_id)
    questions = payload["questions"]
    answers = json.loads(session["answers"])
    if len(answers) < len(questions):
        raise core.Conflict("activity not finished: not all questions answered")

    score = sum(1 for a in answers.values() if a["correct"])
    perfect = score == len(questions)
    spec = _activity(session["activity_id"])
    xp = config.XP_REWARDS["vocabulary_challenge"]
    coins = config.COIN_REWARDS["vocabulary_challenge"]
    if perfect:
        xp += config.PERFECT_BONUS["xp"]
        coins += config.PERFECT_BONUS["coins"]

    result = core.award(
        external_key,
        xp=xp, coins=coins,
        source=session["activity_id"],
        type_="ACTIVITY_REWARD",
        idempotency_key=idempotency_key or f"activity-finish:{session_id}",
    )
    # Суммы фиксируются в сессии при первом завершении: повтор возвращает
    # их же, хотя core.award второй раз ничего не начисляет (§160).
    if session["status"] != "completed":
        payload["reward"] = {"xp": xp, "coins": coins}
        get_conn().execute(
            "UPDATE activity_sessions SET status='completed', score=?, payload=?,"
            " completed_at=datetime('now') WHERE id=?",
            (score, json.dumps(payload, ensure_ascii=False), session_id),
        )
    reward = payload.get("reward", {"xp": xp, "coins": coins})

    quest_result = None
    quest_id = spec.get("quest_id")
    if quest_id:
        try:
            quest_result = core.advance_quest_step(
                external_key, quest_id, "activity", session["activity_id"]
            )
        except core.Conflict:
            quest_result = None  # шаг уже пройден или квест на другом шаге

    return {
        "session_id": session_id,
        "activity_id": session["activity_id"],
        "score": score,
        "total": len(questions),
        "perfect": perfect,
        "xp_delta": reward["xp"],
        "coins_delta": reward["coins"],
        "level_up": result["level_up"],
        "new_level": result["new_level"],
        "new_title": result["new_title"],
        "player": result["player"],
        "quest": quest_result,
    }
