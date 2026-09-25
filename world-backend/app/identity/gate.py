"""Гейт обязательной регистрации: ученические API закрыты до завершения анкеты.

Незарегистрированному игроку (нет player_identity.phone_verified_at) на все
/api/v2/* и /api/world/* возвращаем 403 {"detail": {"code": "registration_required"}}.

Открыты без регистрации: создание игрока, сама регистрация и коды телефона,
вход через Telegram/MAX, админка (свой Bearer), health/статика вне /api/*.
Выключить гейт: REGISTRATION_GATE=0 (локальная отладка).
"""
from __future__ import annotations

import os

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.world import auth
from app.world.db import get_conn

from . import service

_OPEN_PREFIXES = (
    "/api/v2/admin",         # Bearer-авторизация админа, не игрока
    "/api/v2/registration",  # анкета, согласия, коды, recovery
    "/api/v2/auth",          # login email+пароль
    "/api/world/auth",       # вход через Telegram/MAX mini apps
)
_OPEN_PATHS = {
    "/api/world/players",          # POST bootstrap игрока
    "/api/world/session/logout",   # отзыв сессии всегда безопасен
}


def gate_enabled() -> bool:
    return os.environ.get("REGISTRATION_GATE", "1").strip() != "0"


class RegistrationGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not gate_enabled():
            return await call_next(request)
        path = request.url.path
        if not path.startswith(("/api/v2/", "/api/world/")):
            return await call_next(request)
        if path in _OPEN_PATHS or path.startswith(_OPEN_PREFIXES):
            return await call_next(request)
        header = request.headers.get("x-world-player")
        if not header:
            return await call_next(request)  # без заголовка роут сам отвечает 401
        try:
            external_key = auth.verify(header)
        except HTTPException:
            return await call_next(request)  # битый токен — 401 на роуте
        row = get_conn().execute(
            "SELECT id FROM players WHERE external_key=?", (external_key,),
        ).fetchone()
        if row is None or service.is_registered(row["id"]):
            return await call_next(request)
        return JSONResponse(
            {"detail": {"code": "registration_required"}}, status_code=403,
        )
