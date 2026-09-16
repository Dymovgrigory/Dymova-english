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


def test_cors_preflight_from_loopback_frontend():
    resp = TestClient(app).options(
        "/api/world/players",
        headers={
            "Origin": "http://127.0.0.1:3002",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-world-player",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:3002"
