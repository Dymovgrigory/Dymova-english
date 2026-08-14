"""Сторож доступности: предупредить раньше, чем замолчит бот.

Telegram лежал две недели незамеченным (последний апдейт 27.07.2026), потому
что «бот жив» и «бот отвечает пользователям» — разные вещи, и /health знал
только про первое.
"""
import time

import pytest

from app import watchdog
from app.config import settings


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    watchdog.reset_state()
    monkeypatch.setattr(settings, "WATCHDOG_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "WATCHDOG_FAILURES_BEFORE_ALERT", 2, raising=False)
    monkeypatch.setattr(settings, "WATCHDOG_ALERT_COOLDOWN_MIN", 60, raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "token", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_POLLING", True, raising=False)
    yield
    watchdog.reset_state()


class FakeMax:
    def __init__(self):
        self.sent = []

    async def send_message(self, user_id, text, buttons=None):
        self.sent.append({"user_id": user_id, "text": text})
        return True


def _patch_alerts(monkeypatch, max_client):
    monkeypatch.setattr(settings, "ADMIN_MAX_IDS", "111", raising=False)
    monkeypatch.setattr(watchdog, "get_max", lambda: max_client)

    async def no_slack(text):
        return None

    monkeypatch.setattr(watchdog, "notify_slack", no_slack)


def _patch_probe(monkeypatch, ok, reachable_ips=()):
    async def fake_check():
        return watchdog.CheckResult(ok=ok, detail="getMe 200" if ok else "ConnectError")

    async def fake_probe():
        return list(reachable_ips)

    monkeypatch.setattr(watchdog, "check_telegram_api", fake_check)
    monkeypatch.setattr(watchdog, "probe_telegram_ips", fake_probe)


# --- пороги и антиспам -----------------------------------------------------


@pytest.mark.asyncio
async def test_single_failure_does_not_alert(monkeypatch):
    """Одна сетевая осечка — не повод будить администратора."""
    max_client = FakeMax()
    _patch_alerts(monkeypatch, max_client)
    _patch_probe(monkeypatch, ok=False)

    await watchdog.run_check_once()

    assert max_client.sent == []


@pytest.mark.asyncio
async def test_alert_after_threshold_failures(monkeypatch):
    max_client = FakeMax()
    _patch_alerts(monkeypatch, max_client)
    _patch_probe(monkeypatch, ok=False)

    await watchdog.run_check_once()
    await watchdog.run_check_once()

    assert len(max_client.sent) == 1
    text = max_client.sent[0]["text"]
    assert "Telegram" in text
    assert max_client.sent[0]["user_id"] == "111"


@pytest.mark.asyncio
async def test_alert_is_not_repeated_within_cooldown(monkeypatch):
    """Сторож не должен превращаться в спам каждые пять минут."""
    max_client = FakeMax()
    _patch_alerts(monkeypatch, max_client)
    _patch_probe(monkeypatch, ok=False)

    for _ in range(6):
        await watchdog.run_check_once()

    assert len(max_client.sent) == 1


@pytest.mark.asyncio
async def test_recovery_is_reported(monkeypatch):
    max_client = FakeMax()
    _patch_alerts(monkeypatch, max_client)
    _patch_probe(monkeypatch, ok=False)
    await watchdog.run_check_once()
    await watchdog.run_check_once()

    _patch_probe(monkeypatch, ok=True)
    await watchdog.run_check_once()

    assert len(max_client.sent) == 2
    assert "снова" in max_client.sent[1]["text"].lower()


@pytest.mark.asyncio
async def test_alert_names_a_working_ip_to_switch_to(monkeypatch):
    """Главная ценность: не «всё плохо», а «поставь вот этот адрес»."""
    max_client = FakeMax()
    _patch_alerts(monkeypatch, max_client)
    _patch_probe(monkeypatch, ok=False, reachable_ips=["149.154.167.220"])

    await watchdog.run_check_once()
    await watchdog.run_check_once()

    assert "149.154.167.220" in max_client.sent[0]["text"]


@pytest.mark.asyncio
async def test_alert_says_proxy_is_needed_when_no_ip_reachable(monkeypatch):
    max_client = FakeMax()
    _patch_alerts(monkeypatch, max_client)
    _patch_probe(monkeypatch, ok=False, reachable_ips=[])

    await watchdog.run_check_once()
    await watchdog.run_check_once()

    assert "прокси" in max_client.sent[0]["text"].lower()


# --- молчание поллинга -----------------------------------------------------


@pytest.mark.asyncio
async def test_silent_polling_raises_alarm(monkeypatch):
    """API отвечает, но цикл long-polling встал — ровно тот баг с offset."""
    max_client = FakeMax()
    _patch_alerts(monkeypatch, max_client)
    _patch_probe(monkeypatch, ok=True)
    monkeypatch.setattr(settings, "WATCHDOG_POLL_SILENCE_MIN", 5, raising=False)

    watchdog.record_poll_ok()
    watchdog._state.last_poll_ok = time.time() - 20 * 60

    await watchdog.run_check_once()
    await watchdog.run_check_once()

    assert len(max_client.sent) == 1
    assert "опрос" in max_client.sent[0]["text"].lower()


@pytest.mark.asyncio
async def test_fresh_polling_is_not_reported(monkeypatch):
    max_client = FakeMax()
    _patch_alerts(monkeypatch, max_client)
    _patch_probe(monkeypatch, ok=True)

    watchdog.record_poll_ok()
    await watchdog.run_check_once()
    await watchdog.run_check_once()

    assert max_client.sent == []


# --- отчёт о состоянии -----------------------------------------------------


@pytest.mark.asyncio
async def test_status_is_exposed_for_health(monkeypatch):
    max_client = FakeMax()
    _patch_alerts(monkeypatch, max_client)
    _patch_probe(monkeypatch, ok=True)
    watchdog.record_poll_ok()

    await watchdog.run_check_once()
    status = watchdog.status()

    assert status["telegram_api_ok"] is True
    assert status["consecutive_failures"] == 0
    assert status["seconds_since_poll"] is not None
    assert status["seconds_since_poll"] < 60


@pytest.mark.asyncio
async def test_disabled_watchdog_does_nothing(monkeypatch):
    max_client = FakeMax()
    _patch_alerts(monkeypatch, max_client)
    _patch_probe(monkeypatch, ok=False)
    monkeypatch.setattr(settings, "WATCHDOG_ENABLED", False, raising=False)

    await watchdog.run_check_once()
    await watchdog.run_check_once()

    assert max_client.sent == []


@pytest.mark.asyncio
async def test_watchdog_never_raises(monkeypatch):
    """Сторож не имеет права уронить процесс, который он охраняет."""
    max_client = FakeMax()
    _patch_alerts(monkeypatch, max_client)

    async def broken_check():
        raise RuntimeError("boom")

    async def no_probe():
        return []

    monkeypatch.setattr(watchdog, "check_telegram_api", broken_check)
    # Проба адресов ходит в сеть — в тестах она не нужна.
    monkeypatch.setattr(watchdog, "probe_telegram_ips", no_probe)

    await watchdog.run_check_once()
    await watchdog.run_check_once()

    assert watchdog.status()["telegram_api_ok"] is False
