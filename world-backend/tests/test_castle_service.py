"""Покупка облика: проверка звания, монет и повторного нажатия."""
from __future__ import annotations

import pytest

from app.castle import counters, service
from app.world import core
from app.world.core import Conflict
from app.world.db import get_conn


def _give_coins(key: str, coins: int) -> None:
    core.award(key, coins=coins, source="test", type_="TEST_GRANT", idempotency_key=f"grant:{key}:{coins}")


FAKE_WORDS = {f"sp1.m1.w{n}" for n in range(60)}  # фикстурного курса мало для порога 50


@pytest.fixture(autouse=True)
def _wide_course(monkeypatch: pytest.MonkeyPatch):
    real = counters.course_word_ids()
    monkeypatch.setattr(counters, "course_word_ids", lambda: real | FAKE_WORDS)


def _learn_words(player_id: int, count: int) -> None:
    """Отмечает `count` слов выученными (сила 3, как после пары верных ответов)."""
    for atom_id in sorted(FAKE_WORDS)[:count]:
        get_conn().execute(
            "INSERT INTO atom_mastery (player_id, atom_id, strength, correct_count, wrong_count,"
            " due_at, updated_at, learned_at) VALUES (?,?,3,3,0,'2026-09-18','2026-09-18T10:00:00','2026-09-18')",
            (player_id, atom_id),
        )


def test_view_lists_catalog_titles_and_appearance(learner):
    key, _ = learner
    view = service.view(key)
    assert view["appearance"]["banner_color"] == "plum"
    assert any(item["id"] == "time-night" for item in view["catalog"])
    assert len(view["titles"]) == 5
    assert view["owned"] == []


def test_buy_spends_coins_and_unlocks_item(learner):
    key, _ = learner
    _give_coins(key, 100)
    result = service.buy(key, "time-night")
    assert result["owned"] == ["time-night"]
    assert core.get_player(key)["coins"] == 20


def test_buy_twice_does_not_charge_twice(learner):
    key, _ = learner
    _give_coins(key, 100)
    service.buy(key, "time-night")
    service.buy(key, "time-night")
    assert core.get_player(key)["coins"] == 20


def test_buy_without_coins_is_rejected(learner):
    key, _ = learner
    with pytest.raises(Conflict):
        service.buy(key, "time-night")


def test_buy_locked_by_title_is_rejected(learner):
    key, player_id = learner
    _give_coins(key, 500)
    with pytest.raises(Conflict):
        service.buy(key, "season-winter")     # нужен Словесник 2 уровня
    _learn_words(player_id, 50)
    from app.castle import titles
    titles.sync(key)
    assert service.buy(key, "season-winter")["owned"] == ["season-winter"]


def test_item_that_is_not_purchasable_is_rejected(learner):
    key, _ = learner
    _give_coins(key, 500)
    with pytest.raises(Conflict):
        service.buy(key, "weather-aurora")


def test_apply_requires_owning_the_item(learner):
    key, _ = learner
    _give_coins(key, 100)
    with pytest.raises(Conflict):
        service.apply(key, time_of_day="night")
    service.buy(key, "time-night")
    assert service.apply(key, time_of_day="night")["appearance"]["time_of_day"] == "night"


def test_free_variants_apply_without_purchase(learner):
    key, _ = learner
    assert service.apply(key, time_of_day=None, season=None)["appearance"]["season"] is None
