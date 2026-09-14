"""HTTP-контракт /api/world/* — маршруты цикла School Hub."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.world import api as world_api
from app.world import core
from app.world.db import reset_for_tests

HEADERS = {"X-World-Player": "child-api"}


@pytest.fixture()
def client(tmp_path):
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    app = FastAPI()
    app.include_router(world_api.router)
    with TestClient(app) as c:
        c.post("/api/world/players", json={"display_name": "Мария"}, headers=HEADERS)
        yield c
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def test_requires_player_header(client):
    assert client.get("/api/world/player").status_code == 401


def test_quest_step_route(client):
    client.post("/api/world/quests/first-day-at-foxinburg/start", headers=HEADERS)
    r = client.post("/api/world/quests/first-day-at-foxinburg/step",
                    json={"action": "visit", "target": "school-hub"}, headers=HEADERS)
    assert r.status_code == 200 and r.json()["step"] == 1
    bad = client.post("/api/world/quests/first-day-at-foxinburg/step",
                      json={"action": "visit", "target": "school-hub"}, headers=HEADERS)
    assert bad.status_code == 409


def test_activity_flow_over_http(client):
    client.post("/api/world/quests/first-day-at-foxinburg/start", headers=HEADERS)
    started = client.post("/api/world/activities/start",
                          json={"activity_id": "vocabulary-challenge-1"},
                          headers=HEADERS).json()
    sid = started["session_id"]
    assert len(started["questions"]) == 5
    assert all("correct_index" not in q for q in started["questions"])

    for i in range(5):
        r = client.post(f"/api/world/activities/{sid}/answer",
                        json={"index": i, "choice": 0}, headers=HEADERS)
        assert r.status_code == 200
        assert isinstance(r.json()["correct"], bool)

    fin = client.post(f"/api/world/activities/{sid}/finish",
                      json={"idempotency_key": "http-1"}, headers=HEADERS)
    assert fin.status_code == 200
    body = fin.json()
    assert body["total"] == 5 and body["player"]["xp"] > 0


def test_activity_unknown_session_is_404(client):
    r = client.post("/api/world/activities/nope/answer",
                    json={"index": 0, "choice": 0}, headers=HEADERS)
    assert r.status_code == 404
