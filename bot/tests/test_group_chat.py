import pytest

from app import ai_core
from app import config
from app import group_chat
from app import memory
from app.memory import get_store


class FakeMaxClient:
    def __init__(self):
        self.bot_user_id = "999"
        self.bot_username = "foxy"
        self.chat_sent = []
        self.dm_sent = []
        self.admin_sent = []

    async def ensure_bot_identity(self):
        return True

    async def send_to_chat(self, chat_id, text, buttons=None):
        self.chat_sent.append((chat_id, text, buttons))
        return True

    async def send_message(self, user_id, text, buttons=None):
        self.admin_sent.append((user_id, text, buttons))
        return True


class FakeLLM:
    enabled = True

    async def complete(self, messages, temperature=None):
        return "Цена зависит от формата и уровня — подскажу подробнее."


@pytest.fixture
def fresh_store(monkeypatch):
    monkeypatch.setattr(config.settings, "STATE_FILE", "")
    store = memory.MemoryStore()
    monkeypatch.setattr(memory, "_store", store)
    return store


def _group_message(
    text: str,
    *,
    chat_id: int = -70957872769703,
    chat_type: str = "chat",
    bot_user_id: str = "999",
    bot_username: str = "foxy",
    mention: bool = False,
    reply_to_bot: bool = False,
) -> dict:
    body = {"text": text, "markup": []}
    if mention:
        body["markup"].append({"type": "user_mention", "from": 0, "length": 5, "user_id": bot_user_id})
    message = {
        "sender": {"user_id": "123", "name": "Анна", "is_bot": False},
        "recipient": {"chat_id": chat_id, "chat_type": chat_type},
        "body": body,
    }
    if reply_to_bot:
        message["link"] = {
            "type": "reply",
            "message": {"sender": {"user_id": bot_user_id, "name": "Фокси"}},
        }
    if bot_username:
        message["body"]["text"] = text
    return message


def test_is_group_message():
    assert group_chat.is_group_message({"recipient": {"chat_type": "chat"}})
    assert group_chat.is_group_message({"recipient": {"chat_type": "channel"}})
    assert not group_chat.is_group_message({"recipient": {"chat_type": "dialog"}})
    assert group_chat.is_group_message({"recipient": {"chat_type": "", "chat_id": -1}})


def test_is_addressed_to_bot():
    msg1 = _group_message("Привет", mention=True)
    assert group_chat.is_addressed_to_bot(msg1, "999", "foxy")

    msg2 = _group_message("@foxy сколько стоит?")
    assert group_chat.is_addressed_to_bot(msg2, "999", "foxy")

    msg3 = _group_message("Ответ на реплай", reply_to_bot=True)
    assert group_chat.is_addressed_to_bot(msg3, "999", "foxy")

    msg4 = _group_message("Просто разговор")
    assert not group_chat.is_addressed_to_bot(msg4, "999", "foxy")


@pytest.mark.asyncio
async def test_unaddressed_group_message_is_silent(monkeypatch, fresh_store):
    fake = FakeMaxClient()
    monkeypatch.setattr(ai_core, "get_llm", lambda: FakeLLM())

    await group_chat.handle_group_message(_group_message("Сколько стоит обучение?"), fake)

    assert fake.chat_sent == []
    assert fresh_store.all_conversations() == []


@pytest.mark.asyncio
async def test_addressed_kb_question_uses_kb_and_not_store(monkeypatch, fresh_store):
    fake = FakeMaxClient()
    monkeypatch.setattr(ai_core, "get_llm", lambda: FakeLLM())

    await group_chat.handle_group_message(_group_message("@foxy сколько стоит?", mention=True), fake)

    assert len(fake.chat_sent) == 1
    chat_id, text, buttons = fake.chat_sent[0]
    assert chat_id == -70957872769703
    assert text
    assert buttons is None
    assert fresh_store.all_conversations() == []


@pytest.mark.asyncio
async def test_group_complaint_notifies_admins(monkeypatch, fresh_store):
    fake = FakeMaxClient()
    monkeypatch.setattr(config.settings, "ADMIN_MAX_IDS", "111,222")

    await group_chat.handle_group_message(_group_message("@foxy я недовольна, нам никто не перезвонил", mention=True), fake)

    assert len(fake.chat_sent) == 1
    assert "администратору" in fake.chat_sent[0][1].lower()
    assert len(fake.admin_sent) == 2
    assert all("жалоб" in item[1].lower() for item in fake.admin_sent)


@pytest.mark.asyncio
async def test_group_signup_redirects_to_dm(monkeypatch, fresh_store):
    fake = FakeMaxClient()

    await group_chat.handle_group_message(_group_message("@foxy хочу записаться на пробное", mention=True), fake)

    assert len(fake.chat_sent) == 1
    assert "личные сообщения" in fake.chat_sent[0][1].lower()
    assert fresh_store.all_conversations() == []


@pytest.mark.asyncio
async def test_group_whitelist_blocks_other_chats(monkeypatch, fresh_store):
    fake = FakeMaxClient()
    monkeypatch.setattr(config.settings, "GROUP_CHAT_WHITELIST", "-1")

    await group_chat.handle_group_message(_group_message("@foxy сколько стоит?", mention=True), fake)

    assert fake.chat_sent == []


@pytest.mark.asyncio
async def test_ensure_bot_identity_parses_flat_me_response(monkeypatch):
    from app.max_client import MaxClient

    client = MaxClient()

    async def fake_me():
        return {
            "user_id": 299985016,
            "first_name": "Фоксинбург",
            "username": "id611904726658_bot",
            "is_bot": True,
        }

    monkeypatch.setattr(client, "get_bot_info", fake_me)

    assert await client.ensure_bot_identity() is True
    assert client.bot_user_id == "299985016"
    assert client.bot_username == "id611904726658_bot"
