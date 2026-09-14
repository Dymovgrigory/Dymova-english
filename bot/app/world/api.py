"""HTTP API Foxinburg World (§158). Router монтируется в bot/app/main.py.

Auth v1 (slice): заголовок X-World-Player (external_key). Интеграция с
miniapp-auth (TG/MAX initData) и CRM child id — следующий шаг; контракт
эндпоинтов от этого не меняется.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from . import activities, core

router = APIRouter(prefix="/api/world", tags=["world"])


def _player_key(x_world_player: str | None) -> str:
    if not x_world_player:
        raise HTTPException(401, "X-World-Player header required")
    return x_world_player


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except core.NotFound as e:
        raise HTTPException(404, str(e))
    except core.Conflict as e:
        raise HTTPException(409, str(e))


class PlayerCreate(BaseModel):
    display_name: str = "Explorer"
    role: str = "child"


@router.post("/players")
def create_player(body: PlayerCreate, x_world_player: str | None = Header(None)):
    key = _player_key(x_world_player)
    if body.role not in ("child", "parent", "teacher", "admin"):
        raise HTTPException(422, "invalid role")
    return _guard(core.get_or_create_player, key, body.display_name, body.role)


@router.get("/player")
def get_player(x_world_player: str | None = Header(None)):
    return _guard(core.get_player, _player_key(x_world_player))


@router.get("/quests")
def quests(x_world_player: str | None = Header(None)):
    return _guard(core.list_quests, _player_key(x_world_player))


@router.post("/quests/{quest_id}/start")
def quest_start(quest_id: str, x_world_player: str | None = Header(None)):
    return _guard(core.start_quest, _player_key(x_world_player), quest_id)


class CompleteBody(BaseModel):
    idempotency_key: str | None = None


@router.post("/quests/{quest_id}/complete")
def quest_complete(quest_id: str, body: CompleteBody | None = None,
                   x_world_player: str | None = Header(None)):
    return _guard(
        core.complete_quest, _player_key(x_world_player), quest_id,
        body.idempotency_key if body else None,
    )


@router.get("/inventory")
def inventory(x_world_player: str | None = Header(None)):
    return _guard(core.get_inventory, _player_key(x_world_player))


@router.get("/unlocks")
def unlocks(x_world_player: str | None = Header(None)):
    return _guard(core.get_unlocks, _player_key(x_world_player))


class StepBody(BaseModel):
    action: str
    target: str


@router.post("/quests/{quest_id}/step")
def quest_step(quest_id: str, body: StepBody, x_world_player: str | None = Header(None)):
    return _guard(core.advance_quest_step, _player_key(x_world_player), quest_id,
                  body.action, body.target)


class ActivityStartBody(BaseModel):
    activity_id: str


@router.post("/activities/start")
def activity_start(body: ActivityStartBody, x_world_player: str | None = Header(None)):
    return _guard(activities.start, _player_key(x_world_player), body.activity_id)


class ActivityAnswerBody(BaseModel):
    index: int
    choice: int


@router.post("/activities/{session_id}/answer")
def activity_answer(session_id: str, body: ActivityAnswerBody,
                    x_world_player: str | None = Header(None)):
    return _guard(activities.answer, _player_key(x_world_player), session_id,
                  body.index, body.choice)


class ActivityFinishBody(BaseModel):
    idempotency_key: str | None = None


@router.post("/activities/{session_id}/finish")
def activity_finish(session_id: str, body: ActivityFinishBody | None = None,
                    x_world_player: str | None = Header(None)):
    return _guard(activities.finish, _player_key(x_world_player), session_id,
                  body.idempotency_key if body else None)
