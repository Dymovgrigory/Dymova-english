"""Контакт MAX: кнопка «Поделиться номером» и разбор присланной визитки."""
import pytest

from app import max_client
from app import main as main_module
from app import memory as memory_module
from app.config import settings
from app.memory import get_store

VCF = "BEGIN:VCARD\nVERSION:3.0\nN:;Анна;;;\nFN:Анна\nTEL;TYPE=cell:+7 (926) 123-45-67\nEND:VCARD"


def test_contact_button_shape():
    btn = max_client.contact_button("📞 Поделиться номером")
    assert btn == {"type": "request_contact", "text": "📞 Поделиться номером"}


@pytest.mark.parametrize("attachments,expected", [
    ([{"type": "contact", "payload": {"vcf_info": VCF}}], "+79261234567"),
    ([{"type": "contact", "payload": {"vcf_info": "TEL:89261234567"}}], "+79261234567"),
    ([{"type": "contact", "payload": {"max_info": {"phone": "79261234567"}}}], "+79261234567"),
    ([{"type": "image", "payload": {}}], ""),
    ([{"type": "contact", "payload": {"vcf_info": "FN:Без номера"}}], ""),
    ([], ""),
])
def test_phone_from_contact_attachment(attachments, expected):
    assert max_client.phone_from_contact_attachment(attachments) == expected


def test_contact_owner_is_detected():
    own = [{"type": "contact", "payload": {"vcf_info": VCF, "max_info": {"user_id": 555}}}]
    assert max_client.contact_belongs_to(own, "555") is True
    assert max_client.contact_belongs_to(own, "556") is False


class FakeMax:
    configured = True

    def __init__(self):
        self.sent = []

    async def send_message(self, user_id, text, buttons=None):
        self.sent.append((user_id, text, buttons))
        return True


@pytest.fixture(autouse=True)
def gate(monkeypatch):
    memory_module._store = None
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "IDENTIFICATION_REQUIRED", False, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example.ru/app/", raising=False)
    yield
    memory_module._store = None


@pytest.mark.asyncio
async def test_shared_contact_is_saved_confirmed_and_replied():
    fake = FakeMax()
    update = {"message": {
        "sender": {"user_id": 555, "name": "Анна"},
        "body": {"text": "", "attachments": [
            {"type": "contact", "payload": {"vcf_info": VCF, "max_info": {"user_id": 555}}}]},
    }}
    await main_module._process_update(update, "message_created", fake)
    conv = get_store().get("555")
    assert conv.lead.phone == "+79261234567"
    assert conv.lead.phone_confirmed is True
    assert fake.sent and "номер" in fake.sent[-1][1].lower()


@pytest.mark.asyncio
async def test_someone_elses_contact_is_saved_but_not_confirmed():
    fake = FakeMax()
    update = {"message": {
        "sender": {"user_id": 556, "name": "Пётр"},
        "body": {"text": "", "attachments": [
            {"type": "contact", "payload": {"vcf_info": VCF, "max_info": {"user_id": 999}}}]},
    }}
    await main_module._process_update(update, "message_created", fake)
    conv = get_store().get("556")
    assert conv.lead.phone == "+79261234567"
    assert conv.lead.phone_confirmed is False


@pytest.mark.asyncio
async def test_start_menu_offers_contact_button_when_phone_unknown():
    rows = main_module._start_buttons("600", "max")
    assert any(b.get("type") == "request_contact" for row in rows for b in row)


@pytest.mark.asyncio
async def test_start_menu_has_no_contact_button_when_phone_known():
    conv = get_store().get("601")
    conv.lead.set_phone("+79261234567")
    get_store().save(conv)
    rows = main_module._start_buttons("601", "max")
    assert not any(b.get("type") == "request_contact" for row in rows for b in row)
