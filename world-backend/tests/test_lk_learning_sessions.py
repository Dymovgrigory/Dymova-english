import pytest

from app.lk.learning import sessions
from app.world import core
from app.world.db import get_conn, reset_for_tests


@pytest.fixture()
def learning_db(tmp_path):
    reset_for_tests(str(tmp_path / "learning.sqlite"))
    yield
    reset_for_tests(str(tmp_path / "learning-after.sqlite"))


def test_session_is_server_owned_and_finishes_after_correct_answers(learning_db):
    started = sessions.start("crm:1", "pre-a1.family")

    assert started["challenges"][0]["id"] == "family-vocab-1"
    assert "answer_index" not in started["challenges"][0]
    for challenge in started["challenges"]:
        payload = {"index": 0} if challenge["kind"] in {"translate_choice", "listen_choice", "grammar_choice", "read_choice"} else (
            {"value": True} if challenge["kind"] == "read_true_false" else ({"transcript": "I have a brother"} if challenge["kind"] == "speak" else {"text": "mum"})
        )
        sessions.answer("crm:1", started["session_id"], challenge["id"], payload)

    result = sessions.finish("crm:1", started["session_id"])

    assert result["accuracy"] == 1.0
    assert result["points"] == 25


def test_wrong_answer_is_retried_without_closing_challenge(learning_db):
    started = sessions.start("crm:1", "pre-a1.family")
    challenge = started["challenges"][0]

    failed = sessions.answer("crm:1", started["session_id"], challenge["id"], {"index": 2})

    assert failed["correct"] is False
    assert failed["remaining"] == 5
    with pytest.raises(core.Conflict, match="learning_session_not_complete"):
        sessions.finish("crm:1", started["session_id"])


def test_finish_is_idempotent(learning_db):
    started = sessions.start("crm:1", "pre-a1.school")
    for challenge in started["challenges"]:
        payload = {"index": 0} if challenge["kind"] in {"translate_choice", "listen_choice", "grammar_choice", "read_choice"} else ({"value": True} if challenge["kind"] == "read_true_false" else {"text": "pen"})
        sessions.answer("crm:1", started["session_id"], challenge["id"], payload)
    first = sessions.finish("crm:1", started["session_id"])
    assert sessions.finish("crm:1", started["session_id"]) == first
