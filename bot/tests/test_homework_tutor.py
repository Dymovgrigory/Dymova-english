"""Помощник по ДЗ должен учить, а не решать за ученика."""
import pytest

from app.main import (
    HOMEWORK_INVITE,
    _homework_system_prompt,
    _homework_task_text,
    _homework_text_user_prompt,
    _homework_user_prompt,
    explain_homework_text,
)


def test_system_prompt_forbids_solving():
    p = _homework_system_prompt().lower()
    assert "не давай готовых ответов" in p
    assert "не решай задание за него" in p
    assert "пример" in p
    assert "подсказки" in p


def test_system_prompt_teaches_via_invented_example():
    p = _homework_system_prompt().lower()
    # Метод: правило → придуманный похожий пример с решением → план для своего ДЗ.
    assert "правил" in p
    assert "похожее задание" in p
    assert "пошагово" in p
    assert "план" in p
    assert "самостоятельно" in p


def test_user_prompt_forbids_solving():
    p = _homework_user_prompt("").lower()
    assert "не давай готовые ответы" in p
    assert "не решай за ребёнка" in p
    assert "пример" in p


def test_user_prompt_includes_note():
    assert "мама просила помочь" in _homework_user_prompt("мама просила помочь").lower()


def test_text_user_prompt_includes_task_and_forbids_solving():
    p = _homework_text_user_prompt("Вставь am/is/are: I __ nine.").lower()
    assert "вставь am/is/are" in p
    assert "не давай готовые ответы" in p
    assert "не решай за ребёнка" in p


def test_task_text_extracts_real_task():
    task = _homework_task_text("Помоги с домашкой по английскому: вставь am/is/are — I __ nine")
    assert "am/is/are" in task
    assert "помоги" not in task


def test_task_text_empty_for_plain_request():
    assert _homework_task_text("помоги с домашкой") == ""
    assert _homework_task_text("помощь с дз") == ""
    assert _homework_task_text("мне нужна помощь с домашним заданием") == ""


def test_invite_mentions_free_and_no_ready_answers():
    assert "бесплатн" in HOMEWORK_INVITE.lower()
    assert "не дам готовый ответ" in HOMEWORK_INVITE.lower()


@pytest.mark.asyncio
async def test_explain_homework_text_uses_gateway(monkeypatch):
    from app import main

    calls = []

    class FakeGateway:
        async def complete(self, role, messages, *, temperature=None, max_tokens=None, vault=None):
            calls.append((role, messages, temperature, max_tokens))
            return "Правило: глагол to be..."

    monkeypatch.setattr(main, "get_gateway", lambda: FakeGateway())
    reply = await explain_homework_text("Вставь am/is/are: I __ nine.")
    assert reply.startswith("Правило")
    role, messages, temperature, max_tokens = calls[0]
    assert messages[0]["role"] == "system"
    assert "вставь am/is/are" in messages[1]["content"].lower()
    assert max_tokens and max_tokens >= 1000
