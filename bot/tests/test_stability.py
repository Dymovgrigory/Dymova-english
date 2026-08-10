"""Регрессии на «бот завис / потерял сообщение / перепутал контекст».

Каждый тест здесь фиксирует конкретный сценарий, в котором бот раньше
переставал отвечать или отвечал не то.
"""
import asyncio

import pytest

from app import ai_core
from app import main as main_module
from app import memory as memory_module
from app.config import settings


@pytest.fixture(autouse=True)
def reset_state():
    main_module._BACKGROUND_TASKS.clear()
    memory_module._store = None
    ai_core.reset_conversation_locks()
    yield
    main_module._BACKGROUND_TASKS.clear()
    memory_module._store = None
    ai_core.reset_conversation_locks()


class FakeTelegramClient:
    def __init__(self):
        self.sent = []
        self.actions = []

    async def send_message(self, chat_id, text, buttons=None):
        self.sent.append({"chat_id": chat_id, "text": text, "buttons": buttons})
        return True

    async def send_chat_action(self, chat_id, action="typing"):
        self.actions.append({"chat_id": chat_id, "action": action})
        return True

    async def answer_callback_query(self, callback_query_id, text=None):
        self.sent.append({"answer_callback": callback_query_id, "text": text})
        return True


# --------------------------------------------------------------------------
# 1. Long-polling: дубликат не должен замораживать offset
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_loop_advances_offset_even_for_duplicate_update(monkeypatch):
    """Раньше offset двигался только для НОВЫХ апдейтов.

    После рестарта Telegram переотдаёт неподтверждённый апдейт, он уже лежит
    в processed_events → _schedule_telegram_update возвращает False → offset
    остаётся прежним → getUpdates бесконечно возвращает тот же батч, и бот
    больше не отвечает НИКОМУ. Это и есть «бот завис».
    """
    offsets = []

    class PollClient:
        def __init__(self):
            self.calls = 0

        async def delete_webhook(self):
            return True

        async def get_updates(self, offset, timeout=25):
            offsets.append(offset)
            self.calls += 1
            if self.calls >= 3:
                raise asyncio.CancelledError
            return [{"update_id": 10, "message": {"chat": {"id": 1}, "text": "hi"}}]

    # Всегда «дубликат».
    monkeypatch.setattr(main_module, "_schedule_telegram_update", lambda u, t: False)

    with pytest.raises(asyncio.CancelledError):
        await main_module._telegram_poll_loop(PollClient())

    assert offsets[0] is None
    assert offsets[1] == 11, "offset обязан двигаться и для уже обработанного апдейта"


# --------------------------------------------------------------------------
# 2. Параллельные сообщения одного пользователя
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_messages_from_one_user_are_serialized(monkeypatch):
    """Три сообщения подряд не должны наслаиваться на общий Conversation."""
    order = []

    async def slow_route(conv, text, kb, intent):
        order.append(("start", text))
        await asyncio.sleep(0.02)
        order.append(("end", text))
        return f"ответ на {text}"

    monkeypatch.setattr(ai_core, "_route", slow_route)
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", False, raising=False)

    replies = await asyncio.gather(
        ai_core.handle_message("u1", "привет"),
        ai_core.handle_message("u1", "цены?"),
        ai_core.handle_message("u1", "онлайн есть?"),
    )

    assert replies == ["ответ на привет", "ответ на цены?", "ответ на онлайн есть?"]
    # Ни один обработчик не начался, пока не закончился предыдущий.
    for i in range(0, len(order), 2):
        assert order[i][0] == "start" and order[i + 1][0] == "end"
        assert order[i][1] == order[i + 1][1]


