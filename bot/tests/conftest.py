"""Shared fixtures for bot test suite."""
import hashlib
import hmac
import json
import time
import urllib.parse

import pytest

from app import llm
from app import llm_gateway
from app.config import settings


def make_telegram_init_data(
    token: str,
    telegram_user_id: int = 12345,
    first_name: str = "Аня",
    auth_date: int | None = None,
    tamper: bool = False,
) -> str:
    """Собирает подписанный Telegram initData — как его отдаёт настоящий клиент.

    Нужен, чтобы тесты API мини-приложения работали с настоящей подписью, а не
    с доверием к открытому `user_id`.
    """
    fields = {
        "auth_date": str(int(auth_date if auth_date is not None else time.time())),
        "query_id": "AAG_test",
        "user": json.dumps(
            {"id": telegram_user_id, "first_name": first_name, "language_code": "ru"},
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    }
    data_check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if tamper:
        signature = "0" * len(signature)
    return urllib.parse.urlencode({**fields, "hash": signature})


@pytest.fixture(autouse=True)
def _fresh_llm_singletons():
    """Клиент модели и шлюз — синглтоны, кэширующие ключи и адрес провайдера.

    Без сброса тест, подменивший настройки провайдера, оставлял следующим
    «включённый» клиент с недоступным адресом: они честно ходили в сеть и
    ждали ретраев. Сбрасываем до и после — порядок тестов не должен влиять
    ни на их скорость, ни на то, ходит ли тест в сеть вообще.
    """
    _reset_llm()
    yield
    _reset_llm()


def _reset_llm() -> None:
    llm._llm = None
    llm._client = None
    llm._http_client = None
    llm_gateway.reset_gateway()


@pytest.fixture(autouse=True)
def _disable_registration(monkeypatch):
    """Disable registration gate for all tests by default.

    Tests that specifically test registration should override this
    by re-enabling it via monkeypatch.
    """
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", False)
    monkeypatch.setattr(settings, "SITE_SYNC_ENABLED", False)
    # Тесты не должны писать в ./data/bot.db рабочего дерева. В проде DB_PATH
    # persistent (см. memory._resolve_db_path), здесь — явный in-memory.
    monkeypatch.setattr(settings, "DB_PATH", ":memory:")
    monkeypatch.setattr(settings, "STATE_FILE", "")
