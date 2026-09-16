"""Сценарий /api/v2 по HTTP: профиль → путь → урок → награда → словарь."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.learning import api as learning_api
from app.world import api as world_api
from tests.test_learning_sessions import right_answer, stored, wrong_answer

HEADERS = {"X-World-Player": "kid-http"}


@pytest.fixture()
def client(learn_db, learn_course):
    app = FastAPI()
    app.include_router(world_api.router)
    app.include_router(learning_api.router)
    with TestClient(app) as c:
        assert c.post("/api/world/players", json={"display_name": "Маша"}, headers=HEADERS).status_code == 200
        yield c


def test_courses_are_public(client):
    body = client.get("/api/v2/courses").json()
    assert [b["id"] for b in body["books"]] == ["sp1", "sp3"]
    assert body["books"][0]["modules"][0] == {
        "id": "sp1.m1", "order": 1, "title_en": "My Family!", "title_ru": "Моя семья",
    }


def test_full_learning_flow(client):
    assert client.get("/api/v2/home", headers=HEADERS).status_code == 409
    assert client.get("/api/v2/home", headers=HEADERS).json()["detail"] == "profile_required"
    bad = client.put("/api/v2/profile", json={"book_id": "sp1", "module_id": "sp1.m1", "daily_goal_xp": 7}, headers=HEADERS)
    assert bad.status_code == 409
    saved = client.put("/api/v2/profile", json={"book_id": "sp1", "module_id": "sp1.m1", "daily_goal_xp": 10}, headers=HEADERS)
    assert saved.status_code == 200
    assert client.get("/api/v2/profile", headers=HEADERS).json()["module_id"] == "sp1.m1"

    path = client.get("/api/v2/path", params={"book_id": "sp1"}, headers=HEADERS).json()
    first_module = path["modules"][0]
    assert first_module["title_en"] == "My Family!"
    assert first_module["nodes"][0] == {"id": "sp1.m1.n1", "kind": "words", "status": "current", "stars": 0}
    assert first_module["nodes"][1]["status"] == "locked"

    assert client.post("/api/v2/sessions", json={"node_id": "sp1.m1.n2"}, headers=HEADERS).status_code == 409
    assert client.post("/api/v2/nodes/sp1.m1.n4/chest", headers=HEADERS).status_code == 409
    assert client.post("/api/v2/practice", json={}, headers=HEADERS).status_code == 409

    started = client.post("/api/v2/sessions", json={"node_id": "sp1.m1.n1", "allow_speak": False}, headers=HEADERS).json()
    payload = stored(started["session_id"])
    url = f"/api/v2/sessions/{started['session_id']}"
    queue = list(range(len(payload)))
    made_mistake = False
    while queue:
        index = queue.pop(0)
        challenge = payload[index]
        if challenge["graded"] and not made_mistake:
            made_mistake = True
            reply = client.post(f"{url}/answer", json={"index": index, "answer": wrong_answer(challenge), "response_ms": 900}, headers=HEADERS).json()
            assert reply["correct"] is False and reply["requeued"] is True
            queue.append(index)
            continue
        reply = client.post(f"{url}/answer", json={"index": index, "answer": right_answer(challenge)}, headers=HEADERS)
        assert reply.status_code == 200 and reply.json()["correct"] is True

    malformed = client.post(f"{url}/answer", json={"index": 0, "answer": {}}, headers=HEADERS)
    assert malformed.status_code == 409  # уже решено
    result = client.post(f"{url}/finish", headers=HEADERS).json()
    assert result["xp"] == 10 and result["goal_reached"] is True
    assert result["next_node_id"] == "sp1.m1.n2"

    home = client.get("/api/v2/home", headers=HEADERS).json()
    assert home["streak_days"] == 1 and home["today_xp"] == 10 and home["daily_goal_xp"] == 10
    assert home["current_node"]["id"] == "sp1.m1.n2"
    assert home["current_node"]["module_title_en"] == "My Family!"
    assert home["player"]["display_name"] == "Маша"

    words = client.get("/api/v2/words", params={"book_id": "sp1"}, headers=HEADERS).json()
    cat = next(w for m in words["modules"] for w in m["words"] if w["en"] == "cat")
    assert cat["strength"] >= 0 and cat["image"] == "words/cat.webp"


def test_bad_answer_payload_is_422(client):
    client.put("/api/v2/profile", json={"book_id": "sp1", "module_id": "sp1.m1", "daily_goal_xp": 20}, headers=HEADERS)
    started = client.post("/api/v2/sessions", json={"node_id": "sp1.m1.n1", "allow_speak": False}, headers=HEADERS).json()
    payload = stored(started["session_id"])
    index = next(i for i, c in enumerate(payload) if c["graded"])
    reply = client.post(f"/api/v2/sessions/{started['session_id']}/answer", json={"index": index, "answer": {}}, headers=HEADERS)
    assert reply.status_code == 422


def test_requires_player_header(client):
    assert client.get("/api/v2/home").status_code == 401
