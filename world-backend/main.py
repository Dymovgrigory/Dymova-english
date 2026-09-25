"""Foxinburg World — отдельный FastAPI-процесс (не школьный бот, не CRM)."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.admin import api as admin_api
from app.admin import auth as admin_auth
from app.castle import api as castle_api
from app.identity import api as identity_api
from app.identity import gate as identity_gate
from app.identity import messenger as messenger_api
from app.learning import api as learning_api
from app.learning import content as learning_content
from app.world import api as world_api
from app.world import core

_DEFAULT_ORIGINS = (
    "http://localhost:3000,http://localhost:3002,"
    "http://127.0.0.1:3000,http://127.0.0.1:3002"
)


def _cors_origins() -> list[str]:
    raw = os.environ.get("WORLD_CORS_ORIGINS", _DEFAULT_ORIGINS)
    return [part.strip() for part in raw.split(",") if part.strip()]


app = FastAPI(title="Foxinburg World")
# Порядок важен: последний add_middleware — самый внешний. CORS снаружи,
# чтобы 403 гейта тоже уходил с CORS-заголовками.
app.add_middleware(identity_gate.RegistrationGateMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Content-Type", "X-World-Player", "Authorization"],
)
app.include_router(world_api.router)
app.include_router(castle_api.router)
app.include_router(castle_api.quests_router)
app.include_router(learning_api.router)
app.include_router(identity_api.router)
app.include_router(identity_api.auth_router)
app.include_router(messenger_api.router)
app.include_router(admin_api.router)


@app.on_event("startup")
def _seed() -> None:
    core.seed_quests()
    admin_auth.bootstrap()
    learning_content.get_course()  # битый контент Spotlight не даёт стартовать


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
