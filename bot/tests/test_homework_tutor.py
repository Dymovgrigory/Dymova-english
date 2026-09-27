"""Помощник по ДЗ должен учить, а не решать за ученика."""
from unittest.mock import AsyncMock, patch

import pytest

from app import homework
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
    # Раньше подсказки были отдельным пунктом, теперь это часть разбора
    # каждого пункта задания — смысл сохранён, проверяем актуальной фразой.
    assert "на что обратить внимание" in p


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


@pytest.mark.asyncio
async def test_ai_core_route_records_text_homework_to_crm(monkeypatch):
    """Финальное ревью, важное #5: заявки «разбери задание», распознанные по
    смыслу через общий чат (ai_core._route, без явного «домашка»/«дз» в
    тексте — main.py явно перехватывает такой текст раньше), не попадали ни
    в homework_requests, ни в homework_check_context. crm_messages сюда не
    пишем — это уже делает обёртка вокруг handle_message в main.py."""
    from app import ai_core, crm_store, homework
    from app import intent as I
    from app.memory import Conversation

    crm_store.reset()
    try:
        monkeypatch.setattr(
            homework, "explain_homework_text",
            AsyncMock(return_value="📘 Правило: глагол to be..."),
        )
        conv = Conversation(user_id="miniapp:crm-test", platform="telegram")
        reply = await ai_core._route(
            conv, "Вставь am/is/are: I __ nine.", None, I.HOMEWORK
        )
        assert reply.startswith("📘")
        assert conv.homework_check_context is True
        assert conv.homework_check_context_at

        rows = crm_store.list_homework_requests(mode="explain", limit=10)
        assert any(
            r["user_id"] == "miniapp:crm-test" and r["input_type"] == "text"
            and r["reply"] == reply
            for r in rows
        )
    finally:
        crm_store.reset()


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


def test_text_user_prompt_one_example_rule_does_not_forbid_per_item_breakdown():
    """Финальное ревью (важное #2): «Пример строго ОДИН... Не разбирай все
    пункты» в исходной формулировке можно было прочитать двояко — как
    запрет придумывать пример на каждый пункт (верно) ИЛИ как запрет
    разбирать пункты САМОГО задания (противоречило бы системному промпту,
    который требует 🔎 Пункт N на каждый пункт). Формулировка уточнена:
    «один пример-иллюстрация» + явное указание разбирать каждый пункт
    задания отдельно. Пин проверяет, что оба смысла явно разведены."""
    p = _homework_text_user_prompt("Вставь am/is/are: I __ nine.").lower()
    assert "пример" in p and "один" in p
    # Явно сказано не путать пример с разбором пунктов, и что каждый пункт
    # задания разбирается отдельно — а не общий запрет разбора по пунктам.
    assert "каждый пункт" in p
    assert "разбери отдельно" in p or "разбор" in p


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
        # _critic_check читает gateway.enabled до вызова structured —
        # без атрибута заглушка падала бы AttributeError вместо штатного
        # «критик недоступен» (structured тут нет вовсе, критик не нужен).
        enabled = False

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

    raw = "📘 Правило Текст правила. ✏️ Похожий пример Давай рассмотрим. ✅ План для твоего задания 1) шаг ❓ Что получилось?"
    out = _format_tutor_reply(raw)
    assert "\n\n✏️" in out
    assert "\n\n✅" in out
    assert "📘 Правило\nТекст правила." in out


def test_format_tutor_reply_splits_multiple_per_item_sections():
    """🔎 Пункт N повторяется на каждый пункт задания — регэксп обязан
    расставлять переносы перед каждым вхождением по отдельности, а не только
    перед первым (номер в заголовке переменный, это не буквальная строка)."""
    from app.homework import _format_tutor_reply

    raw = (
        "📘 Правило Текст правила. 🔎 Пункт 1 Смотри на число. "
        "🔎 Пункт 2 Смотри на лицо глагола. ✏️ Похожий пример Давай "
        "рассмотрим. ✅ План для твоего задания 1) шаг ❓ Что получилось?"
    )
    out = _format_tutor_reply(raw)
    assert "\n\n🔎 Пункт 1" in out
    assert "\n\n🔎 Пункт 2" in out
    assert "🔎 Пункт 1\nСмотри на число." in out
    assert "🔎 Пункт 2\nСмотри на лицо глагола." in out
    assert "\n\n✏️" in out


def test_format_template_demonstrates_per_item_breakdown_and_drops_hint():
    """_FORMAT_TEMPLATE — образец, на который модель ориентируется сильнее
    прозы, обязан показывать структуру из системного промпта: блок 🔎 Пункт N
    (минимум дважды, чтобы паттерн «один блок на пункт» был однозначен), и не
    должен противоречиво показывать 💡 Подсказка — этого маркера больше нет
    в списке заголовков системного промпта."""
    from app.homework import _FORMAT_TEMPLATE

    assert _FORMAT_TEMPLATE.count("🔎 Пункт") >= 2
    assert "💡" not in _FORMAT_TEMPLATE


