"""Автосинхронизация метаданных групп из внутреннего API пульта владельца.

Публичный API v1 не отдаёт педагога, период, абонемент и цену мероприятия —
догружаем из пульта (BIGBEN_INTERNAL_TOKEN) в overlay bb_group_meta.
Запускается планировщиком каждые GROUP_META_SYNC_INTERVAL_MIN минут,
чтобы сайт и боты всегда показывали актуальных педагогов/периоды/цены.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.platform import bb_store

logger = logging.getLogger(__name__)

API = "https://platformapi.bigbencrm.ru/public/api/groups"
# all+events_mode — чтобы попали мероприятия (for_events=1), их нет
# в выдаче current/future.
LIST_PARAMS = [
    {"status": "current"}, {"status": "future"},
    {"status": "all", "events_mode": "true"},
]


def _date(iso: str) -> str:
    return (iso or "")[:10]


async def sync_group_meta() -> int:
    """Полный проход импорта. Возвращает число обновлённых групп."""
    token = (settings.BIGBEN_INTERNAL_TOKEN or "").strip()
    if not token:
        logger.warning("group_meta: BIGBEN_INTERNAL_TOKEN не задан — пропуск")
        return 0
    total = 0
    async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}, timeout=30) as c:
        for params in LIST_PARAMS:
            resp = await c.get(API, params={
                **params, "sort_by": "caption", "sort_order": "asc",
                "page": 1, "per_page": 500})
            resp.raise_for_status()
            payload = resp.json()
            if not payload.get("success"):
                logger.error("group_meta: API ошибка: %s", str(payload)[:200])
                continue
            for g in payload.get("data", []):
                teacher = ((g.get("teacher") or {}).get("fio") or "").strip()
                monthly = g.get("monthly_payment")
                cpe = g.get("cost_per_event")
                if g.get("for_events") and cpe is None:
                    try:  # цена мероприятия — только в детальной карточке
                        d = await c.get(f"{API}/{g['id']}")
                        if d.status_code == 200:
                            cpe = d.json().get("cost_per_event")
                    except httpx.HTTPError:
                        logger.warning("group_meta: карточка %s недоступна", g["id"])
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
    logger.info("group_meta: синхронизировано групп: %s", total)
    return total
