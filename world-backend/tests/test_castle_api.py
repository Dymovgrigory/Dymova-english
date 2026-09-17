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
