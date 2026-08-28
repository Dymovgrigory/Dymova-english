"""Тесты платформенного слоя: вебхуки, бронирование, телефоны, sync."""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.platform import bb_store, booking
from app.platform.webhooks import verify_signature, _dedup_key


# --- подпись вебхука ---

def test_signature_valid():
    secret = "s3cret"
    body = b'{"event":"lead.created"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, secret)


def test_signature_rejects_tampered_body():
    secret = "s3cret"
    body = b'{"event":"lead.created"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert not verify_signature(b'{"event":"payment.received"}', sig, secret)


def test_signature_rejects_wrong_secret_and_empty():
    body = b"{}"
    sig = hmac.new(b"a", body, hashlib.sha256).hexdigest()
    assert not verify_signature(body, sig, "b")
    assert not verify_signature(body, "", "a")
    assert not verify_signature(body, sig, "")


def test_dedup_key_stable():
    k1 = _dedup_key("lead.created", 1, {"lead_id": 5}, "2026-08-28T10:00:00Z")
    k2 = _dedup_key("lead.created", 1, {"lead_id": 5}, "2026-08-28T10:00:00Z")
    k3 = _dedup_key("lead.created", 1, {"lead_id": 6}, "2026-08-28T10:00:00Z")
    assert k1 == k2 and k1 != k3


def test_webhook_event_dedup(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    bb_store._local.conn = None
    id1, dup1 = bb_store.record_webhook_event("lead.created", 1, {"lead_id": 5}, "ts", "k1")
    id2, dup2 = bb_store.record_webhook_event("lead.created", 1, {"lead_id": 5}, "ts", "k1")
    assert not dup1 and dup2 and id1 == id2


# --- телефоны ---

@pytest.mark.parametrize("raw,expected", [
    ("+7 (926) 123-45-67", "+79261234567"),
    ("89261234567", "+79261234567"),
    ("9261234567", "+79261234567"),
    ("123", ""),
    ("", ""),
])
def test_normalize_phone(raw, expected):
    assert booking.normalize_phone(raw) == expected


# --- вместимость и свободные места ---

def test_free_slots_from_api():
    g = {"capacity": 8, "occupied": 5, "free_slots": 3}
    assert booking.group_free_slots(g) == 3


def test_free_slots_auditory_fallback(monkeypatch):
    monkeypatch.setattr("app.config.settings.BIGBEN_CAPACITY_FALLBACK_AUDITORY", True)
    g = {"capacity": None, "occupied": 6, "free_slots": None,
         "auditory": {"capacity": 8}}
    assert booking.group_free_slots(g) == 2


def test_free_slots_unknown():
    g = {"capacity": None, "occupied": 6, "free_slots": None, "auditory": {}}
    assert booking.group_free_slots(g) is None


# --- anti-race бронирование ---

class _FakeClient:
    def __init__(self, groups, lead_id=101, demo_id=202, fail_demo=False):
        self._groups = groups
        self._lead_id = lead_id
        self._demo_id = demo_id
        self._fail_demo = fail_demo

    async def groups(self, updated_since=None):
        return self._groups

    async def create_lead(self, **kw):
        return {"id": self._lead_id}

    async def create_demo_lesson(self, **kw):
        if self._fail_demo:
            from app.platform.bigben_v2 import BigBenError
            raise BigBenError("boom", status=500, code="server_error")
        return {"id": self._demo_id}


def _group(gid=1, free=2, filial_id=10):
    return {"id": gid, "caption": "English A1", "capacity": 8, "occupied": 8 - free,
            "free_slots": free, "overbooked": False,
            "filial": {"id": filial_id, "caption": "Долгопрудный"}, "auditory": {}}


@pytest.mark.asyncio
async def test_booking_confirmed(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    bb_store._local.conn = None
    fake = _FakeClient([_group()])
    monkeypatch.setattr("app.platform.booking.get_bigben_v2", lambda: fake)
    res = await booking.book_trial(
        parent_name="Иванова Мария", phone="+79261234567", child_name="Маша",
        child_age="8", group_id=1, lesson_id=55)
    assert res.status == "confirmed" and res.lead_id == 101 and res.demo_lesson_id == 202


@pytest.mark.asyncio
async def test_booking_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    bb_store._local.conn = None
    fake = _FakeClient([_group()])
    monkeypatch.setattr("app.platform.booking.get_bigben_v2", lambda: fake)
    kw = dict(parent_name="Иванова Мария", phone="+79261234567", child_name="Маша",
              child_age="8", group_id=1, lesson_id=55, idempotency_key="fixed-key")
    r1 = await booking.book_trial(**kw)
    r2 = await booking.book_trial(**kw)
    assert r1.status == "confirmed" and r2.status == "duplicate"
    assert r1.booking_id == r2.booking_id


@pytest.mark.asyncio
async def test_booking_slot_race_returns_alternatives(tmp_path, monkeypatch):
    """Место заняли между показом и записью → 409 с альтернативами, не 500."""
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    bb_store._local.conn = None
    groups = [_group(1, free=0), _group(2, free=3)]
    fake = _FakeClient(groups)
    monkeypatch.setattr("app.platform.booking.get_bigben_v2", lambda: fake)
    res = await booking.book_trial(
        parent_name="Иванова Мария", phone="+79261234567", child_name="Маша",
        child_age="8", group_id=1, lesson_id=55)
    assert res.status == "slot_unavailable"
    assert res.alternatives and res.alternatives[0]["group_id"] == 2


@pytest.mark.asyncio
async def test_booking_demo_failure_keeps_lead(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    bb_store._local.conn = None
    fake = _FakeClient([_group()], fail_demo=True)
    monkeypatch.setattr("app.platform.booking.get_bigben_v2", lambda: fake)
    res = await booking.book_trial(
        parent_name="Иванова Мария", phone="+79261234567", child_name="Маша",
        child_age="8", group_id=1, lesson_id=55)
    assert res.status == "failed" and res.lead_id == 101
    assert "менеджер" in res.error


def test_filial_capacity_rules():
    from app.platform import booking
    assert booking.filial_capacity("Фоксинбург Лихачевский") == 8
    assert booking.filial_capacity("Фоксинбург Ракетостроителей") == 7
    assert booking.filial_capacity("Новый корпус 11 школа Фоксинбург") == 10
    assert booking.filial_capacity("Детский сад Солнышко") is None


def test_effective_capacity_rule_caps_explicit():
    from app.platform import booking
    # CRM говорит 12, физический лимит филиала 8 → побеждает лимит
    g = {"capacity": 12, "filial": {"caption": "Фоксинбург Лихачевский"}}
    assert booking.effective_capacity(g) == 8
    # без явного лимита — правило филиала
    g2 = {"capacity": None, "filial": {"caption": "Новый корпус 11 школа"}}
    assert booking.effective_capacity(g2) == 10
    # без правила и лимита — fallback аудитории
    g3 = {"capacity": None, "filial": {"caption": "Неизвестный"},
          "auditory": {"capacity": 6}}
    assert booking.effective_capacity(g3) == 6
