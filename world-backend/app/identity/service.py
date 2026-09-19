"""Домен регистрации: анкета, согласия (append-only), коды подтверждения."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from app.world import core
from app.world.db import get_conn

from . import sms
from .schemas import RegistrationStart, mask_phone

CONSENT_VERSION = "2026-09-19"
REQUIRED_CONSENTS = ("pd_child", "privacy")

CODE_TTL_MIN = 10
RESEND_COOLDOWN_SEC = 60
DAILY_CODE_LIMIT = 5
MAX_ATTEMPTS = 5


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _code_hash(salt: str, code: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()


def _player_id(external_key: str) -> int:
    return core.get_or_create_player(external_key)["id"]


def _row_to_identity(row) -> dict:
    return {
        "player_id": row["player_id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "birth_date": row["birth_date"],
        "school_number": row["school_number"],
        "class_grade": row["class_grade"],
        "class_letter": row["class_letter"],
        "parent_email": row["parent_email"],
        "parent_phone_masked": mask_phone(row["parent_phone"]),
        "phone_verified": bool(row["phone_verified_at"]),
        "phone_verified_at": row["phone_verified_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_identity(player_id: int) -> dict | None:
    row = get_conn().execute(
        "SELECT * FROM player_identity WHERE player_id=?", (player_id,)
    ).fetchone()
    return _row_to_identity(row) if row else None


def upsert_identity(player_id: int, body: RegistrationStart) -> None:
    conn = get_conn()
    old = conn.execute(
        "SELECT parent_phone FROM player_identity WHERE player_id=?", (player_id,)
    ).fetchone()
    phone_changed = old is not None and old["parent_phone"] != body.parent_phone
    conn.execute(
        "INSERT INTO player_identity (player_id, first_name, last_name, birth_date,"
        " school_number, class_grade, class_letter, parent_email, parent_phone,"
        " phone_verified_at) VALUES (?,?,?,?,?,?,?,?,?, NULL)"
        " ON CONFLICT(player_id) DO UPDATE SET"
        " first_name=excluded.first_name, last_name=excluded.last_name,"
        " birth_date=excluded.birth_date, school_number=excluded.school_number,"
        " class_grade=excluded.class_grade, class_letter=excluded.class_letter,"
        " parent_email=excluded.parent_email, parent_phone=excluded.parent_phone,"
        " updated_at=datetime('now')",
        (player_id, body.first_name, body.last_name, body.birth_date, body.school_number,
         body.class_grade, body.class_letter, body.parent_email, body.parent_phone),
    )
    if phone_changed:
        conn.execute(
            "UPDATE player_identity SET phone_verified_at=NULL WHERE player_id=?",
            (player_id,),
        )


def record_consents(player_id: int, consents, ip: str | None, user_agent: str | None) -> None:
    conn = get_conn()
    for c in consents:
        conn.execute(
            "INSERT INTO consents (player_id, type, version, ip, user_agent)"
            " VALUES (?,?,?,?,?)",
            (player_id, c.type, c.version, ip, user_agent),
        )


def list_consents(player_id: int) -> list[dict]:
    rows = get_conn().execute(
        "SELECT type, version, accepted_at FROM consents WHERE player_id=?"
        " ORDER BY id",
        (player_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _check_consents(body: RegistrationStart) -> None:
    got = {c.type: c.version for c in body.consents}
    for t in REQUIRED_CONSENTS:
        if got.get(t) != CONSENT_VERSION:
            raise core.Conflict(f"consent_required:{t}")


def _check_rate_limits(player_id: int, phone: str) -> None:
    conn = get_conn()
    row = conn.execute(
        "SELECT created_at FROM phone_verifications WHERE player_id=?"
        " ORDER BY created_at DESC LIMIT 1",
        (player_id,),
    ).fetchone()
    if row and row["created_at"] > _ts(_now() - timedelta(seconds=RESEND_COOLDOWN_SEC)):
        raise core.Conflict("phone_recently_sent")
    day_ago = _ts(_now() - timedelta(hours=24))
    cnt = conn.execute(
        "SELECT COUNT(*) AS c FROM phone_verifications WHERE phone=? AND created_at>?",
        (phone, day_ago),
    ).fetchone()["c"]
    if cnt >= DAILY_CODE_LIMIT:
        raise core.Conflict("phone_daily_limit")


def start_registration(external_key: str, body: RegistrationStart,
                       ip: str | None, user_agent: str | None) -> dict:
    _check_consents(body)
    player_id = _player_id(external_key)
    _check_rate_limits(player_id, body.parent_phone)

    upsert_identity(player_id, body)
    record_consents(player_id, body.consents, ip, user_agent)

    code = f"{secrets.randbelow(1000000):06d}"
    vid = uuid.uuid4().hex
    expires = _ts(_now() + timedelta(minutes=CODE_TTL_MIN))
    provider = sms.get_provider()
    try:
        provider_id = provider.send_code(body.parent_phone, body.channel, code)
    except sms.ProviderError as exc:
        raise core.Conflict("provider_error") from exc  # маппится в 502 на API-слое
    get_conn().execute(
        "INSERT INTO phone_verifications (id, player_id, phone, code_hash, channel,"
        " expires_at, provider_id) VALUES (?,?,?,?,?,?,?)",
        (vid, player_id, body.parent_phone, _code_hash(vid, code), body.channel,
         expires, provider_id),
    )
    out = {
        "status": "code_sent",
        "channel": body.channel,
        "phone_masked": mask_phone(body.parent_phone),
        "cooldown_sec": RESEND_COOLDOWN_SEC,
    }
    if not sms.verification_required():
        out["dev_code"] = code
    return out


def _pending(player_id: int):
    return get_conn().execute(
        "SELECT * FROM phone_verifications WHERE player_id=? AND verified_at IS NULL"
        " ORDER BY created_at DESC LIMIT 1",
        (player_id,),
    ).fetchone()


def verify_code(external_key: str, code: str) -> dict:
    player_id = _player_id(external_key)
    row = _pending(player_id)
    if row is None:
        raise core.Conflict("no_pending_verification")
    now = _now()
    if row["expires_at"] < _ts(now):
        raise core.Conflict("code_expired")
    if row["attempts"] >= MAX_ATTEMPTS:
        raise core.Conflict("too_many_attempts")
    conn = get_conn()
    if not secrets.compare_digest(row["code_hash"], _code_hash(row["id"], code)):
        conn.execute(
            "UPDATE phone_verifications SET attempts=attempts+1 WHERE id=?",
            (row["id"],),
        )
        left = MAX_ATTEMPTS - row["attempts"] - 1
        raise core.Conflict(f"code_invalid|{left}")  # расщепляется на API-слое
    conn.execute(
        "UPDATE phone_verifications SET verified_at=? WHERE id=?",
        (_ts(now), row["id"]),
    )
    conn.execute(
        "UPDATE player_identity SET phone_verified_at=?, updated_at=datetime('now')"
        " WHERE player_id=?",
        (_ts(now), player_id),
    )
    return {"status": "verified"}


def is_registered(player_id: int) -> bool:
    """Регистрация завершена: анкета и согласия записаны на /start,
    телефон подтверждён на /verify (в fake-режиме — dev_code с клиента)."""
    row = get_conn().execute(
        "SELECT phone_verified_at FROM player_identity WHERE player_id=?",
        (player_id,),
    ).fetchone()
    return bool(row and row["phone_verified_at"])


def get_status(external_key: str) -> dict:
    player_id = _player_id(external_key)
    return {
        "identity": get_identity(player_id),
        "consents": list_consents(player_id),
        "is_registered": is_registered(player_id),
    }
