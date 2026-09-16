"""Общие фикстуры движка обучения v2 (контент-фикстура + чистая БД)."""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_CONTENT = Path(__file__).resolve().parent / "fixtures" / "spotlight"


@pytest.fixture()
def learn_course(monkeypatch):
    from app.learning import content

    monkeypatch.setenv("LEARN_CONTENT_DIR", str(FIXTURE_CONTENT))
    content.reset_cache()
    yield content.get_course()
    content.reset_cache()


@pytest.fixture()
def learn_db(tmp_path):
    from app.world import core
    from app.world.db import reset_for_tests

    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    yield
    reset_for_tests(str(tmp_path / "world-after.sqlite"))


@pytest.fixture()
def learner(learn_db, learn_course):
    """Игрок с профилем на Spotlight 1, модуль 1. Возвращает (external_key, player_id)."""
    from app.learning import progress
    from app.world import core

    player = core.get_or_create_player("kid-v2", "Маша")
    progress.set_profile(player["id"], learn_course, book_id="sp1", module_id="sp1.m1", daily_goal_xp=20)
    return "kid-v2", player["id"]
