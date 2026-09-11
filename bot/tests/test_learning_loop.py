"""Ночной анализатор (learning_loop), журнал автоприменений, откат из админки
и CRM-контекст ребёнка в системном промпте (approach-1, разделы 4, 5, 7)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import crm_store
from app import insights
from app import learning_loop
from app import sales
from app.config import settings
from app.knowledge.kb import get_kb
from app.memory import Conversation
from app.pii import PiiVault

TOKEN = "learningtoken"
AUTH = {"X-Admin-Token": TOKEN}


@pytest.fixture(autouse=True)
def _fresh_store():
    crm_store.reset()
    sales.reset_prompt_cache()
    sales.reset_crm_context_cache()
    yield
    crm_store.reset()
    sales.reset_prompt_cache()
    sales.reset_crm_context_cache()


def _weak_summary(total: int = 5) -> dict:
    return {
        "period_days": 1,
        "total_weak_answers": total,
        "unique_questions": 1,
        "gaps": [
            {"question": "Можно ли перенести занятие?", "count": 3, "users": 2,
             "last_ts": 1, "reason": "no_kb"},
        ],
    }


class _FakeGateway:
    """Шлюз-заглушка: structured возвращает заготовленный ответ."""

    def __init__(self, suggestion):
        self._suggestion = suggestion
        self.calls: list[dict] = []

    async def structured(self, role, messages, schema, **kwargs):
        self.calls.append({"role": role, "messages": messages})
        return self._suggestion


def _install(monkeypatch, suggestion, weak_total: int = 5) -> _FakeGateway:
    fake = _FakeGateway(suggestion)
    monkeypatch.setattr(learning_loop, "get_gateway", lambda: fake)
    monkeypatch.setattr(
        insights, "summarize", lambda days=1, top=10: _weak_summary(weak_total))
    return fake


# ------------------------- ночной цикл -------------------------


async def test_nightly_learning_applies_kb_and_prompt(monkeypatch):
    """Валидный JSON: знания дописываются в БЗ, промпт получает новую версию,
    факт применения фиксируется в learning_log."""
    sales.base_prompt()  # seed версии 1
    _install(monkeypatch, {
        "kb_additions": [
            {"topic": "Перенос занятий",
             "text": "Перенос по уважительной причине — через администратора."},
        ],
        "prompt_changes": [
            {"section": "Как отвечать", "change": "add",
             "text": "Если спрашивают про перенос, уточни причину пропуска."},
        ],
    })

    stats = await learning_loop.run_nightly_learning()

    assert stats["kb_added"] == 1
    assert stats["prompt_changed"] is True
    assert stats["insights_analyzed"] == 5

    kb_docs = crm_store.kb_list()
    assert any(doc["title"] == "Перенос занятий" for doc in kb_docs)

    active = crm_store.prompt_active()
    assert active["version"] == 2
    assert active["created_by"] == "learning_loop"
    assert "уточни причину пропуска" in active["content"]
    # Кэш промпта сброшен — диалоги сразу работают на новой версии.
    assert sales.base_prompt() == active["content"]

    log = crm_store.learning_log_list()
    assert len(log) == 1
    assert log[0]["prompt_version_before"] == 1
    assert log[0]["prompt_version_after"] == 2
    assert log[0]["status"] == "active"
    assert log[0]["insights_analyzed"] == 5


async def test_nightly_learning_survives_broken_json(monkeypatch):
    """Битый ответ модели (gateway вернул None): ничего не применяем,
    ошибки наружу нет."""
    sales.base_prompt()
    _install(monkeypatch, None)

    stats = await learning_loop.run_nightly_learning()

    assert stats["kb_added"] == 0
    assert stats["prompt_changed"] is False
    assert crm_store.prompt_active()["version"] == 1
    assert crm_store.kb_list() == []
    assert crm_store.learning_log_list() == []


async def test_nightly_learning_skipped_when_quiet(monkeypatch):
    """Слабых ответов за сутки почти не было — цикл не тратит токены."""
    _install(monkeypatch, {"kb_additions": [], "prompt_changes": []}, weak_total=1)

    stats = await learning_loop.run_nightly_learning()

    assert stats["skipped"] is True
    assert crm_store.learning_log_list() == []


async def test_prompt_changes_replace_is_not_applied(monkeypatch):
    """Ночь — не место для переписывания существующих правил: только add."""
    sales.base_prompt()
    _install(monkeypatch, {
        "kb_additions": [],
        "prompt_changes": [
            {"section": "Как отвечать", "change": "replace",
             "text": "Теперь отвечай иначе."},
        ],
    })

    stats = await learning_loop.run_nightly_learning()

    assert stats["prompt_changed"] is False
    assert crm_store.prompt_active()["version"] == 1


# ------------------------- откат из админки -------------------------


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "ADMIN_TOKEN", TOKEN, raising=False)
    from app import main as main_module

    return TestClient(main_module.app)


def test_learning_log_rollback_restores_prompt(monkeypatch):
    """Откат: активная версия возвращается к «до», запись помечается,
    сам откат фиксируется новой записью журнала."""
    client = _client(monkeypatch)
    sales.base_prompt()  # v1
    new_id = crm_store.prompt_add("v2 content", created_by="learning_loop")
    crm_store.prompt_activate(new_id)
    entry_id = crm_store.learning_log_add(
        prompt_version_before=1, prompt_version_after=2, changes={"x": 1},
        insights_analyzed=3)

    resp = client.post(f"/admin/learning_log/{entry_id}/rollback", headers=AUTH)

    assert resp.status_code == 200
    assert resp.json()["restored_version"] == 1
    assert crm_store.prompt_active()["version"] == 1
    entries = crm_store.learning_log_list()
    assert len(entries) == 2
    rolled = next(e for e in entries if e["id"] == entry_id)
    assert rolled["status"] == "rolled_back"
    rollback_entry = next(e for e in entries if e["id"] != entry_id)
    assert "rollback_of" in rollback_entry["changes_json"]


def test_learning_log_rollback_twice_is_rejected(monkeypatch):
    client = _client(monkeypatch)
    entry_id = crm_store.learning_log_add(
        prompt_version_before=0, prompt_version_after=0, changes={})
    assert client.post(
        f"/admin/learning_log/{entry_id}/rollback", headers=AUTH).status_code == 200
    assert client.post(
        f"/admin/learning_log/{entry_id}/rollback", headers=AUTH).status_code == 400


def test_learning_log_endpoints_require_admin(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/admin/learning_log").status_code == 401
    assert client.post("/admin/learning_log/1/rollback").status_code == 401


def test_learning_log_list_endpoint(monkeypatch):
    client = _client(monkeypatch)
    crm_store.learning_log_add(prompt_version_before=1, prompt_version_after=2,
                               changes={"a": 1}, insights_analyzed=7)
    resp = client.get("/admin/learning_log", headers=AUTH)
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["insights_analyzed"] == 7


# ------------------------- CRM-контекст в промпте -------------------------


def _patch_crm_context(monkeypatch, text: str) -> None:
    from app.platform import bb_store

    monkeypatch.setattr(bb_store, "get_customer_context", lambda student_id, **kw: text)


def test_prompt_without_student_has_no_crm_block():
    conv = Conversation(user_id="anon")
    prompt = sales.build_system_prompt(get_kb(), conv, "")
    assert "Информация о ребёнке родителя (данные из CRM школы):" not in prompt


def test_prompt_with_student_includes_crm_context(monkeypatch):
    _patch_crm_context(monkeypatch, "Ребёнок: Иванова Маша, 9 лет\nГруппа: Elementary A2")
    conv = Conversation(user_id="mom")
    conv.student_id = 42
    prompt = sales.build_system_prompt(get_kb(), conv, "")
    assert "Информация о ребёнке родителя" in prompt
    assert "Группа: Elementary A2" in prompt


def test_crm_context_is_redacted_by_vault(monkeypatch):
    """Имя ребёнка из CRM уходит в модель только как плейсхолдер."""
    _patch_crm_context(monkeypatch, "Ребёнок: Иванова Маша, 9 лет")
    conv = Conversation(user_id="mom2")
    conv.student_id = 42
    vault = PiiVault()
    vault.hide("CHILD_NAME", "Иванова Маша")
    prompt = sales.build_system_prompt(get_kb(), conv, "", vault=vault)
    assert "Иванова Маша" not in prompt
    assert "{{CHILD_NAME}}" in prompt


def test_crm_context_failure_does_not_break_prompt(monkeypatch):
    """Сбой read-model не должен ломать диалог: промпт собирается без блока."""
    from app.platform import bb_store

    def boom(student_id, **kw):
        raise RuntimeError("db down")

    monkeypatch.setattr(bb_store, "get_customer_context", boom)
    conv = Conversation(user_id="mom3")
    conv.student_id = 42
    prompt = sales.build_system_prompt(get_kb(), conv, "")
    assert "Информация о ребёнке родителя (данные из CRM школы):" not in prompt


def test_crm_context_is_cached(monkeypatch):
    """Контекст не пересобирается из read-model на каждый ответ."""
    from app.platform import bb_store

    calls = []

    def fake(student_id, **kw):
        calls.append(student_id)
        return "Ребёнок: Тест"

    monkeypatch.setattr(bb_store, "get_customer_context", fake)
    conv = Conversation(user_id="mom4")
    conv.student_id = 42
    sales.build_system_prompt(get_kb(), conv, "")
    sales.build_system_prompt(get_kb(), conv, "")
    assert calls == [42]


# ------------------------- счётчик fallback-переключений -------------------------


async def test_fallback_switches_counted(monkeypatch):
    """Ответ запасного провайдера увеличивает счётчик (approach-1, р. 7)."""
    from app import llm
    from app.llm import LLMClient, ProviderConfig

    client = LLMClient()
    client.providers = [
        ProviderConfig(base_url="https://primary", api_key="k", model="m1"),
        ProviderConfig(base_url="https://backup", api_key="k", model="m2"),
    ]

    async def fake_complete(http, provider, messages, temperature, **kwargs):
        if provider.model == "m1":
            return None
        return "ответ от запасного"

    monkeypatch.setattr(llm, "_complete_with_provider", fake_complete)
    monkeypatch.setattr(llm, "_get_client", lambda: _null_client())

    assert client.fallback_switches == 0
    reply = await client.complete([{"role": "user", "content": "привет"}])
    assert reply == "ответ от запасного"
    assert client.fallback_switches == 1


async def test_fallback_counter_stays_on_primary(monkeypatch):
    """Основной провайдер ответил сам — переключения не было."""
    from app import llm
    from app.llm import LLMClient, ProviderConfig

    client = LLMClient()
    client.providers = [
        ProviderConfig(base_url="https://primary", api_key="k", model="m1"),
        ProviderConfig(base_url="https://backup", api_key="k", model="m2"),
    ]

    async def fake_complete(http, provider, messages, temperature, **kwargs):
        return "ответ основного"

    monkeypatch.setattr(llm, "_complete_with_provider", fake_complete)
    monkeypatch.setattr(llm, "_get_client", lambda: _null_client())

    reply = await client.complete([{"role": "user", "content": "привет"}])
    assert reply == "ответ основного"
    assert client.fallback_switches == 0


async def _null_client():
    return None
