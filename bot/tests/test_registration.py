"""Tests for the mandatory registration gate."""
import pytest

from app.ai_core import handle_message, handle_start
from app.config import settings
from app.memory import STAGE_REGISTRATION, get_store
from app.registration import (
    REG_COMPLETE,
    REG_WELCOME,
    handle_registration_step,
    is_registered,
    start_registration,
)


@pytest.fixture
def _enable_registration(monkeypatch):
    """Enable registration for tests that need it."""
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True)


# --- Unit tests for registration module ---


class TestIsRegistered:
    def test_registered_user(self):
        store = get_store()
        conv = store.get("reg-done")
        conv.registered = True
        assert is_registered(conv) is True

    def test_unregistered_user_with_flag_enabled(self, _enable_registration):
        store = get_store()
        conv = store.get("reg-new")
        conv.registered = False
        assert is_registered(conv) is False

    def test_unregistered_user_with_flag_disabled(self):
        # conftest disables REGISTRATION_REQUIRED by default
        store = get_store()
        conv = store.get("reg-disabled")
        conv.registered = False
        assert is_registered(conv) is True  # everyone passes


class TestStartRegistration:
    def test_starts_with_welcome_and_first_question(self, _enable_registration):
        store = get_store()
        conv = store.get("reg-start1")
        reply = start_registration(conv)
        assert conv.stage == STAGE_REGISTRATION
        assert conv.registration_step == "fio_parent"
        assert "познакомимся" in reply
        assert "ФИО" in reply or "зовут" in reply.lower()

    def test_skips_already_filled_fields(self, _enable_registration):
        store = get_store()
        conv = store.get("reg-partial")
        conv.lead.fio_parent = "Иванова Анна"
        conv.lead.fio_child = "Миша"
        reply = start_registration(conv)
        assert conv.registration_step == "birthday"
        assert "рождения" in reply.lower() or "возраст" in reply.lower()


class TestRegistrationSteps:
    @pytest.mark.asyncio
    async def test_fio_parent_accepted(self, _enable_registration):
        store = get_store()
        conv = store.get("reg-fio")
        conv.stage = STAGE_REGISTRATION
        conv.registration_step = "fio_parent"

        from app.bigben import get_bigben
        reply, done = await handle_registration_step(conv, "Иванова Анна", get_bigben())
        assert conv.lead.fio_parent == "Иванова Анна"
        assert not done
        assert conv.registration_step == "fio_child"

    @pytest.mark.asyncio
    async def test_fio_parent_rejected(self, _enable_registration):
        store = get_store()
        conv = store.get("reg-fio-bad")
        conv.stage = STAGE_REGISTRATION
        conv.registration_step = "fio_parent"

        from app.bigben import get_bigben
        reply, done = await handle_registration_step(conv, "123", get_bigben())
        assert not conv.lead.fio_parent
        assert "имя" in reply.lower()
        assert not done

    @pytest.mark.asyncio
    async def test_fio_child_accepted(self, _enable_registration):
        store = get_store()
        conv = store.get("reg-child")
        conv.stage = STAGE_REGISTRATION
        conv.registration_step = "fio_child"
        conv.lead.fio_parent = "Иванова Анна"

        from app.bigben import get_bigben
        reply, done = await handle_registration_step(conv, "Миша", get_bigben())
        assert conv.lead.fio_child == "Миша"
        assert not done
        assert conv.registration_step == "birthday"

    @pytest.mark.asyncio
    async def test_birthday_age_accepted(self, _enable_registration):
        store = get_store()
        conv = store.get("reg-age")
        conv.stage = STAGE_REGISTRATION
        conv.registration_step = "birthday"
        conv.lead.fio_parent = "Иванова Анна"
        conv.lead.fio_child = "Миша"

        from app.bigben import get_bigben
        reply, done = await handle_registration_step(conv, "9 лет", get_bigben())
        assert conv.lead.age == "9"
        assert not done
        assert conv.registration_step == "phone"

    @pytest.mark.asyncio
    async def test_birthday_date_accepted(self, _enable_registration):
        store = get_store()
        conv = store.get("reg-bday")
        conv.stage = STAGE_REGISTRATION
        conv.registration_step = "birthday"
        conv.lead.fio_parent = "Иванова Анна"
        conv.lead.fio_child = "Миша"

        from app.bigben import get_bigben
        reply, done = await handle_registration_step(conv, "15.03.2016", get_bigben())
        assert conv.lead.birthday == "2016-03-15"
        assert not done
        assert conv.registration_step == "phone"

    @pytest.mark.asyncio
    async def test_birthday_invalid(self, _enable_registration):
        store = get_store()
        conv = store.get("reg-bday-bad")
        conv.stage = STAGE_REGISTRATION
        conv.registration_step = "birthday"
        conv.lead.fio_parent = "Иванова Анна"
        conv.lead.fio_child = "Миша"

        from app.bigben import get_bigben
        reply, done = await handle_registration_step(conv, "вчера", get_bigben())
        assert not conv.lead.birthday
        assert not conv.lead.age
        assert "возраст" in reply.lower() or "рождения" in reply.lower()
        assert not done

    @pytest.mark.asyncio
    async def test_phone_accepted_completes_registration(self, _enable_registration):
        store = get_store()
        conv = store.get("reg-phone")
        conv.stage = STAGE_REGISTRATION
        conv.registration_step = "phone"
        conv.lead.fio_parent = "Иванова Анна"
        conv.lead.fio_child = "Миша"
        conv.lead.age = "9"

        from app.bigben import get_bigben
        reply, done = await handle_registration_step(
            conv, "+7 999 123 45 67", get_bigben()
        )
        assert conv.lead.phone == "+79991234567"
        assert done
        assert conv.registered is True
        assert "открыты" in reply.lower() or REG_COMPLETE in reply

    @pytest.mark.asyncio
    async def test_phone_rejected(self, _enable_registration):
        store = get_store()
        conv = store.get("reg-phone-bad")
        conv.stage = STAGE_REGISTRATION
        conv.registration_step = "phone"
        conv.lead.fio_parent = "Иванова Анна"
        conv.lead.fio_child = "Миша"
        conv.lead.age = "9"

        from app.bigben import get_bigben
        reply, done = await handle_registration_step(conv, "нет телефона", get_bigben())
        assert not conv.lead.phone
        assert "телефон" in reply.lower()
        assert not done


