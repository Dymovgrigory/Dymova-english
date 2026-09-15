"""Подпись игрока: заголовок X-World-Player больше нельзя угадать вслепую.

Dev (нет WORLD_PLAYER_SECRET): принимаем сырой ключ, как раньше.
Prod (секрет задан): ключ должен быть `external_key.hmac`.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import HTTPException


def player_secret() -> str:
    return os.environ.get("WORLD_PLAYER_SECRET", "").strip()


def sign(external_key: str) -> str:
    secret = player_secret()
    if not secret:
        return external_key
    digest = hmac.new(secret.encode("utf-8"), external_key.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return f"{external_key}.{digest}"


def verify(header: str | None) -> str:
    if not header:
        raise HTTPException(401, "X-World-Player header required")
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
