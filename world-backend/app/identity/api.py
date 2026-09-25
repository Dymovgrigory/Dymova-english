"""HTTP API регистрации: /api/v2/registration/* и /api/v2/auth/login."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.world import core
from app.world.api import _player_key as resolve_player_key

from . import service
from .schemas import (
    LoginBody,
    RecoveryPassword,
    RecoveryStart,
    RecoveryVerify,
    RegistrationStart,
    VerifyBody,
)

router = APIRouter(prefix="/api/v2/registration", tags=["registration"])
auth_router = APIRouter(prefix="/api/v2/auth", tags=["auth"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


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
    ip, ua = _client_meta(request)
    return _guard(service.start_registration, resolve_player_key(x_world_player),
                  body, ip, ua)


@router.post("/verify")
def verify(body: VerifyBody, x_world_player: str | None = Header(None)):
    return _guard(service.verify_code, resolve_player_key(x_world_player), body.code)


@router.post("/confirm-bot")
def confirm_bot(x_world_player: str | None = Header(None)):
    return _guard(service.confirm_via_bot, resolve_player_key(x_world_player))


@router.post("/recovery/start")
def recovery_start(body: RecoveryStart, request: Request):
    ip, ua = _client_meta(request)
    return _guard(service.recovery_start, body.email, body.phone, ip, ua)


@router.post("/recovery/verify")
def recovery_verify(body: RecoveryVerify):
    return _guard(service.recovery_verify, body.email, body.phone, body.code)


@router.post("/recovery/password")
def recovery_password(body: RecoveryPassword):
    return _guard(service.recovery_set_password, body.reset_token, body.password)


@router.get("/status")
def status(x_world_player: str | None = Header(None)):
    return _guard(service.get_status, resolve_player_key(x_world_player))


@auth_router.post("/login")
def login(body: LoginBody):
    return _guard(service.login, body.email, body.password)