# --- Integration tests: full flow through handle_message / handle_start ---


class TestRegistrationIntegration:
    @pytest.mark.asyncio
    async def test_handle_start_begins_registration(self, _enable_registration):
        uid = "reg-int-start"
        get_store().reset(uid)
        reply = await handle_start(uid)
        assert "познакомимся" in reply
        conv = get_store().get(uid)
        assert conv.stage == STAGE_REGISTRATION

    @pytest.mark.asyncio
    async def test_full_registration_flow(self, _enable_registration):
        uid = "reg-int-full"
        get_store().reset(uid)

        # Start
        reply = await handle_start(uid)
        assert "ФИО" in reply or "зовут" in reply.lower()

        # Step 1: fio_parent
        reply = await handle_message(uid, "Петрова Мария")
        assert "ребёнка" in reply.lower() or "зовут" in reply.lower()

        # Step 2: fio_child
        reply = await handle_message(uid, "Саша")
        assert "рождения" in reply.lower() or "возраст" in reply.lower()

        # Step 3: birthday
        reply = await handle_message(uid, "7 лет")
        assert "телефон" in reply.lower()

        # Step 4: phone → completes
        reply = await handle_message(uid, "89991234567")
        assert "открыты" in reply.lower() or "возможности" in reply.lower()

        conv = get_store().get(uid)
        assert conv.registered is True
        assert conv.lead.fio_parent == "Петрова Мария"
        assert conv.lead.fio_child == "Саша"
        assert conv.lead.age == "7"
        assert conv.lead.phone == "+79991234567"

    @pytest.mark.asyncio
    async def test_after_registration_bot_works_normally(self, _enable_registration):
        uid = "reg-int-after"
        get_store().reset(uid)

        # Register first
        await handle_start(uid)
        await handle_message(uid, "Сидорова Ольга")
        await handle_message(uid, "Даша")
        await handle_message(uid, "10 лет")
        reply = await handle_message(uid, "+79161234567")
        assert "открыты" in reply.lower()

        # Now bot should work normally
        reply = await handle_message(uid, "Какие курсы есть?")
        # Should not ask for registration again
        assert "зовут" not in reply.lower() or "познакомимся" not in reply.lower()
        conv = get_store().get(uid)
        assert conv.registered is True

    @pytest.mark.asyncio
    async def test_registered_user_not_asked_again(self, _enable_registration):
        uid = "reg-int-repeat"
        store = get_store()
        conv = store.get(uid)
        conv.registered = True
        store.save(conv)

        reply = await handle_message(uid, "Привет")
        assert "познакомимся" not in reply
        assert "ФИО" not in reply

    @pytest.mark.asyncio
    async def test_handle_start_preserves_registration(self, _enable_registration):
        uid = "reg-int-preserve"
        store = get_store()
        conv = store.get(uid)
        conv.registered = True
        conv.lead.fio_parent = "Тест"
        conv.lead.phone = "+79990000000"
        store.save(conv)

        reply = await handle_start(uid)
        # Should NOT start registration again
        assert "познакомимся" not in reply
        conv = store.get(uid)
        assert conv.registered is True
