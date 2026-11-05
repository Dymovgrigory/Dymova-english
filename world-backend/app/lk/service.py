"""Домен ЛК: аккаунт родителя, подтверждение телефона через ботов, профили детей.

Поток (ТЗ §7, решения владельца 2026-11-02):
1. Родитель вводит телефон + имя на сайте → pending-аккаунт, экран ожидания.
2. Родитель в боте MAX или Telegram делится нативным контактом → бот ставит
   lead.phone_confirmed (замена SMS-коду, механика из Мира, сессия 131).
3. «Проверить» на сайте → мост phone-status → номер совпал → аккаунт active,
   выпускается сессия, по номеру из BigBen собираются профили детей.
4. Номера нет в CRM → гостевой профиль (Мир, словари, рейтинги).
"""
from __future__ import annotations

import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from app.world import core
from app.world.db import get_conn

from . import bigben, bridge
from app.identity.schemas import mask_phone

log = logging.getLogger("world.lk.service")

CONSENT_VERSION = "2026-11-02"
REQUIRED_CONSENTS = ("pd_child", "privacy")

SESSION_TTL_DAYS = 30
START_COOLDOWN_SEC = 60
START_DAILY_LIMIT = 10
CONFIRM_MAX_ATTEMPTS = 5

BOT_LINKS = {
    "max": "https://max.ru/id611904726658_bot",
    "telegram": "https://t.me/foxinburg",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _check_consents(consents) -> None:
    got = {c.type: c.version for c in consents}
    for t in REQUIRED_CONSENTS:
        if got.get(t) != CONSENT_VERSION:
            raise core.Conflict(f"consent_required:{t}")


def _account_by_phone(phone: str):
    return get_conn().execute(
        "SELECT * FROM lk_accounts WHERE phone=?", (phone,)
    ).fetchone()


def _rate_reason(phone: str) -> str | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT created_at FROM lk_auth_attempts WHERE phone=?"
        " ORDER BY created_at DESC LIMIT 1",
        (phone,),
    ).fetchone()
    if row and row["created_at"] > _ts(_now() - timedelta(seconds=START_COOLDOWN_SEC)):
        return "recently_sent"
    day_ago = _ts(_now() - timedelta(hours=24))
    cnt = conn.execute(
        "SELECT COUNT(*) AS c FROM lk_auth_attempts WHERE phone=? AND created_at>?",
        (phone, day_ago),
    ).fetchone()["c"]
    if cnt >= START_DAILY_LIMIT:
        return "daily_limit"
    return None


def _record_attempt(phone: str, kind: str) -> None:
    get_conn().execute(
        "INSERT INTO lk_auth_attempts (phone, kind) VALUES (?,?)", (phone, kind)
    )


def start_auth(phone: str, parent_name: str, consents, ip: str | None,
               user_agent: str | None) -> dict:
    """Старт регистрации/повторного входа: pending-аккаунт + ссылки на ботов."""
    from app.identity.schemas import normalize_phone

    phone = normalize_phone(phone)  # defense-in-depth: схема тоже нормализует
    _check_consents(consents)
    _ = (ip, user_agent)  # reserved для аудит-лога
    reason = _rate_reason(phone)
    if reason:
        raise core.Conflict(reason)
    _record_attempt(phone, "start")

    conn = get_conn()
    existing = _account_by_phone(phone)
    if existing is None:
        conn.execute(
            "INSERT INTO lk_accounts (phone, parent_name) VALUES (?,?)",
            (phone, parent_name),
        )
    else:
        # Повторный вход: обновляем имя, но не трогаем подтверждение.
        conn.execute(
            "UPDATE lk_accounts SET parent_name=?, updated_at=datetime('now')"
            " WHERE phone=?",
            (parent_name, phone),
        )
    return {
        "status": "awaiting_bot",
        "phone_masked": mask_phone(phone),
        "bot_links": dict(BOT_LINKS),
        "cooldown_sec": START_COOLDOWN_SEC,
    }


