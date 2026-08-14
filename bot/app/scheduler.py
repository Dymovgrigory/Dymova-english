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
from app import watchdog

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


async def _purge_loop() -> None:
    """Раз в сутки чистит журнал обработанных событий.

    Единственная таблица, которая росла без ограничений: записи нужны на
    минуты (защита от повторного вебхука), а лежали вечно.
    """
    from app.memory import get_store

    while True:
        try:
            removed = await asyncio.to_thread(get_store().purge_old_events)
            if removed:
                logger.info("purge: удалено старых событий: %d", removed)
        except Exception:
            logger.exception("purge: не удалось почистить журнал событий")
        await asyncio.sleep(24 * 60 * 60)


async def _site_sync_loop() -> None:
    while True:
        try:
            await site_sync.sync_once()
        except Exception:
            logger.exception("site_sync: ошибка синхронизации с сайтом")
        await asyncio.sleep(max(5, settings.SITE_SYNC_INTERVAL_MIN) * 60)


async def _sources_sync_loop() -> None:
    """Синхронизация внешних источников (VK, Яндекс.Карты, Telegram)."""
    from app.knowledge import sources
    from app.sources_config import sources_settings

    while True:
        try:
            if sources_settings.SOURCES_SYNC_ENABLED:
                await sources.sync_sources()
                site_sync.refresh_live_documents()
        except Exception:
            logger.exception("sources: ошибка синхронизации внешних источников")
        await asyncio.sleep(max(5, settings.SITE_SYNC_INTERVAL_MIN) * 60)


def import_reminder_text(age_days: float | None) -> str | None:
    """Текст напоминания о выгрузке. None — напоминать не нужно."""
    from app import cabinet

    if age_days is None:
        return (
            "📅 Расписание в личном кабинете ещё ни разу не загружали. "
            "Загрузите выгрузку в админке бота (вкладка «Расписание»), "
            "и у учеников появятся их занятия."
        )
    if age_days > cabinet.IMPORT_STALE_DAYS:
        return (
            f"📅 Выгрузке расписания уже {int(age_days)} дн. — кабинет "
            "показывает ученикам устаревшие данные. Загрузите свежий "
            "файл в админке бота (вкладка «Расписание»)."
        )
    return None


async def _import_reminder_loop() -> None:
    """Напоминает администраторам о протухшей выгрузке расписания.

    Еженедельная выгрузка — единственный источник расписания в кабинете, и
    про неё легко забыть. Если импорта не было дольше девяти дней, раз в
    сутки шлём напоминание в чат администратора.
    """
    from app import cabinet
    from app.memory import get_store

    while True:
        try:
            store = get_store()
            age = await asyncio.to_thread(cabinet.import_age_days, store)
            text = import_reminder_text(age)
            if text:
                max_client = get_max()
                if max_client.configured and settings.admin_ids:
                    for admin_id in settings.admin_ids:
                        try:
                            await max_client.send_message(admin_id, text)
                        except Exception:
                            logger.exception("import-reminder: не удалось написать администратору")
        except Exception:
            logger.exception("import-reminder: ошибка проверки свежести выгрузки")
        await asyncio.sleep(24 * 60 * 60)


def start() -> list[asyncio.Task]:
    """Запускает фоновые задачи (отчёт + напоминания)."""
    tasks: list[asyncio.Task] = [asyncio.create_task(_purge_loop())]
    tasks.append(asyncio.create_task(_import_reminder_loop()))
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
        tasks.append(asyncio.create_task(_sources_sync_loop()))
    else:
        logger.info("site_sync: синхронизация с сайтом выключена (SITE_SYNC_ENABLED=false)")
    if settings.WATCHDOG_ENABLED:
        tasks.append(asyncio.create_task(watchdog.loop()))
    else:
        logger.info("watchdog: сторож доступности выключен (WATCHDOG_ENABLED=false)")
    return tasks
