"""Тесты постоянного CRM-хранилища (crm_store).

Проверяем: персистентность между «перезапусками», идемпотентность записи,
склейку каналов и клиентов, миграцию из legacy-таблицы, inbox-запросы
и режимы AI.
"""
import json
from dataclasses import asdict

import pytest

from app import crm_store
from app.config import settings
from app.memory import Conversation, Lead


@pytest.fixture(autouse=True)
def crm_db(tmp_path, monkeypatch):
    """Каждый тест — чистая файловая база (файл, а не :memory:, чтобы можно
    было «перезапускать» store закрытием соединения)."""
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "crm.db"))
    monkeypatch.setattr(settings, "STATE_FILE", "")
    crm_store.reset()
    yield tmp_path / "crm.db"
    crm_store.reset()


def _make_dialog(channel="max", external_id="u1", **kwargs):
    customer_id = crm_store.upsert_customer_for_identity(channel, external_id, **kwargs)
    conv_id = crm_store.get_or_create_conversation(customer_id, channel, external_id)
    return customer_id, conv_id


def test_persistence_across_reopen(crm_db):
    customer_id, conv_id = _make_dialog(name="Иванова Анна", phone="+79991234567")
    for i in range(10):
        crm_store.add_message(conv_id, customer_id, "max", "in", "customer", f"msg {i}")
    crm_store.reset()  # «перезапуск» процесса

    conn = crm_store.get_conn()
    assert conn.execute("SELECT COUNT(*) c FROM crm_messages").fetchone()["c"] == 10
    customer = crm_store.get_customer(customer_id)
    assert customer["name"] == "Иванова Анна"
    assert customer["counts"]["messages"] == 10


def test_inbound_event_and_message_idempotency():
    customer_id, conv_id = _make_dialog()
    event_id, dup = crm_store.record_inbound_event("max", "ev-1", {"text": "привет"})
    assert not dup
    crm_store.mark_event_processed(event_id)
    event_id2, dup2 = crm_store.record_inbound_event("max", "ev-1", {"text": "привет"})
    assert dup2 and event_id == event_id2
    row = crm_store.get_conn().execute(
        "SELECT status FROM inbound_events WHERE id = ?", (event_id,)
    ).fetchone()
    assert row["status"] == "duplicate"  # повторный приём пометил дубликат

    m1, d1 = crm_store.add_message(conv_id, customer_id, "max", "in", "customer",
                                   "привет", external_message_id="m-1")
    m2, d2 = crm_store.add_message(conv_id, customer_id, "max", "in", "customer",
                                   "привет", external_message_id="m-1")
    assert not d1 and d2 and m1 == m2
    assert crm_store.get_customer(customer_id)["counts"]["messages"] == 1


def test_channels_merge_by_phone_and_merge_customers():
    # Один и тот же телефон в MAX и Telegram — один клиент, две идентичности.
    max_id = crm_store.upsert_customer_for_identity("max", "u-max", name="Анна", phone="+79991234567")
    tg_id = crm_store.upsert_customer_for_identity("telegram", "tg:42", phone="8(999)123-45-67")
    assert max_id == tg_id
    web_id = crm_store.upsert_customer_for_identity("web", "web:sess1")
    assert web_id != max_id

    # merge_customers: история web-дубля переезжает на основного клиента.
    secondary, web_conv = _make_dialog("web", "web:sess2")
    crm_store.add_message(web_conv, secondary, "web", "in", "customer", "сообщение из виджета")
    crm_store.merge_customers(max_id, secondary, actor="test")
    assert crm_store.get_customer(max_id)["counts"]["messages"] == 1
    archived = crm_store.get_customer(secondary)
    assert archived["status"] == "archived"
    assert "merged into" in archived["archive_reason"]


def _customer_of(channel, external_id):
    row = crm_store.get_conn().execute(
        "SELECT customer_id FROM customer_identities WHERE channel = ? AND external_id = ?",
        (channel, external_id),
    ).fetchone()
    return int(row["customer_id"])


def test_upsert_does_not_overwrite_filled_fields():
    cid = crm_store.upsert_customer_for_identity("max", "u1", name="Анна", phone="+7999")
    crm_store.upsert_customer_for_identity("max", "u1", name="", phone="", child_name="Миша")
    customer = crm_store.get_customer(cid)
    assert customer["name"] == "Анна"
    assert customer["phone"] == "+7999"
    assert customer["child_name"] == "Миша"  # пустое поле дописалось


def test_message_ordering():
    customer_id, conv_id = _make_dialog()
    for i in range(5):
        crm_store.add_message(conv_id, customer_id, "max", "in", "customer", f"m{i}",
                              created_at=f"2026-01-01T00:00:0{i}+00:00")
    messages = crm_store.get_messages(conv_id)
    assert [m["text"] for m in messages] == [f"m{i}" for i in range(5)]
    # Курсорная пагинация назад: before_id отсекает хвост.
    page = crm_store.get_messages(conv_id, before_id=messages[3]["id"], limit=2)
    assert [m["text"] for m in page] == ["m1", "m2"]


