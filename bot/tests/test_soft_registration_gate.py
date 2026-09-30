"""Мягкий гейт анкеты в TG/MAX: сначала ответ по существу, анкета — после.

Разбор прода 29.09: из ~28 пришедших в MAX анкету заполнили двое — на вопрос
о цене бот отвечал одним приглашением на форму, а телефон, присланный
текстом, терялся.
"""
import pytest

from app import ai_core, registration
from app import memory as memory_module
from app.config import settings
from app.memory import get_store


@pytest.fixture(autouse=True)
def gate_on(monkeypatch):
    memory_module._store = None
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "IDENTIFICATION_REQUIRED", False, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example.ru/app/", raising=False)
    yield
    memory_module._store = None


class _SpyBigBen:
    configured = True

    def __init__(self):
        self.leads = []

    async def create_lead(self, lead, source, note="", utm=None):
        self.leads.append((lead.phone, source, note))
        return True


@pytest.fixture
def bigben(monkeypatch):
    spy = _SpyBigBen()
    monkeypatch.setattr(ai_core, "get_bigben", lambda: spy)
    return spy


@pytest.mark.asyncio
async def test_price_question_is_answered_not_only_invited(bigben):
    reply = await ai_core.handle_message("m1", "Сколько стоит обучение английскому?", platform="max")
    body = reply.replace(registration.FORM_INVITE, "")
    assert len(body.strip()) > 40, "на вопрос о цене нужен ответ, а не одно приглашение"
    assert reply != registration.FORM_INVITE
    assert registration.FORM_INVITE_MARK in reply, "под ответом остаётся кнопка анкеты"


@pytest.mark.asyncio
async def test_form_nudge_is_not_repeated_forever(bigben):
    marks = 0
    for i in range(8):
        reply = await ai_core.handle_message("m2", f"Расскажите про курсы, вопрос {i}", platform="max")
        marks += registration.FORM_INVITE_MARK in reply
    assert 1 <= marks <= registration.MAX_FORM_NUDGES


@pytest.mark.asyncio
async def test_phone_sent_in_chat_becomes_crm_lead_once(bigben):
    await ai_core.handle_message("m3", "89013561448", platform="max")
    await ai_core.handle_message("m3", "Спасибо, жду звонка", platform="max")
    assert len(bigben.leads) == 1
    assert bigben.leads[0][0].endswith("9013561448")
    assert get_store().get("m3", platform="max").phone_lead_sent is True


@pytest.mark.asyncio
async def test_chat_phone_lead_not_sent_for_registered_client(bigben):
    conv = get_store().get("m4", platform="max")
    conv.registered = True
    get_store().save(conv)
    await ai_core.handle_message("m4", "мой номер 89013561448", platform="max")
    assert bigben.leads == []


@pytest.mark.asyncio
async def test_handoff_request_still_hands_off(bigben, monkeypatch):
    called = []

    async def fake_hand_off(client, conv, reason=""):
        called.append(reason)

    monkeypatch.setattr(ai_core, "hand_off", fake_hand_off)
    await ai_core.handle_message("m5", "Соедините меня с администратором", platform="max")
    assert called


@pytest.mark.asyncio
async def test_web_keeps_step_by_step():
    reply = await ai_core.handle_message("web:9", "привет", platform="web")
    assert registration.FORM_INVITE_MARK not in reply


@pytest.mark.asyncio
async def test_reply_time_is_recorded_for_funnel(bigben):
    from app.platform import analytics, bb_store

    await ai_core.handle_message("m6", "Где находятся филиалы?", platform="max")
    rows = bb_store._db().execute(
        "SELECT meta_json FROM product_events WHERE event='bot_reply' AND anon_id='m6'"
    ).fetchall()
    assert rows and '"ms"' in rows[0][0]
