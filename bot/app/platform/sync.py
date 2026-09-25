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
import time
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


_STALE_ALERT_COOLDOWN_SEC = 3600  # не чаще раза в час — гейтит и внеплановую
# синхронизацию, и оповещение вместе, иначе при долгом сбое BigBen внеплановая
# попытка дублировала бы обычный запрос на каждом тике (каждые 15 мин)
_last_stale_alert_at: float = 0.0


def _minutes_since(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 60


def check_schedule_freshness(max_age_min: int | None = None) -> bool:
    """True — данные о группах и уроках свежие. Отсутствие данных вовсе
    (last_synced_at=None) тоже считается несвежим: значит синхронизация
    ещё ни разу не прошла успешно."""
    limit = max_age_min if max_age_min is not None else max(15, settings.BIGBEN_SYNC_INTERVAL_MIN) * 4
    fresh = bb_store.freshness()
    for kind in ("groups", "lessons"):
        age = _minutes_since(fresh.get(kind, {}).get("last_synced_at"))
        if age is None or age > limit:
            return False
    return True


async def check_schedule_freshness_and_alert(max_age_min: int | None = None) -> bool:
    """Как check_schedule_freshness, но при устаревании — не чаще раза в
    _STALE_ALERT_COOLDOWN_SEC — пробует внеплановую синхронизацию прямо
    сейчас и, если это не помогло, оповещает администраторов. Между
    окнами cooldown просто молчит и ждёт обычный цикл: иначе при затяжном
    сбое BigBen внеплановая попытка дублировала бы обычный запрос каждые
    15 минут, удваивая нагрузку на и так недоступный сервис."""
    global _last_stale_alert_at
    if check_schedule_freshness(max_age_min):
        return True
    now = time.monotonic()
    if now - _last_stale_alert_at < _STALE_ALERT_COOLDOWN_SEC:
        return False
    _last_stale_alert_at = now
    await run_all("incremental")
    if check_schedule_freshness(max_age_min):
        return True
    from app import watchdog

    limit = max_age_min if max_age_min is not None else max(15, settings.BIGBEN_SYNC_INTERVAL_MIN) * 4
    await watchdog._alert(
        f"🚨 Расписание не обновлялось дольше {limit} мин, внеплановая "
        "синхронизация не помогла — BigBen мог стать недоступен. "
        "Проверьте /admin/insights и логи бота."
    )
    return False


async def _incremental_loop() -> None:
    # стартовая полная выгрузка, если read-model пуста
    fresh = await asyncio.to_thread(bb_store.freshness)
    last_full = time.monotonic()
    if fresh["groups"]["count"] == 0:
        logger.info("sync: read-model пуста — стартовая полная выгрузка")
        await run_all("full")
        last_full = time.monotonic()
    while True:
        await asyncio.sleep(max(1, settings.BIGBEN_SYNC_INTERVAL_MIN) * 60)
        try:
            # Периодическая полная выгрузка: страховка от изменений в CRM,
            # которые не двигают updated_at (записи учеников, участники
            # мероприятий и т.п.) — read-model не должна расходиться с CRM.
            full_every = max(30, settings.BIGBEN_FULL_SYNC_INTERVAL_MIN) * 60
            if time.monotonic() - last_full >= full_every:
                await run_all("full")
                last_full = time.monotonic()
            else:
                await run_all("incremental")
            await check_schedule_freshness_and_alert()
        except Exception:
            logger.exception("sync: ошибка цикла синхронизации")


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
