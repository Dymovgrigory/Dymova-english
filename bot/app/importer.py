"""Импорт еженедельной выгрузки расписания (CSV/XLSX).

Единственный внешний источник данных кабинета. У школы нет API на чтение из
CRM, поэтому раз в неделю администратор загружает файл — и кабинет оживает
расписанием. Кабинет при этом обязан работать и без выгрузки вовсе.

Правила:
- Колонки задаёт школа, поэтому сопоставление (какая колонка — имя ученика,
  какая — день и т.д.) выбирает администратор один раз; выбор запоминается.
- Строка находит своего родителя по телефону (нормализованному), затем по
  имени ребёнка. Несопоставленные строки не выбрасываются молча: они в
  отчёте, и их можно сопоставить руками.
- Партия заменяет предыдущую целиком: повторная загрузка того же файла не
  удваивает расписание.
- Файл не хранится: он нужен только на время разбора, отчёт — часть импорта.
- Телефоны и имена детей не попадают в логи (152-ФЗ): журнал аудита пишет
  только счётчики и имя файла.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET

from app import cabinet

# Поля, которые мы ждём от выгрузки, и слова, по которым угадываем колонку.
# Угаданное сопоставление — только подсказка: решает администратор.
FIELDS = ("student", "phone", "weekday", "time", "program", "teacher", "filial")

_GUESS = {
    "student": ("ученик", "ребёнок", "ребенок", "студент", "имя", "фио", "клиент"),
    "phone": ("телефон", "phone", "тел", "моб"),
    "weekday": ("день", "weekday", "дата"),  # «дата» — крайний случай, день недели из неё не взять
    "time": ("время", "time", "час"),
    "program": ("программа", "курс", "группа", "направление", "предмет"),
    "teacher": ("педагог", "преподаватель", "учитель", "teacher", "тренер"),
    "filial": ("филиал", "адрес", "filial", "локац", "площадк"),
}

# Защита от «выгрузки» на гигабайт: расписание школы — десятки килобайт.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class ImportError_(ValueError):
    """Понятная администратору ошибка разбора файла."""


# ------------------------------------------------------------- нормализация

def normalize_phone(raw: str) -> str:
    """'+7 (926) 123-45-67' → '79261234567'. Пусто, если цифр меньше 10."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    return digits if len(digits) == 11 and digits[0] == "7" else ""


def normalize_time(raw: str) -> str:
    """'17.30' / '17:30–19:00' → '17:30'. Пусто, если времени нет."""
    match = re.search(r"(\d{1,2})[:.](\d{2})", raw or "")
    if not match:
        return ""
    return f"{int(match.group(1)):02d}:{match.group(2)}"


# ------------------------------------------------------------------ разбор

def parse_upload(filename: str, content: bytes) -> tuple[list[str], list[dict]]:
    """Файл → (заголовки, строки-словари). CSV или XLSX, без зависимостей."""
    if len(content) > MAX_UPLOAD_BYTES:
        raise ImportError_("Файл слишком большой для выгрузки расписания")
    name = (filename or "").lower()
    if name.endswith(".xlsx") or content[:2] == b"PK":
        rows = _read_xlsx(content)
    else:
        rows = _read_csv(content)
    if not rows:
        raise ImportError_("В файле нет строк — проверьте, что это выгрузка расписания")
    headers = [str(h).strip() for h in rows[0]]
    if not any(headers):
        raise ImportError_("Не нашлась строка заголовков")
    dicts = []
    for raw in rows[1:]:
        row = {headers[i]: str(raw[i]).strip() for i in range(min(len(headers), len(raw))) if headers[i]}
        if any(row.values()):
            dicts.append(row)
    if not dicts:
        raise ImportError_("Заголовки есть, а строк расписания нет")
    return [h for h in headers if h], dicts


def _read_csv(content: bytes) -> list[list[str]]:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ImportError_("Не удалось прочитать файл: не UTF-8 и не CP1251")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
    return [row for row in csv.reader(io.StringIO(text), dialect) if row]


