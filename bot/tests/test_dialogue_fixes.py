import pytest

from app.ai_core import _drop_trailing_question, _handoff_followup_reply, _wants_manager
from app.knowledge.kb import get_kb
from app.llm import _clean_response
from app.memory import Conversation, Lead
from app import lead_manager


# --- A: английские слова-вставки ---

def test_clean_response_strips_stray_english_filler():
    assert _clean_response("Цена indeed важна для нас") == "Цена важна для нас"


def test_clean_response_keeps_brand_names():
    out = _clean_response("Мы работаем по учебникам My Level и центру Hippo")
    assert "My Level" in out
    assert "Hippo" in out


def test_clean_response_keeps_mostly_english_untouched():
    text = "My Level is an English textbook series"
    assert _clean_response(text) == text


# --- B: дата рождения на шаге телефона ---

@pytest.mark.asyncio
async def test_phone_step_acknowledges_birthday_instead_of_error():
    conv = Conversation(user_id="b1")
    conv.lead = Lead(fio_parent="Иванова Мария", fio_child="Иванов Артём")
    conv.lead_step = "phone"
    reply, submitted = await lead_manager.step(conv, "12.05.2018", get_kb(), None, None)
    assert submitted is False
    assert "Дату рождения записал" in reply
    assert "не полностью" not in reply
    assert conv.lead.birthday == "2018-05-12"


@pytest.mark.asyncio
async def test_consult_uses_configured_history_window(monkeypatch):
    from app import ai_core
    from app.config import settings

    monkeypatch.setattr(settings, "LLM_HISTORY_TURNS", 4)

    conv = Conversation(user_id="h1")
    conv.history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg-{i}"}
        for i in range(10)
    ]
    captured = {}

    class FakeLLM:
        enabled = True

        async def complete(self, messages, temperature=None):
            captured["messages"] = messages
            return "Готово"

    monkeypatch.setattr(ai_core, "get_llm", lambda: FakeLLM())

    reply = await ai_core._consult_with_context(conv, "Сколько стоит обучение?", "")
    assert reply == "Готово"
    assert len(captured["messages"]) == 5
    assert captured["messages"][1:] == conv.history[-4:]


# --- D: жалоба без дословных повторов + руководитель ---

def test_handoff_followup_reacts_to_manager_request():
    conv = Conversation(user_id="d1")
    reply = _handoff_followup_reply(conv, "Хочу поговорить с руководителем")
    assert "руководител" in reply.lower()
    assert "923-23-09" in reply


def test_handoff_followups_do_not_repeat_verbatim():
    conv = Conversation(user_id="d2")
    conv.history = [{"role": "assistant", "content": "x"}]
    first = _handoff_followup_reply(conv, "это уже второй раз")
    conv.history.append({"role": "assistant", "content": "y"})
    second = _handoff_followup_reply(conv, "и снова тишина")
    assert first != second


def test_drop_trailing_question_removes_final_question():
    out = _drop_trailing_question(
        "Пробное длится 45-60 минут. На каком языке хотите заниматься?"
    )
    assert out == "Пробное длится 45-60 минут."


def test_drop_trailing_question_keeps_statement():
    text = "Пробное длится 45-60 минут."
    assert _drop_trailing_question(text) == text


def test_wants_manager_detection():
    assert _wants_manager("позовите директора")
    assert not _wants_manager("сколько стоит обучение")
