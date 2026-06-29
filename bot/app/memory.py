"""Память диалогов: состояние по каждому пользователю MAX.

Хранит этап продажи, собранные данные лида, краткую историю сообщений и
выбранный курс/филиал. По умолчанию — потокобезопасное хранилище в памяти
процесса; при указании STATE_FILE состояние дополнительно сохраняется на диск
в JSON, чтобы пережить перезапуск.
"""
from __future__ import annotations

import json
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
    stage: str = STAGE_GREETING
    lead: Lead = field(default_factory=Lead)
    history: list[dict] = field(default_factory=list)  # [{role, content}]
    selected_course: str = ""
    selected_branch: str = ""
    selected_format: str = ""
    lead_step: str = ""        # какое поле сейчас собираем
    handed_off: bool = False
    recs_shown: bool = False   # уже показывали подборку курсов
    consent_given: bool = False # согласие на обработку ПД
    # UTM-метки/источник (из deep-link при /start или из мини-приложения).
    utm: dict = field(default_factory=dict)

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
            ("birthday", "Дата рождения"), ("email", "E-mail"),
            ("city", "Город"), ("comment", "Комментарий"),
        ):
            val = getattr(l, key)
            if val:
                lines.append(f"{label}: {val}")
        return "\n".join(lines)


class MemoryStore:
    def __init__(self) -> None:
        self._data: dict[str, Conversation] = {}
        self._lock = threading.Lock()
        self._file = Path(settings.STATE_FILE) if settings.STATE_FILE else None
        self._load()

    def get(self, user_id: str) -> Conversation:
        with self._lock:
            conv = self._data.get(user_id)
            if conv is None:
                conv = Conversation(user_id=user_id)
                self._data[user_id] = conv
            return conv

    def save(self, conv: Conversation) -> None:
        with self._lock:
            self._data[conv.user_id] = conv
            self._persist()

    def reset(self, user_id: str) -> Conversation:
        with self._lock:
            conv = Conversation(user_id=user_id)
            self._data[user_id] = conv
            self._persist()
            return conv

    def all_conversations(self) -> list[Conversation]:
        with self._lock:
            return list(self._data.values())

    # ---------- персистентность ----------
    def _persist(self) -> None:
        if not self._file:
            return
        try:
            payload = {uid: _conv_to_dict(c) for uid, c in self._data.items()}
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _load(self) -> None:
        if not self._file or not self._file.exists():
            return
        try:
            raw = json.loads(self._file.read_text(encoding="utf-8"))
            for uid, c in raw.items():
                self._data[uid] = _conv_from_dict(c)
        except Exception:
            pass


def _conv_to_dict(c: Conversation) -> dict:
    d = asdict(c)
    return d


def _conv_from_dict(d: dict) -> Conversation:
    lead = Lead(**d.get("lead", {}))
    return Conversation(
        user_id=d["user_id"],
        stage=d.get("stage", STAGE_GREETING),
        lead=lead,
        history=d.get("history", []),
        selected_course=d.get("selected_course", ""),
        selected_branch=d.get("selected_branch", ""),
        selected_format=d.get("selected_format", ""),
        lead_step=d.get("lead_step", ""),
        handed_off=d.get("handed_off", False),
        recs_shown=d.get("recs_shown", False),
        consent_given=d.get("consent_given", False),
        utm=d.get("utm", {}) or {},
    )


_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
