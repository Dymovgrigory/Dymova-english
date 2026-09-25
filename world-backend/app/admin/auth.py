"""Админ-аутентификация: pbkdf2-пароли и opaque-сессии wadm.* (TTL 12 ч)."""
from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Header, HTTPException

from app.identity.passwords import hash_password, verify_password
from app.world.db import get_conn

SESSION_PREFIX = "wadm."
SESSION_HOURS = 12


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def create_admin(login: str, password: str, role: str = "manager") -> int:
    cur = get_conn().execute(
        "INSERT INTO admin_users (login, password_hash, role) VALUES (?,?,?)",
        (login, hash_password(password), role),
    )
    return int(cur.lastrowid)


def bootstrap() -> None:
    """Startup-seed: первый owner из env, если таблица пуста."""
    login = os.environ.get("ADMIN_BOOTSTRAP_LOGIN", "").strip()
    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "").strip()
    if not (login and password):
        return
    row = get_conn().execute("SELECT COUNT(*) AS c FROM admin_users").fetchone()
    if row["c"] == 0:
        create_admin(login, password, role="owner")


def login_admin(login: str, password: str) -> dict:
    row = get_conn().execute(
        "SELECT * FROM admin_users WHERE login=?", (login,)
    ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        raise HTTPException(401, "invalid_credentials")
    token = f"{SESSION_PREFIX}{uuid.uuid4().hex}.{secrets.token_hex(16)}"
    expires = (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS))
    get_conn().execute(
        "INSERT INTO admin_sessions (id, admin_id, token_hash, expires_at)"
        " VALUES (?,?,?,?)",
        (uuid.uuid4().hex, row["id"], _hash_token(token),
         expires.strftime("%Y-%m-%d %H:%M:%S")),
    )
    return {"token": token, "role": row["role"], "login": row["login"]}


def revoke(token: str) -> None:
    get_conn().execute(
        "UPDATE admin_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
        (_now(), _hash_token(token)),
    )


def _resolve(token: str) -> dict:
    row = get_conn().execute(
        "SELECT s.expires_at, s.revoked_at, a.login, a.role FROM admin_sessions s"
        " JOIN admin_users a ON a.id = s.admin_id"
        " WHERE s.token_hash=?",
        (_hash_token(token),),
    ).fetchone()
    if row is None or row["revoked_at"] or row["expires_at"] < _now():
        raise HTTPException(401, "admin_unauthorized")
    return {"login": row["login"], "role": row["role"]}


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "admin_unauthorized")
    token = authorization[len("Bearer "):].strip()
    if not token.startswith(SESSION_PREFIX):
        raise HTTPException(401, "admin_unauthorized")
    return token


def require_admin(authorization: str | None = Header(None)) -> dict:
    """FastAPI-dependency: Authorization: Bearer wadm.* → {login, role}."""
    return _resolve(bearer_token(authorization))
