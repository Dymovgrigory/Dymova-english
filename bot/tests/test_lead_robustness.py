import pytest
from fastapi.testclient import TestClient

from app import intent as I
from app import lead_manager
from app import main
from app.knowledge.kb import get_kb
from app.memory import Conversation


def test_extract_phone_tolerates_messy_separators():
    assert I.extract_phone("+7 999 123 45 67") == "+79991234567"
    assert I.extract_phone("8(999)123-45-67") == "+79991234567"
    assert I.extract_phone("8.999.123.45.67") == "+79991234567"
    assert I.extract_phone("мой номер 89991234567, звоните") == "+79991234567"
    assert I.extract_phone("позвоните позже") is None


def test_extract_name_strips_noise_and_reordered_data():
    # имя вперемешку с возрастом ребёнка
    assert lead_manager._extract_name_from_text("Иванова Анна, ребёнку 9") == "Иванова Анна"
    # префиксы-согласия и «меня зовут»
    assert lead_manager._extract_name_from_text("меня зовут Пётр Смирнов") == "Пётр Смирнов"
    # мусор отвергается
    assert lead_manager._extract_name_from_text("хочу записаться на пробное") == ""
    assert lead_manager._extract_name_from_text("7 лет") == ""


@pytest.mark.asyncio
async def test_step_captures_reordered_phone_and_branch():
    class FakeBigBen:
        async def create_lead(self, *a, **k):
            return True

    class FakeMax:
        configured = False

        async def send_message(self, *a, **k):
            return True

    conv = Conversation(user_id="robust-1")
    conv.lead.fio_parent = "Иванова Анна"
    conv.lead.fio_child = "Миша"
    conv.lead.age = "9"
    conv.lead_step = "phone"

    reply, submitted = await lead_manager.step(
        conv, "8 999 123 45 67, удобнее Лихачевский", get_kb(), FakeBigBen(), FakeMax()
    )

    assert conv.lead.phone == "+79991234567"
    assert "лихачев" in conv.lead.branch.lower()
    assert submitted is False


def test_miniapp_lead_notifies_admins(monkeypatch):
    sent = []

    class FakeBigBen:
        async def create_lead(self, lead, source, note="", utm=None):
            return True

    class FakeMax:
        async def send_message(self, admin_id, text):
            sent.append((admin_id, text))
            return True

    monkeypatch.setattr(main, "get_bigben", lambda: FakeBigBen())
    monkeypatch.setattr(main, "get_max", lambda: FakeMax())
    monkeypatch.setattr(main.settings, "ADMIN_MAX_IDS", "111,222")

    client = TestClient(main.app)
    resp = client.post(
        "/api/miniapp/lead",
        json={
            "fio_parent": "Иванова Анна",
            "phone": "+79991234567",
            "branch": "Лихачевский 76к1",
            "interest_type": "summer",
            "interest_value": "2 смена",
        },
    )

    assert resp.status_code == 200
    assert {a for a, _ in sent} == {"111", "222"}
    body = sent[0][1]
    assert "Новая заявка" in body
    assert "Иванова Анна" in body
    assert "2 смена" in body