@pytest.mark.asyncio
async def test_different_users_are_not_blocked_by_each_other(monkeypatch):
    """Медленный диалог одного пользователя не должен тормозить остальных."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def route(conv, text, kb, intent):
        if conv.user_id == "slow":
            started.set()
            await release.wait()
            return "медленно"
        return "быстро"

    monkeypatch.setattr(ai_core, "_route", route)

    slow = asyncio.create_task(ai_core.handle_message("slow", "вопрос"))
    await asyncio.wait_for(started.wait(), timeout=1)
    fast = await asyncio.wait_for(ai_core.handle_message("fast", "вопрос"), timeout=1)
    release.set()

    assert fast == "быстро"
    assert await slow == "медленно"


# --------------------------------------------------------------------------
# 3. Дедлайн ответа: бот не молчит бесконечно
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hanging_handler_falls_back_instead_of_silence(monkeypatch):
    """Если внутренняя логика зависла, пользователь получает живой ответ."""

    async def never_returns(conv, text, kb, intent):
        await asyncio.sleep(3600)

    monkeypatch.setattr(ai_core, "_route", never_returns)
    monkeypatch.setattr(settings, "REPLY_TIMEOUT_SEC", 0.05, raising=False)

    reply = await asyncio.wait_for(ai_core.handle_message("u2", "вопрос"), timeout=2)

    assert reply
    assert "ошиб" not in reply.lower()
    assert "traceback" not in reply.lower()


@pytest.mark.asyncio
async def test_timeout_is_recorded_in_history(monkeypatch):
    """После таймаута контекст остаётся связным: вопрос + честный ответ."""

    async def never_returns(conv, text, kb, intent):
        await asyncio.sleep(3600)

    monkeypatch.setattr(ai_core, "_route", never_returns)
    monkeypatch.setattr(settings, "REPLY_TIMEOUT_SEC", 0.05, raising=False)

    reply = await ai_core.handle_message("u3", "сколько стоит?")
    conv = memory_module.get_store().get("u3")

    assert conv.history[-2] == {"role": "user", "content": "сколько стоит?"}
    assert conv.history[-1] == {"role": "assistant", "content": reply}


@pytest.mark.asyncio
async def test_exception_in_route_returns_human_fallback(monkeypatch):
    """Исключение внутри логики не должно всплывать в чат как ошибка."""

    async def boom(conv, text, kb, intent):
        raise RuntimeError("db is down")

    monkeypatch.setattr(ai_core, "_route", boom)

    reply = await ai_core.handle_message("u4", "вопрос")

    assert reply
    assert "db is down" not in reply
    assert "RuntimeError" not in reply


# --------------------------------------------------------------------------
# 4. Платформа диалога: контекст не должен раздваиваться
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telegram_conversation_is_stored_once(monkeypatch):
    """tg-диалог должен лежать в одной строке БД, а не в max- и telegram-."""
    monkeypatch.setattr(ai_core, "_route", _echo_route)

    await ai_core.handle_message("tg:42", "привет", platform="telegram")
    store = memory_module.get_store()
    conv = store.get("tg:42", platform="telegram")

    assert conv.platform == "telegram"
    assert [m["content"] for m in conv.history if m["role"] == "user"] == ["привет"]

    rows = store._conn.execute(
        "SELECT platform FROM conversations WHERE user_id = ?", ("tg:42",)
    ).fetchall()
    assert [r["platform"] for r in rows] == ["telegram"]


@pytest.mark.asyncio
async def test_context_survives_process_restart(monkeypatch, tmp_path):
    """История должна переживать перезапуск процесса (не только кэш в памяти)."""
    monkeypatch.setattr(ai_core, "_route", _echo_route)
    db = tmp_path / "bot.db"

    memory_module._store = memory_module.MemoryStore(db)
    await ai_core.handle_message("tg:7", "какие у вас занятия?", platform="telegram")

    # «Перезапуск»: новый store поверх того же файла.
    memory_module._store = memory_module.MemoryStore(db)
    conv = memory_module.get_store().get("tg:7", platform="telegram")

    assert [m["content"] for m in conv.history if m["role"] == "user"] == [
        "какие у вас занятия?"
    ]


async def _echo_route(conv, text, kb, intent):
    return "ок"


# --------------------------------------------------------------------------
# 5. Telegram: кнопки и живость
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telegram_branch_picker_renders_buttons(monkeypatch):
    """«Позовите администратора» без филиала: вопрос без кнопок = тупик."""
    monkeypatch.setattr(settings, "ADMIN_MAX_IDS", "", raising=False)
    telegram = FakeTelegramClient()

    await main_module._process_telegram_update(
        {
            "update_id": 5001,
            "message": {"chat": {"id": 91}, "text": "соедините с администратором"},
        },
        telegram,
    )

    sent = [s for s in telegram.sent if s.get("text")]
    assert sent, "бот обязан ответить"
    assert sent[-1]["buttons"], "кнопки выбора филиала не должны теряться"


@pytest.mark.asyncio
async def test_telegram_callback_query_is_answered_and_routed(monkeypatch):
    """Нажатие кнопки без answerCallbackQuery = вечный спиннер в клиенте."""
    telegram = FakeTelegramClient()
    answered = []

    async def fake_answer(callback_query_id, text=None):
        answered.append(callback_query_id)
        return True

    telegram.answer_callback_query = fake_answer

    await main_module._process_telegram_update(
        {
            "update_id": 5002,
            "callback_query": {
                "id": "cbq-1",
                "from": {"id": 92},
                "message": {"chat": {"id": 92}},
                "data": "contact:lihachevsky",
            },
        },
        telegram,
    )

    assert answered == ["cbq-1"]
    assert telegram.sent, "после нажатия кнопки должен прийти ответ"


@pytest.mark.asyncio
async def test_telegram_shows_typing_while_thinking(monkeypatch):
    """Пока бот думает, в чате должен идти индикатор «печатает»."""

    async def slow_handle_message(user_id, text, platform="max"):
        await asyncio.sleep(0.05)
        return "готово"

    monkeypatch.setattr(main_module, "handle_message", slow_handle_message)
    monkeypatch.setattr(main_module, "TYPING_REFRESH_SEC", 0.01, raising=False)
    telegram = FakeTelegramClient()

    await main_module._process_telegram_update(
        {"update_id": 5003, "message": {"chat": {"id": 93}, "text": "вопрос про цены"}},
        telegram,
    )

    assert telegram.actions, "sendChatAction('typing') не отправлялся"
    assert telegram.actions[0]["chat_id"] == 93
