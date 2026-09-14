"""Foxinburg World — отдельный FastAPI-процесс (не школьный бот, не CRM)."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.world import api as world_api
from app.world import core

_DEFAULT_ORIGINS = "http://localhost:3000,http://localhost:3002"


def _cors_origins() -> list[str]:
    raw = os.environ.get("WORLD_CORS_ORIGINS", _DEFAULT_ORIGINS)
    return [part.strip() for part in raw.split(",") if part.strip()]


app = FastAPI(title="Foxinburg World")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-World-Player"],
)
app.include_router(world_api.router)


@app.on_event("startup")
def _seed() -> None:
    core.seed_quests()


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
