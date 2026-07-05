"""Tests for warm nudge system (incomplete lead reminders)."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import ai_core
from app import main as main_module
from app import memory as memory_module
from app import nudge as nudge_mod
from app import telegram_client as telegram_module
from app.config import settings
from app.memory import (
    Conversation,
    Lead,
    STAGE_DISCOVERY,
    STAGE_DONE,
    STAGE_GREETING,
    STAGE_HANDOFF,
    STAGE_LEAD,
    STAGE_OBJECTION,
    STAGE_SELECTION,
    get_store,
)


class DisabledLLM:
    enabled = False


class FakeMaxClient:
    def __init__(self):
        self.sent = []
        self.configured = True

    async def send_message(self, user_id, text, buttons=None):
        self.sent.append({"user_id": user_id, "text": text, "buttons": buttons})
        return True


class FakeTelegramClient:
    def __init__(self):
        self.sent = []
        self.configured = True

    async def send_message(self, chat_id, text, buttons=None):
        self.sent.append({"chat_id": chat_id, "text": text, "buttons": buttons})
        return True

    async def set_webhook(self, url, secret=None):
        return True


@pytest.fixture(autouse=True)
def reset_state():
    memory_module._store = None
    main_module._BACKGROUND_TASKS.clear()
    yield
    memory_module._store = None
    main_module._BACKGROUND_TASKS.clear()


def _stale_time(hours_ago: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return dt.isoformat(timespec="seconds")


def _make_conv(
    user_id: str = "12345",
    stage: str = STAGE_DISCOVERY,
    hours_ago: float = 48,
    nudge_sent: bool = False,
    lead_submitted: bool = False,
    fio_parent: str = "",
    fio_child: str = "",
    course: str = "",
    branch: str = "",
    has_user_msg: bool = True,
) -> Conversation:
    store = get_store()
    conv = store.get(user_id)
    conv.stage = stage
    conv.nudge_sent = nudge_sent
    conv.lead_submitted = lead_submitted
    conv.lead.fio_parent = fio_parent
    conv.lead.fio_child = fio_child
    conv.lead.course = course
    conv.selected_branch = branch
    if has_user_msg:
        conv.history = [{"role": "user", "content": "Здравствуйте"}]
    store.save(conv)
    # Override updated_at AFTER save (save() always sets it to now)
    conv.updated_at = _stale_time(hours_ago)
    conv.created_at = _stale_time(hours_ago + 1)
    return conv


# ---- is_nudgeable ----

def test_nudgeable_discovery_after_delay():
    conv = _make_conv(stage=STAGE_DISCOVERY, hours_ago=48)
    assert nudge_mod.is_nudgeable(conv) is True


def test_nudgeable_selection():
    conv = _make_conv(stage=STAGE_SELECTION, hours_ago=40)
    assert nudge_mod.is_nudgeable(conv) is True


def test_nudgeable_objection():
    conv = _make_conv(stage=STAGE_OBJECTION, hours_ago=50)
    assert nudge_mod.is_nudgeable(conv) is True


def test_nudgeable_lead_stage():
    conv = _make_conv(stage=STAGE_LEAD, hours_ago=40)
    assert nudge_mod.is_nudgeable(conv) is True


def test_not_nudgeable_greeting():
    conv = _make_conv(stage=STAGE_GREETING, hours_ago=48)
    assert nudge_mod.is_nudgeable(conv) is False


def test_not_nudgeable_done():
    conv = _make_conv(stage=STAGE_DONE, hours_ago=48)
    assert nudge_mod.is_nudgeable(conv) is False


def test_not_nudgeable_handoff():
    conv = _make_conv(stage=STAGE_HANDOFF, hours_ago=48)
    assert nudge_mod.is_nudgeable(conv) is False


def test_not_nudgeable_already_sent():
    conv = _make_conv(stage=STAGE_DISCOVERY, hours_ago=48, nudge_sent=True)
    assert nudge_mod.is_nudgeable(conv) is False


def test_not_nudgeable_lead_submitted():
    conv = _make_conv(stage=STAGE_DISCOVERY, hours_ago=48, lead_submitted=True)
    assert nudge_mod.is_nudgeable(conv) is False


def test_not_nudgeable_too_recent():
    conv = _make_conv(stage=STAGE_DISCOVERY, hours_ago=10)
    assert nudge_mod.is_nudgeable(conv) is False


def test_not_nudgeable_too_old(monkeypatch):
    monkeypatch.setattr(settings, "NUDGE_MAX_AGE_HOURS", 100, raising=False)
    conv = _make_conv(stage=STAGE_DISCOVERY, hours_ago=150)
    assert nudge_mod.is_nudgeable(conv) is False


def test_not_nudgeable_web_user():
    conv = _make_conv(user_id="web:abc-123", stage=STAGE_DISCOVERY, hours_ago=48)
    assert nudge_mod.is_nudgeable(conv) is False


def test_not_nudgeable_no_user_messages():
    conv = _make_conv(stage=STAGE_DISCOVERY, hours_ago=48, has_user_msg=False)
    assert nudge_mod.is_nudgeable(conv) is False


# ---- compose_message ----

def test_compose_message_with_name():
    conv = _make_conv(fio_parent="Анна Иванова")
    msg = nudge_mod.compose_message(conv)
    assert "Анна Иванова" in msg
    assert "Фокси" in msg
    assert "диагностик" in msg.lower()


def test_compose_message_with_child():
    conv = _make_conv(fio_child="Иванов Миша")
    msg = nudge_mod.compose_message(conv)
    assert "Миша" in msg


def test_compose_message_with_course():
    conv = _make_conv(course="Английский для дошкольников")
    msg = nudge_mod.compose_message(conv)
    assert "Английский для дошкольников" in msg


def test_compose_message_with_branch():
    conv = _make_conv(branch="Лихачевский 76к1")
    msg = nudge_mod.compose_message(conv)
    assert "Лихачевский 76к1" in msg


def test_compose_message_generic():
    conv = _make_conv()
    msg = nudge_mod.compose_message(conv)
    assert "Фокси" in msg
    assert "диагностик" in msg.lower()


# ---- compose_buttons ----

def test_compose_buttons_with_miniapp(monkeypatch):
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example/app/", raising=False)
    conv = _make_conv()
    buttons = nudge_mod.compose_buttons(conv)
    assert len(buttons) >= 1
    assert "signup" in str(buttons[0])


def test_compose_buttons_no_miniapp(monkeypatch):
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "", raising=False)
    conv = _make_conv()
    buttons = nudge_mod.compose_buttons(conv)
    assert buttons == []


# ---- send_nudge ----

@pytest.mark.asyncio
async def test_send_nudge_max(monkeypatch):
    fake_max = FakeMaxClient()
    monkeypatch.setattr(nudge_mod, "get_max", lambda: fake_max)
    conv = _make_conv(user_id="99999", stage=STAGE_DISCOVERY, hours_ago=48)

    ok = await nudge_mod.send_nudge(conv)
    assert ok is True
    assert len(fake_max.sent) == 1
    assert fake_max.sent[0]["user_id"] == "99999"
    assert conv.nudge_sent is True


@pytest.mark.asyncio
async def test_send_nudge_telegram(monkeypatch):
    fake_tg = FakeTelegramClient()
    monkeypatch.setattr(nudge_mod, "get_telegram", lambda: fake_tg)
    conv = _make_conv(user_id="tg:77777", stage=STAGE_DISCOVERY, hours_ago=48)

    ok = await nudge_mod.send_nudge(conv)
    assert ok is True
    assert len(fake_tg.sent) == 1
    assert fake_tg.sent[0]["chat_id"] == 77777
    assert conv.nudge_sent is True


@pytest.mark.asyncio
async def test_send_nudge_web_skipped(monkeypatch):
    conv = _make_conv(user_id="web:abc", stage=STAGE_DISCOVERY, hours_ago=48)
    ok = await nudge_mod.send_nudge(conv)
    assert ok is False
    assert conv.nudge_sent is False


# ---- run_nudges ----

@pytest.mark.asyncio
async def test_run_nudges_sends_to_eligible(monkeypatch):
    fake_max = FakeMaxClient()
    monkeypatch.setattr(nudge_mod, "get_max", lambda: fake_max)
    _make_conv(user_id="u1", stage=STAGE_DISCOVERY, hours_ago=48)
    _make_conv(user_id="u2", stage=STAGE_SELECTION, hours_ago=50)
    _make_conv(user_id="u3", stage=STAGE_DONE, hours_ago=48)  # should be skipped

    stats = await nudge_mod.run_nudges()
    assert stats["sent"] == 2
    assert stats["failed"] == 0
    assert stats["eligible"] == 2


@pytest.mark.asyncio
async def test_run_nudges_no_double_send(monkeypatch):
    fake_max = FakeMaxClient()
    monkeypatch.setattr(nudge_mod, "get_max", lambda: fake_max)
    _make_conv(user_id="u1", stage=STAGE_DISCOVERY, hours_ago=48)

    stats1 = await nudge_mod.run_nudges()
    assert stats1["sent"] == 1

    stats2 = await nudge_mod.run_nudges()
    assert stats2["sent"] == 0
    assert stats2["eligible"] == 0


# ---- find_nudgeable ----

def test_find_nudgeable():
    _make_conv(user_id="a1", stage=STAGE_DISCOVERY, hours_ago=48)
    _make_conv(user_id="a2", stage=STAGE_LEAD, hours_ago=40)
    _make_conv(user_id="a3", stage=STAGE_DONE, hours_ago=48)
    _make_conv(user_id="web:w1", stage=STAGE_DISCOVERY, hours_ago=48)

    nudgeable = nudge_mod.find_nudgeable()
    ids = {c.user_id for c in nudgeable}
    assert "a1" in ids
    assert "a2" in ids
    assert "a3" not in ids
    assert "web:w1" not in ids


# ---- preview ----

def test_preview_returns_rows():
    _make_conv(user_id="p1", stage=STAGE_DISCOVERY, hours_ago=48,
               fio_parent="Тест Тестов", course="Англ.")
    rows = nudge_mod.preview()
    assert len(rows) == 1
    assert rows[0]["user_id"] == "p1"
    assert rows[0]["name"] == "Тест Тестов"
    assert rows[0]["course"] == "Англ."
    assert "message_preview" in rows[0]


# ---- admin endpoints ----

def test_admin_nudge_preview_endpoint(monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "", raising=False)
    _make_conv(user_id="ep1", stage=STAGE_DISCOVERY, hours_ago=48)

    client = TestClient(main_module.app)
    resp = client.get("/admin/nudge/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["eligible"] >= 1
    assert isinstance(data["rows"], list)


def test_admin_nudge_send_endpoint(monkeypatch):
    fake_max = FakeMaxClient()
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    monkeypatch.setattr(nudge_mod, "get_max", lambda: fake_max)
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "", raising=False)
    _make_conv(user_id="ep2", stage=STAGE_DISCOVERY, hours_ago=48)

    client = TestClient(main_module.app)
    resp = client.post("/admin/nudge/send")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sent"] >= 1


# ---- channel detection ----

def test_channel_detection():
    assert nudge_mod._channel("12345") == "max"
    assert nudge_mod._channel("tg:77777") == "telegram"
    assert nudge_mod._channel("web:abc-123") == "web"


# ---- telegram user_id int conversion ----

@pytest.mark.asyncio
async def test_telegram_nudge_chat_id_is_int(monkeypatch):
    fake_tg = FakeTelegramClient()
    monkeypatch.setattr(nudge_mod, "get_telegram", lambda: fake_tg)
    conv = _make_conv(user_id="tg:12345678", stage=STAGE_DISCOVERY, hours_ago=48)

    await nudge_mod.send_nudge(conv)
    assert fake_tg.sent[0]["chat_id"] == 12345678
