"""Домен Этапа 4: Мир Фоксинбурга внутри ЛК (SSO + прогресс ребёнка).

Связка ЛК↔Мир: детерминированный ключ игрока Мира — `lk-crm-<student_id>`
для профилей из CRM, `lk-guest-<account_id>` для гостей. ЛК и Мир живут в
одном процессе world-backend и одной БД, поэтому сессия Мира (wses.*),
выданная из ЛК, сразу валидна.

Регистрация Мира для SSO-игрока: телефон родителя уже подтверждён в ЛК через
ботов MAX/TG (Этап 1) — переносим номер в player_identity и ставим
phone_verified_at, гейт Мира пропускает без анкеты.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.world import core
from app.world.auth import issue_session
from app.world.db import get_conn

from . import service as auth_service
from .words import _profile  # единая валидация токена/профиля

TRACK_LABELS = {
    "spotlight": "Башня Spotlight",
}


def _external_key(profile) -> str:
    if profile["student_id"]:
        return f"lk-crm-{int(profile['student_id'])}"
    return f"lk-guest-{int(profile['account_id'])}"


def world_session(token: str, student_id: int) -> dict:
    """Создать/найти игрока Мира для профиля ЛК и выдать wses-сессию."""
    account, profile = _profile(token, student_id)
    external_key = _external_key(profile)
    player = core.get_or_create_player(external_key, profile["child_name"])
    player_id = int(player["id"])
    conn = get_conn()
    row = conn.execute(
        "SELECT player_id, phone_verified_at FROM player_identity WHERE player_id=?",
        (player_id,),
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO player_identity (player_id, first_name, last_name,"
            " birth_date, school_number, class_grade, class_letter,"
            " parent_email, parent_phone, phone_verified_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (player_id, profile["child_name"], "", "", "", 0, None,
             "", account["phone"],
             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
        )
    elif not row["phone_verified_at"]:
        conn.execute(
            "UPDATE player_identity SET phone_verified_at=?,"
            " updated_at=datetime('now') WHERE player_id=?",
            (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), player_id),
        )
    session = issue_session(player_id)
    return {
        "session": session,
        "external_key": external_key,
        "display_name": profile["child_name"],
    }


def world_progress(token: str, student_id: int) -> dict:
    """Прогресс ребёнка в Мире для дашборда ЛК: уровень, XP, серия, треки, лига."""
    _, profile = _profile(token, student_id)
    external_key = _external_key(profile)
    try:
        player = core.get_player(external_key)
    except core.NotFound:
        return {"linked": False, "child_name": profile["child_name"]}
    player_id = int(player["id"])
    conn = get_conn()
    tracks = [
        {"track": r["track"], "level": int(r["level"])}
        for r in conn.execute(
            "SELECT track, level FROM titles WHERE player_id=?",
            (player_id,),
        ).fetchall()
    ]
    monday = datetime.now(timezone.utc)
    monday = monday.replace(day=monday.day - (monday.weekday()))
    week_start = monday.strftime("%Y-%m-%d")
    league = conn.execute(
        "SELECT rank, weekly_xp FROM league_weeks WHERE player_id=? AND week_start=?",
        (player_id, week_start),
    ).fetchone()
    return {
        "linked": True,
        "child_name": profile["child_name"],
        "display_name": player["display_name"],
        "level": int(player["level"]),
        "xp": int(player["xp"]),
        "coins": int(player["coins"]),
        "streak_days": int(player["streak_days"]),
        "tracks": tracks,
        "league": ({"rank": int(league["rank"]),
                    "weekly_xp": int(league["weekly_xp"])} if league else None),
    }
