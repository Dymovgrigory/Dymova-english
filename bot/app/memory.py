"""Память диалогов: состояние по каждому пользователю MAX.

Хранит этап продажи, собранные данные лида, краткую историю сообщений и
выбранный курс/филиал. Бэкенд — SQLite, чтобы переживать перезапуски процесса.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

MAX_HISTORY = 20

STAGE_GREETING = "greeting"
STAGE_DISCOVERY = "discovery"
STAGE_SELECTION = "selection"
STAGE_OBJECTION = "objection"
STAGE_LEAD = "lead"
STAGE_DONE = "done"
STAGE_HANDOFF = "handoff"
STAGE_REGISTRATION = "registration"


@dataclass
class Lead:
    fio_parent: str = ""
    phone: str = ""
    fio_child: str = ""
    birthday: str = ""
    age: str = ""
    course: str = ""
    branch: str = ""
    comment: str = ""
    email: str = ""
    city: str = ""

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
    history: list[dict] = field(default_factory=list)
    transcript: list[dict] = field(default_factory=list)
    selected_course: str = ""
    selected_branch: str = ""
    selected_format: str = ""
    lead_step: str = ""
    handed_off: bool = False
    lead_submitted: bool = False
    nudge_sent: bool = False
    last_objection: str = ""
    last_user_intent: str = ""
    last_user_mood: str = ""
    last_user_topic: str = ""
    created_at: str = ""
    updated_at: str = ""
    registered: bool = False
    registration_step: str = ""
    utm: dict = field(default_factory=dict)

    def add(self, role: str, content: str) -> None:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.history.append({"role": role, "content": content})
        self.transcript.append({"role": role, "content": content, "ts": ts})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        if len(self.transcript) > 1000:
            self.transcript = self.transcript[-1000:]

    def child_label(self) -> str:
        raw = (self.lead.fio_child or "").strip()
        if not raw:
            return ""
        parts = raw.split()
        return parts[-1] if len(parts) > 1 else raw

    def client_card(self) -> str:
        lines: list[str] = []
        child = self.child_label()
        if child:
            lines.append(f"имя ребёнка: {child}")
        if self.lead.age:
            lines.append(f"возраст ребёнка: {self.lead.age}")
        if self.selected_course or self.lead.course:
            lines.append(f"интересует: {self.selected_course or self.lead.course}")
        if self.selected_format:
            lines.append(f"формат: {self.selected_format}")
        if self.last_objection:
            lines.append(f"ранее сомневался: {self.last_objection}")
        return "\n".join(lines)

    def hours_since_update(self) -> float | None:
        raw = self.updated_at or self.created_at
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0

    def is_returning(self) -> bool:
        return bool(self._facts() and (hours := self.hours_since_update()) is not None and hours >= 12)

    def _facts(self) -> list[str]:
        facts = [self.lead.fio_parent, self.lead.fio_child, self.lead.phone, self.selected_course, self.selected_branch]
        return [item for item in facts if item]

    def summary(self) -> str:
        lines = [f"Этап: {self.stage}"]
        if self.registered:
            lines.append("Регистрация: да")
        if self.selected_course:
            lines.append(f"Интересующий курс: {self.selected_course}")
        if self.selected_branch:
            lines.append(f"Филиал: {self.selected_branch}")
        l = self.lead
        for key, label in (
            ("fio_parent", "Родитель"),
            ("phone", "Телефон"),
            ("fio_child", "Ребёнок"),
            ("age", "Возраст"),
            ("birthday", "Дата рождения"),
            ("comment", "Комментарий"),
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
        self._data: dict[str, Conversation] = {}

    def get(self, user_id: str, platform: str = "max") -> Conversation:
        with self._lock:
            conv = self._data.get(user_id)
            if conv is None:
                conv = self._load_conversation(platform, user_id)
            if conv is None:
                conv = Conversation(platform=platform, user_id=user_id)
            self._data[user_id] = conv
            return conv

    def save(self, conv: Conversation) -> None:
        with self._lock:
            now = self._now()
            if not conv.created_at:
                conv.created_at = now
            conv.updated_at = now
            self._data[conv.user_id] = conv
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

    def all_conversations(self) -> list[Conversation]:
        with self._lock:
            if self._data:
                return list(self._data.values())
            rows = self._conn.execute("SELECT payload FROM conversations").fetchall()
            convs: list[Conversation] = []
            for row in rows:
                conv = _conv_from_dict(json.loads(row["payload"]))
                self._data[conv.user_id] = conv
                convs.append(conv)
            return convs

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

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conv_from_dict(d: dict) -> Conversation:
    lead = Lead(**d.get("lead", {}))
    return Conversation(
        platform=d.get("platform", "max"),
        user_id=d["user_id"],
        stage=d.get("stage", STAGE_GREETING),
        lead=lead,
        history=d.get("history", []),
        transcript=d.get("transcript", []),
        selected_course=d.get("selected_course", ""),
        selected_branch=d.get("selected_branch", ""),
        selected_format=d.get("selected_format", ""),
        lead_step=d.get("lead_step", ""),
        handed_off=d.get("handed_off", False),
        lead_submitted=d.get("lead_submitted", False),
        nudge_sent=d.get("nudge_sent", False),
        last_objection=d.get("last_objection", ""),
        created_at=d.get("created_at", ""),
        updated_at=d.get("updated_at", ""),
        registered=d.get("registered", False),
        registration_step=d.get("registration_step", ""),
        utm=d.get("utm", {}) or {},
    )


def _resolve_db_path() -> str:
    if settings.STATE_FILE:
        return settings.STATE_FILE
    if settings.DB_PATH and settings.DB_PATH != "./data/bot.db":
        return settings.DB_PATH
    return ":memory:"


_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
