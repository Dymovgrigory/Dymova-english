"""Тесты Этапа 4 ЛК: Мир Фоксинбурга — SSO и прогресс ребёнка.

Покрытые потоки (ТЗ §6):
- SSO: сессия Мира (wses.*) для CRM-профиля и гостя; игрок создаётся с
  детерминированным ключом lk-crm-<id>/lk-guest-<id>; телефон переносится в
  player_identity с phone_verified_at (гейт Мира пропускает);
- повторный SSO: тот же игрок, новая сессия;
- прогресс: до привязки linked=false, после — уровень/XP/монеты/треки/лига.
"""
from __future__ import annotations

import pytest

from app.lk import bridge, service, world_link
from app.world import core
from app.world.auth import SESSION_PREFIX
from app.world.db import get_conn

from tests.test_lk_auth import CONSENTS, PHONE, STUDENTS  # noqa: F401


@pytest.fixture()
def lk_world_db(tmp_path, monkeypatch):
    from app.lk import bigben
    from app.world.db import reset_for_tests

    monkeypatch.setattr(bridge, "phone_confirmed", lambda phone: (True, ["telegram"]))
    reset_for_tests(str(tmp_path / "lk.sqlite"))
    monkeypatch.setattr(bigben, "configured", lambda: True)
    monkeypatch.setattr(bigben, "list_students",
                        lambda *a, **kw: list(STUDENTS))
    monkeypatch.setattr(bigben, "groups_by_ids", lambda ids: {})
    yield
    reset_for_tests(str(tmp_path / "lk-after.sqlite"))


def _consents():
    from app.lk.schemas import ConsentIn

    return [ConsentIn(**c) for c in CONSENTS]


def _token(phone: str = PHONE):
    service.start_auth(phone, "Ольга Иванова", _consents(), None, None)
    return service.confirm_via_bot(phone)["token"]


# ---------- SSO ----------

def test_world_session_creates_player_for_crm_profile(lk_world_db):
    token = _token()
    out = world_link.world_session(token, STUDENTS[0]["id"])
    assert out["session"].startswith(SESSION_PREFIX)
    assert out["external_key"] == f"lk-crm-{STUDENTS[0]['id']}"
    assert out["display_name"] == STUDENTS[0]["fio"]
    # гейт Мира: анкета с подтверждённым телефоном есть
    player = core.get_player(out["external_key"])
    row = get_conn().execute(
        "SELECT parent_phone, phone_verified_at FROM player_identity"
        " WHERE player_id=?",
        (player["id"],),
    ).fetchone()
    assert row["parent_phone"] == PHONE
    assert row["phone_verified_at"]
    # токен валиден (та же БД — сессия уже в auth_sessions)
    from app.world import auth

    assert auth.verify(out["session"]) == out["external_key"]


def test_world_session_is_stable_and_reusable(lk_world_db):
    token = _token()
    a = world_link.world_session(token, STUDENTS[0]["id"])
    b = world_link.world_session(token, STUDENTS[0]["id"])
    assert a["external_key"] == b["external_key"]
    assert a["session"] != b["session"]  # новая сессия на каждый вход
    players = get_conn().execute(
        "SELECT COUNT(*) AS c FROM players WHERE external_key=?",
        (a["external_key"],),
    ).fetchone()
    assert players["c"] == 1


def test_world_session_for_guest_profile(lk_world_db, monkeypatch):
    from app.lk import bigben

    monkeypatch.setattr(bigben, "configured", lambda: False)
    service.start_auth("+79000000002", "Гость", _consents(), None, None)
    token = service.confirm_via_bot("+79000000002")["token"]
    out = world_link.world_session(token, 0)
    assert out["external_key"].startswith("lk-guest-")
    assert out["session"].startswith(SESSION_PREFIX)


def test_world_session_foreign_student(lk_world_db):
    token = _token()
    with pytest.raises(core.Conflict) as ei:
        world_link.world_session(token, 999999)
    assert "profile_not_found" in str(ei.value)


# ---------- прогресс ----------

def test_progress_before_and_after_link(lk_world_db):
    token = _token()
    before = world_link.world_progress(token, STUDENTS[0]["id"])
    assert before["linked"] is False
    out = world_link.world_session(token, STUDENTS[0]["id"])
    get_conn().execute(
        "UPDATE players SET xp=120, level=3, coins=45, streak_days=4"
        " WHERE external_key=?",
        (out["external_key"],),
    )
    get_conn().execute(
        "INSERT INTO titles (player_id, track, level) VALUES (?,?,?)"
        " ON CONFLICT(player_id, track) DO UPDATE SET level=excluded.level",
        (core.get_player(out["external_key"])["id"], "spotlight", 2),
    )
    after = world_link.world_progress(token, STUDENTS[0]["id"])
    assert after["linked"] is True
    assert after["level"] == 3 and after["xp"] == 120
    assert after["coins"] == 45 and after["streak_days"] == 4
    assert after["tracks"] == [{"track": "spotlight", "level": 2}]


def test_progress_includes_current_week_league(lk_world_db):
    from datetime import datetime, timedelta, timezone

    token = _token()
    out = world_link.world_session(token, STUDENTS[0]["id"])
    player_id = core.get_player(out["external_key"])["id"]
    today = datetime.now(timezone.utc)
    monday = today - timedelta(days=today.weekday())
    get_conn().execute(
        "INSERT INTO league_weeks (player_id, week_start, rank, weekly_xp)"
        " VALUES (?,?,?,?)",
        (player_id, monday.strftime("%Y-%m-%d"), 3, 150),
    )
    progress = world_link.world_progress(token, STUDENTS[0]["id"])
    assert progress["league"] == {"rank": 3, "weekly_xp": 150}
