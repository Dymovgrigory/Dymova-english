import pytest

import app.main as main
from app import config, memory
from app.memory import Conversation, STAGE_HANDOFF, get_store


class FakeMaxClient:
    def __init__(self):
        self.sent = []
        self.answered = []

    async def send_message(self, user_id, text, buttons=None):
        self.sent.append((user_id, text, buttons))
        return True

    async def answer_callback(self, callback_id, notification=None):
        self.answered.append((callback_id, notification))
        return True


@pytest.fixture
def fresh_store(monkeypatch):
    monkeypatch.setattr(config.settings, "STATE_FILE", "")
    store = memory.MemoryStore()
    monkeypatch.setattr(memory, "_store", store)
    return store


def _message_update(user_id: str, text: str) -> dict:
    return {
        "type": "message_created",
        "message": {
            "sender": {"user_id": user_id, "is_bot": False},
            "body": {"text": text},
        },
    }


def _callback_update(user_id: str, payload: str, callback_id: str = "cb-1") -> dict:
    return {
        "type": "message_callback",
        "callback": {
            "callback_id": callback_id,
            "payload": payload,
            "sender": {"user_id": user_id},
        },
    }


@pytest.mark.asyncio
async def test_admin_contact_asks_for_branch_when_unknown(monkeypatch, fresh_store):
    fake = FakeMaxClient()
    monkeypatch.setattr(main, "get_max", lambda: fake)
    fresh_store._data["u1"] = Conversation(user_id="u1")

    await main._process_update(_message_update("u1", "Соедините меня с администратором"), "message_created", fake)

    assert fake.sent
    user_id, text, buttons = fake.sent[-1]
    assert user_id == "u1"
    assert "какой филиал" in text.lower()
    assert len(buttons) == 2
    payloads = {row[0]["payload"] for row in buttons}
    assert payloads == {"contact:lihachevsky", "contact:raketostroiteley"}
    conv = get_store().get("u1")
    assert conv.selected_branch == ""
    assert conv.stage != STAGE_HANDOFF


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,expected_url,branch_name",
    [
        ("contact:lihachevsky", "tel:+79939232309", "Филиал на Лихачевском"),
        ("contact:raketostroiteley", "tel:+79167323169", "Филиал на Ракетостроителей"),
    ],
)
async def test_admin_contact_callback_routes_to_branch(monkeypatch, fresh_store, payload, expected_url, branch_name):
    fake = FakeMaxClient()
    monkeypatch.setattr(main, "get_max", lambda: fake)
    fresh_store._data["u2"] = Conversation(user_id="u2")

    await main._process_update(_callback_update("u2", payload), "message_callback", fake)

    assert fake.answered and fake.answered[-1][0] == "cb-1"
    assert fake.sent
    user_id, text, buttons = fake.sent[-1]
    assert user_id == "u2"
    assert branch_name.lower() in text.lower()
    assert buttons and buttons[0][0]["type"] == "link"
    assert buttons[0][0]["url"] == expected_url
    assert branch_name.lower() in buttons[0][0]["text"].lower()
    conv = get_store().get("u2")
    assert branch_name.lower() in conv.selected_branch.lower()
    assert conv.stage == STAGE_HANDOFF


@pytest.mark.asyncio
async def test_admin_contact_callback_unknown_branch_graceful(monkeypatch, fresh_store):
    fake = FakeMaxClient()
    monkeypatch.setattr(main, "get_max", lambda: fake)
    fresh_store._data["u3"] = Conversation(user_id="u3")

    await main._process_update(_callback_update("u3", "contact:unknown"), "message_callback", fake)

    assert fake.sent
    _, text, buttons = fake.sent[-1]
    assert "какой филиал" in text.lower()
    assert len(buttons) == 2
    conv = get_store().get("u3")
    assert conv.selected_branch == ""
