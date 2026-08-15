"""Тесты ingestion-слоя: запись сообщений каналов в CRM (crm_ingest).

Главный контракт: сообщения из веб-чата/MAX/Telegram попадают в crm_messages,
клиент создаётся, а сбой CRM-записи не ломает ответ клиенту.
"""
import pytest
from fastapi.testclient import TestClient

from app import ai_core
from app import crm_ingest
from app import crm_store
from app import main as main_module
from app import memory as memory_module
from app.config import settings


class DisabledLLM:
    enabled = False


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "crm.db"))
    monkeypatch.setattr(settings, "STATE_FILE", "")
    memory_module._store = None
    crm_store.reset()
    main_module._BACKGROUND_TASKS.clear()
    yield
    memory_module._store = None
    crm_store.reset()
    main_module._BACKGROUND_TASKS.clear()


def test_web_chat_ingests_in_and_out(monkeypatch):
    monkeypatch.setattr(ai_core, "get_llm", lambda: DisabledLLM())
    client = TestClient(main_module.app)

    resp = client.post("/api/chat", json={"session_id": "sess-1", "text": "Здравствуйте"})
    assert resp.status_code == 200

    conn = crm_store.get_conn()
    messages = conn.execute(
        "SELECT direction, sender_type, text FROM crm_messages ORDER BY id"
    ).fetchall()
    assert [m["direction"] for m in messages] == ["in", "out"]
    assert messages[0]["sender_type"] == "customer"
    assert messages[0]["text"] == "Здравствуйте"
    assert messages[1]["sender_type"] == "ai"
    assert messages[1]["text"] == resp.json()["reply"]

    # Клиент создан, диалог и событие зафиксированы.
    customer = conn.execute("SELECT * FROM customers").fetchone()
    assert customer is not None
    identity = conn.execute(
        "SELECT channel, external_id FROM customer_identities WHERE customer_id = ?",
        (customer["id"],),
    ).fetchone()
    assert (identity["channel"], identity["external_id"]) == ("web", "web:sess-1")
    event = conn.execute("SELECT status FROM inbound_events").fetchone()
    assert event["status"] == "processed"


def test_ingest_inbound_deduplicates_events():
    ctx1 = crm_ingest.ingest_inbound("max", "u1", "привет", external_event_id="ev-1")
    ctx2 = crm_ingest.ingest_inbound("max", "u1", "привет", external_event_id="ev-1")
    assert ctx1 is not None
    assert ctx2 is None  # повтор события не создаёт дубль сообщения
    count = crm_store.get_conn().execute(
        "SELECT COUNT(*) c FROM crm_messages"
    ).fetchone()["c"]
    assert count == 1


def test_ingest_outbound_marks_send_failure():
    ctx = crm_ingest.ingest_inbound("max", "u1", "вопрос", external_event_id="ev-2")
    crm_ingest.ingest_outbound(ctx, "ответ", ok=False, error="network down")
    conn = crm_store.get_conn()
    out = conn.execute(
        "SELECT status, error FROM crm_messages WHERE direction = 'out'"
    ).fetchone()
    assert out["status"] == "failed"
    assert out["error"] == "network down"
    event = conn.execute("SELECT status FROM inbound_events").fetchone()
    assert event["status"] == "failed"


def test_ingest_never_raises_on_broken_store(monkeypatch):
    # CRM упал (закрытое соединение) — ingestion молча логирует и возвращает None.
    crm_store.get_conn().close()
    ctx = crm_ingest.ingest_inbound("max", "u1", "привет")
    assert ctx is None
    crm_ingest.ingest_outbound({"conversation_id": 1, "customer_id": 1, "channel": "max"}, "ответ")
    crm_ingest.ingest_handoff("max", "u1", "тест")
    crm_ingest.ingest_no_answer("u1", "вопрос без ответа")


def test_handoff_and_no_answer_events():
    ctx = crm_ingest.ingest_inbound("max", "u1", "позовите человека", external_event_id="ev-3")
    crm_ingest.ingest_handoff("max", "u1", "запрос администратора")
    crm_ingest.ingest_no_answer("u1", "А есть ли у вас курсы китайского?", "weak_kb_match")

    conn = crm_store.get_conn()
    events = conn.execute("SELECT kind FROM ai_events ORDER BY id").fetchall()
    assert [e["kind"] for e in events] == ["handoff", "no_answer"]
    # Handoff перевёл диалог в режим manager.
    conv = conn.execute("SELECT ai_mode FROM crm_conversations WHERE id = ?",
                        (ctx["conversation_id"],)).fetchone()
    assert conv["ai_mode"] == "manager"
