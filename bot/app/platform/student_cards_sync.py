"""Синхронизация карточек учеников из внутреннего API пульта (все страницы)."""
from __future__ import annotations

import logging

from app.platform import bb_cards, bigben_internal

logger = logging.getLogger(__name__)

PAGE_SIZE = 100
MAX_PAGES = 200  # защита от бесконечного цикла при кривой пагинации


async def sync_student_cards() -> int:
    """Тянет всех учеников и заменяет справочник. Сбой любой страницы —
    исключение, а старые данные остаются нетронутыми."""
    cards: list[dict] = []
    page, last_page = 1, 1
    while page <= last_page and page <= MAX_PAGES:
        payload = await bigben_internal._request(
            "GET", f"/user/students?per_page={PAGE_SIZE}&page={page}"
        )
        for raw in payload.get("data") or []:
            if raw.get("id"):
                cards.append(bb_cards.from_api(raw))
        last_page = int((payload.get("meta") or {}).get("last_page") or 1)
        page += 1
    if not cards:
        # Пустой ответ при живом токене — скорее сбой, чем «учеников нет».
        raise bigben_internal.BigBenInternalError("внутренний API вернул 0 учеников")
    bb_cards.replace_all(cards)
    logger.info("student_cards: синхронизировано учеников: %s", len(cards))
    return len(cards)
