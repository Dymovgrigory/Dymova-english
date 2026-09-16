"""Мир — отдельная платформа: школьный бот не отдаёт /api/world и не содержит пакет app.world."""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


def test_bot_has_no_world_package():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.world")


def test_bot_does_not_serve_world_routes():
    from app.main import app

    resp = TestClient(app).get(
        "/api/world/player", headers={"X-World-Player": "anyone"}
    )
    assert resp.status_code == 404
