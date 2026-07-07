import json

import pytest

from app import intent as I
from app import main as main_module
from app import memory as memory_module
from app.conv_report import conversations_digest
from app.convlog import log_turn
from app.config import settings
from app.memory import STAGE_DONE, STAGE_HANDOFF, get_store


class FakeMaxClient:
    def __init__(self):
        self.sent = []

    async def send_message(self, user_id, text, buttons=None):
        self.sent.append({"user_id": user_id, "text": text, "buttons": buttons})
        return True


@pytest.fixture(autouse=True)
def reset_state():
    main_module._BACKGROUND_TASKS.clear()
    memory_module._store = None
    yield
    main_module._BACKGROUND_TASKS.clear()
    memory_module._store = None


@pytest.mark.asyncio
async def test_homework_intent_routes_to_miniapp_button(monkeypatch):
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example/app/", raising=False)

    fake_client = FakeMaxClient()
    update = {
        "type": "message_created",
        "message": {
            "sender": {"user_id": "501"},
            "body": {"text": "Помоги с домашкой по английскому"},
        },
    }

    assert I.detect_intent("Помоги с домашкой по английскому") == I.HOMEWORK

    await main_module._process_update(update, "message_created", fake_client)

    assert len(fake_client.sent) == 1
    sent = fake_client.sent[0]
    assert "бесплатная" in sent["text"].lower()
    assert sent["buttons"]
    button = sent["buttons"][0][0]
    assert button["type"] == "link"
    assert button["text"] == "📸 Помощь с домашкой (бесплатно)"
    assert button["url"].endswith("#homework")


def test_convlog_and_digest_reflect_dialogues(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CONV_LOG_FILE", str(tmp_path / "conversations.jsonl"), raising=False)
    monkeypatch.setattr(settings, "STATE_FILE", str(tmp_path / "state.json"), raising=False)
    memory_module._store = None
    store = get_store()

    conv_lead = store.get("u1")
    conv_lead.lead.fio_parent = "Анна"
    conv_lead.lead_submitted = True
    conv_lead.stage = STAGE_DONE
    store.save(conv_lead)

    conv_handoff = store.get("u2")
    conv_handoff.lead.fio_parent = "Пётр"
    conv_handoff.handed_off = True
    conv_handoff.stage = STAGE_HANDOFF
    store.save(conv_handoff)

    conv_homework = store.get("u3")
    conv_homework.lead.fio_parent = "Мария"
    store.save(conv_homework)

    log_turn("u1", "Хочу записаться на пробное", "Хорошо, оставьте телефон", "want_signup", STAGE_DONE, "lead")
    log_turn("u2", "Свяжите с администратором", "Передаю администратору", "handoff", STAGE_HANDOFF, "handoff")
    log_turn("u3", "Помоги с дз", "Откройте мини-апп", "homework", "greeting", "homework")

    log_file = tmp_path / "conversations.jsonl"
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    first = json.loads(lines[0])
    assert first["user_id"] == "u1"
    assert first["result"] == "lead"

    digest = conversations_digest(days=1)
    assert "Диалоги за период" in digest
    assert "Заявок: 1" in digest
    assert "Передано администратору: 1" in digest
    assert "Домашка: 1" in digest
    assert "u1 / Анна" in digest
    assert "u2 / Пётр" in digest
    assert "u3 / Мария" in digest
    assert "Помоги с дз" in digest


def test_homework_intent_uses_word_boundary_for_dz():
    assert I.detect_intent("Помоги с дз") == I.HOMEWORK
    assert I.detect_intent("надзор родителей") != I.HOMEWORK
