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
