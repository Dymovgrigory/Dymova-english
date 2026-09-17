"""Fox Brain v0: next_best_action is server-authoritative."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.world import brain, core, srs
from app.world.db import get_conn, reset_for_tests

HEADERS = {"X-World-Player": "child-brain"}


@pytest.fixture()
def client(tmp_path):
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    app = FastAPI()
    from app.world import api as world_api
    app.include_router(world_api.router)
    with TestClient(app) as c:
        c.post("/api/world/players", json={"display_name": "Мира"}, headers=HEADERS)
        yield c
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def test_new_player_nba_is_first_lesson(client):
    home = client.get("/api/world/learn/home", headers=HEADERS).json()
    nba = home["next_best_action"]
    assert nba["kind"] == "lesson"
    assert nba["href"] == "/learn/family-L1"
    assert nba["title"] == "Первый урок"
    assert nba["why"]
    assert nba["analytic_id"] == "world.school.startLesson"
    model = brain.learner_model("child-brain")
    assert model["lessons_starred"] == 0
    assert model["due_count"] == 0


def test_due_words_outrank_new_lesson(client):
    pid = core.get_player("child-brain")["id"]
    srs.touch(pid, "family", "hello", correct=True)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    get_conn().execute(
        "UPDATE word_stats SET due_at=? WHERE player_id=? AND word_en=?",
        (yesterday, pid, "hello"),
    )
    nba = brain.next_best_action("child-brain")
    assert nba["kind"] == "review"
    assert nba["href"] == "/learn/practice"
    assert nba["due"] == 1
    assert "слово" in nba["hint"]
    home = client.get("/api/world/learn/home", headers=HEADERS).json()
    assert home["next_best_action"]["kind"] == "review"


def test_claimable_daily_outranks_review(client):
    pid = core.get_player("child-brain")["id"]
    srs.touch(pid, "family", "hello", correct=True)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    get_conn().execute(
        "UPDATE word_stats SET due_at=? WHERE player_id=? AND word_en=?",
        (yesterday, pid, "hello"),
    )
    core.award(
        "child-brain", xp=80, coins=0, source="t", type_="TEST",
        idempotency_key="brain-daily-xp",
    )
    nba = brain.next_best_action("child-brain")
    assert nba["kind"] == "quest"
    assert nba["href"] == "/world?pulse=quests"
    assert nba["analytic_id"] == "quest.daily.claim"
    home = client.get("/api/world/learn/home", headers=HEADERS).json()
    assert home["next_best_action"]["kind"] == "quest"


def test_weak_words_shape_nba_review_copy(client):
    pid = core.get_player("child-brain")["id"]
    srs.touch(pid, "family", "hello", correct=False)
    srs.touch(pid, "family", "hello", correct=False)
    srs.touch(pid, "family", "thanks", correct=True)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    get_conn().execute(
        "UPDATE word_stats SET due_at=?, strength=0, wrong_count=3, correct_count=0"
        " WHERE player_id=? AND word_en=?",
        (yesterday, pid, "hello"),
    )
    get_conn().execute(
        "UPDATE word_stats SET due_at=? WHERE player_id=? AND word_en=?",
        (yesterday, pid, "thanks"),
    )
    nba = brain.next_best_action("child-brain")
    assert nba["kind"] == "review"
    assert "hello" in nba["hint"].lower() or "hello" in nba["why"].lower()
    assert nba.get("weak_words")
    assert nba["weak_words"][0]["word_en"] == "hello"
    home = client.get("/api/world/learn/home", headers=HEADERS).json()
    assert home["lessons_starred"] == 0
    assert home["next_best_action"]["weak_words"][0]["word_en"] == "hello"


def test_home_exposes_lessons_starred_after_finish(client):
    pid = core.get_player("child-brain")["id"]
    get_conn().execute(
        "INSERT OR REPLACE INTO lesson_progress (player_id, lesson_id, stars, best_score)"
        " VALUES (?,?,?,?)",
        (pid, "family-L1", 2, 5),
    )
    home = client.get("/api/world/learn/home", headers=HEADERS).json()
    assert home["lessons_starred"] >= 1
