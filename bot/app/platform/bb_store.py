"""Read-model BigBen в SQLite: синхронизированные копии сущностей CRM.

BigBen — source of truth; эти таблицы — кэш/read-model для быстрых ответов
сайту, боту и мини-аппу. Каждая запись знает свою свежесть (synced_at) —
UI обязан уметь показать «обновлено N минут назад», а критичные действия
(booking) перед записью перепроверяют данные свежим запросом в API.

Отдельно живут операционные таблицы платформы:
- sync_runs — журнал прогонов синхронизации (мониторинг);
- bb_webhook_events — приёмник вебхуков (дедуп, аудит, replay);
- bookings — записи на пробные (наш источник истины о бронированиях).
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bb_filials (
    id INTEGER PRIMARY KEY,
    caption TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    raw_json TEXT NOT NULL DEFAULT '{}',
    synced_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bb_groups (
    id INTEGER PRIMARY KEY,
    caption TEXT NOT NULL DEFAULT '',
    filial_id INTEGER,
    filial_caption TEXT NOT NULL DEFAULT '',
    auditory_id INTEGER,
    auditory_caption TEXT NOT NULL DEFAULT '',
    capacity INTEGER,
    occupied INTEGER NOT NULL DEFAULT 0,
    free_slots INTEGER,
    overbooked INTEGER NOT NULL DEFAULT 0,
    schedule_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}',
    synced_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bb_groups_filial ON bb_groups(filial_id);
CREATE TABLE IF NOT EXISTS bb_lessons (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    starts_at TEXT,
    ends_at TEXT,
    group_id INTEGER,
    group_caption TEXT NOT NULL DEFAULT '',
    filial_id INTEGER,
    filial_caption TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL DEFAULT '{}',
    synced_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bb_lessons_date ON bb_lessons(date);
CREATE INDEX IF NOT EXISTS idx_bb_lessons_group ON bb_lessons(group_id, date);
CREATE TABLE IF NOT EXISTS bb_students (
    id INTEGER PRIMARY KEY,
    fio TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    balance_kopecks INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT NOT NULL DEFAULT '{}',
    synced_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bb_payments (
    id INTEGER PRIMARY KEY,
    student_id INTEGER,
    student_fio TEXT NOT NULL DEFAULT '',
    group_id INTEGER,
    amount_kopecks INTEGER NOT NULL DEFAULT 0,
    paid_at TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}',
    synced_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bb_payments_paid ON bb_payments(paid_at);
CREATE TABLE IF NOT EXISTS bb_group_meta (
    group_id INTEGER PRIMARY KEY,
    teacher TEXT NOT NULL DEFAULT '',
    period_start TEXT NOT NULL DEFAULT '',
    period_end TEXT NOT NULL DEFAULT '',
    monthly_payment INTEGER,
    synced_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    processed INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bb_webhook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,
    account_id INTEGER,
    payload_json TEXT NOT NULL DEFAULT '{}',
    event_ts TEXT NOT NULL DEFAULT '',
    dedup_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'received',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL,
    processed_at TEXT
);
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    parent_name TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    child_name TEXT NOT NULL DEFAULT '',
    child_age TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'site',
    group_id INTEGER NOT NULL,
    lesson_id INTEGER NOT NULL,
    filial_id INTEGER,
    lead_id INTEGER,
    demo_lesson_id INTEGER,
    idempotency_key TEXT NOT NULL UNIQUE,
    error TEXT NOT NULL DEFAULT '',
    confirmed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_bookings_phone ON bookings(phone);
"""

_local = threading.local()


