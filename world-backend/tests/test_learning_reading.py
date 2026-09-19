"""Чтение (этап 5): схема текстов, лексическое правило, фабрики, сессия end-to-end."""
from __future__ import annotations

import random

import pytest

from app.learning import builder, challenges, checker, content, progress, sessions
from app.learning.errors import BadAnswer, NotFound
from tests.lesson_helpers import right_answer, stored, wrong_answer
from tests.test_learning_content import _copy_fixture, _edit, _errors
from tests.test_learning_sessions import play


def _text() -> content.Text:
    return content.Text.model_validate(
        {
            "id": "sp1.m1.t1",
            "title_en": "Foxy's Family",
            "title_ru": "Семья Фокси",
            "body_en": "Hello! I am Mum. This is Dad. It is a cat.",
            "questions": [
                {"id": "sp1.m1.t1.q1", "kind": "choice", "q_en": "Who is Mum?", "q_ru": "Кто мама?",
                 "options": ["Mum", "Dad", "Foxy"], "answer": "Mum"},
                {"id": "sp1.m1.t1.q2", "kind": "truefalse", "q_en": "It is a dog.", "q_ru": "Это собака.",
                 "answer": "false"},
                {"id": "sp1.m1.t1.q3", "kind": "truefalse", "q_en": "This is Dad.", "q_ru": "Это папа.",
                 "answer": "true"},
                {"id": "sp1.m1.t1.q4", "kind": "gap", "q_en": "It is a ___.", "q_ru": "Это ___.",
                 "options": ["cat", "dog", "sun"], "answer": "cat"},
            ],
        }
    )


# --- схема и индекс курса -------------------------------------------------------------------

def test_course_indexes_texts(learn_course):
    module, text = learn_course.text("sp1.m1.t1")
    assert module.id == "sp1.m1" and len(text.questions) == 5
    module_, node = learn_course.node("sp1.m1.n7")
    assert node.kind == "reading" and node.text_id == "sp1.m1.t1"
    with pytest.raises(NotFound):
        learn_course.text("sp1.m1.t9")


def test_text_schema_requires_four_questions():
    data = _text().model_dump()
    data["questions"] = data["questions"][:3]
    with pytest.raises(ValueError):
        content.Text.model_validate(data)


# --- валидация контента ---------------------------------------------------------------------

def test_validate_catches_duplicate_text_id(tmp_path):
    root = _copy_fixture(tmp_path)

    def dup(d):
        d["texts"].append(dict(d["texts"][0]))

    _edit(root / "sp1" / "m1.json", dup)
    assert "duplicate id sp1.m1.t1" in _errors(root)


def test_validate_catches_unknown_text_in_node(tmp_path):
    root = _copy_fixture(tmp_path)

    def break_node(d):
        next(n for n in d["nodes"] if n["kind"] == "reading")["text_id"] = "sp1.m1.t9"

    _edit(root / "sp1" / "m1.json", break_node)
    assert "unknown text sp1.m1.t9" in _errors(root)


def test_validate_catches_untaught_word_in_text(tmp_path):
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m1.json", lambda d: d["texts"][0].update(body_en="It is a granny."))
    assert "sp1.m1.t1: word 'granny' not taught yet" in _errors(root)


def test_validate_catches_word_from_another_book(tmp_path):
    """'school' изучается в sp3, но не в sp1: слова чужой книги не считаются пройденными."""
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m1.json", lambda d: d["texts"][0].update(body_en="It is a school."))
    assert "word 'school' not taught yet" in _errors(root)


def test_validate_catches_untaught_word_in_question(tmp_path):
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m1.json", lambda d: d["texts"][0]["questions"][0].update(q_en="Is Granny mum?"))
    assert "sp1.m1.t1.q1: word 'granny' not taught yet" in _errors(root)


def test_validate_allows_numerals_and_foxy(tmp_path):
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m1.json", lambda d: d["texts"][0].update(body_en="Foxy has two cats."))
    assert content.load_course(root)


