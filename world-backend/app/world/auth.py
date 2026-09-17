"""Подпись игрока и opaque-сессии (Phase 1 Identity).

Dev (нет WORLD_PLAYER_SECRET): сырой ключ или wses.* сессия.
Prod (секрет задан): HMAC `external_key.hmac` или wses.* сессия.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .db import get_conn

SESSION_PREFIX = "wses."
SESSION_DAYS = 30


def player_secret() -> str:
    return os.environ.get("WORLD_PLAYER_SECRET", "").strip()


def sign(external_key: str) -> str:
    """Legacy HMAC token (migration). Prefer issue_session for new logins."""
    secret = player_secret()
    if not secret:
        return external_key
    digest = hmac.new(secret.encode("utf-8"), external_key.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return f"{external_key}.{digest}"


def _hash_session(session_id: str, secret: str) -> str:
    return hashlib.sha256(f"{session_id}.{secret}".encode("utf-8")).hexdigest()


def issue_session(player_id: int, *, days: int = SESSION_DAYS) -> str:
    session_id = str(uuid.uuid4())
    secret = secrets.token_hex(16)
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    get_conn().execute(
        "INSERT INTO auth_sessions (id, player_id, token_hash, expires_at) VALUES (?,?,?,?)",
        (session_id, player_id, _hash_session(session_id, secret),
         expires.strftime("%Y-%m-%d %H:%M:%S")),
    )
    return f"{SESSION_PREFIX}{session_id}.{secret}"


def _parse_session(token: str) -> tuple[str, str]:
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "wses":
        raise HTTPException(401, "bad session token")
    _, session_id, secret = parts
    if not session_id or not secret:
        raise HTTPException(401, "bad session token")
    return session_id, secret


def _resolve_session(token: str) -> str:
    session_id, secret = _parse_session(token)
    row = get_conn().execute(
        "SELECT s.expires_at, s.revoked_at, p.external_key FROM auth_sessions s"
        " JOIN players p ON p.id = s.player_id"
        " WHERE s.id=? AND s.token_hash=?",
        (session_id, _hash_session(session_id, secret)),
    ).fetchone()
    if row is None:
        raise HTTPException(401, "bad session token")
    if row["revoked_at"]:
        raise HTTPException(401, "session revoked")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if row["expires_at"] < now:
        raise HTTPException(401, "session expired")
    return row["external_key"]


def revoke_session(token: str) -> bool:
    """Revoke opaque wses.* session. Returns False if not a session token."""
    if not token.startswith(SESSION_PREFIX):
        return False
    session_id, secret = _parse_session(token)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cur = get_conn().execute(
        "UPDATE auth_sessions SET revoked_at=? WHERE id=? AND token_hash=? AND revoked_at IS NULL",
        (now, session_id, _hash_session(session_id, secret)),
    )
    return cur.rowcount > 0


def verify(header: str | None) -> str:
    if not header:
        raise HTTPException(401, "X-World-Player header required")
    if header.startswith(SESSION_PREFIX):
        return _resolve_session(header)
    secret = player_secret()
    if not secret:
        return header
    if "." not in header:
        raise HTTPException(401, "signed player token required")
    key, got = header.rsplit(".", 1)
    if not key:
        raise HTTPException(401, "signed player token required")
    expect = hmac.new(secret.encode("utf-8"), key.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    if not hmac.compare_digest(got, expect):
        raise HTTPException(401, "bad player token")
    return key
