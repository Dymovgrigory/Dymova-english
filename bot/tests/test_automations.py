"""Automation Engine + Notification Orchestrator."""
from __future__ import annotations

import datetime as dt
import json

import pytest

from app.platform import automations, bb_store, notifications


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    bb_store._local.conn = None
    return monkeypatch


def test_schedule_dedup(env):
    run_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
    assert automations.schedule("lesson_reminder", {"a": 1}, run_at, "k1")
    assert not automations.schedule("lesson_reminder", {"a": 1}, run_at, "k1")


def test_reminders_scheduled_for_future_lesson(env):
    starts = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=30)).isoformat()
    n = automations.schedule_lesson_reminders(
        booking_id=1, phone="+79261234567",
        lesson_starts_at=starts, group_caption="English A1")
    assert n == 2  # за 24ч и за 2ч


def test_reminders_skipped_for_soon_lesson(env):
    starts = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat()
    n = automations.schedule_lesson_reminders(
        booking_id=1, phone="+79261234567",
        lesson_starts_at=starts, group_caption="English A1")
    assert n == 0  # оба окна уже в прошлом


def test_notification_dedup_and_quiet(env, monkeypatch):
    assert not notifications.already_sent("dk1")
    # имитируем запись об отправке
    db = notifications._db()
    db.execute("INSERT INTO notification_log (dedup_key, created_at, kind, channel,"
               " target, text, status) VALUES ('dk1','','service','tg','1','t','sent')")
    db.commit()
    assert notifications.already_sent("dk1")


def test_quiet_hours_window():
    msk = notifications.MSK
    night = dt.datetime(2026, 8, 28, 23, 0, tzinfo=msk)
    morning = dt.datetime(2026, 8, 28, 10, 0, tzinfo=msk)
    assert notifications.in_quiet_hours(night)
    assert not notifications.in_quiet_hours(morning)


@pytest.mark.asyncio
async def test_send_no_channel(env):
    res = await notifications.send(
        notifications.TRANSACTIONAL, "dk-x", phone="+70000000000", text="hi")
    assert res["skipped"] == "no_channel"


@pytest.mark.asyncio
async def test_run_due_cancels_reminder_for_failed_booking(env):
    """Бронь провалилась/отменена → напоминание не уходит (§57)."""
    bb_store._local.conn = None
    bid, _ = bb_store.create_booking(
        parent_name="А", phone="+79261234567", child_name="", child_age="",
        comment="", source="t", group_id=1, lesson_id=1, filial_id=None,
        idempotency_key="bk1")
    bb_store.fail_booking(bid, "slot_unavailable")
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    assert automations.schedule("lesson_reminder", {
        "booking_id": bid, "phone": "+79261234567",
        "lesson_starts_at": "2026-08-29T17:00:00+03:00",
        "group_caption": "G", "label": "завтра",
    }, past, "job1")
    n = await automations.run_due()
    assert n == 1  # обработана (отменена), без падения
    # сообщение не отправлено: нет записи в notification_log
    assert not notifications.already_sent(f"remind-msg:{bid}:завтра")


async def test_low_balance_scan_notifies_and_dedups(env, monkeypatch):
    from app.platform import automations, bb_store, notifications
    monkeypatch.setattr("app.config.settings.LOW_BALANCE_SCAN_ENABLED", True)
    monkeypatch.setattr("app.config.settings.LOW_BALANCE_ALERT_KOPECKS", 200_000)
    bb_store._local.conn = None
    sent = []

    async def fake_targets(phone):
        return [("telegram", "tg:1")]

    async def fake_channel(channel, external_id, text):
        sent.append((channel, external_id, text))
        return True

    # тихие часы не должны делать тест зависимым от времени суток
    monkeypatch.setattr(notifications, "in_quiet_hours", lambda: False)
    monkeypatch.setattr(notifications, "resolve_targets_by_phone", fake_targets)
    monkeypatch.setattr(notifications, "_send_channel", fake_channel)
    active = {"active_groups": [{"id": 1, "caption": "A1"}]}
    bb_store.upsert_student({"id": 1, "fio": "Низкий Баланс", "phone": "79251112233",
                             "email": "", "balance_kopecks": 50_000, **active})
    bb_store.upsert_student({"id": 2, "fio": "Богатый Ученик", "phone": "79251112234",
                             "email": "", "balance_kopecks": 900_000, **active})
    bb_store.upsert_student({"id": 3, "fio": "Без Телефона", "phone": "",
                             "email": "", "balance_kopecks": 0, **active})
    n = await automations.scan_low_balance()
    assert n == 1
    assert len(sent) == 1
    assert "Низкий Баланс" in sent[0][2]
    # повторный прогон в ту же неделю — дедуп, ничего не уходит
    sent.clear()
    assert await automations.scan_low_balance() == 0
    assert sent == []


async def test_low_balance_scan_disabled(env, monkeypatch):
    from app.platform import automations, bb_store
    monkeypatch.setattr("app.config.settings.LOW_BALANCE_SCAN_ENABLED", False)
    bb_store._local.conn = None
    bb_store.upsert_student({"id": 1, "fio": "X", "phone": "79251112233",
                             "email": "", "balance_kopecks": 0,
                             "active_groups": [{"id": 1}]})
    assert await automations.scan_low_balance() == 0
