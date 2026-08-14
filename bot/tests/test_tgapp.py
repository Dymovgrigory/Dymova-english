"""Telegram Mini App: статика, кнопка запуска и контракт с бэкендом."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.config import settings

TGAPP = Path(main_module.__file__).with_name("tgapp")


@pytest.fixture(autouse=True)
def _no_registration_gate(monkeypatch):
    monkeypatch.setattr(settings, "MINIAPP_REQUIRE_REGISTRATION", False, raising=False)


def test_mini_app_is_served():
    client = TestClient(main_module.app)

    resp = client.get("/tg/")

    assert resp.status_code == 200
    assert "Фоксинбург" in resp.text


def test_mini_app_loads_telegram_sdk_and_own_assets():
    html = (TGAPP / "index.html").read_text(encoding="utf-8")

    assert "telegram-web-app.js" in html
    assert 'href="/tg/app.css?v=' in html
    assert 'src="/tg/app.js?v=' in html


def test_mini_app_is_mobile_first_and_theme_aware():
    html = (TGAPP / "index.html").read_text(encoding="utf-8")
    css = (TGAPP / "app.css").read_text(encoding="utf-8")

    assert "viewport-fit=cover" in html
    # Приложение сознательно светлое в любой теме мессенджера: в тёмной теме
    # экран становился тёмным и плохо читаемым, на что и пожаловались.
    assert 'name="color-scheme" content="light"' in html
    assert "color-scheme: light;" in css
    # Тема клиента остаётся подсказкой для акцентов и системного хрома.
    assert "--tg-theme-text-color" in css
    # Безопасные зоны и запрет горизонтального скролла.
    assert "safe-area-inset-bottom" in css
    assert "overflow-x: hidden" in css
    # Шрифт полей >= 16px, иначе iOS зумит страницу при фокусе.
    assert "font-size: 16px" in css
    assert "prefers-reduced-motion" in css


def test_mini_app_uses_telegram_native_chrome():
    js = (TGAPP / "app.js").read_text(encoding="utf-8")

    for api in ("BackButton", "MainButton", "HapticFeedback", "themeChanged", "expand()"):
        assert api in js, f"не используется {api}"


def test_mini_app_sends_signed_init_data_not_raw_user_id():
    """initDataUnsafe допустим только для приветствия на экране."""
    js = (TGAPP / "app.js").read_text(encoding="utf-8")

    assert "X-Miniapp-Init-Data" in js
    assert "bridge.initData" in js
    # user_id как основание доступа в запросах не отправляется.
    assert "user_id=" not in js


def test_mini_app_escapes_interpolated_data():
    """В innerHTML попадают данные из KB и от LLM — только через esc()."""
    js = (TGAPP / "app.js").read_text(encoding="utf-8")

    interpolations = re.findall(r"esc\(", js)
    assert len(interpolations) > 10
    # Прямая вставка сырого поля в разметку — ошибка.
    assert "+ item.name +" not in js
    assert "+ data.reply +" not in js


def test_mini_app_requests_have_timeout():
    """Без AbortController зависший запрос = вечный спиннер в приложении."""
    js = (TGAPP / "app.js").read_text(encoding="utf-8")

    assert "AbortController" in js
    assert "REQUEST_TIMEOUT_MS" in js


def test_mini_app_handles_offline_and_errors():
    js = (TGAPP / "app.js").read_text(encoding="utf-8")

    assert '"offline"' in js and '"online"' in js
    assert "navigator.onLine" in js
    assert "skeleton" in js


# --- кнопка запуска в чате ------------------------------------------------


def test_webapp_button_is_added_to_menu(monkeypatch):
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example/app/", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_MINIAPP_URL", "", raising=False)

    rows = main_module._telegram_menu_buttons("tg-user")

    assert rows[0][0]["type"] == "web_app"
    assert rows[0][0]["web_app"] == "https://bot.example/tg/"


def test_webapp_button_hidden_until_registration(monkeypatch):
    """Кнопка, ведущая в анкету, — худший вид кнопки: её просто нет."""
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example/app/", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_MINIAPP_URL", "", raising=False)
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True, raising=False)

    from app.memory import get_store

    store = get_store()
    store.reset("tg-newbie", platform="telegram")
    rows = main_module._telegram_menu_buttons("tg-newbie")
    assert all(button["type"] != "web_app" for row in rows for button in row)

    conv = store.get("tg-newbie", platform="telegram")
    conv.registered = True
    store.save(conv)
    rows = main_module._telegram_menu_buttons("tg-newbie")
    assert rows[0][0]["type"] == "web_app"


def test_max_menu_hides_cabinet_until_registration(monkeypatch):
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example/app/", raising=False)
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True, raising=False)

    from app.memory import get_store

    store = get_store()
    store.reset("max-newbie")
    titles = [b.get("text", "") for row in main_module._main_menu("max-newbie") for b in row]
    assert not any("кабинет" in t.lower() for t in titles)

    conv = store.get("max-newbie")
    conv.registered = True
    store.save(conv)
    titles = [b.get("text", "") for row in main_module._main_menu("max-newbie") for b in row]
    assert any("кабинет" in t.lower() for t in titles)


def test_webapp_button_skipped_without_https(monkeypatch):
    """Telegram не откроет Mini App по http — лучше не показывать кнопку,
    чем показывать неработающую."""
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_MINIAPP_URL", "http://insecure/tg/", raising=False)

    assert main_module._telegram_webapp_button() is None


def test_explicit_telegram_miniapp_url_wins(monkeypatch):
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example/app/", raising=False)
    monkeypatch.setattr(settings, "TELEGRAM_MINIAPP_URL", "https://mini.example/", raising=False)

    assert settings.telegram_miniapp_url == "https://mini.example/"


def test_menu_command_answers_with_buttons(monkeypatch):
    """/menu в Telegram раньше уходил в LLM как обычный текст."""
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example/app/", raising=False)
    sent = []

    class FakeTelegram:
        async def send_message(self, chat_id, text, buttons=None):
            sent.append({"chat_id": chat_id, "text": text, "buttons": buttons})
            return True

        async def send_chat_action(self, chat_id, action="typing"):
            return True

    import asyncio

    asyncio.run(
        main_module._process_telegram_update(
            {"update_id": 9001, "message": {"chat": {"id": 5}, "text": "/menu"}},
            FakeTelegram(),
        )
    )

    assert len(sent) == 1
    assert sent[0]["buttons"]
    assert any(b.get("type") == "web_app" for row in sent[0]["buttons"] for b in row)
