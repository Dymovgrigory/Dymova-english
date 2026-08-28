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


def _stub_notify(monkeypatch, sent):
    from app.platform import notifications
    monkeypatch.setattr(notifications, "in_quiet_hours", lambda: False)

    async def fake_targets(phone):
        return [("telegram", "tg:1")]

    async def fake_channel(channel, external_id, text):
        sent.append((channel, external_id, text))
        return True

    monkeypatch.setattr(notifications, "resolve_targets_by_phone", fake_targets)
    monkeypatch.setattr(notifications, "_send_channel", fake_channel)


async def test_subscription_reminder_day_25(env, monkeypatch):
    from datetime import datetime, timezone
    from app.platform import automations, bb_store
    monkeypatch.setattr("app.config.settings.SUBSCRIPTION_REMINDER_ENABLED", True)
    bb_store._local.conn = None
    sent = []
    _stub_notify(monkeypatch, sent)
    active = {"active_groups": [{"id": 1}]}
    bb_store.upsert_student({"id": 1, "fio": "Вася", "phone": "79251112233",
                             "email": "", "balance_kopecks": 0, **active})
    bb_store.upsert_student({"id": 2, "fio": "Без Телефона", "phone": "",
                             "email": "", "balance_kopecks": 0, **active})
    n = await automations.scan_subscription_reminders(
        datetime(2026, 8, 25, 12, tzinfo=timezone.utc))
    assert n == 1
    assert "сентябрь" in sent[0][2] and "счёт" in sent[0][2]
    assert "₽" not in sent[0][2]  # деньги не показываем
    # повтор в тот же день — дедуп
    sent.clear()
    assert await automations.scan_subscription_reminders(
        datetime(2026, 8, 25, 18, tzinfo=timezone.utc)) == 0


async def test_subscription_due_day_skips_paid(env, monkeypatch):
    from datetime import datetime, timezone
    from app.platform import automations, bb_store
    monkeypatch.setattr("app.config.settings.SUBSCRIPTION_REMINDER_ENABLED", True)
    bb_store._local.conn = None
    sent = []
    _stub_notify(monkeypatch, sent)
    active = {"active_groups": [{"id": 1}]}
    bb_store.upsert_student({"id": 1, "fio": "Должник", "phone": "79251112233",
                             "email": "", "balance_kopecks": 0, **active})
    bb_store.upsert_student({"id": 2, "fio": "Оплатил", "phone": "79251112234",
                             "email": "", "balance_kopecks": 0, **active})
    # оплата 26 августа — счёт был выставлен 24 августа, за сентябрь оплачено
    bb_store.upsert_payment({"id": 1, "student_id": 2, "student_fio": "Оплатил",
                             "group_id": 1, "amount_kopecks": 100,
                             "paid_at": "2026-08-26T10:00:00Z"})
    n = await automations.scan_subscription_reminders(
        datetime(2026, 9, 1, 9, tzinfo=timezone.utc))
    assert n == 1
    assert "последний день" in sent[0][2]


async def test_subscription_not_reminder_day(env, monkeypatch):
    from datetime import datetime, timezone
    from app.platform import automations, bb_store
    monkeypatch.setattr("app.config.settings.SUBSCRIPTION_REMINDER_ENABLED", True)
    bb_store._local.conn = None
    bb_store.upsert_student({"id": 1, "fio": "X", "phone": "79251112233",
                             "email": "", "balance_kopecks": 0,
                             "active_groups": [{"id": 1}]})
    assert await automations.scan_subscription_reminders(
        datetime(2026, 8, 10, 12, tzinfo=timezone.utc)) == 0


async def test_subscription_disabled(env, monkeypatch):
    from datetime import datetime, timezone
    from app.platform import automations
    monkeypatch.setattr("app.config.settings.SUBSCRIPTION_REMINDER_ENABLED", False)
    assert await automations.scan_subscription_reminders(
        datetime(2026, 8, 25, 12, tzinfo=timezone.utc)) == 0
