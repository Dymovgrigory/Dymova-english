"""Незарегистрированный клиент TG/MAX получает кнопку анкеты, а не вопросы."""
import pytest

from app import ai_core, registration
from app import main as main_module
from app import memory as memory_module
from app.config import settings


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
