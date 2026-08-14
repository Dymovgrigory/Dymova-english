"""Личный кабинет мини-приложения: дети и попытки теста уровня.

Кабинет сейчас скрыт из интерфейса мини-приложения (решение владельца),
но хранилище и API оставлены: попытки теста пишутся сюда при каждом
прохождении, а дети синхронизируются с заявкой. Всё — только по
подписанной личности (app.miniapp_auth), `user_id` из запроса личностью
не считается.

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

"""

# Порядок уровней теста — из app.leveltest._LEVELS, по возрастанию.
# Дублируется здесь осознанно: кабинет сравнивает коды как ранги, и ранг
# обязан быть стабильным, даже если формулировки в тесте поменяют.
LEVEL_RANK = {"A0–A1": 0, "A1–A2": 1, "A2–B1": 2, "B1+": 3}

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


# ------------------------------------------------------------- «что дальше»

def next_action(conv, attempts: list[dict]) -> dict:
    """Одно действие по состоянию человека. Одно, а не список:
    список из пяти предложений — витрина, а не забота.
    """
    if not attempts and not (conv.need.level or ""):
        return {
            "kind": "level_test",
            "title": "Узнать уровень",
            "text": "Десять заданий с картинками — и мы поймём, с чего начинать.",
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
    first_name = parent_first_name(conv, display_name)
    return {
        "greeting_name": decline(first_name, NOMINATIVE) if first_name else "",
        "registered": bool(conv.registered),
        "children": children,
        "attempts": progress_summary(attempts),
        "lead": lead_payload(conv),
        "next_action": next_action(conv, attempts),
    }
