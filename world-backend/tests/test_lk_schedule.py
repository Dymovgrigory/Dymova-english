"""Тесты Этапа 2 ЛК: расписание из BigBen + посещаемость из вебхука бота.

Покрытые потоки (ТЗ §3, §6):
- расписание: фильтрация занятий по активным группам профиля, чужой
  student_id → profile_not_found, bad_dates, окно > 62 дней;
- посещаемость: record_attendance → join в ответе расписания;
- ingest_attendance: happy path с HMAC-подписью, bad_signature, stale ts,
  relay_disabled (нет секрета в env).
"""
from __future__ import annotations

import time

import pytest

from app.lk import bigben, bridge, service
from app.world import core

from tests.test_lk_auth import CONSENTS, PHONE, STUDENTS  # noqa: F401

LESSONS = [
    {"id": 501, "date": "2026-11-02", "starts_at": "2026-11-02T08:00:00.000000Z",
     "ends_at": "2026-11-02T09:30:00.000000Z",
     "group": {"id": 7, "caption": "SP1 Группа А"},
     "filial": {"id": 3, "caption": "Центр"}},
    # Другая группа — не должна попасть к ученику 101 (у него только группа 7).
    {"id": 502, "date": "2026-11-03", "starts_at": "2026-11-03T08:00:00.000000Z",
     "ends_at": "2026-11-03T09:30:00.000000Z",
     "group": {"id": 9, "caption": "Чужая группа"},
     "filial": {"id": 3, "caption": "Центр"}},
]


@pytest.fixture()
def lk_db_bigben(tmp_path, monkeypatch):
    """Своя БД + подменённый BigBen (фикстуры между файлами не переезжают)."""
    from app.world.db import reset_for_tests

    monkeypatch.setattr(bridge, "phone_confirmed", lambda phone: (True, ["telegram"]))
    reset_for_tests(str(tmp_path / "lk.sqlite"))
    monkeypatch.setattr(bigben, "configured", lambda: True)
    monkeypatch.setattr(bigben, "list_students",
                        lambda *a, **kw: list(STUDENTS))
    monkeypatch.setattr(bigben, "groups_by_ids", lambda ids: {
        i: {"id": i, "caption": g["caption"]}
        for i in ids for g in (STUDENTS[0].get("active_groups") or [])
        if g.get("id") == i
    })
    yield
    reset_for_tests(str(tmp_path / "lk-after.sqlite"))


@pytest.fixture()
def lk_lessons(lk_db_bigben, monkeypatch):  # noqa: F811
    monkeypatch.setattr(bigben, "lessons", lambda f, t: list(LESSONS))
    return lk_db_bigben


def _consents():
    from app.lk.schemas import ConsentIn

    return [ConsentIn(**c) for c in CONSENTS]


def _token():
    service.start_auth(PHONE, "Ольга Иванова", _consents(), None, None)
    return service.confirm_via_bot(PHONE)["token"]


# ---------- расписание ----------

def test_schedule_filters_by_student_groups(lk_lessons):
    token = _token()
    out = service.schedule(token, STUDENTS[0]["id"], "2026-10-26", "2026-11-08")
    assert out["student_id"] == STUDENTS[0]["id"]
    assert [l["id"] for l in out["lessons"]] == [501]
    lesson = out["lessons"][0]
    assert lesson["date"] == "2026-11-02"
    assert lesson["group"]["caption"] == "SP1 Группа А"
    assert lesson["filial"]["caption"] == "Центр"
    assert lesson["attendance"] == "unknown"


def test_schedule_sorts_by_date_and_time(lk_lessons, monkeypatch):
    extra = [dict(LESSONS[0], id=500, date="2026-11-02",
                  starts_at="2026-11-02T07:00:00.000000Z")]
    monkeypatch.setattr(bigben, "lessons", lambda f, t: list(LESSONS) + extra)
    token = _token()
    out = service.schedule(token, STUDENTS[0]["id"], "2026-10-26", "2026-11-08")
    assert [l["id"] for l in out["lessons"]] == [500, 501]


def test_schedule_foreign_student_rejected(lk_lessons):
    token = _token()
    with pytest.raises(core.Conflict) as ei:
        service.schedule(token, 999999, "2026-10-26", "2026-11-08")
    assert "profile_not_found" in str(ei.value)


def test_schedule_unauthorized(lk_lessons):
    with pytest.raises(core.Conflict) as ei:
        service.schedule("no-such-token", STUDENTS[0]["id"], "2026-10-26", "2026-11-08")
    assert "unauthorized" in str(ei.value)


