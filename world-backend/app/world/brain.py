"""Fox Brain v0/v1 — learner model + next best action.

Клиент не выбирает «просто Продолжить». Сервер объясняет WHY.
v1: weak_words влияют на copy review-миссии.
"""
from __future__ import annotations

from . import core, srs
from .db import get_conn


def _plural_words(n: int) -> str:
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return "слово"
    if 2 <= n10 <= 4 and (n100 < 10 or n100 >= 20):
        return "слова"
    return "слов"


def _lessons_starred(player_id: int) -> int:
    return int(
        get_conn()
        .execute(
            "SELECT COUNT(*) AS n FROM lesson_progress WHERE player_id=? AND stars>0",
            (player_id,),
        )
        .fetchone()["n"]
    )


def learner_model(external_key: str) -> dict:
    from . import learn

    player = core.get_player(external_key)
    pid = player["id"]
    due = srs.review_count(pid)
    quests = learn.daily_quests(external_key)
    weak = get_conn().execute(
        "SELECT word_en, unit_id, strength, wrong_count FROM word_stats"
        " WHERE player_id=? AND (strength<=1 OR wrong_count>correct_count)"
        " ORDER BY wrong_count DESC, strength ASC LIMIT 8",
        (pid,),
    ).fetchall()
    return {
        "due_count": due,
        "lessons_starred": _lessons_starred(pid),
        "claimable_quests": sum(1 for q in quests if q.get("claimable")),
        "current_lesson_id": learn.current_lesson_id(external_key),
        "weak_words": [dict(r) for r in weak],
    }


def _weak_focus(weak_words: list[dict]) -> list[dict]:
    out = []
    for w in weak_words[:3]:
        out.append({
            "word_en": w["word_en"],
            "unit_id": w.get("unit_id"),
            "strength": int(w.get("strength") or 0),
            "wrong_count": int(w.get("wrong_count") or 0),
        })
    return out


def next_best_action(external_key: str) -> dict:
    """Приоритет как у клиентского missionFor: claim → review → lesson."""
    from . import learn

    model = learner_model(external_key)
    lesson_id = model["current_lesson_id"] or "family-L1"
    due = int(model["due_count"])
    weak = _weak_focus(model.get("weak_words") or [])

    if model["claimable_quests"] > 0:
        return {
            "kind": "quest",
            "href": "/world?pulse=quests",
            "title": "Награда дня готова",
            "hint": "Забери поручение в беседке — XP уже ждёт",
            "why": "Поручение уже сделано — забери награду, пока день не кончился.",
            "analytic_id": "quest.daily.claim",
        }
    if due > 0:
        top = weak[0]["word_en"] if weak else None
        if top:
            hint = f"Слабое место: {top} — Foxy ждёт {due} {_plural_words(due)}"
            why = f"Чаще всего путается «{top}». Скажи его снова, пока слово не закрепится."
        else:
            hint = f"Foxy отложил {due} {_plural_words(due)} на сегодня"
            why = "Эти слова пора сказать снова, пока они не забылись."
        return {
            "kind": "review",
            "href": "/learn/practice",
            "title": "Повторить слова",
            "hint": hint,
            "why": why,
            "analytic_id": "world.yard.startPractice",
            "due": due,
            "weak_words": weak,
        }
    first = model["lessons_starred"] == 0 and lesson_id == "family-L1"
    return {
        "kind": "lesson",
        "href": f"/learn/{lesson_id}",
        "title": "Первый урок" if first else "Продолжить урок",
        "hint": "Скажи слова вслух — и получишь награду в замке",
        "why": "Foxy знает следующий шаг — урок в школе.",
        "analytic_id": "world.school.startLesson",
        "lesson_id": lesson_id,
    }
