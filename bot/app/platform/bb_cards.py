"""Карточки учеников BigBen из внутреннего API пульта.

Публичный API v1 отдаёт ученика без родителя и с одним телефоном. В пульте у
карточки есть имя ребёнка, имя родителя и несколько телефонов с подписями
(«мама Ольга», «папа»), а у братьев и сестёр общий номер. Здесь хранится ровно
то, что нужно для точного сопоставления с клиентом бота и для админки.

Пароли, паспорт и домашний адрес из пульта сознательно НЕ сохраняются.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from app.platform import bb_store

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bb_student_cards (
    id INTEGER PRIMARY KEY,
    card_json TEXT NOT NULL,
    synced_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bb_student_phones (
    student_id INTEGER NOT NULL,
    phone10 TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_bb_student_phones_phone ON bb_student_phones(phone10);
"""


def digits10(phone: str | None) -> str:
    """Последние 10 цифр — так номера сравниваются во всём проекте."""
    return "".join(c for c in (phone or "") if c.isdigit())[-10:]


def _db():
    conn = bb_store._db()
    conn.executescript(_SCHEMA)
    return conn


def _clean_comment(text: str | None) -> str:
    text = (text or "").strip()
    return "" if re.fullmatch(r"[-–—\s]*", text) else text


def _phones(raw: dict) -> list[dict]:
    """Все телефоны карточки без дублей; подпись берём из любого поля, где она есть."""
    sources = (
        ("phone", raw.get("phone_comment")),
        ("main_phone", ""),
        ("phone1", raw.get("phone1_comment")),
        ("parent_phone", "родитель"),
    )
    merged: dict[str, dict] = {}
    for field, comment in sources:
        number = str(raw.get(field) or "").strip()
        key = digits10(number)
        if len(key) < 10:
            continue
        item = merged.setdefault(key, {"phone": number, "comment": ""})
        if not item["comment"]:
            item["comment"] = _clean_comment(comment)
    return list(merged.values())


def from_api(raw: dict) -> dict:
    """Запись внутреннего API → наша карточка (без секретов)."""
    ages = raw.get("ages")
    return {
        "id": int(raw["id"]),
        "fio": (raw.get("fio") or "").strip(),
        "parentname": (raw.get("parentname") or "").strip(),
        "birthday": (raw.get("birthday") or raw.get("birthdate") or "")[:10],
        "age": str(int(ages)) if isinstance(ages, (int, float)) and ages else "",
        "email": (raw.get("email") or "").strip(),
        "filial": ((raw.get("filial") or {}).get("name") or "").strip(),
        "is_active": bool(raw.get("is_active")),
        "archived": bool(raw.get("archived") or raw.get("deleted")),
        "debt_rub": int(raw.get("debt_sum") or 0),
        "balance_rub": int(raw.get("balance_sum_total") or 0),
        "important_comment": (raw.get("important_comment") or "").strip(),
        "reg_date": (raw.get("reg_date") or "")[:10],
        "groups": [
            {"id": g.get("id"), "name": g.get("name") or "",
             "start_date": (g.get("start_date") or "")[:10],
             "timefinish": (g.get("timefinish") or "")[:10] if g.get("timefinish") else "",
             "is_debtor": bool(g.get("is_debtor"))}
            for g in (raw.get("active_groups") or [])
        ],
        "phones": _phones(raw),
    }


def replace_all(cards: list[dict]) -> None:
    """Полная замена справочника (одной транзакцией: сбой не оставит половину)."""
    conn = _db()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("DELETE FROM bb_student_cards")
        conn.execute("DELETE FROM bb_student_phones")
        for card in cards:
            conn.execute(
                "INSERT INTO bb_student_cards(id, card_json, synced_at) VALUES (?,?,?)",
                (card["id"], json.dumps(card, ensure_ascii=False), now),
            )
            for phone in card["phones"]:
                conn.execute(
                    "INSERT INTO bb_student_phones(student_id, phone10, comment) VALUES (?,?,?)",
                    (card["id"], digits10(phone["phone"]), phone["comment"]),
                )


def find_by_phone(phone: str) -> list[dict]:
    """Все ученики, у которых этот номер — любой из телефонов карточки."""
    key = digits10(phone)
    if len(key) < 10:
        return []
    rows = _db().execute(
        "SELECT c.card_json FROM bb_student_cards c WHERE c.id IN"
        " (SELECT student_id FROM bb_student_phones WHERE phone10 = ?) ORDER BY c.id",
        (key,),
    ).fetchall()
    return [json.loads(r["card_json"]) for r in rows]


def get(student_id: int) -> dict | None:
    row = _db().execute(
        "SELECT card_json FROM bb_student_cards WHERE id = ?", (int(student_id),)
    ).fetchone()
    return json.loads(row["card_json"]) if row else None


def count() -> int:
    return _db().execute("SELECT COUNT(*) c FROM bb_student_cards").fetchone()["c"]


def last_synced_at() -> str | None:
    return _db().execute("SELECT MAX(synced_at) m FROM bb_student_cards").fetchone()["m"]
