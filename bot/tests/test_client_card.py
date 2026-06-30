from datetime import datetime, timedelta, timezone

import pytest

from app.ai_core import handle_start
from app.knowledge.kb import get_kb
from app.memory import Conversation, Lead, get_store
from app.sales import build_system_prompt


def _conv_with_facts() -> Conversation:
    conv = Conversation(user_id="card-1")
    conv.lead = Lead(fio_child="Иванов Миша", age="9")
    conv.selected_course = "Английский для школьников"
    conv.selected_format = "Онлайн"
    conv.last_objection = "дорого"
    return conv


def test_client_card_collects_known_facts():
    conv = _conv_with_facts()
    card = conv.client_card()
    assert "имя ребёнка: Миша" in card
    assert "возраст ребёнка: 9" in card
    assert "интересует: Английский для школьников" in card
    assert "формат: Онлайн" in card
    assert "ранее сомневался: дорого" in card


def test_client_card_empty_when_nothing_known():
    assert Conversation(user_id="card-empty").client_card() == ""


def test_is_returning_requires_pause_and_facts():
    conv = _conv_with_facts()
    # без updated_at — не возвращенец
    assert conv.is_returning() is False
    conv.updated_at = (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()
    assert conv.is_returning() is True
    # недавняя активность — не считается возвращением
    conv.updated_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert conv.is_returning() is False


def test_system_prompt_includes_client_card():
    conv = _conv_with_facts()
    prompt = build_system_prompt(get_kb(), conv, "")
    assert "КАРТОЧКА КЛИЕНТА" in prompt
    assert "Миша" in prompt


@pytest.mark.asyncio
async def test_handle_start_welcomes_returning_client_and_keeps_profile():
    uid = "card-returning"
    store = get_store()
    conv = store.get(uid)
    conv.lead = Lead(fio_parent="Иванова Анна", fio_child="Иванов Миша", age="9")
    conv.selected_course = "Английский для школьников"
    conv.lead_submitted = True
    conv.updated_at = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat()

    reply = await handle_start(uid)

    assert "возвращением" in reply.lower()
    assert "Миша" in reply
    fresh = store.get(uid)
    assert fresh.lead.fio_child == "Иванов Миша"
    assert fresh.selected_course == "Английский для школьников"
    assert fresh.lead_submitted is True


@pytest.mark.asyncio
async def test_handle_start_fresh_client_gets_default_greeting():
    uid = "card-fresh"
    get_store().reset(uid)
    reply = await handle_start(uid)
    assert "возвращением" not in reply.lower()
    assert "Фокси" in reply
