"""HTTP API Foxinburg World (§158).

Отдельный процесс world-backend (не школьный бот). Auth v1: заголовок
X-World-Player (external_key игрока мира). Не CRM и не miniapp школы.
"""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from . import activities, auth, core, engine, learn

router = APIRouter(prefix="/api/world", tags=["world"])

# Light TTS burn protection (per external_key, rolling 60s window).
TTS_RATE_LIMIT = 30
_tts_hits: dict[str, list[float]] = defaultdict(list)


def _player_key(x_world_player: str | None, *, signed: bool = True) -> str:
    if not x_world_player:
        raise HTTPException(401, "X-World-Player header required")
    # Opaque sessions always resolve (bootstrap + API).
    if x_world_player.startswith(auth.SESSION_PREFIX):
        return auth.verify(x_world_player)
    if signed:
        return auth.verify(x_world_player)
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


def _tts_allow(external_key: str) -> bool:
    now = time.monotonic()
    window = list(_tts_hits.get(external_key) or [])
    window = [t for t in window if now - t < 60.0]
    if len(window) >= TTS_RATE_LIMIT:
        _tts_hits[external_key] = window
        return False
    window.append(now)
    _tts_hits[external_key] = window
    return True


class PlayerCreate(BaseModel):
    display_name: str = "Explorer"
    role: str = "child"


@router.post("/players")
def create_player(body: PlayerCreate, x_world_player: str | None = Header(None)):
    """Public bootstrap: child only + opaque session token (Phase 1)."""
    key = _player_key(x_world_player, signed=False)
    role = (body.role or "child").strip().lower()
    if role != "child":
        raise HTTPException(403, "public signup is child-only; elevated roles require staff provisioning")
    player = _guard(core.get_or_create_player, key, body.display_name, "child")
    token = auth.issue_session(player["id"])
    return {**player, "token": token}


@router.post("/session/logout")
def session_logout(x_world_player: str | None = Header(None)):
    """Revoke current opaque session. Legacy HMAC keys are a no-op ok."""
    if not x_world_player:
        raise HTTPException(401, "X-World-Player header required")
    if x_world_player.startswith(auth.SESSION_PREFIX):
        # Resolve first so bad tokens 401; then revoke.
        auth.verify(x_world_player)
        auth.revoke_session(x_world_player)
    return {"ok": True}


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


class SprintAnswerBody(BaseModel):
    en: str
    choice: str


@router.post("/learn/sprint/sessions/{session_id}/answer")
def learn_sprint_answer(session_id: str, body: SprintAnswerBody,
                        x_world_player: str | None = Header(None)):
    return _guard(
        learn.sprint_answer, _player_key(x_world_player), session_id, body.en, body.choice,
    )


class SprintFinishBody(BaseModel):
    session_id: str | None = None
    score: int | None = None
    total: int | None = None


@router.post("/learn/sprint/finish")
def learn_sprint_finish(body: SprintFinishBody, x_world_player: str | None = Header(None)):
    return _guard(
        learn.finish_sprint,
        _player_key(x_world_player),
        body.session_id,
        body.score,
        body.total,
    )


@router.get("/learn/quests")
def learn_quests(x_world_player: str | None = Header(None)):
    return {"quests": _guard(learn.daily_quests, _player_key(x_world_player))}


class DailyClaimBody(BaseModel):
    quest_id: str


@router.post("/learn/quests/claim")
def learn_quest_claim(body: DailyClaimBody, x_world_player: str | None = Header(None)):
    return _guard(learn.claim_daily_quest, _player_key(x_world_player), body.quest_id)


@router.get("/learn/stickers")
def learn_stickers(x_world_player: str | None = Header(None)):
    return _guard(learn.album, _player_key(x_world_player))


@router.get("/learn/league")
def learn_league(x_world_player: str | None = Header(None)):
    return _guard(learn.league, _player_key(x_world_player))


@router.get("/tts")
def tts_speak(q: str = "hello", x_world_player: str | None = Header(None)):
    key = _player_key(x_world_player)  # require identity — no anonymous TTS burn
    if not _tts_allow(key):
        raise HTTPException(429, "tts rate limit")
    from fastapi.responses import FileResponse, JSONResponse
    from .tts import synth_english
    path = synth_english(q)
    if path is None:
        return JSONResponse({"ok": False, "reason": "no-voice"}, status_code=503)
    media = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".aiff": "audio/aiff",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media, filename=f"speak{path.suffix}")