_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _read_xlsx(content: bytes) -> list[list[str]]:
    """Минимальный читатель XLSX: первый лист, sharedStrings и inline-строки.

    openpyxl не тащим ради одного файла в неделю: формат выгрузки простой,
    а зависимость — это ещё одна точка отказа при сборке контейнера.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ImportError_("Файл повреждён или это не XLSX") from exc
    names = set(archive.namelist())

    shared: list[str] = []
    if "xl/sharedStrings.xml" in names:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{_NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))

    sheet = "xl/worksheets/sheet1.xml"
    if sheet not in names:
        sheets = sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        if not sheets:
            raise ImportError_("В XLSX нет ни одного листа")
        sheet = sheets[0]
    root = ET.fromstring(archive.read(sheet))

    rows: list[list[str]] = []
    for row_el in root.iter(f"{_NS}row"):
        cells: dict[int, str] = {}
        for cell in row_el.findall(f"{_NS}c"):
            ref = cell.get("r", "")
            col = 0
            for ch in ref:
                if ch.isalpha():
                    col = col * 26 + (ord(ch.upper()) - 64)
                else:
                    break
            col = max(col - 1, 0)
            cells[col] = _cell_text(cell, shared)
        if cells:
            width = max(cells) + 1
            rows.append([cells.get(i, "") for i in range(width)])
    return rows


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.get("t", "")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(f"{_NS}t")).strip()
    value = cell.find(f"{_NS}v")
    if value is None or value.text is None:
        return ""
    text = value.text
    if kind == "s":
        try:
            return shared[int(text)].strip()
        except (ValueError, IndexError):
            return ""
    # Числа и даты Excel приезжают как есть; время-дробь нас не интересует —
    # школы пишут время текстом.
    return text.strip()


# ------------------------------------------------------- сопоставление колонок

def guess_mapping(headers: list[str]) -> dict:
    """Предположение «какая колонка что значит» по словам в заголовках."""
    mapping: dict[str, str] = {}
    lowered = [(h, h.lower()) for h in headers]
    for field, needles in _GUESS.items():
        for original, low in lowered:
            if any(needle in low for needle in needles):
                mapping[field] = original
                break
    return mapping


# ------------------------------------------------------------------- импорт

def _owner_index(store) -> tuple[dict, dict]:
    """Индексы «телефон → владелец» и «имя ребёнка → владелец».

    Телефон — главный ключ: имена совпадают, номера — почти никогда. Имя
    ребёнка — запасной ключ (сравнение по первому слову, нижний регистр).
    """
    phones: dict[str, tuple[str, str]] = {}
    names: dict[str, tuple[str, str]] = {}
    for conv in store.all_conversations():
        owner = (conv.platform, conv.user_id)
        phone = normalize_phone(conv.lead.phone)
        if phone:
            phones[phone] = owner
        child = (conv.lead.fio_child or "").strip().lower()
        if child:
            names.setdefault(child.split()[0], owner)
            names.setdefault(child, owner)
        for kid in cabinet.list_children(store, conv.platform, conv.user_id):
            key = kid["name"].strip().lower()
            if key:
                names.setdefault(key.split()[0], owner)
                names.setdefault(key, owner)
    return phones, names


def _match(row: dict, phones: dict, names: dict) -> tuple[str, str] | None:
    phone = normalize_phone(row.get("phone", ""))
    if phone and phone in phones:
        return phones[phone]
    student = (row.get("student") or "").strip().lower()
    if student:
        if student in names:
            return names[student]
        first = student.split()[0]
        if first in names:
            return names[first]
    return None


def import_schedule(store, *, filename: str, rows: list[dict], mapping: dict, actor: str) -> dict:
    """Прогоняет выгрузку: партия заменяет предыдущую целиком.

    Возвращает отчёт — он часть импорта, а не отладочный вывод: сколько
    строк, сколько сопоставлено, какие строки остались, чьё расписание
    изменилось.
    """
    if not mapping.get("student"):
        raise ImportError_("Не сопоставлена колонка с именем ученика")

    phones, names = _owner_index(store)
    matched: list[dict] = []
    unmatched: list[dict] = []

    for index, raw in enumerate(rows):
        row = {field: raw.get(header, "") for field, header in mapping.items() if header}
        row["weekday"] = cabinet.normalize_weekday(row.get("weekday", ""))
        row["time"] = normalize_time(row.get("time", ""))
        row["student"] = (row.get("student") or "").strip()
        if not row["student"]:
            continue  # строка без ученика — не расписание, а мусор выгрузки
        owner = _match(row, phones, names)
        entry = {
            "row_index": index,
            "student": row["student"],
            "weekday": row["weekday"],
            "time": row["time"],
            "program": row.get("program", ""),
            "teacher": row.get("teacher", ""),
            "filial": row.get("filial", ""),
            "phone_norm": normalize_phone(row.get("phone", "")),
        }
        if owner is None:
            unmatched.append(entry)
        else:
            entry["platform"], entry["user_id"] = owner
            matched.append(entry)

    changed = sorted({(e["platform"], e["user_id"]) for e in matched})
    report = {
        "rows_total": len(rows),
        "rows_matched": len(matched),
        "rows_unmatched": len(unmatched),
        "unmatched": unmatched,
        "changed_users": len(changed),
    }

    with store._lock:
        # Идемпотентность: прежняя партия уходит целиком, повторная загрузка
        # того же файла даёт тот же набор занятий, а не двойной.
        store._conn.execute("DELETE FROM imported_lessons")
        cur = store._conn.execute(
            "INSERT INTO import_batches(filename, uploaded_by, rows_total,"
            " rows_matched, rows_unmatched, mapping_json, report_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                (filename or "")[:255], actor[:64],
                report["rows_total"], report["rows_matched"], report["rows_unmatched"],
                json.dumps(mapping, ensure_ascii=False),
                json.dumps(report, ensure_ascii=False),
            ),
        )
        batch_id = cur.lastrowid
        for entry in matched:
            store._conn.execute(
                "INSERT INTO imported_lessons(batch_id, platform, user_id,"
                " student_name, phone_norm, weekday, time, program, teacher, filial)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    batch_id, entry["platform"], entry["user_id"], entry["student"],
                    entry["phone_norm"],
                    entry["weekday"], entry["time"], entry["program"],
                    entry["teacher"], entry["filial"],
                ),
            )
    cabinet.remember_mapping(store, mapping)
    # В журнал — только счётчики и имя файла. Имена детей и телефоны в логи
    # и аудит не попадают.
    cabinet.audit(
        store, actor, "schedule_import",
        f"file={filename or '?'} rows={report['rows_total']} "
        f"matched={report['rows_matched']} unmatched={report['rows_unmatched']}",
    )
    report["batch_id"] = batch_id
    return report


def match_manually(store, batch_id: int, row_index: int, platform: str, user_id: str) -> dict:
    """Ручное сопоставление строки из отчёта с родителем из бота."""
    with store._lock:
        row = store._conn.execute(
            "SELECT report_json, rows_matched, rows_unmatched FROM import_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
    if row is None:
        raise LookupError("Партия импорта не найдена")
    report = json.loads(row["report_json"] or "{}")
    unmatched = report.get("unmatched", [])
    entry = next((e for e in unmatched if e["row_index"] == row_index), None)
    if entry is None:
        raise LookupError("Строка уже сопоставлена или не существует")
    with store._lock:
        store._conn.execute(
            "INSERT INTO imported_lessons(batch_id, platform, user_id, student_name,"
            " weekday, time, program, teacher, filial)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                batch_id, platform, user_id, entry["student"], entry["weekday"],
                entry["time"], entry["program"], entry["teacher"], entry["filial"],
            ),
        )
        unmatched.remove(entry)
        report["rows_matched"] = report.get("rows_matched", 0) + 1
        report["rows_unmatched"] = report.get("rows_unmatched", 1) - 1
        store._conn.execute(
            "UPDATE import_batches SET report_json = ?, rows_matched = ?,"
            " rows_unmatched = ? WHERE id = ?",
            (json.dumps(report, ensure_ascii=False),
             report["rows_matched"], report["rows_unmatched"], batch_id),
        )
    cabinet.audit(store, "admin", "schedule_manual_match", f"batch={batch_id} row={row_index}")
    report["batch_id"] = batch_id
    return report


def status(store) -> dict:
    """Состояние импорта для админки: последняя партия, маппинг, свежесть."""
    batch = cabinet.latest_batch(store)
    age = cabinet.import_age_days(store)
    result = {
        "mapping": cabinet.saved_mapping(store),
        "stale_days": cabinet.IMPORT_STALE_DAYS,
        "age_days": round(age, 1) if age is not None else None,
        "needs_import": age is None or age > cabinet.IMPORT_STALE_DAYS,
        "batch": None,
        "unmatched": [],
    }
    if batch is not None:
        with store._lock:
            row = store._conn.execute(
                "SELECT report_json, uploaded_at FROM import_batches WHERE id = ?",
                (batch["id"],),
            ).fetchone()
        report = json.loads(row["report_json"] or "{}") if row else {}
        result["batch"] = batch
        result["unmatched"] = report.get("unmatched", [])
    return result
