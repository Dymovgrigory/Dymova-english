"""Галочки прочтения: открытие мини-приложения отмечает ответы бота прочитанными.

MAX Bot API не присылает событие «сообщение прочитано», поэтому сигнал — открытие
мини-приложения клиентом. Прочитанным считаем исходящие сообщения, созданные
до открытия и ещё не отмеченные.
"""
from __future__ import annotations

import pytest

from app import crm_ingest, crm_store
from app.platform import bb_store


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    bb_store._local.conn = None
    crm_store._conn = None
    yield crm_store
    crm_store._conn = None


def _send_bot_reply(text: str) -> None:
    ctx = crm_ingest.ingest_inbound("max", "7442748", f"вопрос: {text}")
    crm_ingest.ingest_outbound(ctx, text, ok=True)


def test_miniapp_open_marks_earlier_bot_replies_read(store):
    _send_bot_reply("первый ответ")
    _send_bot_reply("второй ответ")
    n = store.mark_outgoing_read("max", "7442748", "2999-01-01T00:00:00+00:00")
    assert n == 2
    conv = store.find_conversation("max", "7442748")
    msgs = [m for m in store.get_messages(conv["id"]) if m["direction"] == "out"]
    assert all(m["read_at"] for m in msgs)


def test_client_messages_never_get_read_mark(store):
    ctx = crm_ingest.ingest_inbound("max", "7442748", "привет")
    assert ctx is not None
    store.mark_outgoing_read("max", "7442748", "2999-01-01T00:00:00+00:00")
    conv = store.find_conversation("max", "7442748")
    incoming = [m for m in store.get_messages(conv["id"]) if m["direction"] == "in"]
    assert incoming and all(not m["read_at"] for m in incoming)


def test_reply_newer_than_open_moment_stays_unread(store):
    """Открытие в прошлом не отмечает ответы, созданные позже этого момента."""
    _send_bot_reply("ответ")
    assert store.mark_outgoing_read("max", "7442748", "2000-01-01T00:00:00+00:00") == 0
    conv = store.find_conversation("max", "7442748")
    out = [m for m in store.get_messages(conv["id"]) if m["direction"] == "out"]
    assert out and all(m["read_at"] is None for m in out)


def test_unknown_client_is_a_noop(store):
    assert store.mark_outgoing_read("max", "nobody", "2999-01-01T00:00:00+00:00") == 0
