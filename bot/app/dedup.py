"""Дедупликация webhook-ивентов MAX."""
from __future__ import annotations

import os
import sqlite3
import threading
from collections import OrderedDict
from pathlib import Path

from app.config import settings

_LRU_LIMIT = 10_000


class _MemoryDedupStore:
    def __init__(self, limit: int = _LRU_LIMIT) -> None:
        self._limit = limit
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()

    def mark_seen(self, event_id: str) -> bool:
        if not event_id:
            return True
        with self._lock:
            if event_id in self._seen:
                self._seen.move_to_end(event_id)
                return False
            self._seen[event_id] = None
            while len(self._seen) > self._limit:
                self._seen.popitem(last=False)
            return True


class _SQLiteDedupStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def mark_seen(self, event_id: str) -> bool:
        if not event_id:
            return True
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO processed_events(event_id) VALUES (?)",
                (event_id,),
            )
            return cur.rowcount == 1


_store: _MemoryDedupStore | _SQLiteDedupStore | None = None


def _resolve_path() -> Path | None:
    explicit = os.getenv("DEDUP_FILE", "").strip()
    if explicit:
        if explicit == ":memory:":
            return None
        return Path(explicit)
    state_file = (settings.STATE_FILE or "").strip()
    if state_file:
        return Path(state_file).expanduser().resolve().parent / "dedup.db"
    return None


def _get_store() -> _MemoryDedupStore | _SQLiteDedupStore:
    global _store
    if _store is None:
        path = _resolve_path()
        _store = _SQLiteDedupStore(path) if path is not None else _MemoryDedupStore()
    return _store


def mark_seen(event_id: str) -> bool:
    return _get_store().mark_seen(event_id)