def test_prompt_requires_single_example_in_task_language():
    p = _homework_system_prompt().lower()
    assert "одно похожее задание" in p
    assert "не несколько" in p
    # Для английского пример — на английском, объяснение по-русски.
    assert "на английском" in p
    assert "по-русски" in p


def test_homework_system_prompt_requires_per_item_breakdown():
    prompt = homework._homework_system_prompt()
    # Подробный разбор по каждому пункту — обязательное требование владельца,
    # проверяем, что промпт явно его формулирует, а не полагается на общую
    # структуру «правило → пример → план».
    assert "каждый пункт" in prompt.lower() or "каждого пункта" in prompt.lower()


_CRITIC_OK = {"ok": True, "issues": []}
_CRITIC_BAD = {"ok": False, "issues": ["в примере дан прямой ответ по заданию ученика"]}


@pytest.mark.asyncio
async def test_explain_homework_text_passes_through_when_critic_ok():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.complete = AsyncMock(return_value="📘 Правило\nТекст\n\n❓ Попробуй?")
        gw.structured = AsyncMock(return_value=_CRITIC_OK)
        result = await homework.explain_homework_text("I ... nine")
    assert result is not None
    assert gw.complete.await_count == 1  # перегенерации не было


@pytest.mark.asyncio
async def test_explain_homework_text_critic_sees_task_text():
    """Важное #3 финального ревью: раньше критик видел только ответ тьютора
    и не мог реально проверить «пропущен ли пункт» или «совпадает ли пример
    с заданием» — без текста задания эти проверки были нерабочими по факту."""
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.complete = AsyncMock(return_value="📘 Правило\nТекст\n\n❓ Попробуй?")
        gw.structured = AsyncMock(return_value=_CRITIC_OK)
        await homework.explain_homework_text("Вставь am/is/are: I __ nine.")
    critic_messages = gw.structured.await_args.args[1]
    user_content = critic_messages[1]["content"]
    assert "ЗАДАНИЕ УЧЕНИКА" in user_content
    assert "Вставь am/is/are: I __ nine." in user_content
    assert "ОТВЕТ ТЬЮТОРА" in user_content


@pytest.mark.asyncio
async def test_explain_homework_image_critic_sees_note_as_task_context():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.vision = AsyncMock(return_value="📘 Правило\nТекст\n\n❓ Попробуй?")
        gw.structured = AsyncMock(return_value=_CRITIC_OK)
        await homework.explain_homework_image(b"fake-bytes", "image/jpeg", note="Задание 4, стр. 12")
    critic_messages = gw.structured.await_args.args[1]
    user_content = critic_messages[1]["content"]
    assert "ЗАДАНИЕ УЧЕНИКА" in user_content
    assert "Задание 4, стр. 12" in user_content


@pytest.mark.asyncio
async def test_check_homework_image_critic_sees_note_as_task_context():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.vision = AsyncMock(return_value="🔎 Пункт 1\nВерно!")
        gw.structured = AsyncMock(return_value=_CRITIC_OK)
        await homework.check_homework_image(b"fake-bytes", "image/jpeg", note="Упражнение 7")
    critic_messages = gw.structured.await_args.args[1]
    user_content = critic_messages[1]["content"]
    assert "ЗАДАНИЕ УЧЕНИКА" in user_content
    assert "Упражнение 7" in user_content


@pytest.mark.asyncio
async def test_critic_check_without_task_context_keeps_old_message_shape():
    """Пустой task_context (например, фото без подписи) не должен добавлять
    пустой блок «ЗАДАНИЕ УЧЕНИКА» — старое поведение для этого случая
    сохраняется."""
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.structured = AsyncMock(return_value=_CRITIC_OK)
        await homework._critic_check("ответ", kind="explain")
    critic_messages = gw.structured.await_args.args[1]
    user_content = critic_messages[1]["content"]
    assert "ЗАДАНИЕ УЧЕНИКА" not in user_content
    assert user_content == "ОТВЕТ ТЬЮТОРА:\nответ"


@pytest.mark.asyncio
async def test_explain_homework_text_regenerates_once_when_critic_flags_issue():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.complete = AsyncMock(side_effect=[
            "📘 Правило\nI am nine — готовый ответ дан\n\n❓ Попробуй?",
            "📘 Правило\nТекст без готового ответа\n\n❓ Попробуй?",
        ])
        gw.structured = AsyncMock(side_effect=[_CRITIC_BAD, _CRITIC_OK])
        result = await homework.explain_homework_text("I ... nine")
    assert gw.complete.await_count == 2  # одна перегенерация
    # Критик проверяет только первый вариант — перегенерацию не перепроверяет.
    assert gw.structured.await_count == 1
    assert "готовый ответ дан" not in result


@pytest.mark.asyncio
async def test_explain_homework_text_returns_first_reply_if_regeneration_also_flagged():
    """Критик не блокирует ответ даже после неудачной перегенерации — молчание
    хуже неидеального разбора (тот же принцип, что у общего критика чата)."""
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.complete = AsyncMock(side_effect=["первый вариант", "второй вариант"])
        gw.structured = AsyncMock(side_effect=[_CRITIC_BAD, _CRITIC_BAD])
        result = await homework.explain_homework_text("задание")
    assert result is not None
    assert gw.complete.await_count == 2
    # Критик не запускается повторно на перегенерации — «одна попытка»
    # означает ровно один вызов критика на весь _with_critic_pass.
    assert gw.structured.await_count == 1