def get_status(phone: str) -> dict:
    account = _account_by_phone(phone)
    if account is None:
        return {
            "status": "none",
            "phone_masked": mask_phone(phone),
            "phone_confirmed": False,
            "has_pending": False,
            "cooldown_sec": 0,
        }
    active = account["status"] == "active"
    return {
        "status": account["status"],
        "phone_masked": mask_phone(phone),
        "phone_confirmed": bool(account["phone_confirmed_at"]),
        "has_pending": not active,
        "cooldown_sec": 0,
    }


def _issue_session(account_id: int) -> tuple[str, str]:
    token = uuid.uuid4().hex + secrets.token_hex(16)
    expires = _ts(_now() + timedelta(days=SESSION_TTL_DAYS))
    get_conn().execute(
        "INSERT INTO lk_sessions (token, account_id, expires_at) VALUES (?,?,?)",
        (token, account_id, expires),
    )
    return token, expires


def _row_to_profile(row, group_names: dict[int, dict]) -> dict:
    groups_raw = row["active_groups_json"] or "[]"
    try:
        groups = json.loads(groups_raw)
    except ValueError:
        groups = []
    named = [group_names.get(g.get("id"), g) for g in groups if isinstance(g, dict)]
    return {
        "id": row["id"],
        "student_id": row["student_id"],
        "child_name": row["child_name"],
        "source": row["source"],
        "active_groups": named,
    }


def _sync_profiles(account, *, force: bool = False) -> list[dict]:
    """Профили детей аккаунта по BigBen; гостевой профиль, если номера нет в CRM."""
    conn = get_conn()
    account_id = account["id"]
    # Детей из CRM показываем только при подтверждённом номере (бот или администратор):
    # самостоятельная регистрация с чужим номером не должна открывать чужого ребёнка.
    students: list[dict] = []
    if account["phone_confirmed_at"]:
        if bigben.configured():
            students = bigben.students_by_phone(account["phone"])
        # Пульт BigBen ищет и по телефону родителя и видит только что созданные карточки
        # (публичный список кэшируется на 15 минут) — объединяем.
        from . import bigben_internal
        if bigben_internal.configured():
            try:
                known = {int(s["id"]) for s in students}
                for st in bigben_internal.find_students_by_phone(account["phone"]):
                    if st.get("id") and int(st["id"]) not in known and not st.get("archived"):
                        students.append({"id": int(st["id"]), "fio": st.get("fio") or "Ученик", "active_groups": []})
            except bigben_internal.BigBenInternalError as exc:
                log.warning("sync_profiles: пульт BigBen недоступен: %s", exc)
            # Группы ученика для расписания: публичный API их не отдаёт — берём из карточки пульта.
            for st in students:
                if st.get("active_groups"):
                    continue
                try:
                    st["active_groups"] = bigben_internal.student_groups(int(st["id"]))
                except bigben_internal.BigBenInternalError as exc:
                    log.warning("sync_profiles: группы ученика %s не получены: %s", st.get("id"), exc)
    if students:
        for s in students:
            conn.execute(
                "INSERT INTO lk_profiles (account_id, student_id, child_name, source,"
                " active_groups_json) VALUES (?,?,?,?,?)"
                " ON CONFLICT(account_id, student_id) DO UPDATE SET"
                " child_name=excluded.child_name,"
                " active_groups_json=excluded.active_groups_json",
                (account_id, s["id"], s.get("fio") or "Ученик", "crm",
                 _json(s.get("active_groups") or [])),
            )
        conn.execute(
            "DELETE FROM lk_profiles WHERE account_id=? AND source='crm'"
            " AND student_id NOT IN (%s)"
            % ",".join("?" for _ in students),
            (account_id, *[s["id"] for s in students]),
        )
    else:
        row = conn.execute(
            "SELECT id FROM lk_profiles WHERE account_id=? AND source='guest'",
            (account_id,),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO lk_profiles (account_id, student_id, child_name, source)"
                " VALUES (?,NULL,'Гостевой профиль','guest')",
                (account_id,),
            )
    rows = conn.execute(
        "SELECT * FROM lk_profiles WHERE account_id=? ORDER BY id", (account_id,)
    ).fetchall()
    group_ids: set[int] = set()
    for r in rows:
        try:
            for g in json.loads(r["active_groups_json"] or "[]"):
                if isinstance(g, dict) and g.get("id"):
                    group_ids.add(int(g["id"]))
        except ValueError:
            pass
    group_names = bigben.groups_by_ids(group_ids) if bigben.configured() else {}
    return [_row_to_profile(r, group_names) for r in rows]


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def confirm_via_bot(phone: str) -> dict:
    """Подтверждение: бот засвидетельствовал владение номером → сессия + профили."""
    account = _account_by_phone(phone)
    if account is None:
        raise core.Conflict("no_pending")
    if account["status"] == "active":
        token, expires = _issue_session(account["id"])
        return {
            "status": "already_active",
            "token": token,
            "token_expires_at": expires,
            "profiles": _sync_profiles(account),
            "guest": _is_guest(account["id"]),
            "phone_masked": mask_phone(phone),
        }

    attempts = account["confirm_attempts"] or 0
    if attempts >= CONFIRM_MAX_ATTEMPTS:
        raise core.Conflict("too_many_attempts")
    _record_attempt(phone, "confirm")
    get_conn().execute(
        "UPDATE lk_accounts SET confirm_attempts=confirm_attempts+1 WHERE id=?",
        (account["id"],),
    )

    confirmed, _providers = bridge.phone_confirmed(phone)
    if not confirmed:
        raise core.Conflict("bot_phone_unconfirmed")

    get_conn().execute(
        "UPDATE lk_accounts SET status='active', phone_confirmed_at=?,"
        " confirm_attempts=0, updated_at=datetime('now') WHERE id=?",
        (_ts(_now()), account["id"]),
    )
    account = _account_by_phone(phone)
    token, expires = _issue_session(account["id"])
    profiles = _sync_profiles(account)
    return {
        "status": "verified",
        "token": token,
        "token_expires_at": expires,
        "profiles": profiles,
        "guest": all(p["source"] == "guest" for p in profiles),
        "phone_masked": mask_phone(phone),
    }


