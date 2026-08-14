"""Личный кабинет мини-приложения: дети, попытки теста, расписание.

Зачем отдельный модуль: кабинет — первое место, где данные бота перестают
быть приватным контекстом диалога и становятся продуктом, к которому
человек возвращается. Диалог (`app.memory`) про разговор, кабинет — про
«что моё»: дети, результаты теста, расписание из выгрузки.

Три принципа, на которых всё построено:
1. Полезен до первого импорта: живёт на том, что бот собрал сам
   (заявка, SMART-профиль, попытки теста).
2. Ничего не выдумывает: если данных нет, кабинет говорит, чего не
   хватает, а не рисует заглушку.
3. Ничего чужого: каждая строка привязана к (platform, user_id), а
   личность проверяется подписанным initData — см. app.miniapp_auth.

Миграций нет: таблицы создаются IF NOT EXISTS рядом с остальными в той же
базе, старые записи диалогов читаются как раньше.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

# МСК: школа работает в этом часовом поясе, «ближайшее занятие» и даты в
# кабинете должны совпадать с календарём родителя, а не с UTC сервера.
MSK = timezone(timedelta(hours=3))

SCHEMA = """
CREATE TABLE IF NOT EXISTS children (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    age TEXT NOT NULL DEFAULT '',
    grade TEXT NOT NULL DEFAULT '',
    level TEXT NOT NULL DEFAULT '',
    program TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS children_owner ON children(platform, user_id);

CREATE TABLE IF NOT EXISTS level_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    user_id TEXT NOT NULL,
    child_id INTEGER,
    child_name TEXT NOT NULL DEFAULT '',
    taken_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    correct INTEGER NOT NULL,
    total INTEGER NOT NULL,
    level_code TEXT NOT NULL,
    answers_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS level_attempts_owner ON level_attempts(platform, user_id);

CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL DEFAULT '',
    uploaded_by TEXT NOT NULL DEFAULT '',
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rows_total INTEGER NOT NULL DEFAULT 0,
    rows_matched INTEGER NOT NULL DEFAULT 0,
    rows_unmatched INTEGER NOT NULL DEFAULT 0,
    mapping_json TEXT NOT NULL DEFAULT '{}',
    report_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS imported_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    platform TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL DEFAULT '',
    student_name TEXT NOT NULL,
    phone_norm TEXT NOT NULL DEFAULT '',
    weekday TEXT NOT NULL DEFAULT '',
    time TEXT NOT NULL DEFAULT '',
    program TEXT NOT NULL DEFAULT '',
    teacher TEXT NOT NULL DEFAULT '',
    filial TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS imported_lessons_owner ON imported_lessons(platform, user_id);

-- Запомненное сопоставление колонок выгрузки: одна строка на школу.
CREATE TABLE IF NOT EXISTS import_mapping (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    mapping_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Журнал действий администратора: кто и когда загрузил выгрузку.
-- Имена детей и телефоны сюда не пишутся — только факт действия и счётчики.
CREATE TABLE IF NOT EXISTS admin_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details TEXT NOT NULL DEFAULT ''
);
"""

# Порядок уровней теста — из app.leveltest._LEVELS, по возрастанию.
# Дублируется здесь осознанно: кабинет сравнивает коды как ранги, и ранг
# обязан быть стабильным, даже если формулировки в тесте поменяют.
LEVEL_RANK = {"A0–A1": 0, "A1–A2": 1, "A2–B1": 2, "B1+": 3}

# Сколько дней расписание из выгрузки считается свежим. Дольше — показываем
# дату импорта и напоминаем администратору (см. app.scheduler).
IMPORT_STALE_DAYS = 9

_WEEKDAY_ORDER = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
_WEEKDAY_FULL = {
    "пн": "понедельник", "вт": "вторник", "ср": "среда", "чт": "четверг",
    "пт": "пятница", "сб": "суббота", "вс": "воскресенье",
}
_WEEKDAY_ALIASES = {
    "понедельник": "пн", "пн": "пн", "mon": "пн", "monday": "пн",
    "вторник": "вт", "вт": "вт", "tue": "вт", "tuesday": "вт",
    "среда": "ср", "ср": "ср", "wed": "ср", "wednesday": "ср",
    "четверг": "чт", "чт": "чт", "thu": "чт", "thursday": "чт",
    "пятница": "пт", "пт": "пт", "fri": "пт", "friday": "пт",
    "суббота": "сб", "сб": "сб", "sat": "сб", "saturday": "сб",
    "воскресенье": "вс", "вс": "вс", "sun": "вс", "sunday": "вс",
}


def init_schema(conn: sqlite3.Connection) -> None:
    """Создаёт таблицы кабинета. Вызывается из MemoryStore._init_schema."""
    conn.executescript(SCHEMA)


def now_msk() -> datetime:
    return datetime.now(MSK)


# ------------------------------------------------------------------ дети

def _child_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "age": row["age"],
        "grade": row["grade"],
        "level": row["level"],
        "program": row["program"],
    }


def list_children(store, platform: str, user_id: str) -> list[dict]:
    with store._lock:
        rows = store._conn.execute(
            "SELECT * FROM children WHERE platform = ? AND user_id = ? ORDER BY id",
            (platform, user_id),
        ).fetchall()
    return [_child_from_row(r) for r in rows]


def upsert_child(store, platform: str, user_id: str, child_id: int | None, fields: dict) -> dict:
    """Создаёт или обновляет ребёнка. Возвращает запись.

    Чужого ребёнка обновить нельзя: child_id проверяется на принадлежность
    владельцу в том же запросе.
    """
    name = str(fields.get("name", "")).strip()[:120]
    age = str(fields.get("age", "")).strip()[:20]
    grade = str(fields.get("grade", "")).strip()[:20]
    level = str(fields.get("level", "")).strip()[:20]
    program = str(fields.get("program", "")).strip()[:160]
    if not name and child_id is None:
        raise ValueError("Имя ребёнка обязательно")
    with store._lock:
        if child_id is None:
            cur = store._conn.execute(
                "INSERT INTO children(platform, user_id, name, age, grade, level, program)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (platform, user_id, name, age, grade, level, program),
            )
            child_id = cur.lastrowid
        else:
            cur = store._conn.execute(
                "UPDATE children SET name=COALESCE(NULLIF(?,''), name), age=?, grade=?,"
                " level=?, program=?, updated_at=CURRENT_TIMESTAMP"
                " WHERE id=? AND platform=? AND user_id=?",
                (name, age, grade, level, program, child_id, platform, user_id),
            )
            if cur.rowcount != 1:
                raise LookupError("Ребёнок не найден")
        row = store._conn.execute(
            "SELECT * FROM children WHERE id = ?", (child_id,)
        ).fetchone()
    return _child_from_row(row)


def ensure_children(store, conv) -> list[dict]:
    """Список детей владельца; ребёнок из заявки попадает туда сам.

    Кабинет обязан быть полезен до первой правки вручную: ребёнок, которого
    человек уже назвал боту в заявке или разговоре, появляется в кабинете
    сам. Добавление идёт по имени: если «Машу» уже завели руками, второй
    Маши из заявки не появится.
    """
    children = list_children(store, conv.platform, conv.user_id)
    name = (conv.lead.fio_child or "").strip()
    if not name:
        return children
    known = {c["name"].strip().lower() for c in children}
    if name.strip().lower() in known:
        return children
    upsert_child(store, conv.platform, conv.user_id, None, {
        "name": name,
        "age": conv.lead.age or conv.need.child_age or "",
        "grade": conv.need.child_grade or "",
        "level": conv.need.level or "",
        "program": conv.selected_course or conv.lead.course or "",
    })
    return list_children(store, conv.platform, conv.user_id)


def sync_child_into_conversation(store, conv, child: dict) -> None:
    """Правка карточки ребёнка уходит в профиль, которым пользуется бот.

    Иначе человек поправил возраст в кабинете, а бот в чате продолжает
    называть старый — два источника правды, расходящихся навсегда.
    Обновляется первый ребёнок диалога (conv.lead/conv.need); дети сверх
    первого в чате пока не адресуются.
    """
    children = list_children(store, conv.platform, conv.user_id)
    if not children or children[0]["id"] != child["id"]:
        return
    # В диалоге уже назван другой ребёнок — карточка про него, и затирать
    # её данными второго ребёнка нельзя.
    existing = (conv.lead.fio_child or "").strip().lower()
    if existing and existing != child["name"].strip().lower():
        return
    changed = False
    if child["name"] and conv.lead.fio_child != child["name"]:
        conv.lead.fio_child = child["name"]
        changed = True
    if child["age"] and conv.lead.age != child["age"]:
        conv.lead.age = child["age"]
        conv.need.child_age = child["age"]
        changed = True
    if child["grade"] and conv.need.child_grade != child["grade"]:
        conv.need.child_grade = child["grade"]
        changed = True
    if child["level"] and conv.need.level != child["level"]:
        conv.need.level = child["level"]
        changed = True
    if child["program"] and conv.selected_course != child["program"]:
        conv.selected_course = child["program"]
        changed = True
    if changed:
        store.save(conv)


# ------------------------------------------------------- попытки теста

def record_attempt(
    store,
    platform: str,
    user_id: str,
    result: dict,
    answers: dict,
    child_id: int | None = None,
) -> dict:
    """Сохраняет попытку теста уровня на сервере.

    Раньше результат жил только в localStorage браузера и терялся вместе с
    кэшем — а динамика между попытками и есть главная ценность кабинета на
    старте. Попытка без child_id привязывается к первому ребёнку владельца,
    если он есть.
    """
    child_name = ""
    if child_id is None:
        children = list_children(store, platform, user_id)
        if children:
            child_id = children[0]["id"]
    if child_id is not None:
        with store._lock:
            row = store._conn.execute(
                "SELECT * FROM children WHERE id = ? AND platform = ? AND user_id = ?",
                (child_id, platform, user_id),
            ).fetchone()
        if row is None:
            child_id = None  # чужой или несуществующий ребёнок — не привязываем
        else:
            child_name = row["name"]
    with store._lock:
        cur = store._conn.execute(
            "INSERT INTO level_attempts(platform, user_id, child_id, child_name,"
            " correct, total, level_code, answers_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                platform, user_id, child_id, child_name,
                int(result.get("correct", 0)), int(result.get("total", 0)),
                str(result.get("level", "")), json.dumps(answers, ensure_ascii=False),
            ),
        )
        attempt_id = cur.lastrowid
        # Свежий результат теста — лучшее, что мы знаем об уровне ребёнка:
        # карточка обновляется сама, а не ждёт ручной правки.
        if child_id is not None and result.get("level"):
            store._conn.execute(
                "UPDATE children SET level = ?, updated_at = CURRENT_TIMESTAMP"
                " WHERE id = ?",
                (str(result["level"]), child_id),
            )
        row = store._conn.execute(
            "SELECT * FROM level_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
    return _attempt_from_row(row)


def _attempt_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "child_id": row["child_id"],
        "child_name": row["child_name"],
        "taken_at": row["taken_at"],
        "correct": row["correct"],
        "total": row["total"],
        "level": row["level_code"],
        "answers": json.loads(row["answers_json"] or "{}"),
    }


def list_attempts(store, platform: str, user_id: str) -> list[dict]:
    with store._lock:
        rows = store._conn.execute(
            "SELECT * FROM level_attempts WHERE platform = ? AND user_id = ?"
            " ORDER BY taken_at, id",
            (platform, user_id),
        ).fetchall()
    return [_attempt_from_row(r) for r in rows]


def _format_date_ru(iso: str) -> str:
    """'2026-08-12 14:03:01' (UTC) → '12 августа' по МСК."""
    try:
        dt = datetime.fromisoformat(iso.replace(" ", "T"))
    except ValueError:
        return iso[:10]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(MSK)
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    return f"{dt.day} {months[dt.month - 1]}"


def progress_summary(attempts: list[dict]) -> dict:
    """Картина прогресса по попыткам теста.

    Одна попытка — не график, а строка с предложением вернуться через месяц.
    Две и больше — серия точек и честная фраза по разнице кодов уровня,
    а не сочинённая моделью.
    """
    if not attempts:
        return {"kind": "none", "points": [], "phrase": ""}
    points = [
        {
            "at": a["taken_at"],
            "date": _format_date_ru(a["taken_at"]),
            "level": a["level"],
            "correct": a["correct"],
            "total": a["total"],
            "child_name": a["child_name"],
        }
        for a in attempts
    ]
    if len(attempts) == 1:
        only = attempts[0]
        return {
            "kind": "single",
            "points": points,
            "phrase": (
                f"Первый результат: {only['level']}, "
                f"{_format_date_ru(only['taken_at'])}. "
                "Пройдите тест снова примерно через месяц — будет видно динамику."
            ),
        }
    first, last = attempts[0], attempts[-1]
    prev = attempts[-2]
    rank_first = LEVEL_RANK.get(first["level"], 0)
    rank_last = LEVEL_RANK.get(last["level"], 0)
    rank_prev = LEVEL_RANK.get(prev["level"], 0)
    if rank_last > rank_prev:
        phrase = (
            f"Рост: {_format_date_ru(prev['taken_at'])} было {prev['level']}, "
            f"сейчас — {last['level']}. База, которая раньше путалась, держится."
        )
    elif rank_last < rank_prev:
        phrase = (
            f"Сейчас {last['level']} — ниже прошлого результата ({prev['level']}). "
            "Это повод для диагностики с методистом, а не для тревоги: "
            "пять заданий — грубая шкала."
        )
    else:
        phrase = f"Уровень держится: {last['level']}."
    return {
        "kind": "series",
        "points": points,
        "phrase": phrase,
        "grew": rank_last > rank_first,
    }


# ------------------------------------------------------------- расписание

def normalize_weekday(value: str) -> str:
    """'Понедельник' / 'Mon' / 'пн' → 'пн'. Незнакомое — пустая строка."""
    text = (value or "").strip().lower()
    if not text:
        return ""
    for key, code in _WEEKDAY_ALIASES.items():
        if text == key or text.startswith(key):
            return code
    return ""


def weekday_label(code: str) -> str:
    return _WEEKDAY_FULL.get(code, code)


def latest_batch(store) -> dict | None:
    with store._lock:
        row = store._conn.execute(
            "SELECT * FROM import_batches ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "uploaded_at": row["uploaded_at"],
        "rows_total": row["rows_total"],
        "rows_matched": row["rows_matched"],
        "rows_unmatched": row["rows_unmatched"],
    }


def import_age_days(store, now: datetime | None = None) -> float | None:
    """Сколько дней прошло с последнего импорта. None — импорта не было."""
    batch = latest_batch(store)
    if batch is None:
        return None
    try:
        uploaded = datetime.fromisoformat(batch["uploaded_at"].replace(" ", "T"))
    except ValueError:
        return None
    if uploaded.tzinfo is None:
        uploaded = uploaded.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (now - uploaded).total_seconds() / 86400.0


def schedule_for(store, platform: str, user_id: str, child_name: str = "") -> dict:
    """Расписание владельца из последней выгрузки.

    Видно только то, что сопоставлено с этим родителем: чужой ученик из
    выгрузки недоступен ни при каком запросе. Дата импорта едет рядом —
    стареющие данные честно помечены.
    """
    batch = latest_batch(store)
    if batch is None:
        return {"has_import": False, "imported_at": "", "stale": False,
                "imported_label": "", "lessons": [], "next": None}
    with store._lock:
        rows = store._conn.execute(
            "SELECT * FROM imported_lessons WHERE platform = ? AND user_id = ?",
            (platform, user_id),
        ).fetchall()
    lessons = []
    for row in rows:
        if child_name and row["student_name"].strip().lower() != child_name.strip().lower():
            continue
        lessons.append({
            "student_name": row["student_name"],
            "weekday": row["weekday"],
            "weekday_label": weekday_label(row["weekday"]),
            "time": row["time"],
            "program": row["program"],
            "teacher": row["teacher"],
            "filial": row["filial"],
        })

    def _sort_key(lesson: dict) -> tuple[int, str]:
        try:
            day = _WEEKDAY_ORDER.index(lesson["weekday"])
        except ValueError:
            day = 99
        return (day, lesson["time"])

    lessons.sort(key=_sort_key)
    age = import_age_days(store)
    stale = bool(age is not None and age > IMPORT_STALE_DAYS)
    next_lesson = _next_lesson(lessons)
    return {
        "has_import": True,
        "imported_at": batch["uploaded_at"],
        "imported_label": _format_date_ru(batch["uploaded_at"]),
        "stale": stale,
        "lessons": lessons,
        "next": next_lesson,
    }


def _next_lesson(lessons: list[dict]) -> dict | None:
    """Ближайшее занятие от текущего момента (МСК)."""
    if not lessons:
        return None
    now = now_msk()
    today_code = _WEEKDAY_ORDER[now.weekday()]
    best: tuple[int, dict] | None = None
    for lesson in lessons:
        if lesson["weekday"] not in _WEEKDAY_ORDER:
            continue
        day_idx = _WEEKDAY_ORDER.index(lesson["weekday"])
        days_ahead = (day_idx - now.weekday()) % 7
        if days_ahead == 0 and lesson["time"]:
            try:
                hour, minute = (int(part) for part in lesson["time"].split(":")[:2])
                if (hour, minute) <= (now.hour, now.minute):
                    days_ahead = 7  # сегодняшнее уже прошло
            except ValueError:
                pass
        if best is None or days_ahead < best[0]:
            best = (days_ahead, lesson)
    if best is None:
        return None
    lesson = dict(best[1])
    days_ahead = best[0]
    if days_ahead == 0:
        lesson["day_hint"] = "сегодня"
    elif days_ahead == 1:
        lesson["day_hint"] = "завтра"
    else:
        lesson["day_hint"] = weekday_label(lesson["weekday"])
    lesson["today_code"] = today_code
    return lesson


# ------------------------------------------------------------- «что дальше»

def next_action(conv, attempts: list[dict], schedule: dict) -> dict:
    """Одно действие по состоянию человека. Одно, а не список:
    список из пяти предложений — витрина, а не забота.
    """
    if not attempts and not (conv.need.level or ""):
        return {
            "kind": "level_test",
            "title": "Узнать уровень",
            "text": "Пять заданий за минуту — и мы поймём, с чего начинать.",
            "sheet": "quiz",
            "cta": "Пройти тест",
        }
    if not conv.lead_submitted:
        return {
            "kind": "signup",
            "title": "Записаться на диагностику",
            "text": "Методист определит точный уровень и подберёт группу. Это бесплатно.",
            "sheet": "signup",
            "cta": "Записаться",
        }
    if not schedule.get("has_import") or not schedule.get("lessons"):
        return {
            "kind": "route",
            "title": "Добраться до филиала",
            "text": "Вы записаны. Постройте маршрут заранее, чтобы первое занятие началось спокойно.",
            "cta": "Построить маршрут",
        }
    return {
        "kind": "ask_teacher",
        "title": "Вопрос педагогу",
        "text": "Что-то непонятно по занятиям или домашке? Спросите — Фокси передаст педагогу.",
        "cta": "Спросить в чате",
    }


def lead_payload(conv) -> dict | None:
    """Заявка человека. Статусы — только достоверные.

    «В обработке» здесь не появится, пока этого кто-то не подтвердил:
    мы знаем лишь, что заявка отправлена и что она передана администратору.
    """
    if not conv.lead_submitted:
        return None
    status = "передана администратору" if conv.handed_off or conv.stage == "done" else "отправлена"
    submitted_at = getattr(conv, "lead_submitted_at", "") or conv.updated_at
    return {
        "date": _format_date_ru(submitted_at) if submitted_at else "",
        "program": conv.selected_course or conv.lead.course,
        "branch": conv.selected_branch or conv.lead.branch,
        "status": status,
    }


def parent_first_name(conv, display_name: str = "") -> str:
    """Имя родителя для приветствия (именительный падеж — обращение)."""
    fio = (conv.lead.fio_parent or "").strip()
    if fio:
        parts = fio.split()
        # «Иванова Анна Сергеевна» → имя вторым словом; «Анна» → как есть.
        return parts[1] if len(parts) >= 2 else parts[0]
    return (display_name or conv.client_name or "").strip().split()[0] if (display_name or conv.client_name) else ""


def build_cabinet(store, conv, display_name: str = "") -> dict:
    """Полная сводка кабинета для мини-приложения."""
    from app.morph import NOMINATIVE, decline

    children = ensure_children(store, conv)
    attempts = list_attempts(store, conv.platform, conv.user_id)
    # Попытка теста могла пройти раньше, чем появился ребёнок (из заявки):
    # тогда уровень лежит в попытке, а карточка пустая. Догоняем карточку
    # последним результатом — это лучшее, что мы знаем об уровне.
    if attempts:
        latest = attempts[-1]
        for child in children:
            if not child["level"] and latest.get("level"):
                child["level"] = latest["level"]
                upsert_child(store, conv.platform, conv.user_id, child["id"], child)
    schedule = schedule_for(store, conv.platform, conv.user_id)
    first_name = parent_first_name(conv, display_name)
    return {
        "greeting_name": decline(first_name, NOMINATIVE) if first_name else "",
        "registered": bool(conv.registered),
        "children": children,
        "attempts": progress_summary(attempts),
        "lead": lead_payload(conv),
        "schedule": schedule,
        "next_action": next_action(conv, attempts, schedule),
    }


# ------------------------------------------------------- журнал и аудит

def audit(store, actor: str, action: str, details: str = "") -> None:
    """Запись в журнал действий администратора.

    PII сюда не попадает: детали — это счётчики и имя файла, а не имена
    детей и телефоны (152-ФЗ: в логах лишнего быть не должно).
    """
    with store._lock:
        store._conn.execute(
            "INSERT INTO admin_audit(actor, action, details) VALUES (?, ?, ?)",
            (actor[:64], action[:64], details[:500]),
        )


def saved_mapping(store) -> dict:
    with store._lock:
        row = store._conn.execute(
            "SELECT mapping_json FROM import_mapping WHERE id = 1"
        ).fetchone()
    if row is None:
        return {}
    try:
        return json.loads(row["mapping_json"] or "{}")
    except ValueError:
        return {}


def remember_mapping(store, mapping: dict) -> None:
    with store._lock:
        store._conn.execute(
            "INSERT INTO import_mapping(id, mapping_json, updated_at)"
            " VALUES (1, ?, CURRENT_TIMESTAMP)"
            " ON CONFLICT(id) DO UPDATE SET mapping_json=excluded.mapping_json,"
            " updated_at=CURRENT_TIMESTAMP",
            (json.dumps(mapping, ensure_ascii=False),),
        )