def test_validate_requires_choice_and_truefalse(tmp_path):
    root = _copy_fixture(tmp_path)

    def no_truefalse(d):
        for q in d["texts"][0]["questions"]:
            if q["kind"] == "truefalse":
                q.update(kind="choice", options=["Yes", "No", "Maybe"], answer="Yes")

    _edit(root / "sp1" / "m1.json", no_truefalse)
    assert "needs at least one choice and one truefalse question" in _errors(root)


def test_validate_checks_choice_answer_and_options(tmp_path):
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m1.json", lambda d: d["texts"][0]["questions"][0].update(answer="Granny"))
    assert "sp1.m1.t1.q1: answer not in options" in _errors(root)

    root = _copy_fixture(tmp_path / "b")
    _edit(root / "sp1" / "m1.json", lambda d: d["texts"][0]["questions"][0].update(options=["Mum", "Dad"]))
    assert "sp1.m1.t1.q1: needs exactly 3 options" in _errors(root)


def test_validate_checks_truefalse_answer(tmp_path):
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m1.json", lambda d: d["texts"][0]["questions"][1].update(answer="maybe"))
    assert "sp1.m1.t1.q2: truefalse answer must be 'true' or 'false'" in _errors(root)


def test_validate_checks_gap(tmp_path):
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m1.json", lambda d: d["texts"][0]["questions"][3].update(q_en="It is a cat."))
    assert "sp1.m1.t1.q4: gap question needs ___" in _errors(root)

    root = _copy_fixture(tmp_path / "b")
    _edit(root / "sp1" / "m1.json",
          lambda d: d["texts"][0]["questions"][3].update(options=["cat", "dog", "zebra"], answer="zebra"))
    assert "sp1.m1.t1.q4: gap answer must be a word of the module" in _errors(root)


# --- фабрики заданий ------------------------------------------------------------------------

def test_read_text_factory_is_ungraded_first_step():
    challenge = challenges.read_text(_text())
    assert challenge.type == "read_text" and challenge.graded is False
    assert challenge.atom_id == "sp1.m1.t1"
    assert challenge.solution == {"kind": "none"}
    prompt = challenge.prompt
    assert prompt["text_id"] == "sp1.m1.t1"
    assert prompt["title_en"] == "Foxy's Family" and prompt["title_ru"] == "Семья Фокси"
    assert prompt["sentences"] == ["Hello!", "I am Mum.", "This is Dad.", "It is a cat."]


def test_read_text_truefalse_factory():
    text = _text()
    challenge = challenges.read_text_truefalse(text, text.questions[1])
    assert challenge.type == "read_text_truefalse" and challenge.graded is True
    assert challenge.prompt == {"text_id": "sp1.m1.t1", "sentence_en": "It is a dog.", "q_ru": "Это собака."}
    assert challenge.solution == {"kind": "bool", "answer": False}


def test_read_text_answer_factory():
    text = _text()
    challenge = challenges.read_text_answer(text, text.questions[0], random.Random(1))
    assert challenge.type == "read_text_answer"
    assert challenge.prompt["q_en"] == "Who is Mum?" and challenge.prompt["q_ru"] == "Кто мама?"
    assert sorted(challenge.prompt["options"]) == ["Dad", "Foxy", "Mum"]
    solution = challenge.solution
    assert solution["kind"] == "choice" and challenge.prompt["options"][solution["index"]] == "Mum"


def test_word_in_context_factory():
    text = _text()
    challenge = challenges.word_in_context(text, text.questions[3], random.Random(1))
    assert challenge.type == "word_in_context"
    assert challenge.prompt["sentence_en"] == "It is a ___."
    assert len(challenge.prompt["options"]) == 3
    assert challenge.prompt["options"][challenge.solution["index"]] == "cat"


# --- проверка ответов ------------------------------------------------------------------------

def test_check_bool():
    assert checker.check_bool(True, True).correct
    assert not checker.check_bool(True, False).correct


def test_grade_bool_answer():
    text = _text()
    challenge = challenges.read_text_truefalse(text, text.questions[1])
    assert challenges.grade(challenge, {"answer": False}).correct
    assert not challenges.grade(challenge, {"answer": True}).correct
    with pytest.raises(BadAnswer):
        challenges.grade(challenge, {"answer": "false"})  # строка вместо bool — брак


