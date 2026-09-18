"""HTTP-контракт замка."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.world import core


@pytest.fixture()
def client(learn_db, learn_course):
    from main import app

    core.get_or_create_player("kid-v2", "Маша")
    with TestClient(app) as test_client:
        yield test_client


HEAD = {"X-World-Player": "kid-v2"}


def test_get_castle_returns_appearance_and_catalog(client):
    body = client.get("/api/v2/castle", headers=HEAD).json()
    assert body["appearance"]["banner_color"] == "plum"
    assert len(body["titles"]) == 5
    assert any(item["id"] == "time-night" for item in body["catalog"])


def test_buy_without_coins_returns_409(client):
    res = client.post("/api/v2/castle/buy", json={"item_id": "time-night"}, headers=HEAD)
    assert res.status_code == 409


def test_buy_then_apply(client):
    core.award("kid-v2", coins=200, source="test", type_="TEST_GRANT", idempotency_key="grant:api")
    assert client.post("/api/v2/castle/buy", json={"item_id": "time-night"}, headers=HEAD).status_code == 200
    body = client.post("/api/v2/castle/appearance", json={"time_of_day": "night"}, headers=HEAD).json()
    assert body["appearance"]["time_of_day"] == "night"


def test_wear_title_without_level_returns_409(client):
    res = client.post("/api/v2/castle/title", json={"track": "glory"}, headers=HEAD)
    assert res.status_code == 409


def test_unknown_item_returns_404(client):
    res = client.post("/api/v2/castle/buy", json={"item_id": "time-полночь"}, headers=HEAD)
    assert res.status_code == 404

def test_lexicon_chest_endpoints(client, monkeypatch):
    from app.castle import counters
    from app.world.db import get_conn

    fake = {f"sp1.m1.w{n}" for n in range(30)}
    real = counters.course_word_ids()
    monkeypatch.setattr(counters, "course_word_ids", lambda: real | fake)
    player_id = int(core.get_player("kid-v2")["id"])
    for atom_id in sorted(fake)[:26]:
        get_conn().execute(
            "INSERT INTO atom_mastery (player_id, atom_id, strength, correct_count, wrong_count,"
            " due_at, updated_at, learned_at) VALUES (?,?,3,3,0,'2026-09-18','2026-09-18T10:00:00','2026-09-18')",
            (player_id, atom_id),
        )

    status = client.get("/api/v2/castle/lexicon-chest", headers=HEAD).json()
    assert status["ready"] == 1
    assert status["progress"] == 1

    opened = client.post("/api/v2/castle/lexicon-chest/open", headers=HEAD).json()
    assert opened["coins"] == 30
    again = client.post("/api/v2/castle/lexicon-chest/open", headers=HEAD).json()
    assert again == opened


def test_quests_endpoints(client):
    client.put("/api/v2/profile", json={"book_id": "sp1", "module_id": "sp1.m1", "daily_goal_xp": 20}, headers=HEAD)
    body = client.get("/api/v2/quests", headers=HEAD).json()
    assert len(body["daily"]) == 3 and len(body["weekly"]) == 3
    res = client.post("/api/v2/quests/claim", json={"quest_id": "lesson-1", "period": "day"}, headers=HEAD)
    assert res.status_code == 409  # не выполнено — не забрать