def test_schedule_bad_dates(lk_lessons):
    token = _token()
    for bad in [("2026-13-01", "2026-11-08"), ("not-a-date", "2026-11-08"),
                ("2026-11-08", "2026-10-26")]:
        with pytest.raises(core.Conflict) as ei:
            service.schedule(token, STUDENTS[0]["id"], bad[0], bad[1])
        assert "bad_dates" in str(ei.value)


def test_schedule_window_too_large(lk_lessons):
    token = _token()
    with pytest.raises(core.Conflict) as ei:
        service.schedule(token, STUDENTS[0]["id"], "2026-01-01", "2026-12-31")
    assert "window_too_large" in str(ei.value)


def test_schedule_attendance_join(lk_lessons):
    token = _token()
    service.record_attendance(STUDENTS[0]["id"], 501, "visited")
    out = service.schedule(token, STUDENTS[0]["id"], "2026-10-26", "2026-11-08")
    assert out["lessons"][0]["attendance"] == "visited"


# ---------- приём посещаемости от бота ----------

def _relay_body(secret: str, student_id=101, lesson_id=501, status="visited"):
    ts = int(time.time())
    sign = service._attendance_sign(secret, student_id, lesson_id, status, ts)
    return {"student_id": student_id, "lesson_id": lesson_id,
            "status": status, "ts": ts, "sign": sign}


def test_ingest_happy_path(lk_lessons, monkeypatch):
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", "s3cret")
    body = _relay_body("s3cret")
    assert service.ingest_attendance(body) == {"status": "ok"}
    token = _token()
    out = service.schedule(token, 101, "2026-10-26", "2026-11-08")
    assert out["lessons"][0]["attendance"] == "visited"


def test_ingest_bad_signature(lk_lessons, monkeypatch):
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", "s3cret")
    body = _relay_body("other-secret")
    with pytest.raises(core.Conflict) as ei:
        service.ingest_attendance(body)
    assert "bad_signature" in str(ei.value)


def test_ingest_stale_ts(lk_lessons, monkeypatch):
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", "s3cret")
    body = _relay_body("s3cret")
    body["ts"] = int(time.time()) - 400
    with pytest.raises(core.Conflict) as ei:
        service.ingest_attendance(body)
    assert "stale" in str(ei.value)


def test_ingest_disabled_without_secret(lk_lessons, monkeypatch):
    monkeypatch.delenv("WORLD_BRIDGE_SECRET", raising=False)
    body = _relay_body("s3cret")
    with pytest.raises(core.Conflict) as ei:
        service.ingest_attendance(body)
    assert "relay_disabled" in str(ei.value)


def test_record_attendance_rejects_bad_status(lk_lessons):
    with pytest.raises(core.Conflict) as ei:
        service.record_attendance(101, 501, "пришёл")
    assert "bad_status" in str(ei.value)


# ---------- привязки ученик↔группа (вебхуки зачисления) ----------

def _membership_body(secret: str, student_id=101, group_id=7, status="active"):
    ts = int(time.time())
    sign = service._membership_sign(secret, student_id, group_id, status, ts)
    return {"student_id": student_id, "group_id": group_id,
            "group_caption": "SP1 Группа А", "status": status, "ts": ts,
            "sign": sign}


def test_membership_feeds_schedule(lk_lessons, monkeypatch):
    """Зачисление из вебхука добавляет группу ученику → занятия видны."""
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", "s3cret")
    # У STUDENTS[0] группа 7; группа 9 (занятие 502) ей не принадлежит.
    token = _token()
    out = service.schedule(token, 101, "2026-10-26", "2026-11-08")
    assert [l["id"] for l in out["lessons"]] == [501]
    service.ingest_membership(_membership_body("s3cret", 101, 9))
    out = service.schedule(token, 101, "2026-10-26", "2026-11-08")
    assert [l["id"] for l in out["lessons"]] == [501, 502]


def test_membership_left_hides_schedule(lk_lessons, monkeypatch):
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", "s3cret")
    token = _token()
    service.ingest_membership(_membership_body("s3cret", 101, 9))
    out = service.schedule(token, 101, "2026-10-26", "2026-11-08")
    assert len(out["lessons"]) == 2
    service.ingest_membership(_membership_body("s3cret", 101, 9, status="left"))
    out = service.schedule(token, 101, "2026-10-26", "2026-11-08")
    assert [l["id"] for l in out["lessons"]] == [501]


def test_membership_bad_signature(lk_lessons, monkeypatch):
    monkeypatch.setenv("WORLD_BRIDGE_SECRET", "s3cret")
    with pytest.raises(core.Conflict) as ei:
        service.ingest_membership(_membership_body("other", 101, 7))
    assert "bad_signature" in str(ei.value)


def test_record_membership_rejects_bad_status(lk_lessons):
    with pytest.raises(core.Conflict) as ei:
        service.record_membership(101, 7, status="expelled")
    assert "bad_status" in str(ei.value)
