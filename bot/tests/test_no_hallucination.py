"""Тесты «не выдумываем»: неизвестный вопрос → мягкий перевод на администратора
и запись пробела в журнал insights."""
import json

import pytest

from app import ai_core
from app import insights
from app.config import settings
from app.knowledge.kb import get_kb
from app.memory import get_store


@pytest.fixture()
def insights_file(tmp_path, monkeypatch):
    path = tmp_path / "insights.jsonl"
    monkeypatch.setattr(settings, "INSIGHTS_FILE", str(path))
    return path


def _read_gaps(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_kb_search_scored_returns_scores():
    kb = get_kb()
    scored = kb.search_scored("сколько стоит английский", limit=3)
    assert scored
    assert all(isinstance(s, float) and s > 0 for s, _ in scored)
    assert [d.title for _, d in scored] == [d.title for d in kb.search("сколько стоит английский", limit=3)]


def test_is_uncertain_reply_detects_marker_and_phrases():
    assert ai_core._is_uncertain_reply("[UNKNOWN] Уточню у администратора.")
    assert ai_core._is_uncertain_reply("К сожалению, я не обладаю данной информацией.")
    assert ai_core._is_uncertain_reply("Этот вопрос лучше уточнить у администратора.")
    assert not ai_core._is_uncertain_reply("Занятия стоят 700 ₽, группы до 7 человек.")


@pytest.mark.asyncio
async def test_uncertain_llm_reply_refers_to_admin_and_logs_gap(monkeypatch, insights_file):
    uid = "nh-uncertain"
    get_store().reset(uid)

    class FakeLLM:
        enabled = True

        async def complete(self, messages, temperature=None):
            return "[UNKNOWN] Точной информации у меня нет."

    notified = []

    async def fake_hand_off(max_client, conv, reason=""):
        notified.append(reason)
        conv.handed_off = True
        return True

    monkeypatch.setattr(ai_core, "get_llm", lambda: FakeLLM())
    monkeypatch.setattr(ai_core, "hand_off", fake_hand_off)

    reply = await ai_core.handle_message(uid, "Есть ли у вас парковка для самокатов?")

    assert "администратор" in reply.lower()
    assert "придумывать не хочу" in reply.lower() or "точной информации" in reply.lower()
    assert notified, "администраторы должны получить уведомление"

    gaps = _read_gaps(insights_file)
    assert gaps and gaps[-1]["reason"] == "llm_uncertain"
    assert "парковка" in gaps[-1]["question"].lower()

    conv = get_store().get(uid)
    assert conv.handed_off is True
    # диалог не блокируется: бот продолжает помогать по другим темам
    assert conv.stage != "handoff"


@pytest.mark.asyncio
async def test_no_answer_without_llm_refers_to_admin_and_logs(monkeypatch, insights_file):
    uid = "nh-no-answer"
    get_store().reset(uid)

    class DisabledLLM:
        enabled = False

        async def complete(self, messages, temperature=None):
            return None

    notified = []

    async def fake_hand_off(max_client, conv, reason=""):
        notified.append(reason)
        return True

    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    monkeypatch.setattr(ai_core, "hand_off", fake_hand_off)

    reply = await ai_core._consult_with_context(get_store().get(uid), "Вопрос про ксзчш?", "")

    assert "администратор" in reply.lower()
    assert notified
    gaps = _read_gaps(insights_file)
    assert gaps and gaps[-1]["reason"] == "no_answer"


@pytest.mark.asyncio
async def test_weak_kb_match_is_logged_but_still_answered(monkeypatch, insights_file):
    uid = "nh-weak-kb"
    get_store().reset(uid)
    conv = get_store().get(uid)

    class FakeLLM:
        enabled = True

        async def complete(self, messages, temperature=None):
            return "Отвечаю уверенно по контексту."

    monkeypatch.setattr(ai_core, "get_llm", lambda: FakeLLM())

    class _KBWrap:
        def __init__(self, kb):
            self._kb = kb

        def search_scored(self, query, limit=5):
            return [(0.1, self._kb.documents[0])]

        def __getattr__(self, name):
            return getattr(self._kb, name)

    monkeypatch.setattr(ai_core, "get_kb", lambda: _KBWrap(get_kb()))

    reply = await ai_core._consult(conv, "очень редкий вопрос")
    assert reply == "Отвечаю уверенно по контексту."
    gaps = _read_gaps(insights_file)
    assert gaps and gaps[-1]["reason"] == "weak_kb_match"


def test_insights_and_digest_settings_exist():
    # раньше отсутствовали в Settings и роняли scheduler/insights в рантайме
    assert isinstance(settings.INSIGHTS_FILE, str)
    assert isinstance(settings.DIGEST_ENABLED, bool)
    assert isinstance(settings.DIGEST_HOUR, int)
    assert isinstance(settings.DIGEST_TZ_OFFSET, int)
    assert isinstance(settings.NUDGE_ENABLED, bool)
    assert isinstance(settings.NUDGE_HOUR, int)


def test_system_prompt_demands_unknown_marker():
    from app import sales

    assert "[UNKNOWN]" in sales.SYSTEM_PROMPT
    assert "уверенно" in sales.SYSTEM_PROMPT
