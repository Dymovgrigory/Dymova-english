"""Relay посещаемости lesson.completed → ЛК (Этап 2 кабинета).

_handle планирует fire-and-forget задачу _relay_attendance; сам relay шлёт
POST {LK_INTERNAL_URL}/api/lk/attendance с HMAC-подписью по WORLD_BRIDGE_SECRET.
"""
import asyncio
import hashlib
import hmac

import pytest

from app.platform import webhooks


class _FakeResp:
    status_code = 200
    text = "ok"


@pytest.fixture()
def lk_url(monkeypatch):
    monkeypatch.setattr(webhooks, "_LK_INTERNAL_URL", "http://lk-test:8010")
    return "http://lk-test:8010"


def _signed_body(secret, student_id, lesson_id, status, ts):
    msg = f"{student_id}\n{lesson_id}\n{status}\n{ts}".encode()
    sign = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return {"student_id": student_id, "lesson_id": lesson_id, "status": status,
            "ts": ts, "sign": sign, "raw": {}}


async def test_lesson_completed_schedules_relay(monkeypatch):
    calls = []

    async def fake_relay(payload):
        calls.append(payload)

    monkeypatch.setattr(webhooks, "_relay_attendance", fake_relay)
    payload = {"student_id": 101, "lesson_id": 501, "visit_status": 1}
    await webhooks._handle("lesson.completed", payload)
    await asyncio.sleep(0.05)
    assert calls == [payload]


async def test_relay_posts_signed_body(monkeypatch, lk_url):
    from app.config import settings

    secret = "relay-secret-for-tests"
    monkeypatch.setattr(settings, "WORLD_BRIDGE_SECRET", secret)
    sent = []

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            sent.append((url, json))
            return _FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)
    await webhooks._relay_attendance(
        {"student_id": 101, "lesson_id": 501, "visit_status": 1, "ts": "now"})

    assert len(sent) == 1
    url, body = sent[0]
    assert url == "http://lk-test:8010/api/lk/attendance"
    assert body["student_id"] == 101 and body["lesson_id"] == 501
    assert body["status"] == "visited"
    expected = _signed_body(secret, 101, 501, "visited", body["ts"])
    assert body["sign"] == expected["sign"]


async def test_relay_maps_non_one_status_to_missed(monkeypatch, lk_url):
    from app.config import settings

    monkeypatch.setattr(settings, "WORLD_BRIDGE_SECRET", "s")
    sent = []

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            sent.append(json)
            return _FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)
    await webhooks._relay_attendance({"student_id": 1, "lesson_id": 2,
                                      "visit_status": 0})
    assert sent[0]["status"] == "missed"


async def test_relay_skips_without_secret(monkeypatch, lk_url):
    from app.config import settings

    monkeypatch.setattr(settings, "WORLD_BRIDGE_SECRET", "")
    called = []

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            called.append(1)
            return _FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)
    await webhooks._relay_attendance({"student_id": 1, "lesson_id": 2,
                                      "visit_status": 1})
    assert called == []


# ---------- зачисления group.enrolled → ЛК ----------

async def test_group_enrolled_schedules_membership_relay(monkeypatch):
    calls = []

    async def fake_relay(payload):
        calls.append(payload)

    monkeypatch.setattr(webhooks, "_relay_membership", fake_relay)
    payload = {"student_id": 101, "group_id": 7, "group_name": "SP1 А"}
    await webhooks._handle("group.enrolled", payload)
    await asyncio.sleep(0.05)
    assert calls == [payload]


async def test_membership_relay_posts_signed_body(monkeypatch, lk_url):
    from app.config import settings

    secret = "members-secret"
    monkeypatch.setattr(settings, "WORLD_BRIDGE_SECRET", secret)
    sent = []

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            sent.append((url, json))
            return _FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)
    await webhooks._relay_membership(
        {"student_id": 101, "group_id": 7, "group_name": "SP1 Группа А"})

    assert len(sent) == 1
    url, body = sent[0]
    assert url == "http://lk-test:8010/api/lk/group-members"
    assert body["student_id"] == 101 and body["group_id"] == 7
    assert body["status"] == "active"
    assert body["group_caption"] == "SP1 Группа А"
    msg = f"101\n7\nactive\n{body['ts']}".encode()
    expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    assert body["sign"] == expected


async def test_membership_relay_reads_nested_group(monkeypatch, lk_url):
    from app.config import settings

    monkeypatch.setattr(settings, "WORLD_BRIDGE_SECRET", "s")
    sent = []

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            sent.append(json)
            return _FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)
    await webhooks._relay_membership(
        {"student_id": 5, "group": {"id": 9, "caption": "B2"}})
    assert sent[0]["group_id"] == 9
    assert sent[0]["group_caption"] == "B2"


async def test_membership_relay_skips_without_group_id(monkeypatch, lk_url):
    from app.config import settings

    monkeypatch.setattr(settings, "WORLD_BRIDGE_SECRET", "s")
    called = []

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            called.append(1)
            return _FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)
    await webhooks._relay_membership({"student_id": 5})
    assert called == []