def _db() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        path = Path(settings.DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        _migrate_bookings(conn)
        _local.conn = conn
    return conn


def _migrate_bookings(conn: sqlite3.Connection) -> None:
    """Платное пробное: колонки инвойса (CREATE TABLE не меняет существующие)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(bookings)")}
    mcols = {r["name"] for r in conn.execute("PRAGMA table_info(bb_group_meta)")}
    if "for_events" not in mcols:
        conn.execute("ALTER TABLE bb_group_meta ADD COLUMN for_events INTEGER NOT NULL DEFAULT 0")
    if "cost_per_event" not in mcols:
        conn.execute("ALTER TABLE bb_group_meta ADD COLUMN cost_per_event INTEGER")
    if "title" not in mcols:
        conn.execute("ALTER TABLE bb_group_meta ADD COLUMN title TEXT NOT NULL DEFAULT ''")
    if "invoice_id" not in cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN invoice_id TEXT")
    if "amount_kopecks" not in cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN amount_kopecks INTEGER")
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- upsert-ы read-model ---

def upsert_filial(item: dict) -> None:
    _db().execute(
        "INSERT INTO bb_filials (id, caption, city, address, active, raw_json, synced_at)"
        " VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET caption=excluded.caption, city=excluded.city,"
        " address=excluded.address, active=excluded.active, raw_json=excluded.raw_json,"
        " synced_at=excluded.synced_at",
        (item["id"], item.get("caption", ""), item.get("city", ""), item.get("address", ""),
         1 if item.get("active", True) else 0, json.dumps(item, ensure_ascii=False), _now()),
    )
    _db().commit()


def upsert_group(item: dict) -> None:
    filial = item.get("filial") or {}
    auditory = item.get("auditory") or {}
    _db().execute(
        "INSERT INTO bb_groups (id, caption, filial_id, filial_caption, auditory_id,"
        " auditory_caption, capacity, occupied, free_slots, overbooked, schedule_json,"
        " updated_at, raw_json, synced_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET caption=excluded.caption, filial_id=excluded.filial_id,"
        " filial_caption=excluded.filial_caption, auditory_id=excluded.auditory_id,"
        " auditory_caption=excluded.auditory_caption, capacity=excluded.capacity,"
        " occupied=excluded.occupied, free_slots=excluded.free_slots,"
        " overbooked=excluded.overbooked, schedule_json=excluded.schedule_json,"
        " updated_at=excluded.updated_at, raw_json=excluded.raw_json, synced_at=excluded.synced_at",
        (item["id"], item.get("caption", ""), filial.get("id"), filial.get("caption", ""),
         auditory.get("id"), auditory.get("caption", ""),
         item.get("capacity"), item.get("occupied", 0), item.get("free_slots"),
         1 if item.get("overbooked") else 0,
         json.dumps(item.get("schedule", []), ensure_ascii=False),
         item.get("updated_at"), json.dumps(item, ensure_ascii=False), _now()),
    )
    _db().commit()


def upsert_lesson(item: dict) -> None:
    group = item.get("group") or {}
    filial = item.get("filial") or {}
    _db().execute(
        "INSERT INTO bb_lessons (id, date, starts_at, ends_at, group_id, group_caption,"
        " filial_id, filial_caption, raw_json, synced_at) VALUES (?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET date=excluded.date, starts_at=excluded.starts_at,"
        " ends_at=excluded.ends_at, group_id=excluded.group_id,"
        " group_caption=excluded.group_caption, filial_id=excluded.filial_id,"
        " filial_caption=excluded.filial_caption, raw_json=excluded.raw_json,"
        " synced_at=excluded.synced_at",
        (item["id"], item.get("date", ""), item.get("starts_at"), item.get("ends_at"),
         group.get("id"), group.get("caption", ""), filial.get("id"), filial.get("caption", ""),
         json.dumps(item, ensure_ascii=False), _now()),
    )
    _db().commit()


def upsert_student(item: dict) -> None:
    _db().execute(
        "INSERT INTO bb_students (id, fio, phone, email, balance_kopecks, raw_json, synced_at)"
        " VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET fio=excluded.fio, phone=excluded.phone,"
        " email=excluded.email, balance_kopecks=excluded.balance_kopecks,"
        " raw_json=excluded.raw_json, synced_at=excluded.synced_at",
        (item["id"], item.get("fio", ""), item.get("phone", ""), item.get("email", ""),
         item.get("balance_kopecks", 0), json.dumps(item, ensure_ascii=False), _now()),
    )
    _db().commit()


def upsert_payment(item: dict) -> None:
    _db().execute(
        "INSERT INTO bb_payments (id, student_id, student_fio, group_id, amount_kopecks,"
        " paid_at, raw_json, synced_at) VALUES (?,?,?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET student_id=excluded.student_id,"
        " student_fio=excluded.student_fio, group_id=excluded.group_id,"
        " amount_kopecks=excluded.amount_kopecks, paid_at=excluded.paid_at,"
        " raw_json=excluded.raw_json, synced_at=excluded.synced_at",
        (item["id"], item.get("student_id"), item.get("student_fio", ""), item.get("group_id"),
         item.get("amount_kopecks", 0), item.get("paid_at"),
         json.dumps(item, ensure_ascii=False), _now()),
    )
    _db().commit()


# --- чтение read-model ---

def _rows(sql: str, params: tuple = ()) -> list[dict]:
    cur = _db().execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def list_groups(filial_id: int | None = None) -> list[dict]:
    if filial_id:
        return _rows("SELECT * FROM bb_groups WHERE filial_id=? ORDER BY caption", (filial_id,))
    return _rows("SELECT * FROM bb_groups ORDER BY filial_caption, caption")


def list_filials(active_only: bool = True) -> list[dict]:
    if active_only:
        return _rows("SELECT * FROM bb_filials WHERE active=1 ORDER BY caption")
    return _rows("SELECT * FROM bb_filials ORDER BY caption")


def list_lessons(date_from: str, date_to: str, group_id: int | None = None) -> list[dict]:
    if group_id:
        return _rows(
            "SELECT * FROM bb_lessons WHERE date>=? AND date<=? AND group_id=? ORDER BY date, starts_at",
            (date_from, date_to, group_id))
    return _rows(
        "SELECT * FROM bb_lessons WHERE date>=? AND date<=? ORDER BY date, starts_at",
        (date_from, date_to))


def find_student_by_phone(phone: str) -> dict | None:
    rows = find_students_by_phone(phone)
    return rows[0] if rows else None


def find_students_by_phone(phone: str) -> list[dict]:
    """Все ученики с этим номером: у одного родителя детей может быть
    несколько, поэтому идентификации нужен весь список, а не первый
    попавшийся."""
    digits = "".join(c for c in phone if c.isdigit())[-10:]
    if not digits:
        return []
    return [
        dict(r) for r in _rows("SELECT * FROM bb_students")
        if "".join(c for c in (r["phone"] or "") if c.isdigit()).endswith(digits)
    ]


def student_age(row: dict) -> str:
    """Возраст ученика из raw_json, если CRM его отдала; иначе пусто."""
    try:
        raw = json.loads(row.get("raw_json") or "{}")
    except (TypeError, ValueError):
        return ""
    for key in ("age", "vozrast"):
        if raw.get(key):
            return str(raw[key])
    birthday = str(raw.get("birthday") or raw.get("birth_date") or "")
    match = re.match(r"(\d{4})-\d{2}-\d{2}", birthday)
    if match:
        age = date.today().year - int(match.group(1))
        if 0 < age < 100:
            return str(age)
    return ""


# --- CRM-контекст ученика для консультаций (спека approach-1, раздел 4) ---

_WEEKDAYS_RU = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
_CONTEXT_DAYS_AHEAD = 7
_CONTEXT_ATTENDANCE_DAYS = 30

# Статусы посещения в сырых данных урока → русская формулировка для промпта.
_VISIT_STATUS_RU = {
    "present": "присутствовал", "visited": "присутствовал", "attended": "присутствовал",
    "присутствовал": "присутствовал", "был": "присутствовал",
    "absent": "отсутствовал", "missed": "отсутствовал",
    "отсутствовал": "отсутствовал", "не был": "отсутствовал",
    "late": "опоздал", "опоздал": "опоздал",
}


def _student_groups(student: dict) -> list[dict]:
    """Активные группы ученика из raw_json.active_groups (см. list_active_students)."""
    try:
        raw = json.loads(student.get("raw_json") or "{}")
    except (TypeError, ValueError):
        return []
    return [g for g in (raw.get("active_groups") or []) if isinstance(g, dict)]


def _lesson_visit_status(lesson: dict, student_id: int) -> str:
    """Статус посещения ученика на уроке, если CRM отдала его в raw_json.

    Публичный API /lessons отдаёт расписание групп; персональные отметки
    посещаемости встречаются не во всех выгрузках, поэтому ищем их
    оборонительно в списках students/visits/attendance. Нет данных — пустая
    строка, и раздел посещаемости в контекст не попадёт вовсе.
    """
    try:
        raw = json.loads(lesson.get("raw_json") or "{}")
    except (TypeError, ValueError):
        return ""
    entries = []
    for key in ("students", "visits", "attendance", "attendances"):
        value = raw.get(key)
        if isinstance(value, list):
            entries.extend(value)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = (entry.get("user_id") or entry.get("student_id")
                    or entry.get("userId") or entry.get("id"))
        if entry_id != student_id:
            continue
        status = str(entry.get("status") or entry.get("visit")
                     or entry.get("attendance_status") or "").strip().lower()
        if status in _VISIT_STATUS_RU:
            return _VISIT_STATUS_RU[status]
        if isinstance(entry.get("visit"), bool):
            return "присутствовал" if entry["visit"] else "отсутствовал"
    return ""


def _format_lesson_line(lesson: dict) -> str:
    """«ср, 12.03, 17:00–18:00 — группа …» из строки bb_lessons."""
    parts = []
    lesson_date = str(lesson.get("date") or "")
    try:
        parsed = date.fromisoformat(lesson_date)
        parts.append(f"{_WEEKDAYS_RU[parsed.weekday()]}, {parsed.strftime('%d.%m')}")
    except ValueError:
        if lesson_date:
            parts.append(lesson_date)
    starts = str(lesson.get("starts_at") or "")[:5]
    ends = str(lesson.get("ends_at") or "")[:5]
    if starts:
        parts.append(f"{starts}–{ends}" if ends else starts)
    line = " ".join(parts) if parts else "занятие"
    caption = lesson.get("group_caption") or ""
    if caption:
        line += f" — {caption}"
    return line


def get_customer_context(student_id: int, *, today: date | None = None) -> str:
    """Текстовый блок о ребёнке для системного промпта консультанта.

    Источник — только локальный read-model (bb_* таблицы). В блок НЕ
    включаются баланс, задолженности, платежи и счета (спека approach-1,
    раздел 4): эти темы — зона администратора, а не бота. Разделы, по
    которым в кэше нет данных (посещаемость без отметок, домашние задания,
    комментарии педагога), опускаются целиком — не выдумываем.
    """
    rows = _rows("SELECT * FROM bb_students WHERE id=?", (student_id,))
    if not rows:
        return ""
    student = rows[0]
    today = today or date.today()
    lines: list[str] = []

    fio = student.get("fio") or ""
    header = f"Ребёнок: {fio}" if fio else f"Ученик №{student_id}"
    age = student_age(student)
    if age:
        header += f", {age} лет"
    lines.append(header)

    groups = _student_groups(student)
    group_ids = [g.get("id") for g in groups if g.get("id")]
    meta = group_meta_map()
    for group in groups:
        caption = group.get("caption") or ""
        teacher = meta.get(group.get("id") or 0, {}).get("teacher") or ""
        line = f"Группа: {caption}" if caption else ""
        if teacher:
            line += f" (преподаватель: {teacher})" if line else f"Преподаватель: {teacher}"
        if line:
            lines.append(line)

    if group_ids:
        upcoming = [
            lesson for lesson in list_lessons(
                today.isoformat(), (today + timedelta(days=_CONTEXT_DAYS_AHEAD)).isoformat())
            if lesson.get("group_id") in group_ids
        ]
        if upcoming:
            lines.append("Расписание на неделю вперёд:")
            lines.extend(f"- {_format_lesson_line(l)}" for l in upcoming[:10])

        past = [
            lesson for lesson in list_lessons(
                (today - timedelta(days=_CONTEXT_ATTENDANCE_DAYS)).isoformat(),
                (today - timedelta(days=1)).isoformat())
            if lesson.get("group_id") in group_ids
        ]
        attendance = []
        for lesson in past:
            status = _lesson_visit_status(lesson, student_id)
            if status:
                attendance.append(f"- {_format_lesson_line(lesson)}: {status}")
        if attendance:
            lines.append("Посещаемость за последние 30 дней:")
            lines.extend(attendance[:10])

    return "\n".join(lines)


def get_group(group_id: int) -> dict | None:
    rows = _rows("SELECT * FROM bb_groups WHERE id=?", (group_id,))
    return rows[0] if rows else None


def freshness() -> dict:
    """Свежесть read-model по сущностям — для UI и health."""
    out = {}
    for table, label in (("bb_filials", "filials"), ("bb_groups", "groups"),
                         ("bb_lessons", "lessons"), ("bb_students", "students"),
                         ("bb_payments", "payments")):
        row = _db().execute(f"SELECT COUNT(*) c, MAX(synced_at) m FROM {table}").fetchone()
        out[label] = {"count": row["c"], "last_synced_at": row["m"]}
    return out


# --- sync_runs ---

def sync_run_start(kind: str, mode: str) -> int:
    cur = _db().execute(
        "INSERT INTO sync_runs (kind, mode, started_at) VALUES (?,?,?)", (kind, mode, _now()))
    _db().commit()
    return int(cur.lastrowid)


def sync_run_finish(run_id: int, *, status: str, processed: int, failed: int = 0, error: str = "") -> None:
    _db().execute(
        "UPDATE sync_runs SET finished_at=?, status=?, processed=?, failed=?, error=? WHERE id=?",
        (_now(), status, processed, failed, error[:500], run_id))
    _db().commit()


def last_sync_runs(limit: int = 20) -> list[dict]:
    return _rows("SELECT * FROM sync_runs ORDER BY id DESC LIMIT ?", (limit,))


# --- webhook events ---

def record_webhook_event(event: str, account_id: int | None, payload: dict,
                         event_ts: str, dedup_key: str) -> tuple[int, bool]:
    """Возвращает (id, is_duplicate). Идемпотентно по dedup_key."""
    try:
        cur = _db().execute(
            "INSERT INTO bb_webhook_events (event, account_id, payload_json, event_ts,"
            " dedup_key, received_at) VALUES (?,?,?,?,?,?)",
            (event, account_id, json.dumps(payload, ensure_ascii=False), event_ts, dedup_key, _now()))
        _db().commit()
        return int(cur.lastrowid), False
    except sqlite3.IntegrityError:
        row = _db().execute("SELECT id FROM bb_webhook_events WHERE dedup_key=?", (dedup_key,)).fetchone()
        return int(row["id"]), True


def mark_webhook_processed(event_id: int, *, error: str = "") -> None:
    status = "failed" if error else "processed"
    _db().execute(
        "UPDATE bb_webhook_events SET status=?, attempts=attempts+1, last_error=?,"
        " processed_at=? WHERE id=?",
        (status, error[:500], _now(), event_id))
    _db().commit()


def failed_webhooks(limit: int = 50) -> list[dict]:
    return _rows(
        "SELECT * FROM bb_webhook_events WHERE status='failed' ORDER BY id DESC LIMIT ?",
        (limit,))


# --- bookings ---

def _ensure_booking_columns(conn) -> None:
    """Миграции bookings: student_id (карточка ученика), child_birthdate."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(bookings)")}
    if "student_id" not in cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN student_id INTEGER")
    if "child_birthdate" not in cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN child_birthdate TEXT NOT NULL DEFAULT ''")
    if "kind" not in cols:
        # trial (пробное) | enroll (запись в группу с оплатой абонемента)
        conn.execute("ALTER TABLE bookings ADD COLUMN kind TEXT NOT NULL DEFAULT 'trial'")
    conn.commit()