def _is_guest(account_id: int) -> bool:
    rows = get_conn().execute(
        "SELECT source FROM lk_profiles WHERE account_id=?", (account_id,)
    ).fetchall()
    return bool(rows) and all(r["source"] == "guest" for r in rows)


def resolve_session(token: str) -> dict | None:
    """Аккаунт по токену (None — невалиден/протух)."""
    row = get_conn().execute(
        "SELECT * FROM lk_sessions WHERE token=? AND revoked_at IS NULL",
        (token,),
    ).fetchone()
    if row is None:
        return None
    if row["expires_at"] < _ts(_now()):
        return None
    account = get_conn().execute(
        "SELECT * FROM lk_accounts WHERE id=?", (row["account_id"],)
    ).fetchone()
    if account is None or account["status"] != "active":
        return None
    return account


def me(token: str) -> dict:
    account = resolve_session(token)
    if account is None:
        raise core.Conflict("unauthorized")
    profiles = _sync_profiles(account)
    return {
        "account": {
            "id": account["id"],
            "parent_name": account["parent_name"],
            "phone_masked": mask_phone(account["phone"]),
            "status": account["status"],
            "guest": all(p["source"] == "guest" for p in profiles),
        },
        "profiles": profiles,
    }


def logout(token: str) -> dict:
    get_conn().execute(
        "UPDATE lk_sessions SET revoked_at=datetime('now') WHERE token=?",
        (token,),
    )
    return {"status": "ok"}


# ---------- Этап 2: расписание и посещаемость ----------