@pytest.mark.asyncio
async def test_explain_homework_text_works_without_critic_available():
    """gateway.structured вернул None (критик недоступен) — ответ всё равно
    уходит, критик необязателен, как в app/critic.py."""
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.complete = AsyncMock(return_value="разбор")
        gw.structured = AsyncMock(return_value=None)
        result = await homework.explain_homework_text("задание")
    assert result == homework._finalize_tutor_reply("разбор")
    assert gw.complete.await_count == 1


@pytest.mark.asyncio
async def test_critic_check_returns_structured_verdict():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.structured = AsyncMock(return_value=_CRITIC_BAD)
        verdict = await homework._critic_check("текст разбора", kind="explain")
    assert verdict == _CRITIC_BAD
    gw.structured.assert_awaited_once()
    call = gw.structured.await_args
    assert call.args[0] == homework.ROLE_CRITIC if hasattr(homework, "ROLE_CRITIC") else True


def test_check_homework_system_prompt_forbids_giving_correct_answer():
    prompt = homework._check_homework_system_prompt()
    assert "не называй" in prompt.lower() or "не давай правильный" in prompt.lower()


def test_check_homework_prompts_forbid_indirect_leak_via_deciding_feature():
    """Владелец: правильный ответ нельзя слить и косвенно — например, назвав
    признак, который в задании с двумя вариантами (is/are, a/an) однозначно
    определяет ответ через исключение второго. Список таких признаков не
    только грамматический (число, лицо, время) — для a/an решающий признак
    ЗВУКОВОЙ (гласный/согласный звук следующего слова), поэтому пин на
    конкретное слово «звук» — чтобы правка, которая случайно сузит защиту
    обратно до одних грамматических категорий, роняла тест."""
    system_prompt = homework._check_homework_system_prompt().lower()
    user_prompt = homework._check_homework_user_prompt("").lower()
    critic_prompt = homework._CRITIC_PROMPT["check"].lower()
    for prompt in (system_prompt, user_prompt, critic_prompt):
        assert "звук" in prompt
        assert "a/an" in prompt


def test_explain_homework_prompts_forbid_indirect_leak_via_deciding_feature():
    """Критический фикс финального ревью (Task 8): у режима РАЗБОРА (explain)
    не было защиты от косвенной утечки ответа вовсе — только у режима
    проверки (check). А разбор — самый частый режим всей фичи. Пин, как у
    check-версии этого теста: system-промпт разбора, шаблон формата разбора
    по пунктам (_FORMAT_TEMPLATE, используется в обоих user-промптах — текст
    и фото) и критик kind="explain" должны явно запрещать называть признак,
    который в задании с двумя вариантами (is/are, a/an) однозначно
    определяет ответ через исключение второго — не только грамматический, но
    и звуковой (a/an). Все три места используют общую константу
    `_DECIDING_FEATURE_HINT`, поэтому пин на «звук»/«a/an» защищает от
    правки, которая случайно сузит формулировку или забудет её скопировать."""
    system_prompt = homework._homework_system_prompt().lower()
    format_template = homework._FORMAT_TEMPLATE.lower()
    critic_prompt = homework._CRITIC_PROMPT["explain"].lower()
    for prompt in (system_prompt, format_template, critic_prompt):
        assert "звук" in prompt
        assert "a/an" in prompt


@pytest.mark.asyncio
async def test_check_homework_image_returns_finalized_reply():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        # Фикстура намеренно НЕ называет решающий признак (см. финальное
        # ревью Task 8): «посмотри на подлежащее» без «во множественном
        # числе» — иначе сам пример в тесте демонстрировал бы утечку ответа,
        # которую проверяет test_check_homework_prompts_forbid_indirect_leak_via_deciding_feature.
        gw.vision = AsyncMock(return_value="🔎 Пункт 1\nВерно!\n\n🔎 Пункт 2\nПосмотри ещё раз на подлежащее в этом предложении и вспомни правило спряжения глагола to be.")
        gw.structured = AsyncMock(return_value={"ok": True, "issues": []})
        result = await homework.check_homework_image(b"fake-image-bytes", "image/jpeg")
    assert result is not None
    assert "Пункт 1" in result
    gw.vision.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_homework_image_regenerates_when_critic_flags_leaked_answer():
    with patch("app.homework.get_gateway") as get_gw:
        gw = get_gw.return_value
        gw.vision = AsyncMock(side_effect=[
            "Правильный вариант — are, ты написал is",
            "Посмотри на подлежащее — множественное число, какой глагол ему нужен?",
        ])
        gw.structured = AsyncMock(side_effect=[
            {"ok": False, "issues": ["назван правильный ответ вместо ученика"]},
            {"ok": True, "issues": []},
        ])
        result = await homework.check_homework_image(b"bytes", "image/jpeg")
    assert gw.vision.await_count == 2
    assert "are" not in result or "Правильный вариант" not in result
