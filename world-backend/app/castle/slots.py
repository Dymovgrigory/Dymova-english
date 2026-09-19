"""Слоты украшений на сцене замка: где что может стоять."""
from __future__ import annotations

from .catalog import Item

SLOTS = {
    "gate-left", "gate-right", "gate-far-left", "gate-far-right",
    "bridge", "courtyard", "roofs", "stream", "meadow", "walls",
}

# У ворот четыре точки, у остальных якорей — одноимённый слот.
_ANCHOR_SLOTS = {"gate": {"gate-left", "gate-right", "gate-far-left", "gate-far-right"}}


def allowed_slots(anchor: str | None) -> set[str]:
    if anchor is None:
        return set()
    return _ANCHOR_SLOTS.get(anchor, {anchor})


# Калиброванные позиции у ворот; остальные предметы встают в одноимённый слот якоря.
_DEFAULT_SLOTS = {
    "decor-gate-lantern": "gate-left",
    "decor-gate-fox-statue": "gate-right",
    "decor-gate-pots": "gate-far-left",
    "decor-gate-pumpkins": "gate-far-right",
}


def default_slot(item: Item) -> str | None:
    return _DEFAULT_SLOTS.get(item.id) or item.anchor
