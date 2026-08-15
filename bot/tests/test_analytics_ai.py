"""Тесты этапов 10-12: аналитика, база знаний из БД, версии промптов,
центр ошибок, system health."""
import pytest
from fastapi.testclient import TestClient

from app import crm_store
from app import main as main_module
from app import sales
from app.config import settings
from app.knowledge import kb as kb_module

TOKEN = "test-admin-token"
AUTH = {"X-Admin-Token": TOKEN}


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "crm.db"))
    monkeypatch.setattr(settings, "STATE_FILE", "")
    monkeypatch.setattr(settings, "ADMIN_TOKEN", TOKEN, raising=False)
    crm_store.reset()
    sales.reset_prompt_cache()
    kb_module._kb = None  # синглтон базы знаний — пересоздаём на чистой БД
    main_module._BACKGROUND_TASKS.clear()
    yield
    crm_store.reset()
    sales.reset_prompt_cache()
    kb_module._kb = None
    main_module._BACKGROUND_TASKS.clear()


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _seed_dialog(channel="max", external_id="u1", name="Анна", days_ago=0):
    cid = crm_store.upsert_customer_for_identity(channel, external_id, name=name)
    conv = crm_store.get_or_create_conversation(cid, channel, external_id)
    return cid, conv


# --------- аналитика ---------


def test_analytics_aggregates(client):
    cid1, conv1 = _seed_dialog("max", "u1", "Анна")
    cid2, conv2 = _seed_dialog("telegram", "tg:2", "Борис")
    crm_store.add_message(conv1, cid1, "max", "in", "customer", "вопрос")
    crm_store.add_message(conv1, cid1, "max", "out", "ai", "ответ")
    crm_store.add_message(conv1, cid1, "max", "out", "manager", "ответ менеджера")
    crm_store.add_message(conv2, cid2, "telegram", "in", "customer", "цена?")
    crm_store.add_ai_event("handoff", conv1, cid1, {})
    crm_store.add_ai_event("no_answer", conv2, cid2, {"question": "китайский?"})
    bid = crm_store.create_broadcast("т", "текст")
    crm_store.update_broadcast_status(bid, "done", total=5, delivered=4, failed_count=1)

    data = client.get("/admin/api/analytics?days=30", headers=AUTH).json()
    assert data["leads"]["new_in_period"] == 2
    assert data["ai"]["ai_messages"] == 1
    assert data["ai"]["manager_messages"] == 1
    assert data["ai"]["ai_share"] == 0.5
    assert data["ai"]["handoff"] == 1
    assert data["ai"]["no_answer"] == 1
    assert data["broadcasts"]["delivered"] == 4
    assert data["broadcasts"]["failed"] == 1
    msg_channels = {r["channel"]: r["messages"] for r in data["channels"]["messages"]}
    assert msg_channels == {"max": 3, "telegram": 1}
    cust_channels = {r["channel"]: r["c"] for r in data["channels"]["customers"]}
    assert cust_channels == {"max": 1, "telegram": 1}
    # Дневные ряды содержат сегодняшний день.
    assert data["daily"]["customers"] and data["daily"]["messages"]
    assert data["ai"]["avg_conversation_length"] >= 1


def test_analytics_period_filter(client):
    cid, conv = _seed_dialog()
    crm_store.add_message(conv, cid, "max", "in", "customer", "старое",
                          created_at="2020-01-01T10:00:00+00:00")
    data = client.get("/admin/api/analytics?days=7", headers=AUTH).json()
    assert data["ai"]["ai_messages"] == 0
    assert data["days"] == 7


# --------- база знаний ---------


