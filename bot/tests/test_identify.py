"""Идентификация клиента по номеру телефона (спека approach-1, разделы 2/6)."""
import json

import pytest

import app.main as main
from app import identify
from app import memory as memory_module
from app.ai_core import handle_message, handle_start
from app.config import settings
from app.memory import MemoryStore, get_store
from app.platform import bb_store


@pytest.fixture
def _enabled(monkeypatch):
    """Включает гейт идентификации и даёт чистую read-model CRM."""
    monkeypatch.setattr(settings, "IDENTIFICATION_REQUIRED", True)
    bb_store._local.conn = None


@pytest.fixture
def fresh_store(monkeypatch):
    monkeypatch.setattr(settings, "STATE_FILE", "")
    store = MemoryStore()
    monkeypatch.setattr(memory_module, "_store", store)
    return store


def _student(student_id, fio, phone="79251112233", **extra):
    bb_store.upsert_student({
        "id": student_id, "fio": fio, "phone": phone,
        "email": "", "balance_kopecks": 0, **extra,
    })


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


# --- Нормализация и нечёткие имена ---


class TestPhoneNormalize:
    def test_variants(self):
        assert identify.normalize_phone("+7 (925) 111-22-33") == "+79251112233"
        assert identify.normalize_phone("89251112233") == "+79251112233"
        assert identify.normalize_phone("9251112233") == "+79251112233"

    def test_garbage(self):
        assert identify.normalize_phone("привет") == ""


class TestNameMatches:
    @pytest.mark.parametrize("given,fio", [
        ("Маша", "Иванова Мария"),
        ("мария", "Иванова Мария"),
        ("Петя", "Сидоров Пётр"),
        ("Настя", "Анастасия Ким"),
        ("Соня", "Орлова София"),
    ])
    def test_match(self, given, fio):
        assert identify.name_matches(given, fio) is True

    @pytest.mark.parametrize("given,fio", [
        ("Катя", "Иванова Мария"),
        ("Марьяна", "Иванова Мария"),
        ("", "Иванова Мария"),
    ])
    def test_no_match(self, given, fio):
        assert identify.name_matches(given, fio) is False


# --- Сценарий handle_contact ---


class TestHandleContact:
    def test_unknown_phone_makes_new_lead(self, _enabled, fresh_store):
        conv = get_store().get("id-new")
        reply = identify.handle_contact(conv, "+7 925 111-22-33")
        assert conv.lead.phone == "+79251112233"
        assert conv.student_id == 0
        assert conv.identify_state == ""
        assert not identify.needs_gate(conv)

    def test_single_student_asks_child_name(self, _enabled, fresh_store):
        _student(11, "Иванова Мария")
        conv = get_store().get("id-one")
        reply = identify.handle_contact(conv, "89251112233")
        assert "как зовут" in reply.lower()
        assert conv.identify_state == identify.STATE_AWAIT_CHILD_NAME
        assert conv.identify_candidates[0]["id"] == 11

    def test_several_children_offer_choice(self, _enabled, fresh_store):
        _student(11, "Иванова Мария")
        _student(12, "Иванов Пётр")
        conv = get_store().get("id-many")
        reply = identify.handle_contact(conv, "+79251112233")
        assert "Иванова Мария" in reply and "Иванов Пётр" in reply
        assert conv.identify_state == identify.STATE_AWAIT_CHILD_CHOICE
        assert len(conv.identify_candidates) == 2

    def test_age_shown_when_known(self, _enabled, fresh_store):
        _student(11, "Иванова Мария", age=7)
        _student(12, "Иванов Пётр")
        conv = get_store().get("id-age")
        reply = identify.handle_contact(conv, "+79251112233")
        assert "Иванова Мария (7 лет)" in reply


class TestPending:
    def test_name_match_identifies(self, _enabled, fresh_store):
        _student(11, "Иванова Мария")
        conv = get_store().get("p-match")
        identify.handle_contact(conv, "+79251112233")
        reply = identify.handle_pending(conv, "Маша")
        assert conv.student_id == 11
        assert conv.registered is True
        assert conv.lead.fio_child == "Иванова Мария"
        assert "нашла" in reply.lower()
        assert not identify.needs_gate(conv)

    def test_name_mismatch_makes_new_lead(self, _enabled, fresh_store):
        _student(11, "Иванова Мария")
        conv = get_store().get("p-mismatch")
        identify.handle_contact(conv, "+79251112233")
        reply = identify.handle_pending(conv, "Катя")
        assert conv.student_id == 0
        assert conv.identify_state == ""
        assert conv.lead.phone == "+79251112233"  # номер сохраняется в лид
        assert not identify.needs_gate(conv)

    def test_choice_by_number(self, _enabled, fresh_store):
        _student(11, "Иванова Мария")
        _student(12, "Иванов Пётр")
        conv = get_store().get("p-num")
        identify.handle_contact(conv, "+79251112233")
        identify.handle_pending(conv, "2")
        assert conv.student_id == 12

    def test_choice_by_name(self, _enabled, fresh_store):
        _student(11, "Иванова Мария")
        _student(12, "Иванов Пётр")
        conv = get_store().get("p-name")
        identify.handle_contact(conv, "+79251112233")
        identify.handle_pending(conv, "Петя")
        assert conv.student_id == 12

    def test_choice_unknown_repeats_list(self, _enabled, fresh_store):
        _student(11, "Иванова Мария")
        _student(12, "Иванов Пётр")
        conv = get_store().get("p-unknown")
        identify.handle_contact(conv, "+79251112233")
        reply = identify.handle_pending(conv, "Зара")
        assert conv.student_id == 0
        assert conv.identify_state == identify.STATE_AWAIT_CHILD_CHOICE
        assert "Иванова Мария" in reply


