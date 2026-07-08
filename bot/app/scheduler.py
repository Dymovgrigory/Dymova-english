"""Планировщик фоновых задач: ежедневный отчёт и тёплые напоминания.

Задачи:
1. Дайджест администраторам (по умолчанию 21:00 МСК)
2. Тёплые напоминания (nudge) для незавершённых заявок (по умолчанию 11:00 МСК)

Реализовано как фоновые asyncio-задачи, без внешних зависимостей.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.conv_report import conversations_digest
from app import insights
from app import nudge as nudge_mod
from app.config import settings
from app.knowledge import site_sync
from app.max_client import get_max

logger = logging.getLogger(__name__)


def _seconds_until(hour: int, minute: int, now: datetime | None = None) -> float:
    tz = timezone(timedelta(hours=settings.DIGEST_TZ_OFFSET))
    now = now or datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _seconds_until_next_run(now: datetime | None = None) -> float:
    return _seconds_until(settings.DIGEST_HOUR, settings.DIGEST_MINUTE, now)


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


async def _nudge_loop() -> None:
    while True:
        delay = _seconds_until(settings.NUDGE_HOUR, settings.NUDGE_MINUTE)
        logger.info("nudge: следующая проверка через %.0f мин", delay / 60)
        await asyncio.sleep(delay)
        try:
            stats = await nudge_mod.run_nudges()
            # Notify admins about nudge results if any were sent
            if stats["sent"] > 0:
                max_client = get_max()
                for admin_id in settings.admin_ids:
                    try:
                        await max_client.send_message(
                            admin_id,
                            f"\U0001f514 Тёплые напоминания: отправлено {stats['sent']}, "
                            f"не удалось {stats['failed']}, "
                            f"всего подходило {stats['eligible']}.",
                        )
                    except Exception:
                        logger.exception("nudge: failed to notify admin %s", admin_id)
        except Exception:
            logger.exception("nudge: ошибка при отправке напоминаний")
        await asyncio.sleep(60)


async def _site_sync_loop() -> None:
    while True:
        try:
            await site_sync.sync_once()
        except Exception:
            logger.exception("site_sync: ошибка синхронизации с сайтом")
        await asyncio.sleep(max(5, settings.SITE_SYNC_INTERVAL_MIN) * 60)


def start() -> list[asyncio.Task]:
    """Запускает фоновые задачи (отчёт + напоминания)."""
    tasks: list[asyncio.Task] = []
    if settings.DIGEST_ENABLED:
        tasks.append(asyncio.create_task(_loop()))
    else:
        logger.info("digest: ежедневный отчёт выключен (DIGEST_ENABLED=false)")
    if settings.NUDGE_ENABLED:
        tasks.append(asyncio.create_task(_nudge_loop()))
    else:
        logger.info("nudge: тёплые напоминания выключены (NUDGE_ENABLED=false)")
    if settings.SITE_SYNC_ENABLED:
        tasks.append(asyncio.create_task(_site_sync_loop()))
    else:
        logger.info("site_sync: синхронизация с сайтом выключена (SITE_SYNC_ENABLED=false)")
    return tasks
