"""Режим просмотра CASTLE_OPEN_ALL=1: вся витрина открыта и покупки бесплатны.

Нужен владельцу для ревью наград и кастомизации без прокачки. По умолчанию выключен,
в бою включается только на время проверки через переменную окружения.
"""
from __future__ import annotations

import pytest

from app.castle import catalog, service
from app.world import core


@pytest.fixture()
def player_key(learn_db: None) -> str:
    key = "open-all-check"
    core.get_or_create_player(key)
    return key


def test_closed_by_default(player_key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CASTLE_OPEN_ALL", raising=False)
    view = service.view(player_key)
    assert any(not item["unlocked"] for item in view["catalog"] if item["requires_track"])


def test_open_all_unlocks_catalog(player_key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASTLE_OPEN_ALL", "1")
    view = service.view(player_key)
    assert all(item["unlocked"] for item in view["catalog"])


def test_open_all_buy_is_free_and_skips_title(player_key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASTLE_OPEN_ALL", "1")
    gated = next(i for i in catalog.ITEMS.values() if i.requires_track is not None)
    before = service.view(player_key)["coins"]
    view = service.buy(player_key, gated.id)
    assert view["coins"] == before                      # монеты не списаны
    assert gated.id in view["owned"]
    # повторная покупка тоже не списывает
    assert service.buy(player_key, gated.id)["coins"] == before


def test_open_all_apply_without_ownership(player_key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASTLE_OPEN_ALL", "1")
    view = service.apply(player_key, season="winter", time_of_day="night", decor_on=["decor-stream-boat"])
    assert view["appearance"]["season"] == "winter"
    assert view["appearance"]["time_of_day"] == "night"
    boat = next(d for d in view["decor"] if d["item_id"] == "decor-stream-boat")
    assert boat["active"]


def test_closed_buy_charges(player_key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CASTLE_OPEN_ALL", raising=False)
    core.award(player_key, coins=500, source="test", type_="TEST", idempotency_key="open-all:charge")
    item = next(i for i in catalog.ITEMS.values() if i.purchasable and i.requires_track is None and i.price > 0)
    before = service.view(player_key)["coins"]
    view = service.buy(player_key, item.id)
    assert view["coins"] == before - item.price
