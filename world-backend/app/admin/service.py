"""Домен админки: список учеников, карточка, корректировки, аудит."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from app.identity.schemas import IdentityPatch, mask_phone
from app.world import core
from app.world.db import get_conn

MAX_ADJUST = 100_000


def audit(actor: str, action: str, entity: str, payload: dict | None = None) -> None:
    get_conn().execute(
        "INSERT INTO admin_audit (actor, action, entity, payload) VALUES (?,?,?,?)",
        (actor, action, entity, json.dumps(payload or {}, ensure_ascii=False)),
    )


def _escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_students(q: str | None, class_grade: int | None, verified: str | None,
                  page: int, per_page: int) -> dict:
    where: list[str] = []
    params: list = []
    if q:
        like = f"%{_escape_like(q)}%"
        where.append(
            "(i.first_name LIKE ? ESCAPE '\\' OR i.last_name LIKE ? ESCAPE '\\'"
            " OR p.display_name LIKE ? ESCAPE '\\' OR i.parent_phone LIKE ? ESCAPE '\\'"
            " OR i.parent_email LIKE ? ESCAPE '\\' OR i.school_number LIKE ? ESCAPE '\\')"
        )
        params += [like] * 6
    if class_grade is not None:
        where.append("i.class_grade=?")
        params.append(class_grade)
    if verified == "true":
        where.append("i.phone_verified_at IS NOT NULL")
    elif verified == "false":
        where.append("i.phone_verified_at IS NULL")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    conn = get_conn()
    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM players p"
        f" LEFT JOIN player_identity i ON i.player_id=p.id {clause}",
        params,
    ).fetchone()["c"]
    rows = conn.execute(
        f"SELECT p.id, p.display_name, p.xp, p.coins, p.streak_days,"
        f" i.first_name, i.last_name, i.class_grade, i.school_number,"
        f" i.parent_phone, i.phone_verified_at,"
        f" (SELECT MAX(d.day) FROM daily_activity d WHERE d.player_id=p.id) AS last_active_day"
        f" FROM players p LEFT JOIN player_identity i ON i.player_id=p.id {clause}"
        f" ORDER BY COALESCE(i.updated_at, p.updated_at) DESC, p.id DESC"
        f" LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page],
    ).fetchall()
    items = [
        {
            "player_id": r["id"],
            "display_name": r["display_name"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "class_grade": r["class_grade"],
            "school_number": r["school_number"],
            "phone_masked": mask_phone(r["parent_phone"]) if r["parent_phone"] else None,
            "phone_verified": bool(r["phone_verified_at"]),
            "xp": r["xp"],
            "coins": r["coins"],
            "streak_days": r["streak_days"],
            "last_active_day": r["last_active_day"],
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def _player_row(player_id: int):
    row = get_conn().execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if row is None:
        raise core.NotFound("player_not_found")
    return row


def student_card(player_id: int) -> dict:
    conn = get_conn()
    row = _player_row(player_id)
    player = dict(row)
    from app.identity import service as identity_service

    identity = identity_service.get_identity(player_id)
    consents = identity_service.list_consents(player_id)
    identities = [
        dict(r)
        for r in conn.execute(
            "SELECT provider, provider_user_id, display_name, created_at"
            " FROM external_identities WHERE player_id=? ORDER BY created_at",
            (player_id,),
        ).fetchall()
    ]
    profile_row = conn.execute(
        "SELECT book_id, module_id, daily_goal_xp FROM learner_profile WHERE player_id=?",
        (player_id,),
    ).fetchone()
    titles = [
        dict(r)
        for r in conn.execute(
            "SELECT track, level, awarded_at, worn FROM titles WHERE player_id=?"
            " ORDER BY track",
            (player_id,),
        ).fetchall()
    ]
    weakest = [
        dict(r)
        for r in conn.execute(
            "SELECT atom_id, strength, wrong_count FROM atom_mastery WHERE player_id=?"
            " ORDER BY strength ASC, wrong_count DESC LIMIT 10",
            (player_id,),
        ).fetchall()
    ]
    mistakes = [
        {"unit_id": r["unit_id"], "item": r["item"]}
        for r in conn.execute(
            "SELECT unit_id, item FROM mistakes WHERE player_id=? AND cleared=0"
            " ORDER BY id DESC LIMIT 10",
            (player_id,),
        ).fetchall()
    ]
    daily = [
        dict(r)
        for r in conn.execute(
            "SELECT day, xp, sessions FROM daily_activity WHERE player_id=?"
            " ORDER BY day DESC LIMIT 14",
            (player_id,),
        ).fetchall()
    ]
    counters = {
        "inventory": conn.execute(
            "SELECT COUNT(*) AS c FROM inventory WHERE player_id=?", (player_id,)
        ).fetchone()["c"],
        "castle_owned": conn.execute(
            "SELECT COUNT(*) AS c FROM castle_owned WHERE player_id=?", (player_id,)
        ).fetchone()["c"],
        "sessions_total": conn.execute(
            "SELECT COUNT(*) AS c FROM learn_sessions WHERE player_id=?", (player_id,)
        ).fetchone()["c"],
    }
    return {
        "player": player,
        "identity": identity,
        "consents": consents,
        "identities": identities,
        "profile": dict(profile_row) if profile_row else None,
        "titles": titles,
        "weakest_atoms": weakest,
        "mistakes": mistakes,
        "daily_activity": daily,
        "counters": counters,
    }


def patch_identity(player_id: int, body: IdentityPatch, actor: str) -> dict:
    _player_row(player_id)
    fields = body.model_dump(exclude={"reason"}, exclude_none=True)
    if fields:
        conn = get_conn()
        sets = []
        params: list = []
        for name, value in fields.items():
            sets.append(f"{name}=?")
            params.append(value)
        if "parent_phone" in fields:
            sets.append("phone_verified_at=NULL")
        sets.append("updated_at=datetime('now')")
        cur = conn.execute(
            f"UPDATE player_identity SET {', '.join(sets)} WHERE player_id=?",
            params + [player_id],
        )
        if cur.rowcount == 0:
            raise core.NotFound("identity_not_found")
    audit(actor, "patch_identity", f"player:{player_id}",
          {"fields": sorted(fields), "reason": body.reason})
    from app.identity import service as identity_service

    return {"identity": identity_service.get_identity(player_id)}


def adjust(player_id: int, kind: str, delta: int, reason: str, actor: str) -> dict:
    row = _player_row(player_id)
    if abs(delta) > MAX_ADJUST:
        raise core.Conflict("delta_too_large")
    key = row["external_key"]
    idem = f"admin:{actor}:{uuid.uuid4().hex}"
    if kind == "coins":
        if delta > 0:
            core.award(key, coins=delta, source="admin", type_="ADMIN_ADJUST",
                       idempotency_key=idem)
        else:
            try:
                core.spend(key, coins=-delta, source="admin", type_="ADMIN_ADJUST",
                           idempotency_key=idem)
            except core.Conflict:
                raise core.Conflict("not_enough_coins")
    else:  # xp
        if delta < 0 and row["xp"] + delta < 0:
            raise core.Conflict("not_enough_xp")
        core.award(key, xp=delta, source="admin", type_="ADMIN_ADJUST",
                   idempotency_key=idem)
    audit(actor, "adjust", f"player:{player_id}",
          {"kind": kind, "delta": delta, "reason": reason})
    fresh = _player_row(player_id)
    return {"coins": fresh["coins"], "xp": fresh["xp"]}


def mastery(player_id: int, atom_id: str, action: str, reason: str, actor: str) -> dict:
    _player_row(player_id)
    conn = get_conn()
    if action == "reset":
        conn.execute(
            "DELETE FROM atom_mastery WHERE player_id=? AND atom_id=?",
            (player_id, atom_id),
        )
    else:  # master
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        due = (now + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        today = now.strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO atom_mastery (player_id, atom_id, strength, correct_count,"
            " wrong_count, due_at, updated_at, learned_at)"
            " VALUES (?,?,3,1,0,?,?,?)"
            " ON CONFLICT(player_id, atom_id) DO UPDATE SET"
            " strength=3, correct_count=MAX(correct_count,1), due_at=excluded.due_at,"
            " updated_at=excluded.updated_at,"
            " learned_at=COALESCE(atom_mastery.learned_at, excluded.learned_at)",
            (player_id, atom_id, due, now.strftime("%Y-%m-%d %H:%M:%S"), today),
        )
    audit(actor, "mastery", f"player:{player_id}",
          {"atom_id": atom_id, "action": action, "reason": reason})
    return {"ok": True}


def items(player_id: int, item_id: str, action: str, reason: str, actor: str) -> dict:
    _player_row(player_id)
    conn = get_conn()
    if conn.execute("SELECT 1 FROM items WHERE id=?", (item_id,)).fetchone() is None:
        raise core.NotFound("item_not_found")
    if action == "grant":
        conn.execute(
            "INSERT OR IGNORE INTO inventory (player_id, item_id, source) VALUES (?,?,'admin')",
            (player_id, item_id),
        )
    else:  # revoke
        conn.execute(
            "DELETE FROM inventory WHERE player_id=? AND item_id=?", (player_id, item_id)
        )
    audit(actor, "items", f"player:{player_id}",
          {"item_id": item_id, "action": action, "reason": reason})
    return {"ok": True}


def list_audit(player_id: int | None, limit: int) -> dict:
    conn = get_conn()
    if player_id is not None:
        rows = conn.execute(
            "SELECT * FROM admin_audit WHERE entity=? ORDER BY id DESC LIMIT ?",
            (f"player:{player_id}", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM admin_audit ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"items": [
        {"id": r["id"], "actor": r["actor"], "action": r["action"],
         "entity": r["entity"], "payload": json.loads(r["payload"]),
         "created_at": r["created_at"]}
        for r in rows
    ]}