ATTENDANCE_STATUSES = ("visited", "missed", "unknown")


def _account_profile(account_id: int, student_id: int):
    return get_conn().execute(
        "SELECT * FROM lk_profiles WHERE account_id=? AND student_id=?",
        (account_id, student_id),
    ).fetchone()


def schedule(token: str, student_id: int, date_from: str, date_to: str) -> dict:
    """Расписание ребёнка: занятия групп ученика за окно дат + отметки.

    Расписание — мастер BigBen (ТЗ §3): фильтруем занятия по активным группам
    профиля. Педагоги/темы в публичном API отсутствуют — отдаём группу и филиал.
    """
    from datetime import date as _date

    account = resolve_session(token)
    if account is None:
        raise core.Conflict("unauthorized")
    try:
        _date.fromisoformat(date_from)
        _date.fromisoformat(date_to)
    except ValueError:
        raise core.Conflict("bad_dates") from None
    if date_from > date_to:
        raise core.Conflict("bad_dates")
    from datetime import date as _d

    if (_d.fromisoformat(date_to) - _d.fromisoformat(date_from)).days > 62:
        raise core.Conflict("window_too_large")

    profile = _account_profile(account["id"], student_id)
    if profile is None:
        raise core.Conflict("profile_not_found")
    group_ids = _student_group_ids(profile)

    lessons = [
        l for l in bigben.lessons(date_from, date_to)
        if (l.get("group") or {}).get("id") in group_ids
    ]
    lessons.sort(key=lambda l: (l.get("date") or "", l.get("starts_at") or ""))

    lesson_ids = [l["id"] for l in lessons]
    marks: dict[int, str] = {}
    if lesson_ids:
        marks = _attendance_map(student_id, lesson_ids)

    return {
        "student_id": student_id,
        "child_name": profile["child_name"],
        "from": date_from,
        "to": date_to,
        "lessons": [
            {
                "id": l["id"],
                "date": l.get("date"),
                "starts_at": l.get("starts_at"),
                "ends_at": l.get("ends_at"),
                "group": l.get("group") or {},
                "filial": l.get("filial") or {},
                "attendance": marks.get(l["id"], "unknown"),
            }
            for l in lessons
        ],
    }


def _student_group_ids(profile) -> set[int]:
    """Группы ученика: из active_groups профиля (если CRM их отдаёт) + из
    вебхуков зачисления (lk_group_members) — публичный API BigBen их не отдаёт."""
    ids: set[int] = set()
    try:
        groups = json.loads(profile["active_groups_json"] or "[]")
    except ValueError:
        groups = []
    for g in groups:
        if isinstance(g, dict) and g.get("id"):
            ids.add(int(g["id"]))
    rows = get_conn().execute(
        "SELECT group_id FROM lk_group_members"
        " WHERE student_id=? AND status='active'",
        (profile["student_id"],),
    ).fetchall()
    ids.update(int(r["group_id"]) for r in rows)
    return ids


def record_membership(student_id: int, group_id: int, group_caption: str = "",
                      status: str = "active", source: str = "webhook",
                      raw: dict | None = None) -> None:
    if status not in ("active", "left"):
        raise core.Conflict("bad_status")
    get_conn().execute(
        "INSERT INTO lk_group_members (student_id, group_id, group_caption,"
        " status, source, raw_json) VALUES (?,?,?,?,?,?)"
        " ON CONFLICT(student_id, group_id) DO UPDATE SET"
        " group_caption=excluded.group_caption, status=excluded.status,"
        " source=excluded.source, raw_json=excluded.raw_json,"
        " updated_at=datetime('now')",
        (student_id, group_id, group_caption, status, source,
         json.dumps(raw or {}, ensure_ascii=False)),
    )