# --- Гейтинг в диалоге ---


class TestGating:
    @pytest.mark.asyncio
    async def test_start_asks_contact(self, _enabled, fresh_store):
        reply = await handle_start("g-start")
        assert "номером телефона" in reply
        conv = get_store().get("g-start")
        assert conv.identify_state == identify.STATE_AWAIT_CONTACT

    @pytest.mark.asyncio
    async def test_message_without_phone_is_gated(self, _enabled, fresh_store):
        reply = await handle_message("g-msg", "Сколько стоит английский?")
        assert "номер" in reply.lower()
        assert "стоим" not in reply.lower() or "номер" in reply.lower()
        conv = get_store().get("g-msg")
        assert conv.identify_state == identify.STATE_AWAIT_CONTACT

    @pytest.mark.asyncio
    async def test_phone_in_text_is_treated_as_contact(self, _enabled, fresh_store):
        _student(11, "Иванова Мария")
        reply = await handle_message("g-phone", "мой номер +7 925 111-22-33")
        assert "как зовут" in reply.lower()
        conv = get_store().get("g-phone")
        assert conv.identify_state == identify.STATE_AWAIT_CHILD_NAME

    @pytest.mark.asyncio
    async def test_identified_user_passes_gate(self, _enabled, fresh_store):
        conv = get_store().get("g-ok")
        conv.student_id = 11
        assert not identify.needs_gate(conv)

    @pytest.mark.asyncio
    async def test_new_lead_goes_to_registration_with_phone_known(
        self, _enabled, fresh_store, monkeypatch
    ):
        """После идентификации «новый лид» анкета начинается с ФИО родителя,
        шаг телефона пропускается (раздел 2 спеки)."""
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True)
        reply = await handle_message("g-reg", "+7 925 111-22-33")
        conv = get_store().get("g-reg")
        assert conv.lead.phone == "+79251112233"
        assert conv.registration_step == "fio_parent"
        assert "зовут" in reply.lower() or "ФИО" in reply


# --- Транспорт ---


class TestTelegramTransport:
    @pytest.mark.asyncio
    async def test_send_contact_request_keyboard(self, monkeypatch):
        from app.telegram_client import TelegramClient

        client = TelegramClient()
        sent = {}

        async def fake_post(method, data, **kwargs):
            sent.update(data)
            return {"message_id": 1}

        monkeypatch.setattr(client, "_post", fake_post)
        ok = await client.send_contact_request(123, "Нажмите кнопку ниже")
        assert ok is True
        markup = json.loads(sent["reply_markup"])
        button = markup["keyboard"][0][0]
        assert button["request_contact"] is True
        assert "номером" in button["text"]

    @pytest.mark.asyncio
    async def test_telegram_contact_message_identifies(
        self, _enabled, fresh_store, monkeypatch
    ):
        _student(11, "Иванова Мария")

        class FakeTelegram:
            def __init__(self):
                self.sent = []

            async def send_message(self, chat_id, text, buttons=None):
                self.sent.append(text)
                return True

        tg = FakeTelegram()
        update = {
            "update_id": 1,
            "message": {
                "chat": {"id": 777},
                "contact": {"phone_number": "+79251112233"},
            },
        }
        await main._process_telegram_update(update, tg)
        assert tg.sent and "как зовут" in tg.sent[-1].lower()
        conv = get_store().get("tg:777", platform="telegram")
        assert conv.identify_state == identify.STATE_AWAIT_CHILD_NAME


class TestMaxTransport:
    @pytest.mark.asyncio
    async def test_start_has_share_button(self, _enabled, fresh_store):
        fake = FakeMaxClient()
        await main._process_update(
            {"type": "bot_started", "user": {"user_id": "m-start"}}, "bot_started", fake
        )
        assert fake.sent
        _uid, _text, buttons = fake.sent[-1]
        assert buttons[0][0]["payload"] == identify.SHARE_BUTTON_PAYLOAD

    @pytest.mark.asyncio
    async def test_share_callback_asks_phone_text(self, _enabled, fresh_store):
        fake = FakeMaxClient()
        update = {
            "type": "message_callback",
            "callback": {
                "callback_id": "cb-1",
                "payload": identify.SHARE_BUTTON_PAYLOAD,
                "sender": {"user_id": "m-share"},
            },
        }
        await main._process_update(update, "message_callback", fake)
        assert fake.answered
        _uid, text, _buttons = fake.sent[-1]
        assert "номер телефона текстом" in text
        conv = get_store().get("m-share")
        assert conv.identify_state == identify.STATE_AWAIT_CONTACT