def test_kb_document_found_by_search_and_disabled_hides(client):
    resp = client.post("/admin/api/kb", headers=AUTH, json={
        "title": "Летний интенсив", "text": "Июль, будни, интенсив английского, 20000 рублей",
    })
    assert resp.json()["ok"]
    doc_id = resp.json()["id"]

    kb = kb_module.get_kb()
    kb._db_docs_cached_at = 0  # сброс кэша 60с
    found = kb.search("летний интенсив июль")
    assert any(d.title == "Летний интенсив" for d in found)

    # Мягкое выключение — документ уходит из поиска.
    assert client.delete(f"/admin/api/kb/{doc_id}", headers=AUTH).json()["ok"]
    kb._db_docs_cached_at = 0
    found = kb.search("летний интенсив июль")
    assert not any(d.title == "Летний интенсив" for d in found)

    # PATCH включил обратно.
    assert client.patch(f"/admin/api/kb/{doc_id}", headers=AUTH,
                        json={"enabled": 1, "title": "Летний интенсив 2026"}).json()["ok"]
    items = client.get("/admin/api/kb", headers=AUTH).json()["items"]
    assert items[0]["enabled"] == 1


def test_kb_db_failure_falls_back_to_yaml():
    """БД сломана — поиск продолжает работать на документах из data.yaml."""
    kb = kb_module.get_kb()
    crm_store.get_conn().close()  # имитация упавшей БД
    kb._db_docs_cached_at = 0
    docs = kb.search("сколько стоит английский")
    assert docs  # yaml-документы на месте
    crm_store.reset()  # восстановим для следующих тестов (fixture тоже сбросит)


# --------- промпты ---------


def test_prompt_seed_activate_rollback(client):
    # Первое обращение сеет кодовый SYSTEM_PROMPT как v1.
    assert sales.base_prompt() == sales.SYSTEM_PROMPT
    versions = client.get("/admin/api/ai/prompts", headers=AUTH).json()["items"]
    assert len(versions) == 1 and versions[0]["active"] == 1

    # Новая версия + активация: бот использует её.
    created = client.post("/admin/api/ai/prompts", headers=AUTH,
                          json={"content": "ТЫ — ТЕСТОВЫЙ ПРОМПТ V2"}).json()
    client.post(f"/admin/api/ai/prompts/{created['id']}/activate", headers=AUTH)
    assert sales.base_prompt() == "ТЫ — ТЕСТОВЫЙ ПРОМПТ V2"

    # Откат на v1.
    v1 = client.get("/admin/api/ai/prompts", headers=AUTH).json()["items"]
    v1_id = [p for p in v1 if p["version"] == 1][0]["id"]
    client.post(f"/admin/api/ai/prompts/{v1_id}/activate", headers=AUTH)
    assert sales.base_prompt() == sales.SYSTEM_PROMPT
    # Активация пишет аудит.
    audit = crm_store.get_conn().execute(
        "SELECT action FROM audit_log WHERE entity_type = 'ai_prompt'").fetchall()
    assert len(audit) >= 2


def test_prompt_db_failure_falls_back_to_code():
    sales.reset_prompt_cache()
    crm_store.get_conn().close()
    assert sales.base_prompt() == sales.SYSTEM_PROMPT
    crm_store.reset()


# --------- центр ошибок и система ---------


def test_errors_feed(client):
    cid, conv = _seed_dialog()
    crm_store.add_ai_event("no_answer", conv, cid, {"question": "китайский?"})
    crm_store.add_ai_event("error", conv, cid, {"reason": "timeout"})
    crm_store.add_message(conv, cid, "max", "out", "manager", "не ушло",
                          status="failed", error="network")
    bid = crm_store.create_broadcast("т", "текст")
    rid, _ = crm_store.add_broadcast_recipient(bid, cid, "max", "u1")
    crm_store.update_recipient_status(rid, "failed", error="boom")

    items = client.get("/admin/api/errors?days=7", headers=AUTH).json()["items"]
    categories = {e["category"] for e in items}
    assert {"ai", "channel", "broadcast"} <= categories

    ai_only = client.get("/admin/api/errors?category=ai", headers=AUTH).json()["items"]
    assert all(e["category"] == "ai" for e in ai_only)
    broadcast_only = client.get("/admin/api/errors?category=broadcast", headers=AUTH).json()["items"]
    assert broadcast_only[0]["broadcast_id"] == bid


def test_system_endpoint(client):
    data = client.get("/admin/api/system", headers=AUTH).json()
    assert data["db_ok"] is True
    assert "db_size_bytes" in data
    assert "inbound_24h" in data
    assert "started_at" in data
    assert client.get("/admin/api/system").status_code == 401
