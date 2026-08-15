"""Регрессионные тесты против «залипания» бота.

Каждый тест закрывает конкретный механизм, из-за которого клиент получал
одинаковые шаблонные ответы:
1. Анкета регистрации бесконечно переспрашивала имя на любой вопрос.
2. После передачи администратору любой вопрос получал «вопрос уже у администратора».
3. Без LLM одинаковый вопрос получал байт-идентичный ответ.
4. Служебные фолбэки (таймаут/ошибка) попадали в контекст LLM как «реплики бота».
5. MAX-апдейт без id обрабатывался повторно при ретрае вебхука.
6. Повторная эскалация в том же эпизоде спамила админ-чат.
"""
import pytest

from app import ai_core
from app.ai_core import ERROR_REPLY, TIMEOUT_REPLY, handle_message
from app.config import settings
from app.memory import STAGE_DISCOVERY, STAGE_HANDOFF, get_store


@pytest.fixture
def _enable_registration(monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True)


# --- 1. Off-topic вопросы во время регистрации ---


@pytest.mark.asyncio
async def test_registration_answers_question_instead_of_looping(_enable_registration):
    uid = "stick-reg-offtopic"
    await handle_message(uid, "привет", platform="web")
    reply = await handle_message(uid, "Сколько стоит обучение?", platform="web")
    # Не голое переспрашивание имени: есть и ответ по существу, и возврат к анкете.
    assert reply != "Напишите, пожалуйста, ваше имя и фамилию 😊"
    assert "Как вас зовут" in reply


@pytest.mark.asyncio
async def test_registration_offtopic_replies_differ(_enable_registration):
    uid = "stick-reg-two"
    await handle_message(uid, "привет", platform="web")
    first = await handle_message(uid, "Сколько стоит обучение?", platform="web")
    second = await handle_message(uid, "Где вы находитесь?", platform="web")
    assert first != second


@pytest.mark.asyncio
async def test_registration_still_accepts_name(_enable_registration):
    uid = "stick-reg-name"
    await handle_message(uid, "привет", platform="web")
    reply = await handle_message(uid, "Иванова Мария", platform="web")
    assert "ребёнка" in reply.lower()


# --- 2. Выход из handoff при смене темы ---


@pytest.mark.asyncio
async def test_handoff_exits_on_new_topic():
    store = get_store()
    conv = store.get("stick-handoff", platform="web")
    conv.registered = True
    conv.stage = STAGE_HANDOFF
    conv.handed_off = True
    store.save(conv)
    reply = await handle_message("stick-handoff", "Сколько стоит английский?", platform="web")
    assert "уже у администратора" not in reply
    assert "передал ваш вопрос" not in reply
    assert conv.stage == STAGE_DISCOVERY


@pytest.mark.asyncio
async def test_handoff_stays_on_repeat_operator_request():
    store = get_store()
    conv = store.get("stick-handoff2", platform="web")
    conv.registered = True
    conv.stage = STAGE_HANDOFF
    conv.handed_off = True
    store.save(conv)
    reply = await handle_message("stick-handoff2", "позовите администратора", platform="web")
    assert "администратор" in reply.lower()


# --- 3. Анти-повтор без LLM ---


@pytest.mark.asyncio
async def test_same_question_twice_never_returns_identical_reply():
    uid = "stick-repeat"
    first = await handle_message(uid, "Где вы находитесь?", platform="web")
    second = await handle_message(uid, "Где вы находитесь?", platform="web")
    assert first != second


# --- 4. Служебные фолбэки не попадают в контекст LLM ---


@pytest.mark.asyncio
async def test_service_fallbacks_filtered_from_llm_history(monkeypatch):
    store = get_store()
    conv = store.get("stick-history", platform="web")
    conv.registered = True
    conv.history = [
        {"role": "user", "content": "первый вопрос"},
        {"role": "assistant", "content": TIMEOUT_REPLY},
        {"role": "user", "content": "второй вопрос"},
        {"role": "assistant", "content": ERROR_REPLY},
        {"role": "user", "content": "текущий вопрос"},
    ]
    store.save(conv)

    captured = {}

    class _FakeLLM:
        enabled = True

    async def fake_ask(messages, vault):
        captured["messages"] = messages
        return "Осмысленный ответ."

    monkeypatch.setattr(ai_core, "get_llm", lambda: _FakeLLM())
    monkeypatch.setattr(ai_core, "_ask", fake_ask)

    reply = await ai_core._consult_with_context(conv, "текущий вопрос", "контекст")
    assert reply == "Осмысленный ответ."
    contents = [m["content"] for m in captured["messages"]]
    assert TIMEOUT_REPLY not in contents
    assert ERROR_REPLY not in contents
    assert "текущий вопрос" in contents


# --- 5. Дедуп MAX-апдейта без id ---


@pytest.mark.asyncio
async def test_max_update_without_id_deduped():
    from unittest.mock import AsyncMock
    from app import main as main_module

    update = {
        "update_type": "message_created",
        "timestamp": 1786808328,
        "message": {
            "body": {"text": "привет"},
            "sender": {"user_id": 424242},
        },
    }
    max_client = AsyncMock()
    assert main_module._schedule_update(update, "message_created", max_client) is True
    # Ретрай вебхука тем же телом — пропускаем.
    assert main_module._schedule_update(dict(update), "message_created", max_client) is False
    for task in list(main_module._BACKGROUND_TASKS):
        task.cancel()


# --- 6. Эскалация не спамит админов в пределах одного эпизода ---


@pytest.mark.asyncio
async def test_handoff_notifies_admins_once_per_episode(monkeypatch):
    from unittest.mock import AsyncMock
    from app.admin_router import hand_off

    monkeypatch.setattr(settings, "ADMIN_MAX_IDS", "999000111")
    max_client = AsyncMock()
    max_client.send_message = AsyncMock(return_value=True)

    store = get_store()
    conv = store.get("stick-notify", platform="web")

    await hand_off(max_client, conv, reason="первый")
    assert max_client.send_message.await_count == 1

    # Повторная эскалация, диалог всё ещё в handoff — без нового уведомления.
    await hand_off(max_client, conv, reason="второй")
    assert max_client.send_message.await_count == 1

    # Эпизод закончился (клиент сменил тему и получил ответ) — новая
    # эскалация снова уведомляет.
    conv.stage = STAGE_DISCOVERY
    await hand_off(max_client, conv, reason="новый эпизод")
    assert max_client.send_message.await_count == 2


# --- 7. Вопрос о цене получает документ с ценой, а не про режим работы ---


@pytest.mark.asyncio
async def test_price_question_returns_actual_prices():
    reply = await handle_message("stick-price", "Сколько стоит английский для ребёнка 9 лет?", platform="web")
    assert "9:00" not in reply
    assert "₽" in reply or "стоимост" in reply.lower() or "цен" in reply.lower()


# --- 8. «Спасибо» — короткий человеческий ответ, а не выгрузка из базы ---


@pytest.mark.asyncio
async def test_thanks_gets_short_human_reply():
    await handle_message("stick-thanks", "Расскажите про курсы", platform="web")
    reply = await handle_message("stick-thanks", "спасибо!", platform="web")
    assert len(reply) < 120
    assert "пожалуйста" in reply.lower()
