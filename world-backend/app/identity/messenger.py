"""Вход через мини-приложения Telegram и MAX: /api/world/auth/{telegram,max}.

Валидация initData (одинаковая схема у обоих, см. dev.max.ru/docs/webapps/validation):
data-check-string = все поля кроме hash, отсортированные key=value через "\\n";
secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token);
hash == HMAC_SHA256(key=secret_key, msg=data-check-string) в hex.
Плюс проверка свежести auth_date (≤ 24ч, допуск 5 мин на рассинхрон часов).

Токены ботов — только env: TELEGRAM_BOT_TOKEN / MAX_BOT_TOKEN.
Без токена провайдер отвечает 503 {"detail": {"code": "provider_not_configured"}}.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.world import auth, core
from app.world.db import get_conn

from . import bridge, service

router = APIRouter(prefix="/api/world/auth", tags=["messenger-auth"])

MAX_INIT_DATA_AGE_SEC = 24 * 3600
FUTURE_SKEW_SEC = 300

_PROVIDERS = {
    "telegram": "TELEGRAM_BOT_TOKEN",
    "max": "MAX_BOT_TOKEN",
}


class MessengerAuthBody(BaseModel):
    init_data: str


def validate_init_data(init_data: str, bot_token: str, *, now: float | None = None) -> dict:
    """Проверяет подпись и свежесть initData, возвращает объект user."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    their_hash = pairs.pop("hash", None)
    if not their_hash:
        raise HTTPException(401, {"code": "bad_init_data", "reason": "no_hash"})
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(secret, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, their_hash):
        raise HTTPException(401, {"code": "bad_init_data", "reason": "bad_signature"})
    try:
        auth_date = int(pairs.get("auth_date") or 0)
    except ValueError:
        auth_date = 0
    now = time.time() if now is None else now
    if auth_date <= 0 or now - auth_date > MAX_INIT_DATA_AGE_SEC or auth_date - now > FUTURE_SKEW_SEC:
        raise HTTPException(401, {"code": "bad_init_data", "reason": "stale_auth_date"})
    try:
        user = json.loads(pairs.get("user") or "{}")
    except json.JSONDecodeError:
        user = {}
    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(401, {"code": "bad_init_data", "reason": "no_user"})
    return user


def _display_name(user: dict) -> str:
    parts = [str(user.get("first_name") or "").strip(), str(user.get("last_name") or "").strip()]
    name = " ".join(p for p in parts if p)
    return name or str(user.get("username") or "").strip() or "Ученик"


def _login(provider: str, body: MessengerAuthBody) -> dict:
    bot_token = os.environ.get(_PROVIDERS[provider], "").strip()
    if not bot_token:
        raise HTTPException(503, {"code": "provider_not_configured", "provider": provider})
    user = validate_init_data(body.init_data, bot_token)
    provider_user_id = str(user["id"])
    conn = get_conn()
    link = conn.execute(
        "SELECT player_id FROM external_identities WHERE provider=? AND provider_user_id=?",
        (provider, provider_user_id),
    ).fetchone()
    if link is None:
        player = core.get_or_create_player(
            f"{provider}:{provider_user_id}", _display_name(user), "child",
        )
        conn.execute(
            "INSERT INTO external_identities (provider, provider_user_id, player_id, display_name)"
            " VALUES (?,?,?,?)",
            (provider, provider_user_id, player["id"], player["display_name"]),
        )
    else:
        conn.execute(
            "UPDATE external_identities SET display_name=?"
            " WHERE provider=? AND provider_user_id=?",
            (_display_name(user), provider, provider_user_id),
        )
        row = conn.execute(
            "SELECT external_key FROM players WHERE id=?", (link["player_id"],),
        ).fetchone()
        if row is None:
            raise HTTPException(401, {"code": "bad_init_data", "reason": "broken_link"})
        player = core.get_player(row["external_key"])
    token = auth.issue_session(player["id"])
    registered = service.is_registered(player["id"])
    prefill = None if registered else bridge.fetch_bot_prefill(provider, provider_user_id)
    return {**player, "token": token, "is_registered": registered, "prefill": prefill}


@router.post("/telegram")
def auth_telegram(body: MessengerAuthBody) -> dict:
    return _login("telegram", body)


@router.post("/max")
def auth_max(body: MessengerAuthBody) -> dict:
    return _login("max", body)
