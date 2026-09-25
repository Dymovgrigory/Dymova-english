"""Alert Center: уровни, детекторы, retry вебхука."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.platform import bb_store


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("app.config.settings.BIGBEN_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.DIGEST_ENABLED", False)
    monkeypatch.setattr("app.config.settings.NUDGE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.SITE_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.WATCHDOG_ENABLED", False)
    monkeypatch.setattr("app.config.settings.TELEGRAM_POLLING", False)
    monkeypatch.setattr("app.config.settings.ADMIN_TOKEN", "admintoken")
    monkeypatch.setattr("app.config.settings.BIGBEN_PUBLIC_API_KEY", "bb_key")
    monkeypatch.setattr("app.config.settings.BIGBEN_WEBHOOK_SECRET", "")
    bb_store._local.conn = None
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_alerts_requires_auth(client):
    assert client.get("/admin/api/platform/alerts").status_code == 401


def test_alerts_detects_empty_and_unconfigured(client):
    r = client.get("/admin/api/platform/alerts",
                   headers={"X-Admin-Token": "admintoken"})
    assert r.status_code == 200
    codes = [a["code"] for a in r.json()["alerts"]]
    assert "webhook_not_configured" in codes
    assert any(c.startswith("sync_empty_") for c in codes)
    assert "payments_disabled" in codes


def test_alerts_quiet_when_fresh(client):
    bb_store.upsert_filial({"id": 1, "caption": "F", "city": "", "address": "", "active": True})
    bb_store.upsert_group({"id": 1, "caption": "G", "capacity": 8, "occupied": 1,
                           "free_slots": 7, "overbooked": False,
                           "filial": {"id": 1, "caption": "F"}, "auditory": {}, "schedule": []})
    bb_store.upsert_lesson({"id": 1, "date": "2030-01-01", "starts_at": None, "ends_at": None,
                            "group": {"id": 1, "caption": "G"},
                            "filial": {"id": 1, "caption": "F"}})
    bb_store.upsert_student({"id": 1, "fio": "S", "phone": "", "email": "", "balance_kopecks": 0})
    bb_store.upsert_payment({"id": 1, "student_id": 1, "student_fio": "S", "group_id": 1,
                             "amount_kopecks": 100, "paid_at": "2030-01-01"})
    r = client.get("/admin/api/platform/alerts",
                   headers={"X-Admin-Token": "admintoken"})
    codes = [a["code"] for a in r.json()["alerts"]]
    assert not any(c.startswith("sync_empty_") or c.startswith("sync_stale_") for c in codes)
    critical = [a for a in r.json()["alerts"] if a["level"] == "critical"]
    assert critical == []


from unittest.mock import AsyncMock, patch

from app.platform import sync as sync_module


def test_check_schedule_freshness_true_when_recent(monkeypatch):
    from datetime import datetime, timezone
    recent = datetime.now(timezone.utc).isoformat()
    with patch("app.platform.bb_store.freshness",
              return_value={"lessons": {"count": 10, "last_synced_at": recent},
                            "groups": {"count": 5, "last_synced_at": recent}}):
        assert sync_module.check_schedule_freshness(max_age_min=60) is True


def test_check_schedule_freshness_false_and_alerts_when_stale(monkeypatch):
    from datetime import datetime, timedelta, timezone
    stale = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    sync_module._last_stale_alert_at = 0.0
    with patch("app.platform.bb_store.freshness",
              return_value={"lessons": {"count": 10, "last_synced_at": stale},
                            "groups": {"count": 5, "last_synced_at": stale}}), \
         patch("app.platform.sync.run_all", new=AsyncMock()) as run_all, \
         patch("app.watchdog._alert", new=AsyncMock()) as alert:
        import asyncio
        result = asyncio.run(sync_module.check_schedule_freshness_and_alert(max_age_min=60))
        assert result is False
        # Внеплановая синхронизация пробуется ДО оповещения — раз данные
        # всё равно остались несвежими (bb_store.freshness замокан статично),
        # проверяем только сам факт попытки и что после неё пришло письмо.
        run_all.assert_called_once_with("incremental")
        alert.assert_called_once()
        assert "расписан" in alert.call_args.args[0].lower()


def test_check_schedule_freshness_no_data_at_all_counts_as_stale():
    with patch("app.platform.bb_store.freshness",
              return_value={"lessons": {"count": 0, "last_synced_at": None},
                            "groups": {"count": 0, "last_synced_at": None}}):
        assert sync_module.check_schedule_freshness(max_age_min=60) is False


def test_stale_alert_has_cooldown_no_double_alert(monkeypatch):
    from datetime import datetime, timedelta, timezone
    stale = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    sync_module._last_stale_alert_at = 0.0
    with patch("app.platform.bb_store.freshness",
              return_value={"lessons": {"count": 10, "last_synced_at": stale},
                            "groups": {"count": 5, "last_synced_at": stale}}), \
         patch("app.platform.sync.run_all", new=AsyncMock()), \
         patch("app.watchdog._alert", new=AsyncMock()) as alert:
        import asyncio
        asyncio.run(sync_module.check_schedule_freshness_and_alert(max_age_min=60))
        asyncio.run(sync_module.check_schedule_freshness_and_alert(max_age_min=60))
        assert alert.call_count == 1


def test_freshness_restored_after_unplanned_sync_skips_alert(monkeypatch):
    """Внеплановая run_all() иногда чинит дело сама — тогда предупреждение
    не нужно вовсе."""
    from datetime import datetime, timedelta, timezone
    stale = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    fresh = datetime.now(timezone.utc).isoformat()
    sync_module._last_stale_alert_at = 0.0
    responses = iter([
        {"lessons": {"count": 10, "last_synced_at": stale}, "groups": {"count": 5, "last_synced_at": stale}},
        {"lessons": {"count": 10, "last_synced_at": fresh}, "groups": {"count": 5, "last_synced_at": fresh}},
    ])
    with patch("app.platform.bb_store.freshness", side_effect=lambda: next(responses)), \
         patch("app.platform.sync.run_all", new=AsyncMock()) as run_all, \
         patch("app.watchdog._alert", new=AsyncMock()) as alert:
        import asyncio
        result = asyncio.run(sync_module.check_schedule_freshness_and_alert(max_age_min=60))
        assert result is True
        run_all.assert_called_once_with("incremental")
        alert.assert_not_called()
