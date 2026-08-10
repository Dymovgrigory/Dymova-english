"""Обязательная регистрация с настоящими данными.

В CRM должны попадать живые контакты, а не «Привет», «ааа» и «0 лет».
Прежняя проверка имени пропускала любую строку без цифр и знака вопроса.
"""
import pytest

from app import registration
from app.config import settings
from app.memory import Conversation, STAGE_REGISTRATION


class FakeBigBen:
    def __init__(self):
        self.leads = []

    async def create_lead(self, lead, source="", note="", utm=None):
        self.leads.append({"lead": lead, "source": source, "note": note})
        return True


@pytest.fixture(autouse=True)
def _require_registration(monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True, raising=False)


# --- имена ------------------------------------------------------------------


@pytest.mark.parametrize(
    "junk",
    ["Привет", "привет", "тест", "test", "не знаю", "ааа", "ффф", "asdf", "ок", "да"],
)
def test_junk_is_not_accepted_as_a_name(junk):
    assert registration._extract_name(junk) == ""


@pytest.mark.parametrize(
    "name",
    ["Григорий", "Иванова Анна", "Пётр", "Анна-Мария", "Ким Ир", "Ли"],
)
def test_real_names_are_accepted(name):
    assert registration._extract_name(name) == name


@pytest.mark.asyncio
async def test_greeting_instead_of_a_name_is_asked_again():
    conv = Conversation(user_id="reg-junk")
    registration.start_registration(conv)

    reply, done = await registration.handle_registration_step(
        conv, "Привет", FakeBigBen()
    )

    assert done is False
    assert conv.lead.fio_parent == ""
    assert "имя" in reply.lower()


# --- возраст и дата рождения ------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["0", "150", "не знаю", "маленький"])
async def test_implausible_age_is_rejected(bad):
    conv = Conversation(user_id="reg-age")
    conv.lead.fio_parent = "Иванова Анна"
    conv.lead.fio_child = "Миша"
    conv.registration_step = "birthday"

    reply, done = await registration.handle_registration_step(conv, bad, FakeBigBen())

    assert done is False
    assert conv.lead.age == ""
    assert conv.lead.birthday == ""
    assert "возраст" in reply.lower()


@pytest.mark.asyncio
async def test_plausible_age_is_accepted():
    conv = Conversation(user_id="reg-age-ok")
    conv.lead.fio_parent = "Иванова Анна"
    conv.lead.fio_child = "Миша"
    conv.registration_step = "birthday"

    await registration.handle_registration_step(conv, "9 лет", FakeBigBen())

    assert conv.lead.age == "9"


@pytest.mark.asyncio
async def test_birthday_from_the_wrong_century_is_rejected():
    conv = Conversation(user_id="reg-bday")
    conv.lead.fio_parent = "Иванова Анна"
    conv.lead.fio_child = "Миша"
    conv.registration_step = "birthday"

    reply, done = await registration.handle_registration_step(
        conv, "15.03.1899", FakeBigBen()
    )

    assert done is False
    assert conv.lead.birthday == ""


# --- телефон ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_phone_must_be_a_real_russian_number():
    conv = Conversation(user_id="reg-phone")
    conv.lead.fio_parent = "Иванова Анна"
    conv.lead.fio_child = "Миша"
    conv.lead.age = "9"
    conv.registration_step = "phone"

    reply, done = await registration.handle_registration_step(
        conv, "123", FakeBigBen()
    )

    assert done is False
    assert conv.lead.phone == ""
    assert "телефон" in reply.lower()


# --- гейт и передача в CRM --------------------------------------------------


@pytest.mark.asyncio
async def test_registration_blocks_the_bot_until_it_is_finished():
    """Пока регистрация не пройдена, бот не отвечает на вопросы по существу."""
    from app.ai_core import handle_message
    from app.memory import get_store

    uid = "reg-gate"
    store = get_store()
    store.reset(uid)

    reply = await handle_message(uid, "Сколько стоят занятия?")

    assert store.get(uid).stage == STAGE_REGISTRATION
    assert "8 200" not in reply


@pytest.mark.asyncio
async def test_completed_registration_goes_to_crm_with_all_fields():
    bigben = FakeBigBen()
    conv = Conversation(user_id="reg-crm")
    registration.start_registration(conv)

    await registration.handle_registration_step(conv, "Иванова Анна", bigben)
    await registration.handle_registration_step(conv, "Миша", bigben)
    await registration.handle_registration_step(conv, "15.03.2016", bigben)
    reply, done = await registration.handle_registration_step(conv, "89991234567", bigben)

    assert done is True
    assert conv.registered is True
    assert len(bigben.leads) == 1
    lead = bigben.leads[0]["lead"]
    assert lead.fio_parent == "Иванова Анна"
    assert lead.fio_child == "Миша"
    assert lead.birthday == "2016-03-15"
    assert lead.phone == "+79991234567"
    assert "регистрация" in bigben.leads[0]["source"].lower()
