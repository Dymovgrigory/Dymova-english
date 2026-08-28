"""Детерминированные ответы бота о расписании из живых данных."""
from __future__ import annotations

import datetime as dt

import pytest

from app.platform import bb_store, bot_bridge
from app import intent as I


@pytest.fixture()
def seed(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    bb_store._local.conn = None
    day = (dt.date.today() + dt.timedelta(days=7)).isoformat()
    bb_store.upsert_filial({"id": 10, "caption": "Фоксинбург Ракетостроителей",
                            "city": "Долгопрудный", "address": "", "active": True})
    bb_store.upsert_group({"id": 1, "caption": "Английский 8-10 лет пн-ср 17:00",
                           "capacity": 8, "occupied": 5, "free_slots": 3,
                           "overbooked": False,
                           "filial": {"id": 10, "caption": "Фоксинбург Ракетостроителей"},
                           "auditory": {}, "schedule": []})
    bb_store.upsert_group({"id": 2, "caption": "Английский 8-10 лет вт-чт 18:00",
                           "capacity": 8, "occupied": 8, "free_slots": 0,
                           "overbooked": True,
                           "filial": {"id": 10, "caption": "Фоксинбург Ракетостроителей"},
                           "auditory": {}, "schedule": []})
    bb_store.upsert_group({"id": 3, "caption": "Немецкий 12-14 лет сб 12:00",
                           "capacity": 8, "occupied": 2, "free_slots": 6,
                           "overbooked": False,
                           "filial": {"id": 10, "caption": "Фоксинбург Ракетостроителей"},
                           "auditory": {}, "schedule": []})
    for gid in (1, 2, 3):
        bb_store.upsert_lesson({"id": 100 + gid, "date": day,
                                "starts_at": day + "T17:00:00+03:00", "ends_at": None,
                                "group": {"id": gid, "caption": f"g{gid}"},
                                "filial": {"id": 10, "caption": ""}})
    return day


def test_intent_schedule_detected():
    assert I.detect_intent("какое у вас расписание?") == I.SCHEDULE
    assert I.detect_intent("есть ли свободные места в группах?") == I.SCHEDULE


def test_extract_age():
    assert bot_bridge.extract_age("дочке 8 лет") == 8
    assert bot_bridge.extract_age("сыну 10") == 10
    assert bot_bridge.extract_age("мне 45") is None
    assert bot_bridge.extract_age("привет") is None


def test_reply_filters_by_age_and_availability(seed):
    reply = bot_bridge.schedule_reply("расписание для ребёнка 9 лет")
    assert "8-10 лет" in reply
    assert "пн-ср" in reply               # группа с местами показана
    assert "вт-чт" not in reply           # полная группа скрыта
    assert "Немецкий" not in reply        # возраст не подходит
    assert "живые" in reply or "актуальные" in reply


def test_reply_filial_matching(seed):
    reply = bot_bridge.schedule_reply("есть места на ракетостроителей?")
    assert "Ракетостроителей" in reply


def test_reply_no_fit_is_honest(seed):
    reply = bot_bridge.schedule_reply("расписание для ребёнка 4 лет")
    assert "не вижу" in reply             # честный ответ, без выдуманных групп
    assert "8-10" not in reply


def test_no_data_honest(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "empty.db"))
    bb_store._local.conn = None
    reply = bot_bridge.schedule_reply("какое расписание?")
    assert "не вижу" in reply and "администратор" in reply
