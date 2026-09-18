"""HTTP API тренажёра Spotlight: /api/v2 (урок, путь, профиль, словарь)."""
from __future__ import annotations

from typing import Callable, Literal, TypeVar

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.world import core
from app.world.db import get_conn
from app.world.api import _player_key as resolve_player_key  # единая авторизация с v1

from . import builder, clock, content, progress, sessions, views
from .errors import LearningError

router = APIRouter(prefix="/api/v2", tags=["learning"])

T = TypeVar("T")


def _run(fn: Callable[..., T], *args, **kwargs) -> T:
    try:
        return fn(*args, **kwargs)
    except LearningError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except core.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except core.Conflict as exc:
        raise HTTPException(409, str(exc)) from exc


def _player_id(key: str) -> int:
    return int(_run(core.get_player, key)["id"])


class ProfileBody(BaseModel):
    book_id: str
    module_id: str
    daily_goal_xp: int = 20


class SessionBody(BaseModel):
    node_id: str
    allow_speak: bool = True


class AnswerBody(BaseModel):
    index: int
    answer: dict
    response_ms: int | None = None


class PairBody(BaseModel):
    index: int
    left: str
    right: str


class PracticeBody(BaseModel):
    allow_speak: bool = True
    mode: Literal["practice", "trial"] = "practice"


@router.get("/courses")
def get_courses():
    return views.courses(content.get_course())


@router.get("/profile")
def get_profile(x_world_player: str | None = Header(None)):
    key = resolve_player_key(x_world_player)
    return _run(progress.get_profile, _player_id(key))


@router.put("/profile")
def put_profile(body: ProfileBody, x_world_player: str | None = Header(None)):
    key = resolve_player_key(x_world_player)
    return _run(progress.set_profile, _player_id(key), content.get_course(), book_id=body.book_id,
                module_id=body.module_id, daily_goal_xp=body.daily_goal_xp)


@router.get("/home")
def get_home(x_world_player: str | None = Header(None)):
    return _run(views.home, resolve_player_key(x_world_player), content.get_course())


@router.get("/path")
def get_path(book_id: str, x_world_player: str | None = Header(None)):
    return _run(views.path, resolve_player_key(x_world_player), content.get_course(), book_id)


@router.post("/sessions")
def start_session(body: SessionBody, x_world_player: str | None = Header(None)):
    return _run(sessions.start, resolve_player_key(x_world_player), body.node_id, allow_speak=body.allow_speak)


@router.post("/sessions/{session_id}/answer")
def answer(session_id: str, body: AnswerBody, x_world_player: str | None = Header(None)):
    return _run(sessions.answer, resolve_player_key(x_world_player), session_id, body.index, body.answer,
                response_ms=body.response_ms)


@router.post("/sessions/{session_id}/pair")
def check_pair(session_id: str, body: PairBody, x_world_player: str | None = Header(None)):
    return _run(sessions.check_pair, resolve_player_key(x_world_player), session_id, body.index, body.left, body.right)


@router.post("/sessions/{session_id}/finish")
def finish(session_id: str, x_world_player: str | None = Header(None)):
    return _run(sessions.finish, resolve_player_key(x_world_player), session_id)


@router.post("/nodes/{node_id}/chest")
def open_chest(node_id: str, x_world_player: str | None = Header(None)):
    return _run(progress.open_chest, resolve_player_key(x_world_player), content.get_course(), node_id)


@router.post("/practice")
def start_practice(body: PracticeBody, x_world_player: str | None = Header(None)):
    node = sessions.TRIAL_NODE if body.mode == "trial" else sessions.PRACTICE_NODE
    return _run(sessions.start, resolve_player_key(x_world_player), node,
                allow_speak=body.allow_speak)


@router.get("/practice/status")
def practice_status(x_world_player: str | None = Header(None)):
    """Статус испытания дня: пройдено ли сегодня и есть ли из чего его собрать."""
    key = resolve_player_key(x_world_player)
    player = _run(core.get_player, key)
    player_id = int(player["id"])
    day = clock.local_day(clock.now())
    done = get_conn().execute(
        "SELECT COUNT(*) AS c FROM coin_transactions"
        " WHERE player_id=? AND type='TRIAL_REWARD' AND created_at>=?",
        (player_id, clock.day_start_sql(day)),
    ).fetchone()["c"]
    word_ids = {w.id for m in content.get_course().modules for w in m.words}
    marks = ",".join("?" for _ in word_ids) or "''"
    seen = get_conn().execute(
        f"SELECT COUNT(*) AS c FROM atom_mastery WHERE player_id=? AND atom_id IN ({marks})",
        (player_id, *sorted(word_ids)),
    ).fetchone()["c"]
    return {"trial_done_today": bool(done), "trial_available": seen >= builder.TRIAL_SIZE}


@router.get("/words")
def get_words(book_id: str, x_world_player: str | None = Header(None)):
    return _run(views.words, resolve_player_key(x_world_player), content.get_course(), book_id)
