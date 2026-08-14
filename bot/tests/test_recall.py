"""Долгосрочная память: что человек рассказал двадцать реплик назад.

Главная проверка здесь — что факты не исчезают при выходе из окна истории.
Раньше `add()` просто отрезал старое, и бот заново спрашивал возраст у того,
кто его уже называл. Тесты идут и с моделью, и без неё: сжатие обязано
работать в обоих режимах, иначе память держится на доступности провайдера.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import recall, sales
from app.ai_core import handle_message, handle_start
from app.knowledge.kb import get_kb
from app.memory import MAX_DROPPED, MAX_HISTORY, Conversation, Lead, get_store
from app.smart import NeedProfile


@pytest.fixture(autouse=True)
def _fresh_store():
    get_store()._data.clear()


def _talkative(count: int) -> Conversation:
    conv = Conversation(user_id="recall-test")
    for i in range(count):
        conv.add("user", f"сообщение клиента {i}")
        conv.add("assistant", f"ответ бота {i}")
    return conv


# ------------------------- окно истории -------------------------


def test_dropped_messages_are_queued_not_lost():
    conv = _talkative(15)
    assert len(conv.history) == MAX_HISTORY
    assert conv.dropped, "выпавшие сообщения обязаны попасть в очередь на сжатие"
    assert conv.dropped[0]["content"] == "сообщение клиента 0"


def test_dropped_queue_is_bounded():
    conv = _talkative(60)
    assert len(conv.dropped) <= MAX_DROPPED


def test_short_dialogue_drops_nothing():
    conv = _talkative(3)
    assert conv.dropped == []
    assert not recall.needs_fold(conv)


# ------------------------- свёртка -------------------------


async def test_fold_without_model_keeps_client_facts():
    """LLM недоступна — память всё равно обязана сохранить сказанное."""
    conv = Conversation(user_id="recall-nomodel")
    conv.dropped = [
        {"role": "user", "content": "Сыну 9 лет, третий класс"},
        {"role": "assistant", "content": "Понял вас"},
        {"role": "user", "content": "Ему тяжело даётся говорение"},
    ]
    await recall.fold(conv)
    assert "9 лет" in conv.digest
    assert "говорение" in conv.digest
    assert conv.dropped == []


async def test_fold_uses_the_model_when_available(monkeypatch):
    conv = Conversation(user_id="recall-model")
    conv.dropped = [{"role": "user", "content": "Сыну 9 лет"}]
    monkeypatch.setattr(
        recall, "get_gateway", lambda: _FakeGateway("Сыну 9 лет, ищут английский.")
    )
    await recall.fold(conv)
    assert conv.digest == "Сыну 9 лет, ищут английский."
    assert conv.dropped == []


async def test_fold_falls_back_when_model_fails(monkeypatch):
    conv = Conversation(user_id="recall-broken")
    conv.dropped = [{"role": "user", "content": "Сыну 9 лет"}]
    monkeypatch.setattr(recall, "get_gateway", lambda: _FakeGateway(error=True))
    await recall.fold(conv)
    assert "9 лет" in conv.digest
    assert conv.dropped == []


async def test_fold_ignores_empty_model_answer(monkeypatch):
    """«нет» от модели означает «фактов не было», а не «сотри память»."""
    conv = Conversation(user_id="recall-empty")
    conv.digest = "Сыну 9 лет."
    conv.dropped = [{"role": "user", "content": "ок"}]
    monkeypatch.setattr(recall, "get_gateway", lambda: _FakeGateway("нет"))
    await recall.fold(conv)
    assert "9 лет" in conv.digest


async def test_digest_stays_bounded():
    conv = Conversation(user_id="recall-long")
    conv.dropped = [
        {"role": "user", "content": f"длинная реплика клиента номер {i} " * 10}
        for i in range(MAX_DROPPED)
    ]
    await recall.fold(conv)
    assert len(conv.digest) <= recall.DIGEST_LIMIT + 1


async def test_fold_is_idempotent_when_queue_is_empty():
    conv = Conversation(user_id="recall-idle")
    conv.digest = "Сыну 9 лет."
    await recall.fold(conv)
    assert conv.digest == "Сыну 9 лет."


# ------------------------- память в промпте -------------------------


def test_digest_reaches_the_system_prompt():
    conv = Conversation(user_id="recall-prompt")
    conv.digest = "Сыну 9 лет, тяжело даётся говорение."
    prompt = sales.build_system_prompt(get_kb(), conv, "")
    assert "тяжело даётся говорение" in prompt


def test_prompt_has_no_memory_block_without_digest():
    prompt = sales.build_system_prompt(get_kb(), Conversation(user_id="x"), "")
    assert "ИЗ ПРОШЛЫХ СООБЩЕНИЙ" not in prompt


async def test_long_dialogue_does_not_lose_the_early_facts():
    """Сквозная проверка: факт из начала разговора жив после выхода из окна."""
    uid = "recall-live"
    await handle_message(uid, "Сыну 9 лет, ищем английский")
    for i in range(12):
        await handle_message(uid, f"а ещё вопрос номер {i}")
    conv = get_store().get(uid)
    assert conv.digest, "давние сообщения обязаны свернуться в память"
    assert "9 лет" in conv.digest


# ------------------------- возвращение клиента -------------------------


def test_returning_line_names_the_child_and_subject():
    conv = Conversation(user_id="ret-1")
    conv.lead = Lead(fio_child="Иванова Маша")
    conv.selected_course = "Английский для школьников"
    line = recall.returning_line(conv)
    assert "для Маши" in line
    assert "английский для школьников" in line


def test_returning_line_works_with_child_name_only():
    conv = Conversation(user_id="ret-2")
    conv.lead = Lead(fio_child="Иванова Маша")
    assert recall.returning_line(conv) == "Мы с вами обсуждали занятия для Маши."


def test_returning_line_falls_back_to_the_topic():
    conv = Conversation(user_id="ret-3")
    conv.need = NeedProfile(child_age="9 лет")
    assert "ребёнка 9 лет" in recall.returning_line(conv)


def test_returning_line_is_empty_when_nothing_is_known():
    assert recall.returning_line(Conversation(user_id="ret-4")) == ""


async def test_returning_greeting_is_human_not_forensic():
    """ТЗ прямо запрещает «11 августа в 14:35 вы сообщили»."""
    uid = "ret-live"
    store = get_store()
    conv = store.get(uid)
    conv.lead = Lead(fio_parent="Иванова Анна", fio_child="Иванова Маша", phone="+79990000000")
    conv.selected_course = "Английский для школьников"
    conv.updated_at = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat()

    reply = await handle_start(uid)

    assert "Маши" in reply
    assert "возвращением" in reply.lower()
    for creepy in ("14:", "августа", "прошлый диалог", "записи о вас"):
        assert creepy not in reply.lower()


class _FakeGateway:
    """Шлюз, отвечающий заранее заданным текстом (или падающий по требованию)."""

    enabled = True

    def __init__(self, reply: str = "", error: bool = False):
        self._reply = reply
        self._error = error

    async def complete(self, role, messages, **kwargs):
        if self._error:
            raise RuntimeError("провайдер недоступен")
        return self._reply
