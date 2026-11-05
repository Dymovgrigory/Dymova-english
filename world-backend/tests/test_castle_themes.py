"""Темы оформления Мира: покупка, применение целиком, сброс при ручной смене слоя."""
from __future__ import annotations

import pytest

from app.castle import catalog, service
from app.world import core
from app.world.core import Conflict


@pytest.fixture
def key(learner):
    return learner[0]


def _rich(key: str) -> None:
    core.award(key, coins=1000, source="test", type_="TEST", idempotency_key=f"rich:{key}")


def test_catalog_has_themes():
    themes = [i for i in catalog.ITEMS.values() if i.kind == "theme"]
    assert len(themes) >= 6
    assert all(i.value in catalog.THEMES for i in themes)


def test_theme_needs_purchase(key):
    with pytest.raises(Conflict):
        service.apply(key, theme="winter-tale")


def test_theme_applies_all_layers(key):
    _rich(key)
    service.buy(key, "theme-polar-night")
    view = service.apply(key, theme="polar-night")
    ap = view["appearance"]
    assert (ap["theme"], ap["season"], ap["time_of_day"], ap["weather"]) == ("polar-night", "winter", "night", "aurora")


def test_manual_layer_resets_theme(key):
    _rich(key)
    service.buy(key, "theme-blossom")
    service.apply(key, theme="blossom")
    view = service.apply(key, weather=None)
    assert view["appearance"]["theme"] is None