def _membership_sign(secret: str, student_id: int, group_id: int, status: str,
                     ts: int) -> str:
    import hashlib
    import hmac

    msg = f"{student_id}\n{group_id}\n{status}\n{ts}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def ingest_membership(body: dict) -> dict:
    """Приём зачисления/отчисления из вебхука group.enrolled (relay бота)."""
    import os
    import time as _time

    secret = os.environ.get("WORLD_BRIDGE_SECRET", "").strip()
    if not secret:
        raise core.Conflict("relay_disabled")
    student_id = int(body.get("student_id") or 0)
    group_id = int(body.get("group_id") or 0)
    status = str(body.get("status") or "active")
    ts = int(body.get("ts") or 0)
    sign = str(body.get("sign") or "")
    if not student_id or not group_id or status not in ("active", "left"):
        raise core.Conflict("bad_payload")
    if abs(_time.time() - ts) > 300:
        raise core.Conflict("stale")
    import secrets as _secrets

    expected = _membership_sign(secret, student_id, group_id, status, ts)
    if not _secrets.compare_digest(expected, sign):
        raise core.Conflict("bad_signature")
    record_membership(student_id, group_id,
                      str(body.get("group_caption") or ""),
                      status=status, source="bot-relay",
                      raw=body.get("raw") if isinstance(body.get("raw"), dict) else None)
    return {"status": "ok"}


def _attendance_map(student_id: int, lesson_ids: list[int]) -> dict[int, str]:
    placeholders = ",".join("?" for _ in lesson_ids)
    rows = get_conn().execute(
        f"SELECT lesson_id, status FROM lk_attendance"
        f" WHERE student_id=? AND lesson_id IN ({placeholders})",
        (student_id, *lesson_ids),
    ).fetchall()
    return {int(r["lesson_id"]): r["status"] for r in rows}


def record_attendance(student_id: int, lesson_id: int, status: str,
                      source: str = "webhook", raw: dict | None = None) -> None:
    if status not in ATTENDANCE_STATUSES:
        raise core.Conflict("bad_status")
    get_conn().execute(
        "INSERT INTO lk_attendance (student_id, lesson_id, status, source, raw_json)"
        " VALUES (?,?,?,?,?)"
        " ON CONFLICT(student_id, lesson_id) DO UPDATE SET"
        " status=excluded.status, source=excluded.source,"
        " raw_json=excluded.raw_json, updated_at=datetime('now')",
        (student_id, lesson_id, status, source, json.dumps(raw or {}, ensure_ascii=False)),
    )


def _attendance_sign(secret: str, student_id: int, lesson_id: int, status: str,
                     ts: int) -> str:
    import hashlib
    import hmac

    msg = f"{student_id}\n{lesson_id}\n{status}\n{ts}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def ingest_attendance(body: dict) -> dict:
    """Приём отметки посещаемости от бота (relay вебхука lesson.completed).

    Подпись HMAC(World_BRIDGE-секрет) — тот же секрет, что у моста бота↔мир;
    внутри общей docker-сети, наружу эндпоинт не светится.
    """
    import os
    import time as _time

    secret = os.environ.get("WORLD_BRIDGE_SECRET", "").strip()
    if not secret:
        raise core.Conflict("relay_disabled")
    student_id = int(body.get("student_id") or 0)
    lesson_id = int(body.get("lesson_id") or 0)
    status = str(body.get("status") or "")
    ts = int(body.get("ts") or 0)
    sign = str(body.get("sign") or "")
    if not student_id or not lesson_id or status not in ATTENDANCE_STATUSES:
        raise core.Conflict("bad_payload")
    if abs(_time.time() - ts) > 300:
        raise core.Conflict("stale")
    import secrets as _secrets

    expected = _attendance_sign(secret, student_id, lesson_id, status, ts)
    if not _secrets.compare_digest(expected, sign):
        raise core.Conflict("bad_signature")
    record_attendance(student_id, lesson_id, status, source="bot-relay",
                      raw=body.get("raw") if isinstance(body.get("raw"), dict) else None)
    return {"status": "ok"}
