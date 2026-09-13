"""Активности World: серверные сессии челленджа, проверка ответов, награда."""
import json

import pytest

from app.world import activities, core
from app.world.db import get_conn, reset_for_tests


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    core.get_or_create_player("child-1", "Мария")
    yield
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def test_start_returns_questions_without_answers():
    session = activities.start("child-1", "vocabulary-challenge-1", seed=1)
    assert session["total"] == 5
    assert len(session["questions"]) == 5
    for i, q in enumerate(session["questions"]):
        assert q["index"] == i
        assert len(q["options"]) == 4
        assert "correct_index" not in q
        assert "example_ru" not in q


def test_start_keeps_answers_on_server():
    session = activities.start("child-1", "vocabulary-challenge-1", seed=1)
    row = get_conn().execute(
        "SELECT payload FROM activity_sessions WHERE id=?", (session["session_id"],)
    ).fetchone()
    payload = json.loads(row["payload"])
    assert all("correct_index" in q for q in payload["questions"])


def test_start_unknown_activity():
    with pytest.raises(core.NotFound):
        activities.start("child-1", "no-such-activity")
