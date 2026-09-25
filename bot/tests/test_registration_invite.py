"""Незарегистрированный клиент TG/MAX получает кнопку анкеты, а не вопросы."""
import pytest

from app import ai_core, registration
from app import main as main_module
from app import memory as memory_module
from app.config import settings
from app.memory import get_store
from app.platform import bb_store


@pytest.fixture(autouse=True)
def gate_on(monkeypatch):
    memory_module._store = None
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example.ru/app/", raising=False)
    yield
    memory_module._store = None


@pytest.mark.asyncio
@pytest.mark.parametrize("platform,user", [("telegram", "tg:5"), ("max", "55")])
async def test_first_message_gets_form_invite(platform, user):
    reply = await ai_core.handle_message(user, "Здравствуйте, сколько стоит?", platform=platform)
    assert registration.FORM_INVITE_MARK in reply
    assert "Как вас зовут" not in reply


@pytest.mark.asyncio
async def test_web_widget_keeps_step_by_step():
    reply = await ai_core.handle_message("web:1", "привет", platform="web")
    assert registration.FORM_INVITE_MARK not in reply


def test_telegram_invite_gets_webapp_button_to_register():
    rows = main_module._telegram_buttons("привет", registration.FORM_INVITE)
    button = rows[0][0]
    assert button["type"] == "web_app"
    assert button["web_app"].endswith("/tg/#register")


def test_max_invite_gets_link_to_register():
    rows = main_module._link_button_rows("привет", registration.FORM_INVITE)
    assert "#register" in str(rows[0][0])


@pytest.mark.asyncio
async def test_telegram_contact_share_gets_form_invite_not_old_questions():
    """Шаринг контакта в Telegram (может прийти прямо во время заполнения
    анкеты в мини-приложении — requestContact у Telegram независим от формы)
    не должен подсовывать старый пошаговый опрос, когда анкета — форма."""
    bb_store._local.conn = None  # чистая read-model: номер не найден ни у одного ученика

    class FakeTelegram:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text, buttons=None):
            self.sent.append((text, buttons))
            return True

    tg = FakeTelegram()
    update = {
        "update_id": 1,
        "message": {
            "chat": {"id": 999},
            "from": {"id": 999},
            "contact": {"phone_number": "+79250000001", "user_id": 999},
        },
    }
    await main_module._process_telegram_update(update, tg)
    assert tg.sent
    reply, buttons = tg.sent[-1]
    assert "Как вас зовут" not in reply
    assert registration.FORM_INVITE_MARK in reply
    assert buttons, "приглашение на анкету не должно быть тупиком без кнопки"


class _FakeMaxClient:
    def __init__(self):
        self.sent = []
        self.answered = []

    async def send_message(self, user_id, text, buttons=None):
        self.sent.append((user_id, text, buttons))
        return True

    async def answer_callback(self, callback_id, notification=None):
        self.answered.append((callback_id, notification))
        return True


@pytest.mark.asyncio
async def test_max_menu_callback_gets_form_invite_button_for_unregistered():
    """Пункт меню MAX для незарегистрированного клиента отвечает
    приглашением на анкету — с кнопкой, а не тупиком."""
    fake = _FakeMaxClient()
    update = {
        "type": "message_callback",
        "callback": {
            "callback_id": "cb-price",
            "payload": "menu:price",
            "sender": {"user_id": "m-price"},
        },
    }
    await main_module._process_update(update, "message_callback", fake)
    assert fake.sent
    _uid, reply, buttons = fake.sent[-1]
    assert registration.FORM_INVITE_MARK in reply
    assert buttons, "приглашение на анкету не должно быть тупиком без кнопки"
