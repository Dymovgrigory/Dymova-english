"""Наборы сцены (scene_set) и слоты украшений (decor_place / авто-слоты)."""
from __future__ import annotations

import pytest

from app.castle import catalog, service
from app.world import core
from app.world.core import Conflict


def _give_coins(key: str, coins: int) -> None:
    core.award(key, coins=coins, source="test", type_="TEST_GRANT", idempotency_key=f"grant:{key}:{coins}")


def _decor(view: dict, item_id: str) -> dict:
    return next(d for d in view["decor"] if d["item_id"] == item_id)


def test_catalog_has_three_scene_sets():
    scenes = [item for item in catalog.ITEMS.values() if item.kind == "scene"]
    assert {item.value for item in scenes} == {"garland", "lanterns", "pumpkins"}
    assert {item.price for item in scenes} == {120, 150}


def test_buy_scene_and_apply(learner):
    key, _ = learner
    _give_coins(key, 200)
    view = service.buy(key, "scene-garland")
    assert view["coins"] == 80
    view = service.apply(key, scene_set="garland")
    assert view["appearance"]["scene_set"] == "garland"


def test_scene_set_reapply_is_idempotent(learner):
    key, _ = learner
    _give_coins(key, 200)
    service.buy(key, "scene-garland")
    service.apply(key, scene_set="garland")
    view = service.apply(key, scene_set="garland")
    assert view["appearance"]["scene_set"] == "garland"
    assert view["coins"] == 80  # повторная установка не списывает


def test_scene_set_null_clears(learner):
    key, _ = learner
    _give_coins(key, 200)
    service.buy(key, "scene-garland")
    service.apply(key, scene_set="garland")
    view = service.apply(key, scene_set=None)
    assert view["appearance"]["scene_set"] is None


def test_scene_set_not_owned(learner):
    key, _ = learner
    with pytest.raises(Conflict, match="item_not_owned"):
        service.apply(key, scene_set="lanterns")


def test_decor_place_valid_slot(learner):
    key, _ = learner
    _give_coins(key, 50)
    service.buy(key, "decor-gate-lantern")
    view = service.apply(key, decor_place=[{"item_id": "decor-gate-lantern", "slot": "gate-right"}])
    lantern = _decor(view, "decor-gate-lantern")
    assert lantern["active"] is True
    assert lantern["slot"] == "gate-right"


def test_decor_place_invalid_slot(learner):
    key, _ = learner
    _give_coins(key, 50)
    service.buy(key, "decor-gate-lantern")
    with pytest.raises(Conflict, match="invalid_slot"):
        service.apply(key, decor_place=[{"item_id": "decor-gate-lantern", "slot": "bridge"}])


def test_decor_place_slot_occupied(learner):
    key, _ = learner
    _give_coins(key, 200)
    service.buy(key, "decor-gate-lantern")
    service.buy(key, "decor-gate-pots")
    service.apply(key, decor_place=[{"item_id": "decor-gate-lantern", "slot": "gate-right"}])
    with pytest.raises(Conflict, match="slot_occupied"):
        service.apply(key, decor_place=[{"item_id": "decor-gate-pots", "slot": "gate-right"}])


def test_decor_on_default_slot_occupied(learner):
    key, _ = learner
    _give_coins(key, 200)
    service.buy(key, "decor-gate-lantern")
    service.buy(key, "decor-gate-pots")
    # кашпо сняты, фонарь переставлен на их дефолтный слот
    service.apply(key, decor_off=["decor-gate-pots"],
                  decor_place=[{"item_id": "decor-gate-lantern", "slot": "gate-far-left"}])
    with pytest.raises(Conflict, match="slot_occupied"):
        service.apply(key, decor_on=["decor-gate-pots"])


def test_view_returns_slot_and_scene_set(learner):
    key, _ = learner
    _give_coins(key, 400)
    service.buy(key, "scene-pumpkins")
    service.buy(key, "decor-gate-lantern")
    service.buy(key, "decor-stream-boat")
    service.apply(key, scene_set="pumpkins", decor_off=["decor-stream-boat"])
    view = service.view(key)
    assert view["appearance"]["scene_set"] == "pumpkins"
    assert _decor(view, "decor-gate-lantern")["slot"] == "gate-left"
    assert _decor(view, "decor-stream-boat")["slot"] is None  # снят — слота нет


def test_open_all_scene_sets(learner, monkeypatch: pytest.MonkeyPatch):
    key, _ = learner
    monkeypatch.setenv("CASTLE_OPEN_ALL", "1")
    view = service.apply(key, scene_set="lanterns")
    assert view["appearance"]["scene_set"] == "lanterns"
    view = service.buy(key, "scene-pumpkins")
    assert "scene-pumpkins" in view["owned"]
    assert view["coins"] == 0  # режим просмотра: бесплатно
