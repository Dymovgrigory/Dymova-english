"""Отдельный процесс мира: health без CRM/бота."""
from fastapi.testclient import TestClient

from main import app


def test_health_ok():
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_world_player_requires_header():
    resp = TestClient(app).get("/api/world/player")
    assert resp.status_code == 401
