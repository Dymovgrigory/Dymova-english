"""Домен регистрации: анкета, согласия, коды, пароль, вход.

Контакт родителя подтверждается одним из двух способов:
- email — код из письма (канал "email": браузер и MAX);
- telegram — нативный контакт через бота (канал "telegram").
Регистрация завершена, когда есть password_hash и подтверждён контакт
(email_verified_at или phone_verified_at). Один аккаунт на email/телефон.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from app.world import auth, core
from app.world.db import get_conn

from . import bridge, emailer
from .passwords import hash_password, verify_password
from .schemas import RegistrationStart, mask_email, mask_phone, normalize_phone

CONSENT_VERSION = "2026-09-19"
REQUIRED_CONSENTS = ("pd_child", "privacy")

CODE_TTL_MIN = 10
RESEND_COOLDOWN_SEC = 60
DAILY_CODE_LIMIT = 5
MAX_ATTEMPTS = 5
RESET_TOKEN_TTL_MIN = 30


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
        "email_verified": bool(row["email_verified_at"]),
        "email_verified_at": row["email_verified_at"],
        "verified": bool(row["phone_verified_at"] or row["email_verified_at"]),
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
        "SELECT parent_phone, parent_email FROM player_identity WHERE player_id=?",
        (player_id,),
    ).fetchone()
    phone_changed = old is not None and old["parent_phone"] != body.parent_phone
    email_changed = old is not None and old["parent_email"] != body.parent_email
    pw_hash = hash_password(body.password)
    conn.execute(
        "INSERT INTO player_identity (player_id, first_name, last_name, birth_date,"
        " school_number, class_grade, class_letter, parent_email, parent_phone,"
        " phone_verified_at, password_hash) VALUES (?,?,?,?,?,?,?,?,?,NULL,?)"
        " ON CONFLICT(player_id) DO UPDATE SET"
        " first_name=excluded.first_name, last_name=excluded.last_name,"
        " birth_date=excluded.birth_date, school_number=excluded.school_number,"
        " class_grade=excluded.class_grade, class_letter=excluded.class_letter,"
        " parent_email=excluded.parent_email, parent_phone=excluded.parent_phone,"
        " password_hash=excluded.password_hash,"
        " updated_at=datetime('now')",
        (player_id, body.first_name, body.last_name, body.birth_date, body.school_number,
         body.class_grade, body.class_letter, body.parent_email, body.parent_phone, pw_hash),
    )
    if phone_changed:
        conn.execute(
            "UPDATE player_identity SET phone_verified_at=NULL WHERE player_id=?",
            (player_id,),
        )
    if email_changed:
        conn.execute(
            "UPDATE player_identity SET email_verified_at=NULL WHERE player_id=?",
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


def _email_rate_reason(player_id: int, email: str) -> str | None:
    """None если можно слать; иначе 'email_recently_sent' / 'email_daily_limit'."""
    conn = get_conn()
    row = conn.execute(
        "SELECT created_at FROM email_verifications WHERE player_id=?"
        " ORDER BY created_at DESC LIMIT 1",
        (player_id,),
    ).fetchone()
    if row and row["created_at"] > _ts(_now() - timedelta(seconds=RESEND_COOLDOWN_SEC)):
        return "email_recently_sent"
    day_ago = _ts(_now() - timedelta(hours=24))
    cnt = conn.execute(
        "SELECT COUNT(*) AS c FROM email_verifications WHERE email=? AND created_at>?",
        (email, day_ago),
    ).fetchone()["c"]
    if cnt >= DAILY_CODE_LIMIT:
        return "email_daily_limit"
    return None


def _check_email_rate_limits(player_id: int, email: str) -> None:
    reason = _email_rate_reason(player_id, email)
    if reason:
        raise core.Conflict(reason)


def _new_code(player_id: int, email: str, purpose: str) -> tuple[str, str]:
    """Создать код и запись верификации. Возвращает (code, verification_id)."""
    code = f"{secrets.randbelow(1000000):06d}"
    vid = uuid.uuid4().hex
    expires = _ts(_now() + timedelta(minutes=CODE_TTL_MIN))
    get_conn().execute(
        "INSERT INTO email_verifications (id, player_id, email, code_hash, purpose,"
        " expires_at) VALUES (?,?,?,?,?,?)",
        (vid, player_id, email, _code_hash(vid, code), purpose, expires),
    )
    return code, vid


def _send_code(email: str, purpose: str, code: str) -> None:
    provider = emailer.get_provider()
    try:
        provider.send_code(email, purpose, code)
    except emailer.ProviderError as exc:
        raise core.Conflict("provider_error") from exc


def _assert_contacts_free(player_id: int, phone: str | None, email: str | None) -> None:
    if phone:
        taken = _verified_player_by_phone(phone)
        if taken is not None and taken["player_id"] != player_id:
            raise core.Conflict("phone_taken")
    if email:
        taken_email = _verified_player_by_email(email)
        if taken_email is not None and taken_email["player_id"] != player_id:
            raise core.Conflict("email_taken")


def start_registration(external_key: str, body: RegistrationStart,
                       ip: str | None, user_agent: str | None) -> dict:
    _check_consents(body)
    player_id = _player_id(external_key)
    _assert_contacts_free(player_id, body.parent_phone, body.parent_email)

    if body.channel == "email":
        _check_email_rate_limits(player_id, body.parent_email)

    upsert_identity(player_id, body)
    record_consents(player_id, body.consents, ip, user_agent)

    if body.channel == "telegram":
        return {
            "status": "awaiting_bot",
            "channel": "telegram",
            "phone_masked": mask_phone(body.parent_phone),
            "cooldown_sec": 0,
        }

    code, _vid = _new_code(player_id, body.parent_email, "registration")
    _send_code(body.parent_email, "registration", code)
    out = {
        "status": "code_sent",
        "channel": "email",
        "email_masked": mask_email(body.parent_email),
        "cooldown_sec": RESEND_COOLDOWN_SEC,
    }
    if not emailer.verification_required():
        out["dev_code"] = code
    return out


def _pending(player_id: int, purpose: str = "registration"):
    return get_conn().execute(
        "SELECT * FROM email_verifications WHERE player_id=? AND purpose=?"
        " AND verified_at IS NULL ORDER BY created_at DESC LIMIT 1",
        (player_id, purpose),
    ).fetchone()


def _check_code(row, code: str) -> None:
    """Общая проверка кода: срок, попытки, сверка хэша. Conflict при ошибке."""
    now = _now()
    if row["expires_at"] < _ts(now):
        raise core.Conflict("code_expired")
    if row["attempts"] >= MAX_ATTEMPTS:
        raise core.Conflict("too_many_attempts")
    conn = get_conn()
    if not secrets.compare_digest(row["code_hash"], _code_hash(row["id"], code)):
        conn.execute(
            "UPDATE email_verifications SET attempts=attempts+1 WHERE id=?",
            (row["id"],),
        )
        left = MAX_ATTEMPTS - row["attempts"] - 1
        raise core.Conflict(f"code_invalid|{left}")
    conn.execute(
        "UPDATE email_verifications SET verified_at=? WHERE id=?",
        (_ts(now), row["id"]),
    )


def verify_code(external_key: str, code: str) -> dict:
    player_id = _player_id(external_key)
    row = _pending(player_id)
    if row is None:
        raise core.Conflict("no_pending_verification")
    _check_code(row, code)
    get_conn().execute(
        "UPDATE player_identity SET email_verified_at=?, updated_at=datetime('now')"
        " WHERE player_id=?",
        (_ts(_now()), player_id),
    )
    return _session_after_verify(player_id)


def is_registered(player_id: int) -> bool:
    """Анкета + подтверждённый контакт (email-код или Telegram).

    Legacy: контакт подтвердили до появления паролей — гейт всё равно пропускает
    (password_hash может быть NULL).
    """
    row = get_conn().execute(
        "SELECT phone_verified_at, email_verified_at, password_hash"
        " FROM player_identity WHERE player_id=?",
        (player_id,),
    ).fetchone()
    if not row:
        return False
    return bool(row["phone_verified_at"] or row["email_verified_at"])


def _verified_player_by_phone(phone: str):
    """Зарегистрированный игрок с этим телефоном родителя (канонический аккаунт)."""
    return get_conn().execute(
        "SELECT player_id, parent_email FROM player_identity"
        " WHERE parent_phone=?"
        " AND (phone_verified_at IS NOT NULL OR email_verified_at IS NOT NULL)"
        " ORDER BY updated_at DESC LIMIT 1",
        (phone,),
    ).fetchone()


def _verified_player_by_email(email: str):
    """Зарегистрированный игрок с этим email родителя."""
    return get_conn().execute(
        "SELECT player_id, parent_email, parent_phone FROM player_identity"
        " WHERE parent_email=?"
        " AND (phone_verified_at IS NOT NULL OR email_verified_at IS NOT NULL)"
        " ORDER BY updated_at DESC LIMIT 1",
        (email,),
    ).fetchone()


def _merge_into(donor_id: int, keeper_id: int) -> None:
    """Переносит привязки мессенджера с donor на keeper; анкету donor снимает."""
    if donor_id == keeper_id:
        return
    conn = get_conn()
    links = conn.execute(
        "SELECT provider, provider_user_id, display_name FROM external_identities"
        " WHERE player_id=?",
        (donor_id,),
    ).fetchall()
    for link in links:
        conn.execute(
            "DELETE FROM external_identities WHERE provider=? AND provider_user_id=?",
            (link["provider"], link["provider_user_id"]),
        )
        conn.execute(
            "INSERT INTO external_identities (provider, provider_user_id, player_id, display_name)"
            " VALUES (?,?,?,?)",
            (link["provider"], link["provider_user_id"], keeper_id, link["display_name"]),
        )
    # Если у keeper нет пароля — забрать с donor.
    keeper = conn.execute(
        "SELECT password_hash FROM player_identity WHERE player_id=?", (keeper_id,)
    ).fetchone()
    donor = conn.execute(
        "SELECT password_hash FROM player_identity WHERE player_id=?", (donor_id,)
    ).fetchone()
    if keeper and donor and not keeper["password_hash"] and donor["password_hash"]:
        conn.execute(
            "UPDATE player_identity SET password_hash=? WHERE player_id=?",
            (donor["password_hash"], keeper_id),
        )
    conn.execute("DELETE FROM player_identity WHERE player_id=?", (donor_id,))
    conn.execute("DELETE FROM consents WHERE player_id=?", (donor_id,))
    conn.execute(
        "DELETE FROM email_verifications WHERE player_id=? AND verified_at IS NULL",
        (donor_id,),
    )


def _session_payload(player_id: int, status: str) -> dict:
    player = get_conn().execute(
        "SELECT external_key, display_name FROM players WHERE id=?",
        (player_id,),
    ).fetchone()
    if player is None:
        raise core.Conflict("no_pending_verification")
    return {
        "status": status,
        "token": auth.issue_session(player_id),
        "external_key": player["external_key"],
        "display_name": player["display_name"],
    }


def _session_after_verify(player_id: int) -> dict:
    """После подтверждения: склейка по телефону или email; сессия канонического игрока."""
    conn = get_conn()
    ident = conn.execute(
        "SELECT parent_phone, parent_email FROM player_identity WHERE player_id=?",
        (player_id,),
    ).fetchone()
    target_id = player_id
    if ident:
        other = None
        if ident["parent_phone"]:
            other = _verified_player_by_phone(ident["parent_phone"])
        if (other is None or other["player_id"] == player_id) and ident["parent_email"]:
            other = _verified_player_by_email(ident["parent_email"])
        if other is not None and other["player_id"] != player_id:
            _merge_into(player_id, other["player_id"])
            target_id = other["player_id"]
    return _session_payload(target_id, "verified")


def confirm_via_bot(external_key: str) -> dict:
    """Подтверждение телефона через бота; email тоже помечаем verified (TG-доказательство)."""
    player_id = _player_id(external_key)
    conn = get_conn()
    identity = conn.execute(
        "SELECT parent_phone, phone_verified_at, email_verified_at"
        " FROM player_identity WHERE player_id=?",
        (player_id,),
    ).fetchone()
    if identity is None:
        raise core.Conflict("no_pending_verification")
    if identity["phone_verified_at"] or identity["email_verified_at"]:
        return _session_after_verify(player_id)
    _assert_contacts_free(player_id, identity["parent_phone"], None)
    link = conn.execute(
        "SELECT provider_user_id FROM external_identities"
        " WHERE player_id=? AND provider='telegram'",
        (player_id,),
    ).fetchone()
    if link is None:
        raise core.Conflict("no_telegram_link")
    prefill = bridge.fetch_bot_prefill("telegram", link["provider_user_id"])
    lead_phone = (prefill or {}).get("phone") or ""
    if not lead_phone or (prefill or {}).get("phone_confirmed") is not True:
        raise core.Conflict("bot_phone_unconfirmed")
    try:
        bot_phone = normalize_phone(lead_phone)
    except ValueError:
        raise core.Conflict("bot_phone_unconfirmed") from None
    if bot_phone != identity["parent_phone"]:
        raise core.Conflict("phone_mismatch")
    now = _ts(_now())
    conn.execute(
        "UPDATE player_identity SET phone_verified_at=?, email_verified_at=?,"
        " updated_at=datetime('now') WHERE player_id=?",
        (now, now, player_id),
    )
    return _session_after_verify(player_id)


def _player_by_email(email: str):
    """Игрок по email родителя из анкеты (последний обновлённый)."""
    return get_conn().execute(
        "SELECT player_id FROM player_identity WHERE parent_email=?"
        " ORDER BY updated_at DESC LIMIT 1",
        (email,),
    ).fetchone()


def login(email: str, password: str) -> dict:
    """Вход в браузере: email + пароль → сессия."""
    row = _verified_player_by_email(email)
    if row is None:
        # Незавершённая анкета с этим email — тоже не пускаем с деталями.
        pending = _player_by_email(email)
        if pending is not None:
            ident = get_conn().execute(
                "SELECT password_hash, phone_verified_at, email_verified_at"
                " FROM player_identity WHERE player_id=?",
                (pending["player_id"],),
            ).fetchone()
            if ident and ident["password_hash"] and not (
                ident["phone_verified_at"] or ident["email_verified_at"]
            ):
                raise core.Conflict("email_not_verified")
        raise core.Conflict("bad_credentials")
    ident = get_conn().execute(
        "SELECT password_hash FROM player_identity WHERE player_id=?",
        (row["player_id"],),
    ).fetchone()
    if not ident or not ident["password_hash"]:
        raise core.Conflict("bad_credentials")
    if not verify_password(password, ident["password_hash"]):
        raise core.Conflict("bad_credentials")
    return _session_payload(row["player_id"], "ok")


def _resolve_recovery_owner(email: str | None, phone: str | None):
    """Найти зарегистрированного владельца по телефону или email. (row, lookup_email)."""
    row = None
    lookup_email = email
    if phone:
        row = _verified_player_by_phone(phone)
        if row is not None:
            lookup_email = row["parent_email"]
    if row is None and lookup_email:
        found = _player_by_email(lookup_email)
        if found is not None and is_registered(found["player_id"]):
            row = get_conn().execute(
                "SELECT player_id, parent_email FROM player_identity WHERE player_id=?",
                (found["player_id"],),
            ).fetchone()
            lookup_email = row["parent_email"] if row else lookup_email
    return row, lookup_email


def recovery_start(email: str | None, phone: str | None,
                   ip: str | None, user_agent: str | None) -> dict:
    """Код восстановления на email из анкеты (по email и/или телефону)."""
    _ = (ip, user_agent)  # reserved for audit trail
    row, lookup_email = _resolve_recovery_owner(email, phone)

    masked_email = mask_email(lookup_email) if lookup_email else "***"
    base: dict = {"status": "code_sent", "email_masked": masked_email}
    if phone:
        base["phone_masked"] = mask_phone(phone)

    if row is None or not lookup_email:
        return base

    player_id = row["player_id"]
    if _email_rate_reason(player_id, lookup_email):
        return base

    code, _vid = _new_code(player_id, lookup_email, "recovery")
    _send_code(lookup_email, "recovery", code)
    if not emailer.verification_required():
        base["dev_code"] = code
    return base


def recovery_verify(email: str | None, phone: str | None, code: str) -> dict:
    """Код из письма верен → reset_token для задания нового пароля (сессию ещё не даём)."""
    lookup_email = email
    if phone and not lookup_email:
        owner = _verified_player_by_phone(phone)
        if owner is None:
            raise core.Conflict("no_pending_verification")
        lookup_email = owner["parent_email"]
    if not lookup_email:
        raise core.Conflict("no_pending_verification")
    row = get_conn().execute(
        "SELECT * FROM email_verifications WHERE email=? AND purpose='recovery'"
        " AND verified_at IS NULL ORDER BY created_at DESC LIMIT 1",
        (lookup_email,),
    ).fetchone()
    if row is None:
        raise core.Conflict("no_pending_verification")
    _check_code(row, code)
    return {
        "status": "code_ok",
        "reset_token": row["id"],
        "email_masked": mask_email(lookup_email),
    }


def recovery_set_password(reset_token: str, password: str) -> dict:
    """После кода: новый пароль → сессия."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM email_verifications WHERE id=? AND purpose='recovery'"
        " AND verified_at IS NOT NULL",
        (reset_token,),
    ).fetchone()
    if row is None:
        raise core.Conflict("no_pending_verification")
    if row["verified_at"] < _ts(_now() - timedelta(minutes=RESET_TOKEN_TTL_MIN)):
        raise core.Conflict("code_expired")
    conn.execute(
        "UPDATE player_identity SET password_hash=?, updated_at=datetime('now')"
        " WHERE player_id=?",
        (hash_password(password), row["player_id"]),
    )
    conn.execute("DELETE FROM email_verifications WHERE id=?", (reset_token,))
    return _session_payload(row["player_id"], "verified")


def get_status(external_key: str) -> dict:
    player_id = _player_id(external_key)
    return {
        "identity": get_identity(player_id),
        "consents": list_consents(player_id),
        "is_registered": is_registered(player_id),
    }
