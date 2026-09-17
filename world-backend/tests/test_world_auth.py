"""Подпись игрока и перевод SQL на Postgres."""
import os

import pytest
from fastapi import HTTPException

from app.world import auth
from app.world.db import adapt_sql


def test_unsigned_key_works_without_secret(monkeypatch):
    monkeypatch.delenv("WORLD_PLAYER_SECRET", raising=False)
    assert auth.verify("child-1") == "child-1"
    assert auth.sign("child-1") == "child-1"


def test_signed_token_is_required_when_secret_is_set(monkeypatch):
    monkeypatch.setenv("WORLD_PLAYER_SECRET", "test-secret")
    token = auth.sign("child-1")
    assert token.startswith("child-1.")
    assert auth.verify(token) == "child-1"
    with pytest.raises(HTTPException) as raw:
        auth.verify("child-1")
    assert raw.value.status_code == 401
    with pytest.raises(HTTPException):
        auth.verify("child-1.deadbeef")


def test_adapt_sql_rewrites_sqlite_idioms():
    assert "%s" in adapt_sql("SELECT * FROM players WHERE id=?")
    assert "CURRENT_TIMESTAMP" in adapt_sql("UPDATE p SET t=datetime('now')")
    assert "ON CONFLICT DO NOTHING" in adapt_sql("INSERT OR IGNORE INTO items (id) VALUES (?)")
    assert adapt_sql("BEGIN IMMEDIATE") == "BEGIN"
