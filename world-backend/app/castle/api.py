"""HTTP API замка: облик, покупки, звания."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.world import core
from app.world.api import _player_key as resolve_player_key

from . import lexicon_chest, quests, service, titles

router = APIRouter(prefix="/api/v2/castle", tags=["castle"])


class BuyBody(BaseModel):
    item_id: str


class AppearanceBody(BaseModel):
    season: str | None = None
    time_of_day: str | None = None
    weather: str | None = None
    banner_color: str | None = None
    banner_emblem: str | None = None
    decor_on: list[str] | None = None
    decor_off: list[str] | None = None


class TitleBody(BaseModel):
    track: str


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except core.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except core.Conflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("")
def get_castle(x_world_player: str | None = Header(None)):
    return _run(service.view, resolve_player_key(x_world_player))


@router.post("/buy")
def buy(body: BuyBody, x_world_player: str | None = Header(None)):
    return _run(service.buy, resolve_player_key(x_world_player), body.item_id)


@router.post("/appearance")
def appearance(body: AppearanceBody, x_world_player: str | None = Header(None)):
    fields = body.model_dump(exclude_unset=True)
    return _run(service.apply, resolve_player_key(x_world_player), **fields)


@router.post("/title")
def wear_title(body: TitleBody, x_world_player: str | None = Header(None)):
    key = resolve_player_key(x_world_player)
    player = _run(core.get_player, key)
    _run(titles.wear, int(player["id"]), body.track)
    return _run(service.view, key)


@router.get("/lexicon-chest")
def lexicon_chest_status(x_world_player: str | None = Header(None)):
    player = _run(core.get_player, resolve_player_key(x_world_player))
    return lexicon_chest.status(int(player["id"]))


@router.post("/lexicon-chest/open")
def lexicon_chest_open(x_world_player: str | None = Header(None)):
    return _run(lexicon_chest.open, resolve_player_key(x_world_player))


quests_router = APIRouter(prefix="/api/v2/quests", tags=["quests"])


class ClaimBody(BaseModel):
    quest_id: str
    period: str  # "day" | "week"


@quests_router.get("")
def list_quests(x_world_player: str | None = Header(None)):
    return _run(quests.quests, resolve_player_key(x_world_player))


@quests_router.post("/claim")
def claim_quest(body: ClaimBody, x_world_player: str | None = Header(None)):
    return _run(quests.claim, resolve_player_key(x_world_player), body.quest_id, body.period)
