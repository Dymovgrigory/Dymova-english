#!/usr/bin/env python3
"""Импорт метаданных групп (педагог, период, абонемент) из внутреннего API
пульта владельца lk.bigbencrm.ru в overlay-таблицу bb_group_meta.

Публичный API v1 этих полей не отдаёт, поэтому используем сессионный токен
владельца (env BIGBEN_INTERNAL_TOKEN). Токен живёт ~30 дней — периодически
обновлять из localStorage пульта (auth_token).

Запуск:
  BIGBEN_INTERNAL_TOKEN="..." python3 scripts/import_group_meta.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from app.platform import bb_store  # noqa: E402

API = "https://platformapi.bigbencrm.ru/public/api/groups"
# all+events_mode — чтобы попали мероприятия (for_events=1), их нет
# в выдаче current/future.
LIST_PARAMS = [
    {"status": "current"}, {"status": "future"},
    {"status": "all", "events_mode": "true"},
]


def _date(iso: str) -> str:
    """'2026-08-03 00:00:00' → '2026-08-03'."""
    return (iso or "")[:10]


def main() -> None:
    token = os.environ.get("BIGBEN_INTERNAL_TOKEN", "").strip()
    if not token:
        raise SystemExit("Задайте BIGBEN_INTERNAL_TOKEN (auth_token из пульта владельца)")
    total = 0
    with httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=30) as c:
        for params in LIST_PARAMS:
            resp = c.get(API, params={
                **params, "sort_by": "caption", "sort_order": "asc",
                "page": 1, "per_page": 500,
            })
            resp.raise_for_status()
            payload = resp.json()
            if not payload.get("success"):
                raise SystemExit(f"API вернул ошибку: {payload}")
            for g in payload.get("data", []):
                teacher = ((g.get("teacher") or {}).get("fio") or "").strip()
                monthly = g.get("monthly_payment")
                cpe = g.get("cost_per_event")
                if g.get("for_events") and cpe is None:
                    # Цена мероприятия — только в детальной карточке.
                    d = c.get(f"{API}/{g['id']}", timeout=30)
                    if d.status_code == 200:
                        cpe = d.json().get("cost_per_event")
                bb_store.upsert_group_meta(
                    g["id"],
                    teacher=teacher,
                    period_start=_date(g.get("timestart", "")),
                    period_end=_date(g.get("timefinish", "")),
                    monthly_payment=int(monthly) if monthly else None,
                    for_events=bool(g.get("for_events")),
                    cost_per_event=int(cpe) if cpe else None,
                    title=(g.get("caption") or "").strip())
                total += 1
    print(f"Импортировано метаданных групп: {total}")


if __name__ == "__main__":
    main()
