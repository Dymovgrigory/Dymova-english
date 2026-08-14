"""Дизайн-контракт мини-приложения MAX.

Приложений у школы несколько, и требования ТЗ относятся ко всем: фирменный
знак вместо системной эмодзи-лисы, собственные иконки вместо пиктограмм
шрифта, читаемость и доступность. Telegram-версия закрыта своим тестом
(`test_tgapp_design.py`) — здесь то же самое для MAX, чтобы редизайн одного
приложения не оставлял второе в прежнем виде.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

MINIAPP = Path(__file__).resolve().parents[1] / "app" / "miniapp"

HTML = (MINIAPP / "index.html").read_text(encoding="utf-8")
JS = (MINIAPP / "app.js").read_text(encoding="utf-8")

# Пиктограммы и дингбаты: запрещены не только лисы, но и «📅», «☎» — весь
# класс системных картинок вместо иконок. Стрелка «←» в кнопке «в меню»
# допустима: это типографский знак, а не цветная картинка шрифта.
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


@pytest.mark.parametrize("name", ["index.html", "app.js"])
def test_no_system_emoji(name):
    text = (MINIAPP / name).read_text(encoding="utf-8")
    found = sorted(set(_EMOJI_RE.findall(text)))
    assert not found, f"{name}: найдены системные emoji {found}"


def test_favicon_is_the_brand_mark():
    """Раньше фавиконом была inline-SVG с текстом «🦊»."""
    assert 'rel="icon" href="img/fox-head-yellow.png"' in HTML
    assert "text>🦊" not in HTML


def test_hero_shows_the_real_mascot():
    assert 'class="hero__mark" src="img/fox-head-yellow.png"' in HTML


def test_menu_tiles_use_drawn_icons():
    """Иконки — векторные и свои, а не картинки системного шрифта."""
    assert HTML.count('class="tile__ic"') == 6
    assert HTML.count("<svg") >= 6


def test_branch_list_uses_drawn_icons():
    for icon in ("IC_PIN", "IC_PHONE", "IC_CLOCK"):
        assert icon in JS, f"иконка {icon} потерялась"


def test_tile_title_keeps_full_contrast():
    """Обёртка подписи — тоже span, из-за чего заголовок терял контраст."""
    assert ".menu-tile b {" in HTML and "color: var(--ink);" in HTML
    assert ".tile__note { display: block; font-size: 12.5px; color: var(--ink-soft); }" in HTML


def test_brand_palette_is_declared():
    for token in ("--amber", "--violet", "--ink", "--bg-elev"):
        assert token in HTML, f"нет фирменного токена {token}"


def test_app_stays_light_and_readable():
    """Тёмная тема делала экран тёмным и плохо читаемым — от неё отказались
    сознательно, в пользу постоянной светлой и контрастной палитры."""
    assert "color-scheme: light;" in HTML
    assert "prefers-color-scheme: dark" not in HTML
    assert "--ink: #14110c;" in HTML


def test_motion_can_be_switched_off():
    assert "prefers-reduced-motion: reduce" in HTML


def test_touch_targets_are_large_enough():
    """44 пикселя — минимальный размер, за который можно уверенно попасть."""
    assert "min-height: 44px" in HTML or "min-height: 48px" in HTML
    assert ":focus-visible" in HTML


def test_page_never_scrolls_sideways():
    assert "overflow-x: hidden" in HTML


def test_inputs_do_not_trigger_ios_zoom():
    """Шрифт мельче 16px заставляет iOS приближать страницу на фокусе."""
    match = re.search(r"input, select, textarea \{[^}]*font-size: (\d+)px", HTML)
    assert match and int(match.group(1)) >= 16


def test_all_screens_and_controls_survived_the_redesign():
    """Редизайн не должен ломать разметку, на которую опирается app.js."""
    for screen in ("menu", "select", "signup", "homework", "catalog", "branches", "cabinet"):
        assert f'id="screen-{screen}"' in HTML
    for control in (
        "sel-age", "sel-format", "sel-go", "sel-results",
        "lf-parent", "lf-child", "lf-age", "lf-phone", "lf-branch",
        "lf-comment", "lf-submit", "lf-status",
        "hw-file", "hw-preview", "hw-note", "hw-submit", "hw-status", "hw-answer",
        "catalog", "branches", "cabinet-greeting", "cabinet-signup",
    ):
        assert f'id="{control}"' in HTML, f"потерян элемент {control}"


def test_max_bridge_still_loads_before_the_app():
    bridge = HTML.index("max-web-app.js")
    own = HTML.index('src="app.js"')
    assert bridge < own
