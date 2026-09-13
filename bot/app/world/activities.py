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
