"""Время ученика: сутки считаем по Москве, хранение — UTC ISO."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3))


def now() -> datetime:
    return datetime.now(timezone.utc)


def local_day(moment: datetime) -> str:
    return moment.astimezone(MSK).strftime("%Y-%m-%d")


def day_start_sql(day: str) -> str:
    """Начало местных суток в том виде, в каком SQLite пишет `created_at` (UTC, без зоны).

    Нужно, чтобы сравнивать ledger-строки с местным днём и не дублировать смещение MSK в SQL.
    """
    start = datetime.fromisoformat(day).replace(tzinfo=MSK)
    return start.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def add_days(day: str, days: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()


def to_iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def from_iso(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
