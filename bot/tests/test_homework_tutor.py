"""Помощник по ДЗ должен учить, а не решать за ученика."""
from app.main import _homework_system_prompt, _homework_user_prompt


def test_system_prompt_forbids_solving():
    p = _homework_system_prompt().lower()
    assert "не давать готовые ответы" in p or "не давай готовые ответы" in p
    assert "не выполнять его за ученика" in p or "решать за него" in p
    assert "пример" in p
    assert "как это сделать" in p


def test_user_prompt_forbids_solving():
    p = _homework_user_prompt("").lower()
    assert "не давай готовые ответы" in p
    assert "не решай за ребёнка" in p
    assert "пример" in p


def test_user_prompt_includes_note():
    assert "мама просила помочь" in _homework_user_prompt("мама просила помочь").lower()
