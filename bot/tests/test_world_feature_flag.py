"""Feature-флаг WORLD_API_ENABLED: /api/world/* смонтирован только явным опт-ином.

У мира пока нет настоящей авторизации (личность — заголовок X-World-Player,
который клиент сам себе генерирует), а роутер смонтирован в прод-бота —
поэтому по умолчанию маршрутов /api/world/* быть не должно вовсе.

Остальные тесты мира (test_world.py, test_world_activities.py,
test_world_api.py) собирают свой собственный FastAPI() с роутером напрямую и
от этого флага не зависят.
"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.config import settings
from app.world.db import reset_for_tests

HEADERS = {"X-World-Player": "flag-test-player"}


@pytest.fixture()
def world_main(monkeypatch, tmp_path):
    """Перестраивает app.main с нужным значением WORLD_API_ENABLED.

    Монтирование роутера и настройка CORS в main.py — решение времени
    построения приложения, поэтому единственный способ проверить обе ветки —
    пересобрать модуль с другим значением флага. После теста модуль
    возвращается в исходное (выключенное) состояние, чтобы не влиять на
    остальной сьют — TestClient(main.app) в других тестах используется без
    контекстного менеджера, поэтому startup-событие (сиды и т.п.) здесь тоже
    не запускается.
    """
    original = settings.WORLD_API_ENABLED

    def _build(enabled: bool):
        reset_for_tests(str(tmp_path / f"world-flag-{enabled}.sqlite"))
        monkeypatch.setattr(settings, "WORLD_API_ENABLED", enabled)
        importlib.reload(main_module)
        return main_module.app

    yield _build

    monkeypatch.setattr(settings, "WORLD_API_ENABLED", original)
    importlib.reload(main_module)


def test_world_routes_absent_when_disabled(world_main):
    app = world_main(False)
    client = TestClient(app)

    resp = client.get("/api/world/player", headers=HEADERS)

    assert resp.status_code == 404


def test_world_routes_present_when_enabled(world_main):
    app = world_main(True)
    client = TestClient(app)

    created = client.post(
        "/api/world/players", json={"display_name": "Флаг"}, headers=HEADERS
    )
    assert created.status_code == 200

    resp = client.get("/api/world/player", headers=HEADERS)

    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Флаг"
