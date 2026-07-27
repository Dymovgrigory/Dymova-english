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


@pytest.mark.asyncio
async def test_confirm_step_accepts_natural_yes_phrasing():
    """Раньше подтверждение принимало только точный список фраз ("да",
    "верно", "все верно", ...) — любая естественная формулировка вроде
    «Да, всё верно, отправляйте заявку» не совпадала ни с одной из них, и
    бот бесконечно повторял один и тот же текст подтверждения, не
    продвигая заявку (описано пользователем как «бот завис на моменте
    оформления заявки, отвечает одно и то же на всё»)."""
    submitted_leads = []

    class FakeBigBen:
        async def create_lead(self, *a, **k):
            submitted_leads.append(a)
            return True

    class FakeMax:
        configured = False

        async def send_message(self, *a, **k):
            return True

    conv = Conversation(user_id="robust-confirm")
    conv.lead.fio_parent = "Иванова Анна"
    conv.lead.fio_child = "Миша"
    conv.lead.age = "9"
    conv.lead.phone = "+79991234567"
    conv.selected_branch = "Лихачевский 76к1"
    conv.lead_step = "confirm"

    reply, submitted = await lead_manager.step(
        conv, "Да, всё верно, отправляйте заявку", get_kb(), FakeBigBen(), FakeMax()
    )

    assert submitted is True
    assert len(submitted_leads) == 1
    assert "Готово" in reply


@pytest.mark.asyncio
async def test_confirm_step_negative_imperative_does_not_submit():
    """«не отправляйте пока» contains "отправ" (a _YES_RE trigger) — must not submit."""
    class FakeBigBen:
        async def create_lead(self, *a, **k):
            raise AssertionError("should not submit when user says not to")

    class FakeMax:
        configured = False

        async def send_message(self, *a, **k):
            return True

    conv = Conversation(user_id="robust-no-submit")
    conv.lead.fio_parent = "Иванова Анна"
    conv.lead.fio_child = "Миша"
    conv.lead.age = "9"
    conv.lead.phone = "+79991234567"
    conv.selected_branch = "Лихачевский 76к1"
    conv.lead_step = "confirm"

    reply, submitted = await lead_manager.step(
        conv, "подождите, не отправляйте пока", get_kb(), FakeBigBen(), FakeMax()
    )

    assert submitted is False


@pytest.mark.asyncio
async def test_fio_parent_retry_acknowledges_signup_restatement():
    """Пользователь снова говорит «хочу записаться» вместо имени — бот не
    должен молча повторять один и тот же голый вопрос."""
    class FakeBigBen:
        async def create_lead(self, *a, **k):
            return True

    class FakeMax:
        configured = False

        async def send_message(self, *a, **k):
            return True

    conv = Conversation(user_id="robust-name-restate")
    conv.lead_step = "fio_parent"

    reply, submitted = await lead_manager.step(
        conv, "давайте запишем сына", get_kb(), FakeBigBen(), FakeMax()
    )

    assert submitted is False
    assert conv.lead.fio_parent == ""
    assert "уже записываю" in reply.lower()


@pytest.mark.asyncio
async def test_confirm_step_correction_is_not_mistaken_for_yes():
    class FakeBigBen:
        async def create_lead(self, *a, **k):
            raise AssertionError("should not submit on a correction request")

    class FakeMax:
        configured = False

        async def send_message(self, *a, **k):
            return True

    conv = Conversation(user_id="robust-correct")
    conv.lead.fio_parent = "Иванова Анна"
    conv.lead.fio_child = "Миша"
    conv.lead.age = "9"
    conv.lead.phone = "+79991234567"
    conv.selected_branch = "Лихачевский 76к1"
    conv.lead_step = "confirm"

    reply, submitted = await lead_manager.step(
        conv, "нет, телефон неверно указан", get_kb(), FakeBigBen(), FakeMax()
    )

    assert submitted is False
    assert conv.lead_step == ""


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


def test_miniapp_lead_blocks_unregistered_user(monkeypatch):
    class FakeBigBen:
        async def create_lead(self, *args, **kwargs):
            raise AssertionError("should not submit")

    monkeypatch.setattr(main, "get_bigben", lambda: FakeBigBen())
    monkeypatch.setattr(main.settings, "ADMIN_MAX_IDS", "111,222")

    client = TestClient(main.app)
    resp = client.post(
        "/api/miniapp/lead",
        json={
            "user_id": "max:unregistered",
            "fio_parent": "Иванова Анна",
            "phone": "+79991234567",
        },
    )

    assert resp.status_code == 403
    assert "зарегистр" in resp.json()["error"].lower()
