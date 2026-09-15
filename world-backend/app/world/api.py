"""HTTP API Foxinburg World (§158).

Отдельный процесс world-backend (не школьный бот). Auth v1: заголовок
X-World-Player (external_key игрока мира). Не CRM и не miniapp школы.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from . import activities, auth, core, engine, learn

router = APIRouter(prefix="/api/world", tags=["world"])


def _player_key(x_world_player: str | None, *, signed: bool = True) -> str:
    if signed:
        return auth.verify(x_world_player)
    if not x_world_player:
        raise HTTPException(401, "X-World-Player header required")
    if auth.player_secret() and "." in x_world_player:
        return auth.verify(x_world_player)
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
    key = _player_key(x_world_player, signed=False)
    if body.role not in ("child", "parent", "teacher", "admin"):
        raise HTTPException(422, "invalid role")
    player = _guard(core.get_or_create_player, key, body.display_name, body.role)
    return {**player, "token": auth.sign(key)}


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


@router.get("/learn/path")
def learn_path(x_world_player: str | None = Header(None)):
    return _guard(engine.get_path, _player_key(x_world_player))


class LessonStartBody(BaseModel):
    lesson_id: str


@router.post("/learn/lessons/start")
def learn_start(body: LessonStartBody, x_world_player: str | None = Header(None)):
    return _guard(engine.start_lesson, _player_key(x_world_player), body.lesson_id)


class LessonAnswerBody(BaseModel):
    index: int
    value: dict


@router.post("/learn/sessions/{session_id}/answer")
def learn_answer(session_id: str, body: LessonAnswerBody,
                 x_world_player: str | None = Header(None)):
    return _guard(engine.answer, _player_key(x_world_player), session_id,
                  body.index, body.value)


@router.post("/learn/sessions/{session_id}/finish")
def learn_finish(session_id: str, x_world_player: str | None = Header(None)):
    return _guard(engine.finish, _player_key(x_world_player), session_id)


@router.get("/learn/home")
def learn_home(x_world_player: str | None = Header(None)):
    return _guard(learn.home, _player_key(x_world_player))


@router.get("/learn/shop")
def learn_shop():
    return {"items": learn.shop()}


class ShopBuyBody(BaseModel):
    sku: str


@router.post("/learn/hearts/restore")
def learn_hearts_restore(x_world_player: str | None = Header(None)):
    return _guard(learn.restore_hearts, _player_key(x_world_player))


@router.post("/learn/shop/buy")
def learn_buy(body: ShopBuyBody, x_world_player: str | None = Header(None)):
    return _guard(learn.buy, _player_key(x_world_player), body.sku)


@router.post("/learn/practice/start")
def learn_practice(x_world_player: str | None = Header(None)):
    return _guard(engine.start_practice, _player_key(x_world_player))


@router.get("/learn/words/{unit_id}")
def learn_words(unit_id: str, x_world_player: str | None = Header(None)):
    return _guard(learn.words, _player_key(x_world_player), unit_id)


@router.get("/learn/review")
def learn_review(x_world_player: str | None = Header(None)):
    return _guard(learn.review, _player_key(x_world_player))


@router.get("/learn/sprint")
def learn_sprint(x_world_player: str | None = Header(None)):
    return _guard(learn.sprint, _player_key(x_world_player))


class SprintFinishBody(BaseModel):
    score: int
    total: int


@router.post("/learn/sprint/finish")
def learn_sprint_finish(body: SprintFinishBody, x_world_player: str | None = Header(None)):
    return _guard(learn.finish_sprint, _player_key(x_world_player), body.score, body.total)


@router.get("/learn/quests")
def learn_quests(x_world_player: str | None = Header(None)):
    return {"quests": _guard(learn.daily_quests, _player_key(x_world_player))}


@router.get("/learn/stickers")
def learn_stickers(x_world_player: str | None = Header(None)):
    return _guard(learn.album, _player_key(x_world_player))


@router.get("/learn/league")
def learn_league(x_world_player: str | None = Header(None)):
    return _guard(learn.league, _player_key(x_world_player))


@router.get("/tts")
def tts_speak(q: str = "hello"):
    from fastapi.responses import FileResponse, JSONResponse
    from .tts import synth_english
    path = synth_english(q)
    if path is None:
        return JSONResponse({"ok": False, "reason": "no-voice"}, status_code=503)
    media = "audio/wav" if path.suffix == ".wav" else "audio/aiff"
    return FileResponse(path, media_type=media, filename="speak.wav")
