"""Планировщик ежедневного отчёта администраторам.

Раз в сутки в заданное время (по умолчанию 21:00 МСК) бот сам присылает
администраторам дайджест «слабых мест» — вопросы, на которые он отвечал неуверенно.
Реализовано как фоновая asyncio-задача, без внешних зависимостей.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.conv_report import conversations_digest
from app import insights
from app.config import settings
from app.max_client import get_max

logger = logging.getLogger(__name__)


def _seconds_until_next_run(now: datetime | None = None) -> float:
    tz = timezone(timedelta(hours=settings.DIGEST_TZ_OFFSET))
    now = now or datetime.now(tz)
    target = now.replace(
        hour=settings.DIGEST_HOUR, minute=settings.DIGEST_MINUTE,
        second=0, microsecond=0,
    )
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def send_digest_now() -> int:
    """Отправляет дайджест всем администраторам. Возвращает число доставок."""
    admins = settings.admin_ids
    if not admins:
        logger.info("digest: нет администраторов (ADMIN_MAX_IDS) — пропускаю")
        return 0
    max_client = get_max()
    if not max_client.configured:
        logger.warning("digest: MAX не сконфигурирован — пропускаю")
        return 0
    conv_text = conversations_digest(days=settings.DIGEST_DAYS)
    insights_text = insights.digest(days=settings.DIGEST_DAYS)
    sent = 0
    for admin_id in admins:
        try:
            if await max_client.send_message(admin_id, conv_text):
                sent += 1
            if await max_client.send_message(admin_id, insights_text):
                sent += 1
        except Exception:
            logger.exception("digest: не удалось отправить администратору %s", admin_id)
    logger.info("digest: отправлено %s/%s администраторам", sent, len(admins))
    return sent


async def _loop() -> None:
    while True:
        delay = _seconds_until_next_run()
        logger.info("digest: следующий отчёт через %.0f мин", delay / 60)
        await asyncio.sleep(delay)
        try:
            await send_digest_now()
        except Exception:
            logger.exception("digest: ошибка при отправке отчёта")
        # небольшой отступ, чтобы не сработать дважды в ту же минуту
        await asyncio.sleep(60)


def start() -> asyncio.Task | None:
    """Запускает фоновую задачу планировщика (если включён)."""
    if not settings.DIGEST_ENABLED:
        logger.info("digest: ежедневный отчёт выключен (DIGEST_ENABLED=false)")
        return None
    return asyncio.create_task(_loop())
