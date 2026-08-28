"""Sync engine BigBen → read-model.

Режимы:
- full: полная выгрузка (первый запуск и периодическая сверка);
- incremental: updated_since от момента предыдущего успешного прогона.

Каждый прогон фиксируется в sync_runs (duration/processed/failed/status) —
это основа мониторинга интеграции. Ошибка синхронизации одной сущности не
отменяет остальные: школе важнее свежее расписание, чем отсутствие платежей.

Важно про updated_since (из документации BigBen): у legacy-записей поле
изменения — заглушка, они никогда не попадут в инкремент. Поэтому
инкремент только ДОГОНЯЕТ полную копию, а reconciliation (full) периодически
переписывает всё.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.platform import bb_store
from app.platform.bigben_v2 import BigBenError, get_bigben_v2

logger = logging.getLogger(__name__)

_STATE_KEY_PREFIX = "sync:last_success:"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _last_success(kind: str) -> str | None:
    rows = bb_store._rows(
        "SELECT finished_at FROM sync_runs WHERE kind=? AND status='ok'"
        " ORDER BY id DESC LIMIT 1", (kind,))
    return rows[0]["finished_at"] if rows else None


async def sync_filials() -> int:
    client = get_bigben_v2()
    items = await client.filials()
    for it in items:
        await asyncio.to_thread(bb_store.upsert_filial, it)
    return len(items)


async def sync_groups(updated_since: str | None = None) -> int:
    client = get_bigben_v2()
    items = await client.groups(updated_since=updated_since)
    for it in items:
        await asyncio.to_thread(bb_store.upsert_group, it)
    return len(items)


async def sync_lessons(updated_since: str | None = None) -> int:
    client = get_bigben_v2()
    today = datetime.now(timezone.utc).date()
    date_to = (today + timedelta(days=settings.BIGBEN_LESSONS_WINDOW_DAYS)).isoformat()
    items = await client.lessons(today.isoformat(), date_to, updated_since=updated_since)
    for it in items:
        await asyncio.to_thread(bb_store.upsert_lesson, it)
    return len(items)


async def sync_students(updated_since: str | None = None) -> int:
    client = get_bigben_v2()
    items = await client.students(updated_since=updated_since)
    for it in items:
        await asyncio.to_thread(bb_store.upsert_student, it)
    return len(items)


async def sync_payments() -> int:
    client = get_bigben_v2()
    today = datetime.now(timezone.utc).date()
    date_from = (today - timedelta(days=92)).isoformat()
    items = await client.payments(date_from=date_from, date_to=today.isoformat())
    for it in items:
        await asyncio.to_thread(bb_store.upsert_payment, it)
    return len(items)


_KINDS = {
    "filials": sync_filials,
    "groups": sync_groups,
    "lessons": sync_lessons,
    "students": sync_students,
    "payments": sync_payments,
}
_INCREMENTAL_KINDS = ("groups", "lessons", "students")


async def run_sync(kind: str, mode: str) -> dict:
    """Один прогон синхронизации сущности. Возвращает статистику."""
    run_id = await asyncio.to_thread(bb_store.sync_run_start, kind, mode)
    processed, failed, error = 0, 0, ""
    try:
        fn = _KINDS[kind]
        if mode == "incremental" and kind in _INCREMENTAL_KINDS:
            processed = await fn(updated_since=_last_success(kind))
        elif mode == "incremental":
            processed = await fn()
        else:
            processed = await fn() if kind not in _INCREMENTAL_KINDS else await fn(None)
        status = "ok"
    except BigBenError as exc:
        failed, error, status = 1, f"{exc.code}: {exc}", "failed"
        logger.warning("sync %s: %s", kind, error)
    except Exception as exc:
        failed, error, status = 1, repr(exc), "failed"
        logger.exception("sync %s: неожиданная ошибка", kind)
    await asyncio.to_thread(
        bb_store.sync_run_finish, run_id,
        status=status, processed=processed, failed=failed, error=error)
    return {"kind": kind, "mode": mode, "status": status,
            "processed": processed, "failed": failed, "error": error}


async def run_all(mode: str) -> list[dict]:
    results = []
    for kind in _KINDS:
        results.append(await run_sync(kind, mode))
    ok = sum(1 for r in results if r["status"] == "ok")
    logger.info("sync %s: %d/%d сущностей ок, %s",
                mode, ok, len(results),
                {r["kind"]: r["processed"] for r in results})
    return results


def configured() -> bool:
    return bool(settings.BIGBEN_PUBLIC_API_KEY and settings.BIGBEN_PUBLIC_API_BASE)


async def _incremental_loop() -> None:
    # стартовая полная выгрузка, если read-model пуста
    fresh = await asyncio.to_thread(bb_store.freshness)
    if fresh["groups"]["count"] == 0:
        logger.info("sync: read-model пуста — стартовая полная выгрузка")
        await run_all("full")
    while True:
        await asyncio.sleep(max(1, settings.BIGBEN_SYNC_INTERVAL_MIN) * 60)
        try:
            await run_all("incremental")
        except Exception:
            logger.exception("sync: ошибка инкрементального цикла")


async def _full_loop() -> None:
    while True:
        await asyncio.sleep(max(1, settings.BIGBEN_FULL_SYNC_HOURS) * 3600)
        try:
            await run_all("full")
        except Exception:
            logger.exception("sync: ошибка полной сверки")


def start() -> list[asyncio.Task]:
    """Фоновые задачи синхронизации (вызывается из scheduler.start())."""
    if not settings.BIGBEN_SYNC_ENABLED:
        logger.info("sync: выключен (BIGBEN_SYNC_ENABLED=false)")
        return []
    if not configured():
        logger.warning("sync: нет BIGBEN_PUBLIC_API_KEY — синхронизация не запущена")
        return []
    return [asyncio.create_task(_incremental_loop()), asyncio.create_task(_full_loop())]