def test_inbox_filters_and_fulltext():
    cid1, conv1 = _make_dialog("max", "u1", name="Анна")
    cid2, conv2 = _make_dialog("telegram", "tg:7", name="Борис")
    crm_store.add_message(conv1, cid1, "max", "in", "customer", "Интересует подготовка к ЕГЭ",
                          created_at="2026-01-02T10:00:00+00:00")
    crm_store.add_message(conv2, cid2, "telegram", "in", "customer", "Сколько стоит?",
                          created_at="2026-01-03T10:00:00+00:00")

    assert len(crm_store.list_conversations()["items"]) == 2
    assert len(crm_store.list_conversations(channel="telegram")["items"]) == 1
    assert len(crm_store.list_conversations(unread=True)["items"]) == 2
    assert len(crm_store.list_conversations(date_from="2026-01-03")["items"]) == 1
    assert len(crm_store.list_conversations(date_to="2026-01-02T23:59:59")["items"]) == 1
    assert len(crm_store.list_conversations(search="Борис")["items"]) == 1

    ege = crm_store.list_conversations(q="ЕГЭ")
    assert len(ege["items"]) == 1
    assert ege["items"][0]["customer_name"] == "Анна"
    hits = crm_store.search_messages("ЕГЭ")
    assert len(hits) == 1 and "ЕГЭ" in hits[0]["text"]


def test_ai_mode_pause_and_handoff_mode():
    _, conv_id = _make_dialog()
    crm_store.set_ai_mode(conv_id, "paused", paused_until="2026-02-01T00:00:00+00:00")
    conv = crm_store.get_conn().execute(
        "SELECT ai_mode, ai_paused_until FROM crm_conversations WHERE id = ?", (conv_id,)
    ).fetchone()
    assert conv["ai_mode"] == "paused"
    assert conv["ai_paused_until"].startswith("2026-02-01")
    crm_store.set_ai_mode(conv_id, "active")
    conv = crm_store.get_conn().execute(
        "SELECT ai_mode, ai_paused_until FROM crm_conversations WHERE id = ?", (conv_id,)
    ).fetchone()
    assert conv["ai_mode"] == "active" and conv["ai_paused_until"] is None


def test_notes_tasks_tags_timeline():
    customer_id, conv_id = _make_dialog(name="Анна")
    crm_store.add_message(conv_id, customer_id, "max", "in", "customer", "вопрос")
    crm_store.add_note(customer_id, "admin", "Перезвонить вечером")
    task_id = crm_store.add_task(customer_id, "Отправить договор")
    crm_store.assign_tag(customer_id, "vip")
    crm_store.add_ai_event("no_answer", conv_id, customer_id, {"question": "q"})

    customer = crm_store.get_customer(customer_id)
    assert customer["tags"][0]["name"] == "vip"
    assert customer["counts"]["notes"] == 1
    assert customer["counts"]["open_tasks"] == 1
    crm_store.complete_task(task_id)
    assert crm_store.get_customer(customer_id)["counts"]["open_tasks"] == 0

    timeline = crm_store.customer_timeline(customer_id)
    types = {event["type"] for event in timeline}
    assert {"message", "note", "task", "ai_event"} <= types
    timestamps = [event["ts"] for event in timeline]
    assert timestamps == sorted(timestamps)


def _seed_legacy(db_path, conversations):
    """Пишет legacy-строки conversations напрямую, как это делает MemoryStore."""
    import sqlite3

    conn = crm_store.get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            platform TEXT NOT NULL, user_id TEXT NOT NULL,
            payload TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (platform, user_id)
        );
        """
    )
    for platform, user_id, conv in conversations:
        conn.execute(
            "INSERT INTO conversations(platform, user_id, payload) VALUES (?, ?, ?)",
            (platform, user_id, json.dumps(asdict(conv), ensure_ascii=False)),
        )


def test_migration_from_legacy(crm_db):
    conv = Conversation(user_id="u-legacy", platform="max")
    conv.lead = Lead(fio_parent="Иванова Анна", phone="+79991234567",
                     fio_child="Иванов Миша", age="9")
    conv.utm = {"utm_source": "vk"}
    conv.add("user", "Здравствуйте")
    conv.add("assistant", "Здравствуйте! Чем помочь?")
    conv.add("user", "Интересует ЕГЭ")
    _seed_legacy(crm_db, [("max", "u-legacy", conv)])

    report = crm_store.migrate_from_legacy()
    assert report["legacy_conversations"] == 1
    assert report["legacy_messages"] == 3
    assert report["customers_after"] - report["customers_before"] == 1
    assert report["messages_after"] - report["messages_before"] == 3

    customer_id = _customer_of("max", "u-legacy")
    customer = crm_store.get_customer(customer_id)
    assert customer["name"] == "Иванова Анна"
    assert customer["phone"] == "+79991234567"
    assert customer["child_name"] == "Иванов Миша"
    assert customer["child_age"] == "9"
    assert customer["utm"]["utm_source"] == "vk"

    conv_row = crm_store.get_conn().execute(
        "SELECT id FROM crm_conversations WHERE channel = 'max' AND external_user_id = 'u-legacy'"
    ).fetchone()
    messages = crm_store.get_messages(conv_row["id"])
    assert [m["sender_type"] for m in messages] == ["customer", "ai", "customer"]
    assert [m["direction"] for m in messages] == ["in", "out", "in"]
    # Полнотекстовый индекс наполнен после миграции.
    assert len(crm_store.search_messages("ЕГЭ")) == 1

    # Повторный запуск: маркер стоит, ничего не дублируется.
    again = crm_store.migrate_from_legacy()
    assert again.get("skipped")
    assert crm_store.get_customer(customer_id)["counts"]["messages"] == 3


def test_migration_without_marker_skips_existing(crm_db):
    """Если маркер снят (например, --force), уже перенесённый диалог не дублируется."""
    conv = Conversation(user_id="u2", platform="telegram")
    conv.add("user", "привет")
    _seed_legacy(crm_db, [("telegram", "u2", conv)])
    crm_store.migrate_from_legacy()
    crm_store.get_conn().execute("DELETE FROM crm_meta WHERE key = 'legacy_migrated'")
    report = crm_store.migrate_from_legacy()
    assert report["skipped_existing"] == 1
    assert report["messages_after"] - report["messages_before"] == 0