def create_booking(*, parent_name: str, phone: str, child_name: str, child_age: str,
                   comment: str, source: str, group_id: int, lesson_id: int,
                   filial_id: int | None, idempotency_key: str,
                   child_birthdate: str = "", kind: str = "trial") -> tuple[int, bool]:
    """Создаёт бронь в pending. (id, is_duplicate) по idempotency_key."""
    conn = _db()
    _ensure_booking_columns(conn)
    try:
        cur = conn.execute(
            "INSERT INTO bookings (created_at, parent_name, phone, child_name, child_age,"
            " comment, source, group_id, lesson_id, filial_id, idempotency_key,"
            " child_birthdate, kind)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_now(), parent_name, phone, child_name, child_age, comment, source,
             group_id, lesson_id, filial_id, idempotency_key, child_birthdate, kind))
        conn.commit()
        return int(cur.lastrowid), False
    except sqlite3.IntegrityError:
        row = conn.execute(
            "SELECT id FROM bookings WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        return int(row["id"]), True


def list_active_students(limit: int = 5000) -> list[dict]:
    """Ученики, у которых есть хотя бы одна активная группа (raw_json.active_groups)."""
    return _rows(
        "SELECT * FROM bb_students "
        "WHERE json_array_length(json_extract(raw_json, '$.active_groups')) > 0 LIMIT ?",
        (limit,))


def has_payment_since(student_id: int, since_iso_date: str) -> bool:
    """Была ли у ученика оплата с датой >= since_iso_date (YYYY-MM-DD)."""
    row = _rows(
        "SELECT 1 AS x FROM bb_payments WHERE student_id = ? AND paid_at >= ? LIMIT 1",
        (student_id, since_iso_date))
    return bool(row)


def list_bookings_by_phone(phone: str, limit: int = 50) -> list[dict]:
    """Заявки на пробное по телефону (нормализация — как у find_student_by_phone)."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())[-10:]
    if not digits:
        return []
    # Заявок немного (операционная таблица), телефон хранится в свободном
    # формате — нормализуем в Python по последним 10 цифрам.
    rows = _rows("SELECT * FROM bookings ORDER BY id DESC LIMIT 1000")
    return [r for r in rows
            if "".join(ch for ch in r.get("phone", "") if ch.isdigit())[-10:] == digits
            ][:limit]


def list_payments_by_student(student_id: int, limit: int = 50) -> list[dict]:
    return _rows(
        "SELECT * FROM bb_payments WHERE student_id = ? ORDER BY paid_at DESC LIMIT ?",
        (student_id, limit))


def upsert_group_meta(group_id: int, *, teacher: str = "", period_start: str = "",
                      period_end: str = "", monthly_payment: int | None = None,
                      for_events: bool = False, cost_per_event: int | None = None,
                      title: str = "") -> None:
    _db().execute(
        "INSERT INTO bb_group_meta (group_id, teacher, period_start, period_end,"
        " monthly_payment, for_events, cost_per_event, title, synced_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(group_id) DO UPDATE SET teacher=excluded.teacher,"
        " period_start=excluded.period_start, period_end=excluded.period_end,"
        " monthly_payment=excluded.monthly_payment,"
        " for_events=excluded.for_events,"
        " cost_per_event=excluded.cost_per_event, title=excluded.title,"
        " synced_at=excluded.synced_at",
        (group_id, teacher, period_start, period_end, monthly_payment,
         1 if for_events else 0, cost_per_event, title, _now()))
    _db().commit()


def group_meta_map() -> dict[int, dict]:
    rows = _rows("SELECT * FROM bb_group_meta")
    return {r["group_id"]: dict(r) for r in rows}

def group_period_map() -> dict[int, tuple[str, str]]:
    """Период группы: (первая, последняя дата) по синхронизированным урокам."""
    rows = _rows(
        "SELECT group_id, MIN(date) AS d0, MAX(date) AS d1 FROM bb_lessons"
        " GROUP BY group_id")
    return {r["group_id"]: (r["d0"], r["d1"]) for r in rows if r.get("group_id")}

def lesson_duration_map(date_from: str, date_to: str) -> dict[int, int]:
    """Типовая длительность урока группы (минуты, мода по окну расписания)."""
    from collections import Counter
    rows = _rows(
        "SELECT group_id, starts_at, ends_at FROM bb_lessons"
        " WHERE date BETWEEN ? AND ? AND starts_at IS NOT NULL AND ends_at IS NOT NULL",
        (date_from, date_to))
    per_group: dict[int, Counter] = {}
    for r in rows:
        try:
            t0 = datetime.fromisoformat(str(r["starts_at"]).replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(str(r["ends_at"]).replace("Z", "+00:00"))
            mins = int((t1 - t0).total_seconds() // 60)
            if 15 <= mins <= 240:
                per_group.setdefault(r["group_id"], Counter())[mins] += 1
        except (ValueError, TypeError):
            continue
    return {gid: c.most_common(1)[0][0] for gid, c in per_group.items()}

def booking_by_invoice(invoice_id: str) -> dict | None:
    rows = _rows("SELECT * FROM bookings WHERE invoice_id=?", (invoice_id,))
    return rows[0] if rows else None


def set_booking_awaiting_payment(booking_id: int, invoice_id: str,
                                 amount_kopecks: int) -> None:
    _db().execute(
        "UPDATE bookings SET status='awaiting_payment', invoice_id=?,"
        " amount_kopecks=? WHERE id=?",
        (invoice_id, amount_kopecks, booking_id))
    _db().commit()


def mark_booking_paid_unfulfilled(booking_id: int) -> None:
    """Деньги получены, но CRM-регистрация не выполнена (CRM недоступна).
    Отдельный статус, чтобы такие записи не потерялись и их можно было
    дообработать вручную/replay."""
    _db().execute(
        "UPDATE bookings SET status='paid_unfulfilled' WHERE id=?", (booking_id,))
    _db().commit()

def booking_by_id(booking_id: int) -> dict | None:
    rows = _rows("SELECT * FROM bookings WHERE id=?", (booking_id,))
    return rows[0] if rows else None


def confirm_booking(booking_id: int, *, lead_id: int | None,
                    demo_lesson_id: int | None,
                    student_id: int | None = None) -> None:
    conn = _db()
    _ensure_booking_columns(conn)
    conn.execute(
        "UPDATE bookings SET status='confirmed', lead_id=?, demo_lesson_id=?,"
        " student_id=?, confirmed_at=?, error='' WHERE id=?",
        (lead_id, demo_lesson_id, student_id, _now(), booking_id))
    conn.commit()


def fail_booking(booking_id: int, error: str) -> None:
    _db().execute(
        "UPDATE bookings SET status='failed', error=? WHERE id=?",
        (error[:500], booking_id))
    _db().commit()
