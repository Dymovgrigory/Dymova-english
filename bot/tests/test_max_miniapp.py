"""MAX Mini App: без моста личность не приходит, и приложение пустое.

Ссылка в кабинете MAX Бизнес ведёт на /app/. Приложение читает window.WebApp,
но этот объект появляется только после загрузки библиотеки MAX Bridge — без
неё initData пустой, бэкенд никого не опознаёт и пользователь видит просьбу
«откройте внутри MAX», уже находясь внутри MAX.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from app import main as main_module

MINIAPP = Path(main_module.__file__).with_name("miniapp")
BRIDGE_SRC = "https://st.max.ru/js/max-web-app.js"


def test_mini_app_is_served():
    client = TestClient(main_module.app)

    resp = client.get("/app/")

    assert resp.status_code == 200
    assert "Фоксинбург" in resp.text


def test_mini_app_loads_max_bridge():
    html = (MINIAPP / "index.html").read_text(encoding="utf-8")

    assert BRIDGE_SRC in html


def test_bridge_is_loaded_before_own_script():
    """Порядок обязателен: app.js читает window.WebApp сразу при запуске."""
    html = (MINIAPP / "index.html").read_text(encoding="utf-8")

    assert html.index(BRIDGE_SRC) < html.index('src="app.js"')


def test_bridge_script_is_not_deferred():
    """defer/async сдвинут бы мост за пределы старта app.js."""
    html = (MINIAPP / "index.html").read_text(encoding="utf-8")
    tag_start = html.index(BRIDGE_SRC)
    tag = html[html.rindex("<script", 0, tag_start) : html.index(">", tag_start) + 1]

    assert "defer" not in tag
    assert "async" not in tag
