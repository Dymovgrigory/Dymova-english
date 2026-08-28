"""Т-Банк провайдер: подпись, вебхук CONFIRMED/REJECTED, идемпотентность."""
from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.platform import bb_store, billing

KEY, PWD = "1726756291526", "test_password_123"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("app.config.settings.BIGBEN_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.DIGEST_ENABLED", False)
    monkeypatch.setattr("app.config.settings.NUDGE_ENABLED", False)
    monkeypatch.setattr("app.config.settings.SITE_SYNC_ENABLED", False)
    monkeypatch.setattr("app.config.settings.WATCHDOG_ENABLED", False)
    monkeypatch.setattr("app.config.settings.TELEGRAM_POLLING", False)
    monkeypatch.setattr("app.config.settings.BILLING_PROVIDER", "tbank")
    monkeypatch.setattr("app.config.settings.TBANK_ENABLED", True)
    monkeypatch.setattr("app.config.settings.TBANK_TERMINAL_KEY", KEY)
    monkeypatch.setattr("app.config.settings.TBANK_PASSWORD", PWD)
    bb_store._local.conn = None
    from app.main import app
    with TestClient(app) as c:
        yield c


def _token(params: dict) -> str:
    pairs = sorted((k, str(v)) for k, v in params.items()
                   if k != "Token" and not isinstance(v, (dict, list)))
    return hashlib.sha256(("".join(v for _, v in pairs) + PWD).encode()).hexdigest()


def _invoice() -> str:
    p = billing.get_provider()
    return p.create_invoice_local(amount_kopecks=650000, phone="79251112233")


def _notify(client, invoice_id, status="CONFIRMED", amount=650000, token_ok=True):
    data = {"TerminalKey": KEY, "OrderId": invoice_id, "Success": True,
            "Status": status, "PaymentId": 998877, "Amount": amount}
    data["Token"] = _token(data) if token_ok else "deadbeef"
    return client.post("/api/webhooks/tbank", json=data)


def test_confirmed_marks_paid_idempotent(client):
    inv = _invoice()
    r = _notify(client, inv)
    assert r.status_code == 200
    row = billing.get_payment(inv)
    assert row["status"] == "paid"
    assert row["transaction_id"] == "998877"
    # повторная нотификация — не дублирует
    r2 = _notify(client, inv)
    assert r2.status_code == 200
    assert billing.get_payment(inv)["status"] == "paid"


def test_bad_token_rejected(client):
    inv = _invoice()
    assert _notify(client, inv, token_ok=False).status_code == 401
    assert billing.get_payment(inv)["status"] == "created"


def test_amount_mismatch_rejected(client):
    inv = _invoice()
    assert _notify(client, inv, amount=100).status_code == 400
    assert billing.get_payment(inv)["status"] == "created"


def test_rejected_marks_failed(client):
    inv = _invoice()
    assert _notify(client, inv, status="REJECTED").status_code == 200
    assert billing.get_payment(inv)["status"] == "failed"


def test_unknown_order_404(client):
    assert _notify(client, "no-such-invoice").status_code == 404


def test_token_algorithm_official_example():
    """Вектор из доки Т-Банка: сортировка по ключу + пароль в конце."""
    params = {"Amount": 140000, "OrderId": "21090", "Description": "Подарок",
              "TerminalKey": "TinkoffBankTest"}
    raw = "140000Подарок21090TinkoffBankTest" + "TinkoffBankTest"
    expected = hashlib.sha256(raw.encode()).hexdigest()
    import app.config as cfg
    old = cfg.settings.TBANK_PASSWORD
    cfg.settings.TBANK_PASSWORD = "TinkoffBankTest"
    try:
        assert billing.TBankProvider._token(params) == expected
    finally:
        cfg.settings.TBANK_PASSWORD = old
