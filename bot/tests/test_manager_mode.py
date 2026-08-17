"""Кнопка «Позвать менеджера» и авто-возврат диалога боту.

Контракты:
- кнопка (MAX callback menu:admin, мини-апп /api/miniapp/manager-call)
  создаёт заявку, шлёт уведомление админам и включает режим менеджера;
  повторное нажатие — подтверждение клиенту без спама админам;
- режим менеджера — скользящее окно MANAGER_AUTO_RESUME_MIN: тишина дольше
  окна возвращает диалог боту, сообщение клиента окно продлевает;
- reply менеджера и handoff выставляют paused_until (режим не вечный).
"""
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import ai_core
from app import config
from app import crm_ingest
from app import crm_store
from app import main as main_module
from app import memory as memory_module
from app.config import settings

from tests.conftest import make_telegram_init_data

TOKEN = "test-admin-token"
AUTH = {"X-Admin-Token": TOKEN}
TG_TOKEN = "test-tg-token"


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "crm.db"))
    monkeypatch.setattr(settings, "STATE_FILE", "")
    monkeypatch.setattr(settings, "ADMIN_TOKEN", TOKEN, raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", TG_TOKEN)
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://example.test/app/")
    monkeypatch.setattr(settings, "ADMIN_MAX_IDS", "admin-1")
    memory_module._store = None
    crm_store.reset()
    main_module._BACKGROUND_TASKS.clear()
    yield
    memory_module._store = None
    crm_store.reset()
    main_module._BACKGROUND_TASKS.clear()


@pytest.fixture
def client():
    return TestClient(main_module.app)


class FakeMaxClient:
    def __init__(self):
        self.sent = []

    async def send_message(self, user_id, text, buttons=None):
        self.sent.append((user_id, text, buttons))
        return True

    async def send_message_ext(self, user_id, text, buttons=None):
        self.sent.append((user_id, text, buttons))
        return True, "ext-1", None

    async def answer_callback(self, callback_id, notification=None):
        return True


@pytest.fixture
def fake_max(monkeypatch):
    fake = FakeMaxClient()
    monkeypatch.setattr(main_module, "get_max", lambda: fake)
    monkeypatch.setattr("app.admin_api.get_max", lambda: fake)

    async def _slack_noop(text):
        return True

    monkeypatch.setattr(main_module, "notify_slack", _slack_noop)
    return fake


def _callback_update(user_id: str, payload: str) -> dict:
    return {
        "type": "message_callback",
        "callback": {
            "callback_id": "cb-1",
            "payload": payload,
            "sender": {"user_id": user_id},
        },
    }


# --------- кнопка «Позвать менеджера» (MAX) ---------


@pytest.mark.asyncio
async def test_menu_admin_button_creates_request_and_notifies(fake_max):
    await main_module._process_update(_callback_update("u1", "menu:admin"), "message_callback", fake_max)

    # Клиент получил подтверждение.
    assert any("менеджер" in text.lower() for u, text, _ in fake_max.sent if u == "u1")
    # Админы получили уведомление со ссылкой на заявку.
    admin_msgs = [(u, t, b) for u, t, b in fake_max.sent if u == "admin-1"]
    assert len(admin_msgs) == 1
    assert "Заявка: #" in admin_msgs[0][1]
    assert admin_msgs[0][2] and "requests" in admin_msgs[0][2][0][0]["url"]
    # Заявка создана, режим менеджера с авто-возвратом.
    reqs = crm_store.list_callback_requests()
    assert len(reqs) == 1 and reqs[0]["kind"] == "admin_request"
    conv = crm_store.find_conversation("max", "u1")
    assert conv["ai_mode"] == "manager"
    assert conv["ai_paused_until"]


@pytest.mark.asyncio
async def test_menu_admin_button_second_press_no_spam(fake_max):
    await main_module._process_update(_callback_update("u1", "menu:admin", ), "message_callback", fake_max)
    await main_module._process_update(_callback_update("u1", "menu:admin"), "message_callback", fake_max)

    admin_msgs = [m for m in fake_max.sent if m[0] == "admin-1"]
    assert len(admin_msgs) == 1  # уведомление одно
    user_msgs = [m for m in fake_max.sent if m[0] == "u1"]
    assert "уже подключён" in user_msgs[-1][1].lower()
    assert len(crm_store.list_callback_requests()) == 1  # заявка не задублирована


# --------- кнопка в мини-аппе ---------


def test_miniapp_manager_call(client, fake_max):
    init_data = make_telegram_init_data(TG_TOKEN, telegram_user_id=555)
    resp = client.post("/api/miniapp/manager-call",
                       headers={main_module.INIT_DATA_HEADER: init_data})
    assert resp.status_code == 200 and resp.json()["ok"]
    assert "менеджер" in resp.json()["reply"].lower()

    conv = crm_store.find_conversation("telegram", "tg:555")
    assert conv["ai_mode"] == "manager" and conv["ai_paused_until"]
    assert len(crm_store.list_callback_requests()) == 1
    # Подтверждение записано в историю — мини-апп заберёт его поллингом.
    msgs = crm_store.get_messages(conv["id"], limit=10)
    assert [m["direction"] for m in msgs] == ["in", "out"]

    resp2 = client.post("/api/miniapp/manager-call",
                        headers={main_module.INIT_DATA_HEADER: init_data})
    assert "уже подключён" in resp2.json()["reply"].lower()
    assert len([m for m in fake_max.sent if m[0] == "admin-1"]) == 1


def test_miniapp_manager_call_requires_auth(client):
    assert client.post("/api/miniapp/manager-call").status_code == 401


# --------- авто-возврат бота через 15 минут тишины ---------


def _seed_conv(mode="manager", paused_until=None):
    cid = crm_store.upsert_customer_for_identity("max", "u-auto")
    conv_id = crm_store.get_or_create_conversation(cid, "max", "u-auto")
    crm_store.set_ai_mode(conv_id, mode, paused_until=paused_until)
    return conv_id


def test_manager_mode_expires_after_window():
    past = (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat(timespec="seconds")
    conv_id = _seed_conv("manager", past)
    assert ai_core._crm_ai_silenced("max", "u-auto") is False
    assert crm_store.get_conversation(conv_id)["ai_mode"] == "active"


def test_manager_mode_extends_window_on_message():
    future = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat(timespec="seconds")
    conv_id = _seed_conv("manager", future)
    assert ai_core._crm_ai_silenced("max", "u-auto") is True
    # Окно скользящее: продлено до ~полных MANAGER_AUTO_RESUME_MIN от «сейчас».
    until = datetime.fromisoformat(crm_store.get_conversation(conv_id)["ai_paused_until"])
    assert until > datetime.now(timezone.utc) + timedelta(minutes=settings.MANAGER_AUTO_RESUME_MIN - 1)


def test_manager_mode_without_window_gets_window():
    conv_id = _seed_conv("manager", None)  # наследие до авто-возврата
    assert ai_core._crm_ai_silenced("max", "u-auto") is True
    assert crm_store.get_conversation(conv_id)["ai_paused_until"]


def test_paused_mode_still_expires():
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    conv_id = _seed_conv("paused", past)
    assert ai_core._crm_ai_silenced("max", "u-auto") is False
    assert crm_store.get_conversation(conv_id)["ai_mode"] == "active"


# --------- handoff и reply выставляют авто-возврат ---------


def test_handoff_sets_auto_resume():
    cid = crm_store.upsert_customer_for_identity("max", "u-ho")
    crm_store.get_or_create_conversation(cid, "max", "u-ho")
    crm_ingest.ingest_handoff("max", "u-ho", "тест")
    conv = crm_store.find_conversation("max", "u-ho")
    assert conv["ai_mode"] == "manager" and conv["ai_paused_until"]


def test_reply_sets_auto_resume(client, fake_max):
    cid = crm_store.upsert_customer_for_identity("max", "u-re")
    conv_id = crm_store.get_or_create_conversation(cid, "max", "u-re")
    resp = client.post(f"/admin/api/conversations/{conv_id}/reply",
                       headers=AUTH, json={"text": "Отвечаю лично"})
    assert resp.status_code == 200 and resp.json()["ok"]
    conv = crm_store.get_conversation(conv_id)
    assert conv["ai_mode"] == "manager" and conv["ai_paused_until"]
    # Клиенту ушло с пометкой менеджера.
    assert fake_max.sent[-1][1].startswith("👤 Менеджер:")
