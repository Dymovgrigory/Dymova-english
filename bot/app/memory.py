"""Память диалогов: состояние по каждому пользователю MAX.

Хранит этап продажи, собранные данные лида, краткую историю сообщений и
выбранный курс/филиал. По умолчанию — потокобезопасное хранилище в памяти
процесса; при указании STATE_FILE состояние дополнительно сохраняется на диск
в JSON, чтобы пережить перезапуск.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import settings

MAX_HISTORY = 20
MAX_TRANSCRIPT = 1000

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
    interest_type: str = ""
    interest_value: str = ""
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

    def interest_label(self) -> str:
        return " / ".join(
            part for part in (self.interest_type, self.interest_value) if part
        )


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
    last_objection: str = ""    # последнее возражение клиента
    lead_submitted: bool = False # заявка уже отправлялась
    created_at: str = ""
    updated_at: str = ""
    transcript: list[dict] = field(default_factory=list)
    # UTM-метки/источник (из deep-link при /start или из мини-приложения).
    utm: dict = field(default_factory=dict)

    def add(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        self.transcript.append(
            {
                "role": role,
                "content": content,
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        if len(self.transcript) > MAX_TRANSCRIPT:
            self.transcript = self.transcript[-MAX_TRANSCRIPT:]

    def child_label(self) -> str:
        """Имя ребёнка для обращения (без фамилии, если можно отделить)."""
        name = (self.lead.fio_child or "").strip()
        if not name:
            return ""
        parts = name.split()
        # «Иванов Миша» → «Миша»: берём более короткую часть как имя.
        return parts[-1] if len(parts) > 1 else parts[0]

    def hours_since_update(self) -> float | None:
        if not self.updated_at:
            return None
        try:
            last = datetime.fromisoformat(self.updated_at)
        except ValueError:
            return None
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last).total_seconds() / 3600.0

    def client_card(self) -> str:
        """Карточка клиента для персонализации ответов LLM.

        Возвращает компактный список того, что уже известно о клиенте, чтобы
        бот не переспрашивал и обращался персонально. Пусто, если ничего нет.
        """
        bits: list[str] = []
        if self.lead.fio_parent:
            bits.append(f"имя родителя (собеседник): {self.lead.fio_parent}")
        child = self.child_label()
        if child:
            bits.append(f"имя ребёнка: {child}")
        if self.lead.age:
            bits.append(f"возраст ребёнка: {self.lead.age}")
        interest = self.selected_course or self.lead.course or self.lead.interest_label()
        if interest:
            bits.append(f"интересует: {interest}")
        if self.selected_format:
            bits.append(f"формат: {self.selected_format}")
        branch = self.selected_branch or self.lead.branch
        if branch:
            bits.append(f"филиал: {branch}")
        if self.last_objection:
            bits.append(f"ранее сомневался: {self.last_objection}")
        if self.lead_submitted:
            bits.append("заявка уже оставлена ранее")
        return "; ".join(bits)

    def is_returning(self) -> bool:
        """Клиент возвращается после паузы, и о нём уже что-то известно."""
        hours = self.hours_since_update()
        return bool(hours and hours >= 12 and self.client_card())

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
        interest = l.interest_label()
        if interest:
            lines.append(f"Интерес: {interest}")
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
                if not conv.created_at:
                    conv.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                self._data[user_id] = conv
            return conv

    def save(self, conv: Conversation) -> None:
        with self._lock:
            if not conv.created_at:
                conv.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            conv.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self._data[conv.user_id] = conv
            self._persist()

    def reset(self, user_id: str) -> Conversation:
        with self._lock:
            conv = Conversation(user_id=user_id)
            if not conv.created_at:
                conv.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
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
        last_objection=d.get("last_objection", ""),
        lead_submitted=d.get("lead_submitted", False),
        created_at=d.get("created_at", ""),
        updated_at=d.get("updated_at", ""),
        transcript=d.get("transcript", []),
        utm=d.get("utm", {}) or {},
    )


_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
