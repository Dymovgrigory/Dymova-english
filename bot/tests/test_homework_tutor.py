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


def test_system_prompt_requires_clean_structure():
    p = _homework_system_prompt().lower()
    # Формат для мессенджера: абзацы, эмодзи-заголовки, запрет markdown.
    assert "абзац" in p
    assert "пустая строка" in p
    assert "эмодзи" in p
    assert "никакого markdown" in p


def test_strip_markdown_removes_markup():
    from app.main import _strip_markdown

    raw = "## Правило\n\n**Глагол to be** меняется так:\n* I am\n* You are\n\n\n\n`Пример` готов."
    cleaned = _strip_markdown(raw)
    assert "**" not in cleaned
    assert "#" not in cleaned
    assert "`" not in cleaned
    assert "— I am" in cleaned
    assert "\n\n\n" not in cleaned
    assert "Глагол to be меняется так" in cleaned


def test_strip_markdown_keeps_math_and_blanks():
    from app.main import _strip_markdown

    # Одиночные * (умножение) и __ (пропуски в заданиях) — не разметка.
    assert _strip_markdown("3 * 4 = 12, I __ nine.") == "3 * 4 = 12, I __ nine."


@pytest.mark.asyncio
async def test_ai_core_routes_homework_to_tutor(monkeypatch):
    """Мини-приложение и виджет идут через ai_core.handle_message — домашка
    там тоже обязана попадать в тьютора, а не в общую консультацию."""
    from app import ai_core, homework
    from app import intent as I
    from app.memory import Conversation

    async def fake_tutor(task_text):
        fake_tutor.seen = task_text
        return "📘 Правило: глагол to be..."

    monkeypatch.setattr(homework, "explain_homework_text", fake_tutor)
    conv = Conversation(user_id="miniapp:test")
    reply = await ai_core._route(conv, "помоги с домашкой: вставь am/is/are — I __ nine", None, I.HOMEWORK)
    assert reply.startswith("📘")
    assert "am/is/are" in fake_tutor.seen

    reply = await ai_core._route(conv, "помоги с домашкой", None, I.HOMEWORK)
    assert reply == homework.HOMEWORK_INVITE
    assert conv.awaiting_homework is True

    # Следующее сообщение без триггеров — само задание.
    reply = await ai_core._route(conv, "Вставь was/were: we __ happy.", None, None)
    assert reply.startswith("📘")
    assert conv.awaiting_homework is False


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
    from app import homework

    calls = []

    class FakeGateway:
        async def complete(self, role, messages, *, temperature=None, max_tokens=None, vault=None):
            calls.append((role, messages, temperature, max_tokens))
            return "Правило: глагол to be..."

    monkeypatch.setattr(homework, "get_gateway", lambda: FakeGateway())
    reply = await explain_homework_text("Вставь am/is/are: I __ nine.")
    assert reply.startswith("Правило")
    role, messages, temperature, max_tokens = calls[0]
    assert messages[0]["role"] == "system"
    assert "вставь am/is/are" in messages[1]["content"].lower()
    assert max_tokens and max_tokens >= 1000


@pytest.mark.asyncio
async def test_intent_refiner_never_overrides_homework(monkeypatch):
    """LLM-рефайнер не должен уводить домашку в QUESTION — иначе задание
    попадает в консультацию, которая решает за ребёнка."""
    from app import ai_core
    from app import intent as I
    from app.memory import Conversation

    async def fake_refine(text, history, vault=None):
        return I.QUESTION

    monkeypatch.setattr(ai_core.intent_ai, "refine", fake_refine)
    conv = Conversation(user_id="test:refine")
    intent = await ai_core._detect_intent(conv, "помоги с домашкой: вставь am/is/are — I __ nine")
    assert intent == I.HOMEWORK


def test_prompts_include_format_template():
    # Образец формата (эмодзи-заголовки) — без него gpt-4o-mini писала сплошняком.
    assert "📘" in _homework_text_user_prompt("x")
    assert "✏️" in _homework_user_prompt("")
    assert "СТРОГО по этому образцу" in _homework_text_user_prompt("x")


def test_critic_keeps_tutor_structural_emoji():
    from app import critic
    from app.memory import Conversation

    reply = (
        "📘 Правило\nТекст правила.\n\n✏️ Похожий пример\n1) шаг\n2) шаг\n\n"
        "✅ План для твоего задания\n1) шаг\n2) шаг\n\n💡 Подсказка\nПодсказка.\n\n"
        "❓ Что получилось?"
    )
    conv = Conversation(user_id="test:critic")
    assert "too_many_emoji" not in critic.inspect(reply, conv, True)


def test_trim_emoji_removes_variation_selector():
    from app import critic

    # Раньше базовый символ срезался, а U+FE0F оставался сиротой («️ текст»).
    trimmed = critic._trim_emoji("привет 👋 как ✅ дела ❓ норм", 1)
    assert "\uFE0F" not in trimmed or trimmed.count("\uFE0F") <= trimmed.count("👋")


def test_format_tutor_reply_splits_sections():
    from app.homework import _format_tutor_reply

    raw = "📘 Правило Текст правила. ✏️ Похожий пример Давай рассмотрим. ✅ План для твоего задания 1) шаг 💡 Подсказка Обрати внимание. ❓ Что получилось?"
    out = _format_tutor_reply(raw)
    assert "\n\n✏️" in out
    assert "\n\n✅" in out
    assert "\n\n💡" in out
    assert "📘 Правило\nТекст правила." in out
    assert "💡 Подсказка\nОбрати внимание." in out
