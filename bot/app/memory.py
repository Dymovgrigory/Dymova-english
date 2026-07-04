"""Память диалогов: состояние по каждому пользователю MAX.

Хранит этап продажи, собранные данные лида, краткую историю сообщений и
выбранный курс/филиал. Бэкенд — SQLite, чтобы переживать перезапуски процесса.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import settings

MAX_HISTORY = 12

# Этапы воронки продаж — синхронны «мышлению» бота из ТЗ.
STAGE_GREETING = "greeting"        # начало общения
STAGE_DISCOVERY = "discovery"      # выявление потребности
STAGE_SELECTION = "selection"      # подбор курса
STAGE_OBJECTION = "objection"      # работа с возражениями
STAGE_LEAD = "lead"                # сбор данных для записи
STAGE_DONE = "done"                # заявка отправлена
STAGE_HANDOFF = "handoff"          # передано администратору


@dataclass
class Lead:
    fio_parent: str = ""
    phone: str = ""
    fio_child: str = ""
    birthday: str = ""          # yyyy-mm-dd
    age: str = ""
    course: str = ""
    branch: str = ""
    comment: str = ""

    def missing_required(self) -> list[str]:
        required = {
            "fio_parent": "ФИО родителя",
            "phone": "телефон",
            "fio_child": "ФИО ребёнка",
        }
        return [label for key, label in required.items() if not getattr(self, key)]

    def is_complete(self) -> bool:
        return not self.missing_required()


@dataclass
class Conversation:
    user_id: str
    platform: str = "max"
    stage: str = STAGE_GREETING
    lead: Lead = field(default_factory=Lead)
    history: list[dict] = field(default_factory=list)  # [{role, content}]
    selected_course: str = ""
    selected_branch: str = ""
    selected_format: str = ""
    lead_step: str = ""        # какое поле сейчас собираем
    handed_off: bool = False

    def add(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]

    def summary(self) -> str:
        """Краткое резюме для передачи администратору."""
        lines = [f"Этап: {self.stage}"]
        if self.selected_course:
            lines.append(f"Интересующий курс: {self.selected_course}")
        if self.selected_branch:
            lines.append(f"Филиал: {self.selected_branch}")
        l = self.lead
        for key, label in (
            ("fio_parent", "Родитель"), ("phone", "Телефон"),
            ("fio_child", "Ребёнок"), ("age", "Возраст"),
            ("birthday", "Дата рождения"), ("comment", "Комментарий"),
        ):
            val = getattr(l, key)
            if val:
                lines.append(f"{label}: {val}")
        return "\n".join(lines)


class MemoryStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or _resolve_db_path())
        self._lock = threading.RLock()
        self._conn = self._connect()
        self._init_schema()

    def get(self, user_id: str, platform: str = "max") -> Conversation:
        with self._lock:
            conv = self._load_conversation(platform, user_id)
            if conv is None:
                conv = Conversation(platform=platform, user_id=user_id)
            return conv

    def save(self, conv: Conversation) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO conversations(platform, user_id, payload, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(platform, user_id)
                DO UPDATE SET payload=excluded.payload, updated_at=CURRENT_TIMESTAMP
                """,
                (conv.platform, conv.user_id, json.dumps(asdict(conv), ensure_ascii=False)),
            )

    def reset(self, user_id: str, platform: str = "max") -> Conversation:
        with self._lock:
            conv = Conversation(platform=platform, user_id=user_id)
            self.save(conv)
            return conv

    def mark_event_seen(self, event_id: str, platform: str = "max", user_id: str = "", event_type: str = "") -> bool:
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO processed_events(platform, event_id, user_id, event_type, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (platform, event_id, user_id, event_type),
            )
            return cur.rowcount == 1

    def ping(self) -> bool:
        with self._lock:
            self._conn.execute("SELECT 1")
        return True

    # ---------- internal ----------
    def _connect(self) -> sqlite3.Connection:
        db_path = self._db_path
        uri = db_path.startswith("file:")
        if db_path not in (":memory:",) and not uri:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False, uri=uri, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error:
            pass
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    platform TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (platform, user_id)
                );

                CREATE TABLE IF NOT EXISTS processed_events (
                    platform TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    user_id TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (platform, event_id)
                );
                """
            )

    def _load_conversation(self, platform: str, user_id: str) -> Conversation | None:
        row = self._conn.execute(
            "SELECT payload FROM conversations WHERE platform = ? AND user_id = ?",
            (platform, user_id),
        ).fetchone()
        if row is None:
            return None
        return _conv_from_dict(json.loads(row["payload"]))


def _conv_from_dict(d: dict) -> Conversation:
    lead = Lead(**d.get("lead", {}))
    return Conversation(
        platform=d.get("platform", "max"),
        user_id=d["user_id"],
        stage=d.get("stage", STAGE_GREETING),
        lead=lead,
        history=d.get("history", []),
        selected_course=d.get("selected_course", ""),
        selected_branch=d.get("selected_branch", ""),
        selected_format=d.get("selected_format", ""),
        lead_step=d.get("lead_step", ""),
        handed_off=d.get("handed_off", False),
    )


def _resolve_db_path() -> str:
    if settings.DB_PATH:
        return settings.DB_PATH
    if settings.STATE_FILE:
        return settings.STATE_FILE
    return "./data/bot.db"


_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
