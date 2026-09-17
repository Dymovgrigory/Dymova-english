"""Каталог облика и сохранение выбранного вида замка."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.castle import catalog, state
from app.world.core import Conflict


def test_season_follows_calendar():
    assert catalog.season_by_date(datetime(2026, 1, 15, tzinfo=timezone.utc)) == "winter"
    assert catalog.season_by_date(datetime(2026, 4, 15, tzinfo=timezone.utc)) == "spring"
    assert catalog.season_by_date(datetime(2026, 7, 15, tzinfo=timezone.utc)) == "summer"
    assert catalog.season_by_date(datetime(2026, 10, 15, tzinfo=timezone.utc)) == "autumn"


def test_catalog_prices_match_spec():
    assert catalog.ITEMS["season-winter"].price == 150
    assert catalog.ITEMS["time-night"].price == 80
    assert 60 <= catalog.ITEMS["weather-snow"].price <= 120
    assert catalog.ITEMS["banner-emerald"].price == 50


def test_rarest_item_cannot_be_bought():
    item = catalog.ITEMS["weather-aurora"]
    assert item.purchasable is False
    assert item.requires_track == "nest"
    assert item.requires_level == 5


def test_default_appearance_is_free_and_seasonal(learner):
    _, player_id = learner
    view = state.appearance(player_id)
    assert view["season"] is None       # означает «по календарю»
    assert view["time_of_day"] is None  # означает «как за окном»
    assert view["weather"] is None
    assert view["banner_color"] == "plum"


def test_set_appearance_saves_and_validates(learner):
    _, player_id = learner
    view = state.set_appearance(player_id, time_of_day="night", banner_color="emerald")
    assert view["time_of_day"] == "night"
    assert view["banner_color"] == "emerald"
    with pytest.raises(Conflict):
        state.set_appearance(player_id, time_of_day="полночь")
