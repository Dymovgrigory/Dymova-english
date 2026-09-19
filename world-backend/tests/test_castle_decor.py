"""Декор замка: каталог с точками, покупка, постановка и снятие."""
from __future__ import annotations

import pytest

from app.castle import catalog, service
from app.world import core
from app.world.core import Conflict


def _give_coins(key: str, coins: int) -> None:
    core.award(key, coins=coins, source="test", type_="TEST_GRANT", idempotency_key=f"grant:{key}:{coins}")


def test_catalog_has_14_decor_items_with_anchors():
    decor = [item for item in catalog.ITEMS.values() if item.kind == "decor"]
    assert len(decor) == 14
    anchors = {"gate", "bridge", "courtyard", "roofs", "stream", "meadow", "walls"}
    assert all(item.anchor in anchors for item in decor)
    assert all(40 <= item.price <= 200 for item in decor)


def test_bought_decor_is_placed_at_its_anchor(learner):
    key, _ = learner
    _give_coins(key, 50)
    view = service.buy(key, "decor-gate-lantern")
    assert view["decor"] == [
        {"item_id": "decor-gate-lantern", "anchor": "gate", "title_ru": "Фонарь у ворот",
         "active": True, "slot": "gate-left"}
    ]


def test_decor_off_and_on(learner):
    key, _ = learner
    _give_coins(key, 50)
    service.buy(key, "decor-gate-lantern")
    view = service.apply(key, decor_off=["decor-gate-lantern"])
    assert view["decor"][0]["active"] is False
    view = service.apply(key, decor_on=["decor-gate-lantern"])
    assert view["decor"][0]["active"] is True


def test_cannot_place_decor_not_owned(learner):
    key, _ = learner
    with pytest.raises(Conflict):
        service.apply(key, decor_on=["decor-gate-lantern"])


def test_cannot_hide_decor_not_owned(learner):
    key, _ = learner
    with pytest.raises(Conflict):
        service.apply(key, decor_off=["decor-gate-lantern"])


def test_fox_statue_requires_nest_level_3(learner):
    key, _ = learner
    _give_coins(key, 500)
    with pytest.raises(Conflict):
        service.buy(key, "decor-gate-fox-statue")


def test_decor_buy_is_idempotent(learner):
    key, _ = learner
    _give_coins(key, 50)
    service.buy(key, "decor-gate-lantern")
    service.buy(key, "decor-gate-lantern")
    assert core.get_player(key)["coins"] == 10
