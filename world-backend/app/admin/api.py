"""HTTP API админки: /api/v2/admin/*."""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.identity.schemas import IdentityPatch
from app.world import core

from . import auth, service

router = APIRouter(prefix="/api/v2/admin", tags=["admin"])

# Rate-limit логина: 5 неудачных попыток/мин с IP (in-memory).
LOGIN_RATE = 5
_login_fails: dict[str, list[float]] = defaultdict(list)


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except core.NotFound as e:
        raise HTTPException(404, str(e))
    except core.Conflict as e:
        raise HTTPException(409, str(e))


def reset_rate_limit() -> None:
    """Хук для тестов: сброс счётчиков логина."""
    _login_fails.clear()


class LoginBody(BaseModel):
    login: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
def login(body: LoginBody, request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = [t for t in _login_fails.get(ip, []) if now - t < 60.0]
    _login_fails[ip] = window
    if len(window) >= LOGIN_RATE:
        raise HTTPException(429, "too_many_attempts")
    try:
        return auth.login_admin(body.login, body.password)
    except HTTPException as exc:
        if exc.status_code == 401:
            window.append(now)
        raise


@router.post("/logout")
def logout(admin: dict = Depends(auth.require_admin),
           authorization: str | None = Header(None)):
    token = auth.bearer_token(authorization)
    auth.revoke(token)
    return {"ok": True}


@router.get("/me")
def me(admin: dict = Depends(auth.require_admin)):
    return {"login": admin["login"], "role": admin["role"]}


@router.get("/students")
def students(admin: dict = Depends(auth.require_admin),
             q: str | None = Query(None),
             class_grade: int | None = Query(None),
             verified: str | None = Query(None),
             page: int = Query(1, ge=1),
             per_page: int = Query(20, ge=1, le=100)):
    if verified not in (None, "true", "false"):
        raise HTTPException(422, "verified must be true or false")
    return service.list_students(q, class_grade, verified, page, per_page)


@router.get("/students/{player_id}")
def student(player_id: int, admin: dict = Depends(auth.require_admin)):
    return _guard(service.student_card, player_id)


@router.patch("/students/{player_id}")
def student_patch(player_id: int, body: IdentityPatch,
                  admin: dict = Depends(auth.require_admin)):
    return _guard(service.patch_identity, player_id, body, admin["login"])


class AdjustBody(BaseModel):
    kind: str
    delta: int
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("kind")
    @classmethod
    def _kind_ok(cls, v: str) -> str:
        if v not in ("coins", "xp"):
            raise ValueError("kind must be coins or xp")
        return v


@router.post("/students/{player_id}/adjust")
def student_adjust(player_id: int, body: AdjustBody,
                   admin: dict = Depends(auth.require_admin)):
    return _guard(service.adjust, player_id, body.kind, body.delta, body.reason,
                  admin["login"])


class MasteryBody(BaseModel):
    atom_id: str = Field(min_length=1, max_length=120)
    action: str
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("action")
    @classmethod
    def _action_ok(cls, v: str) -> str:
        if v not in ("reset", "master"):
            raise ValueError("action must be reset or master")
        return v


@router.post("/students/{player_id}/mastery")
def student_mastery(player_id: int, body: MasteryBody,
                    admin: dict = Depends(auth.require_admin)):
    return _guard(service.mastery, player_id, body.atom_id, body.action, body.reason,
                  admin["login"])


class ItemBody(BaseModel):
    item_id: str = Field(min_length=1, max_length=120)
    action: str
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("action")
    @classmethod
    def _action_ok(cls, v: str) -> str:
        if v not in ("grant", "revoke"):
            raise ValueError("action must be grant or revoke")
        return v


@router.post("/students/{player_id}/items")
def student_items(player_id: int, body: ItemBody,
                  admin: dict = Depends(auth.require_admin)):
    return _guard(service.items, player_id, body.item_id, body.action, body.reason,
                  admin["login"])


@router.get("/audit")
def audit_feed(admin: dict = Depends(auth.require_admin),
               player_id: int | None = Query(None),
               limit: int = Query(50, ge=1, le=500)):
    return service.list_audit(player_id, limit)
