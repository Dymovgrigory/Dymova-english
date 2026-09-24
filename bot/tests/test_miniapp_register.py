"""Анкета мини-приложения: ручка регистрации и согласий."""
import pytest
from fastapi.testclient import TestClient

from app import consents, crm_store, registration
from app import main as main_module
from app import memory as memory_module
from app.config import settings
from app.memory import get_store
from tests.conftest import make_telegram_init_data

TOKEN = "123456:AA-test-token"
FORM = {
    "fio_parent": "Анна Петрова",
    "fio_child": "Маша",
    "child_birth": "9",
    "phone": "+79161234567",
    "consents": {"pd_child": True, "privacy": True, "marketing": True},
}


def auth(uid: int = 777) -> dict:
    return {
        "X-Miniapp-Init-Data": make_telegram_init_data(TOKEN, telegram_user_id=uid),
        "X-Miniapp-Platform": "telegram",
    }


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    memory_module._store = None
    crm_store.reset()
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", TOKEN, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_AUTH_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_REQUIRE_REGISTRATION", True, raising=False)
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True, raising=False)
    sent_leads: list[dict] = []

    async def fake_submit(conv, bigben, source="", extra_note=""):
        sent_leads.append({"user": conv.user_id, "source": source, "note": extra_note})

    monkeypatch.setattr(registration, "_submit_registration", fake_submit)
    chat_messages: list[tuple] = []

    async def fake_notify(identity, text):
        chat_messages.append((identity.user_id, text))

    monkeypatch.setattr(main_module, "_notify_registered_in_chat", fake_notify)
    main_module._test_sent_leads = sent_leads
    main_module._test_chat_messages = chat_messages
    yield
    memory_module._store = None
    crm_store.reset()


def test_register_requires_signed_identity():
    client = TestClient(main_module.app)
    resp = client.post("/api/miniapp/register", json=FORM)
    assert resp.status_code == 401


def test_access_state_locked_with_legal_texts_before_form():
    client = TestClient(main_module.app)
    access = client.get("/api/miniapp/access", headers=auth()).json()
    assert access["locked"] is True
    assert access["legal"]["version"] == consents.LEGAL_VERSION
    assert set(access["legal"]["labels"]) == {"pd_child", "privacy", "marketing"}


def test_register_happy_path_unlocks_and_sends_everywhere():
    client = TestClient(main_module.app)
    resp = client.post("/api/miniapp/register", json=FORM, headers=auth())
    body = resp.json()
    assert resp.status_code == 200 and body["ok"] is True
    assert body["access"]["locked"] is False
    conv = get_store().get("tg:777", platform="telegram")
    assert conv.registered and conv.lead.fio_child == "Маша"
    assert consents.has_required("telegram", "tg:777")
    lead = main_module._test_sent_leads[0]
    assert "Согласия" in lead["note"] and "мини-приложение" in lead["source"]
    assert main_module._test_chat_messages[0][0] == "tg:777"
    row = crm_store.get_conn().execute(
        "SELECT c.name, c.child_name FROM customers c JOIN customer_identities i"
        " ON i.customer_id = c.id WHERE i.channel = 'telegram' AND i.external_id = 'tg:777'"
    ).fetchone()
    assert row is not None and row["child_name"] == "Маша"


def test_register_validation_errors_returned_per_field():
    client = TestClient(main_module.app)
    bad = {**FORM, "fio_parent": "привет", "consents": {"pd_child": True}}
    resp = client.post("/api/miniapp/register", json=bad, headers=auth())
    assert resp.status_code == 400
    assert set(resp.json()["errors"]) >= {"fio_parent", "consents"}
    assert not get_store().get("tg:777", platform="telegram").registered


def test_old_registered_user_needs_consents_only():
    store = get_store()
    conv = store.get("tg:777", platform="telegram")
    conv.registered = True
    store.save(conv)
    client = TestClient(main_module.app)
    access = client.get("/api/miniapp/access", headers=auth()).json()
    assert access["locked"] is False and access["needs_consents"] is True
    resp = client.post("/api/miniapp/consents",
                       json={"consents": {"pd_child": True, "privacy": True, "marketing": True}},
                       headers=auth())
    assert resp.status_code == 200
    access = client.get("/api/miniapp/access", headers=auth()).json()
    assert access["needs_consents"] is False