def test_grade_index_answer():
    text = _text()
    challenge = challenges.word_in_context(text, text.questions[3], random.Random(2))
    assert challenges.grade(challenge, {"index": challenge.solution["index"]}).correct
    assert not challenges.grade(challenge, {"index": (challenge.solution["index"] + 1) % 3}).correct


# --- сборка сессии ---------------------------------------------------------------------------

def test_reading_session_layout(learn_course):
    for seed in range(10):
        plan = builder.build_session(learn_course, "sp1.m1.n7", player_id=None, seed=seed, allow_speak=True)
        assert plan.kind == "reading"
        first = plan.challenges[0]
        assert first.type == "read_text" and first.graded is False
        graded = [c for c in plan.challenges if c.graded]
        assert len(graded) == 5
        types = sorted(c.type for c in graded)
        assert types == ["read_text_answer", "read_text_answer", "read_text_truefalse",
                         "read_text_truefalse", "word_in_context"]
        assert all(c.atom_id == "sp1.m1.t1" for c in plan.challenges)


# --- сессия end-to-end -----------------------------------------------------------------------

def _unlock_reading(player_id: int) -> None:
    from app.learning import clock

    for node_id in ("sp1.m1.n1", "sp1.m1.n2", "sp1.m1.n3"):
        progress.complete_node(player_id, node_id, stars=0, accuracy=1.0, now=clock.now())


def test_reading_session_end_to_end(learner):
    key, pid = learner
    _unlock_reading(pid)
    started = sessions.start(key, "sp1.m1.n7", allow_speak=False, seed=11)
    assert started["kind"] == "reading" and started["graded_total"] == 5
    assert started["challenges"][0]["type"] == "read_text"
    assert all("solution" not in c for c in started["challenges"])

    replies = play(key, started)
    assert all(r["correct"] for r in replies)
    result = sessions.finish(key, started["session_id"])
    assert result["passed"] is True and result["accuracy"] == 1.0
    assert result["xp"] == 15  # урок + бонус за отсутствие ошибок
    assert result["node_completed"] is True and result["next_node_id"] == "sp1.m1.n4"


def test_reading_session_bool_mistake_requeues(learner):
    key, pid = learner
    _unlock_reading(pid)
    started = sessions.start(key, "sp1.m1.n7", allow_speak=False, seed=12)
    payload = stored(started["session_id"])
    bool_index = next(i for i, c in enumerate(payload) if c["solution"]["kind"] == "bool")
    bad = sessions.answer(key, started["session_id"], bool_index, wrong_answer(payload[bool_index]))
    assert bad["correct"] is False and bad["requeued"] is True
    play(key, started)
    result = sessions.finish(key, started["session_id"])
    assert result["passed"] is True and result["mistakes"] >= 1


# --- узел на тропе (HTTP) --------------------------------------------------------------------

def test_reading_node_in_path_api(learn_db, learn_course):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.learning import api as learning_api
    from app.world import api as world_api

    app = FastAPI()
    app.include_router(world_api.router)
    app.include_router(learning_api.router)
    headers = {"X-World-Player": "kid-reading"}
    with TestClient(app) as client:
        client.post("/api/world/players", json={"display_name": "Маша"}, headers=headers)
        client.put("/api/v2/profile", json={"book_id": "sp1", "module_id": "sp1.m1", "daily_goal_xp": 10},
                   headers=headers)
        path = client.get("/api/v2/path", params={"book_id": "sp1"}, headers=headers).json()
    nodes = path["modules"][0]["nodes"]
    reading = next(n for n in nodes if n["kind"] == "reading")
    assert reading["id"] == "sp1.m1.n7" and reading["status"] == "locked"
    assert [n["id"] for n in nodes] == ["sp1.m1.n1", "sp1.m1.n2", "sp1.m1.n3", "sp1.m1.n7",
                                        "sp1.m1.n4", "sp1.m1.n5", "sp1.m1.n6"]
