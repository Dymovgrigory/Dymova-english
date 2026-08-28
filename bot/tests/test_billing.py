"""Billing: подпись CloudPayments, идемпотентность оплаты, вебхуки."""
from __future__ import annotations

import base64
import hashlib
import hmac
import urllib.parse

import pytest
from fastapi.testclient import TestClient

from app import miniapp_auth
from app.platform import bb_store, billing


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("app.config.settings.BIGBEN_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.DIGEST_ENABLED", False)
    monkeypatch.setattr("app.config.settings.NUDGE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.SITE_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.WATCHDOG_ENABLED", False)
    monkeypatch.setattr("app.config.settings.TELEGRAM_POLLING", False)
    monkeypatch.setattr("app.config.settings.CLOUDPAYMENTS_ENABLED", True)
    monkeypatch.setattr("app.config.settings.CLOUDPAYMENTS_PUBLIC_ID", "pk_test")
    monkeypatch.setattr("app.config.settings.CLOUDPAYMENTS_API_SECRET", "cpsecret")
    bb_store._local.conn = None
    identity = miniapp_auth.MiniAppIdentity(user_id="tg:777", platform="telegram")
    monkeypatch.setattr(miniapp_auth, "identify", lambda **kw: identity)
    from app.main import app
    with TestClient(app) as c:
        yield c


def _sig(body: bytes) -> str:
    return base64.b64encode(
        hmac.new(b"cpsecret", body, hashlib.sha256).digest()).decode()


def test_create_invoice_widget_params(env):
    r = env.post("/api/miniapp/account/pay", json={"amount_rub": 1500.50})
    assert r.status_code == 201
    body = r.json()
    assert body["widget"]["publicId"] == "pk_test"
    assert body["widget"]["amount"] == 1500.5
    assert body["widget"]["currency"] == "RUB"
    assert billing.get_payment(body["invoice_id"])["amount_kopecks"] == 150050


def test_pay_webhook_confirms_and_is_idempotent(env):
    r = env.post("/api/miniapp/account/pay", json={"amount_rub": 1000})
    invoice_id = r.json()["invoice_id"]
    form = urllib.parse.urlencode(
        {"InvoiceId": invoice_id, "TransactionId": "tx1", "Amount": "1000.00"}).encode()
    # без подписи — 401
    assert env.post("/api/webhooks/cloudpayments/pay", content=form).status_code == 401
    # check: инвойс существует
    r = env.post("/api/webhooks/cloudpayments/check", content=form,
                 headers={"Content-HMAC-SHA256": _sig(form)})
    assert r.json()["code"] == 0
    # pay: первая доставка — paid
    r = env.post("/api/webhooks/cloudpayments/pay", content=form,
                 headers={"Content-HMAC-SHA256": _sig(form)})
    assert r.json()["code"] == 0
    assert billing.get_payment(invoice_id)["status"] == "paid"
    # повтор — не дублирует
    r = env.post("/api/webhooks/cloudpayments/pay", content=form,
                 headers={"Content-HMAC-SHA256": _sig(form)})
    assert r.json()["code"] == 0
    row = billing.get_payment(invoice_id)
    assert row["status"] == "paid" and row["transaction_id"] == "tx1"


def test_check_rejects_unknown_invoice(env):
    form = urllib.parse.urlencode({"InvoiceId": "nope", "TransactionId": "x"}).encode()
    r = env.post("/api/webhooks/cloudpayments/check", content=form,
                 headers={"Content-HMAC-SHA256": _sig(form)})
    assert r.json()["code"] == 10


def test_pay_disabled_without_config(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("app.config.settings.BIGBEN_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.CLOUDPAYMENTS_ENABLED", False)
    bb_store._local.conn = None
    identity = miniapp_auth.MiniAppIdentity(user_id="tg:1", platform="telegram")
    monkeypatch.setattr(miniapp_auth, "identify", lambda **kw: identity)
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post("/api/miniapp/account/pay", json={"amount_rub": 100})
    assert r.status_code == 503


def test_server_price_overrides_client_amount(env, monkeypatch):
    """SUBSCRIPTION_PRICE_RUB задан — клиентская сумма игнорируется."""
    from app.config import settings
    monkeypatch.setattr(settings, "SUBSCRIPTION_PRICE_RUB", 6900)
    r = env.post("/api/miniapp/account/pay", json={"amount_rub": 1})
    assert r.status_code == 201
    assert r.json()["widget"]["amount"] == 6900.0


def test_amount_required_when_no_server_price_and_no_amount(env):
    r = env.post("/api/miniapp/account/pay", json={})
    assert r.status_code == 400
    assert r.json()["error"] == "amount_required"
