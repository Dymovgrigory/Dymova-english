"""Карточка контакта клиента MAX: приходит менеджеру с кнопкой «Чат», даже если номер скрыт."""
import pytest
from fastapi.testclient import TestClient

from app import admin_router, crm_store, max_client
from app.config import settings
from app.memory import Conversation


def test_attachment_shape():
    att = max_client.contact_card_attachment(555, "Ольга")
    assert att == [{"type": "contact", "payload": {"name": "Ольга", "contact_id": 555}}]


class FakeMax:
    configured = True

    def __init__(self):
        self.cards = []
        self.texts = []

    async def send_message(self, user_id, text, buttons=None):
        self.texts.append((user_id, text))
        return True

    async def send_contact_card(self, to_user_id, contact_user_id, name, text=""):
        self.cards.append((to_user_id, contact_user_id, name))
        return True


@pytest.mark.asyncio
async def test_handoff_sends_contact_card_for_max_client(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_MAX_IDS", "900,901", raising=False)
    fake = FakeMax()
    conv = Conversation(user_id="555", platform="max")
    conv.client_name = "Ольга"
    await admin_router.hand_off(fake, conv, reason="тест")
    assert fake.cards == [("900", 555, "Ольга"), ("901", 555, "Ольга")]


@pytest.mark.asyncio
async def test_handoff_no_card_for_telegram_or_web(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_MAX_IDS", "900", raising=False)
    fake = FakeMax()
    for uid, platform in (("tg:77", "telegram"), ("web:abc", "web")):
        await admin_router.hand_off(fake, Conversation(user_id=uid, platform=platform), reason="t")
    assert fake.cards == []


@pytest.mark.asyncio
async def test_card_failure_does_not_break_handoff(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_MAX_IDS", "900", raising=False)

    class Broken(FakeMax):
        async def send_contact_card(self, *a, **k):
            raise RuntimeError("boom")

    ok = await admin_router.hand_off(Broken(), Conversation(user_id="556", platform="max"), reason="t")
    assert ok is True


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    for flag in ("BIGBEN_SYNC_ENABLED", "DIGEST_ENABLED", "NUDGE_ENABLED", "SITE_SYNC_ENABLED",
                 "WATCHDOG_ENABLED", "TELEGRAM_POLLING"):
        monkeypatch.setattr(f"app.config.settings.{flag}", False)
    monkeypatch.setattr("app.config.settings.ADMIN_TOKEN", "admintoken")
    monkeypatch.setattr("app.config.settings.ADMIN_MAX_IDS", "900")
    crm_store._conn = None
    from app.main import app
    with TestClient(app) as c:
        yield c


def _h():
    return {"X-Admin-Token": "admintoken"}


def test_endpoint_sends_card_to_admins(client, monkeypatch):
    fake = FakeMax()
    monkeypatch.setattr("app.admin_api.get_max", lambda: fake)
    cid = crm_store.upsert_customer_for_identity("max", "4242", name="Анна")
    r = client.post(f"/admin/api/customers/{cid}/max-contact-card", headers=_h())
    assert r.status_code == 200 and r.json()["sent"] == 1
    assert fake.cards == [("900", 4242, "Анна")]


def test_endpoint_needs_max_identity_and_auth(client, monkeypatch):
    monkeypatch.setattr("app.admin_api.get_max", lambda: FakeMax())
    cid = crm_store.upsert_customer_for_identity("telegram", "tg:5", name="Пётр")
    assert client.post(f"/admin/api/customers/{cid}/max-contact-card", headers=_h()).status_code == 400
    assert client.post(f"/admin/api/customers/{cid}/max-contact-card").status_code == 401
