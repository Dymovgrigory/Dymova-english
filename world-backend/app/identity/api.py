"""HTTP API регистрации: /api/v2/registration/*."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.world import core
from app.world.api import _player_key as resolve_player_key

from . import service
from .schemas import RegistrationStart, VerifyBody

router = APIRouter(prefix="/api/v2/registration", tags=["registration"])


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except core.Conflict as e:
        msg = str(e)
        if msg == "provider_error":
            raise HTTPException(502, "provider_error")
        if msg.startswith("code_invalid|"):
            left = int(msg.split("|", 1)[1])
            return JSONResponse(
                {"detail": "code_invalid", "attempts_left": left}, status_code=409,
            )
        raise HTTPException(409, msg)


@router.post("/start")
def start(body: RegistrationStart, request: Request,
          x_world_player: str | None = Header(None)):
    key = resolve_player_key(x_world_player)
    ip = request.client.host if request.client else None
    return _guard(service.start_registration, key, body, ip,
                  request.headers.get("user-agent"))


@router.post("/verify")
def verify(body: VerifyBody, x_world_player: str | None = Header(None)):
    return _guard(service.verify_code, resolve_player_key(x_world_player), body.code)


@router.get("/status")
def status(x_world_player: str | None = Header(None)):
    return _guard(service.get_status, resolve_player_key(x_world_player))
