"""Время ученика: сутки считаем по Москве, хранение — UTC ISO."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3))


def now() -> datetime:
    return datetime.now(timezone.utc)


def local_day(moment: datetime) -> str:
    return moment.astimezone(MSK).strftime("%Y-%m-%d")


def add_days(day: str, days: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()


def to_iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def from_iso(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
