"""Сила атома контента (слово, фраза, пункт грамматики) и срок его повторения.

Лейтнер 0–5 с интервалами из `app.world.srs`. Верный ответ поднимает силу и
отодвигает срок, ошибка опускает силу и возвращает атом на повтор сегодня.
Даты сроков — московские дни `YYYY-MM-DD`, сравниваются строками.
"""
from __future__ import annotations

from datetime import datetime

from app.world.db import get_conn
from app.world.srs import INTERVALS_DAYS, MAX_STRENGTH

from . import clock


def record(player_id: int, atom_id: str, *, correct: bool, now: datetime | None = None) -> int:
    moment = now or clock.now()
    today = clock.local_day(moment)
    conn = get_conn()
    row = conn.execute(
        "SELECT strength FROM atom_mastery WHERE player_id=? AND atom_id=?", (player_id, atom_id)
    ).fetchone()
    old = int(row["strength"]) if row else 0
    strength = min(MAX_STRENGTH, old + 1) if correct else max(0, old - 1)
    due = clock.add_days(today, INTERVALS_DAYS[strength]) if correct else today
    conn.execute(
        "INSERT INTO atom_mastery (player_id, atom_id, strength, correct_count, wrong_count, due_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(player_id, atom_id) DO UPDATE SET"
        " strength=excluded.strength,"
        " correct_count=atom_mastery.correct_count+excluded.correct_count,"
        " wrong_count=atom_mastery.wrong_count+excluded.wrong_count,"
        " due_at=excluded.due_at, updated_at=excluded.updated_at",
        (player_id, atom_id, strength, int(correct), int(not correct), due, clock.to_iso(moment)),
    )
    return strength


def strengths(player_id: int, atom_ids: list[str]) -> dict[str, int]:
    if not atom_ids:
        return {}
    marks = ",".join("?" for _ in atom_ids)
    rows = get_conn().execute(
        f"SELECT atom_id, strength FROM atom_mastery WHERE player_id=? AND atom_id IN ({marks})",
        (player_id, *atom_ids),
    ).fetchall()
    return {r["atom_id"]: int(r["strength"]) for r in rows}


def due_atoms(
    player_id: int, *, limit: int, exclude: set[str] | frozenset[str] = frozenset(), now: datetime | None = None
) -> list[str]:
    today = clock.local_day(now or clock.now())
    rows = get_conn().execute(
        "SELECT atom_id FROM atom_mastery WHERE player_id=? AND due_at<=?"
        " ORDER BY strength ASC, due_at ASC, updated_at ASC",
        (player_id, today),
    ).fetchall()
    return [r["atom_id"] for r in rows if r["atom_id"] not in exclude][:limit]


def weakest(player_id: int, atom_ids: list[str], limit: int) -> list[str]:
    known = strengths(player_id, atom_ids)
    return sorted(atom_ids, key=lambda atom_id: known.get(atom_id, 0))[:limit]


def weakest_seen(player_id: int, limit: int) -> list[str]:
    rows = get_conn().execute(
        "SELECT atom_id FROM atom_mastery WHERE player_id=? ORDER BY strength ASC, updated_at ASC LIMIT ?",
        (player_id, limit),
    ).fetchall()
    return [r["atom_id"] for r in rows]
