"""Дизайн-контракт мини-приложения.

ТЗ формулирует часть требований как жёсткие запреты (никаких системных
emoji-лис, только фирменный маскот, 3D лениво и с запасным вариантом).
Такие вещи легко потерять при следующей правке вёрстки, поэтому они
зафиксированы тестами, а не только договорённостью.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

TGAPP = Path(__file__).resolve().parents[1] / "app" / "tgapp"

HTML = (TGAPP / "index.html").read_text(encoding="utf-8")
CSS = (TGAPP / "app.css").read_text(encoding="utf-8")
JS = (TGAPP / "app.js").read_text(encoding="utf-8")
MASCOT = (TGAPP / "mascot.js").read_text(encoding="utf-8")

# Пиктограммы и дингбаты. Диапазон намеренно широкий: запрещены не только
# лисы, но и «📅», «☎» — весь класс системных картинок вместо иконок.
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF←-⇿☀-➿️]")


@pytest.mark.parametrize("name", ["index.html", "app.css", "app.js", "mascot.js"])
def test_no_system_emoji_anywhere(name):
    """«Никаких стандартных emoji-лис» — принципиальное требование ТЗ."""
    text = (TGAPP / name).read_text(encoding="utf-8")
    found = sorted(set(_EMOJI_RE.findall(text)))
    assert not found, f"{name}: найдены системные emoji {found}"


def test_favicon_is_the_brand_mascot_not_an_emoji():
    """Раньше фавиконом была inline-SVG с текстом «🦊»."""
    assert 'rel="icon" href="assets/foxi.webp"' in HTML
    assert "text>🦊" not in HTML


def test_real_mascot_assets_are_shipped():
    """Маскот лежит в репозитории и уже работает на сайте — используем его."""
    still = TGAPP / "assets" / "foxi.webp"
    model = TGAPP / "assets" / "foxi.glb"
    assert still.exists() and model.exists()
    # Статичный маскот обязан быть лёгким: он на первом экране.
    assert still.stat().st_size < 60_000
    assert model.stat().st_size < 1_200_000


def test_static_mascot_is_shown_immediately():
    """Первый экран не должен ждать 3D — картинка видна сразу."""
    assert 'id="mascot-still"' in HTML
    assert 'rel="preload" as="image" href="assets/foxi.webp"' in HTML
    assert 'alt="Фокси, маскот школы Фоксинбург"' in HTML


def test_tiles_use_inline_svg_icons():
    """Иконки — векторные и фирменные, а не системные картинки из шрифта."""
    assert HTML.count("<svg") >= 6
    assert 'class="tile__ic"' in HTML


# --------------------------- 3D: лениво и безопасно ---------------------------

def test_three_js_is_not_loaded_eagerly():
    """Рантайм 3D весит больше мегабайта — в начальную загрузку он не входит."""
    assert "await import('three')" in MASCOT
    assert '<script src="./vendor/three' not in HTML
    assert 'type="module" src="mascot.js"' in HTML


def test_three_js_is_self_hosted_not_from_cdn():
    """Вебвью мессенджера часто за плохой сетью, а сторонний домен блокируется."""
    assert '"three": "./vendor/three/three.module.min.js"' in HTML
    assert "cdn.jsdelivr.net" not in HTML
    assert (TGAPP / "vendor" / "three" / "three.module.min.js").exists()
    assert (TGAPP / "vendor" / "draco" / "draco_decoder.wasm").exists()


def test_3d_is_skipped_on_weak_devices_and_saved_data():
    """Fallback для слабых устройств — прямое требование ТЗ."""
    assert "saveData" in MASCOT
    assert "deviceMemory" in MASCOT
    assert "hardwareConcurrency" in MASCOT
    assert "webgl2" in MASCOT


def test_3d_respects_reduced_motion():
    assert "prefers-reduced-motion" in MASCOT
    assert "reducedMotion" in MASCOT


def test_3d_failure_leaves_the_static_mascot():
    """Провал загрузки не должен ломать экран."""
    assert "catch" in MASCOT
    assert "remove('is-3d')" in MASCOT


def test_3d_does_not_render_while_hidden():
    """Рендерить невидимую сцену — чистый расход батареи."""
    assert "IntersectionObserver" in MASCOT
    assert "visibilitychange" in MASCOT


def test_3d_pixel_ratio_is_capped():
    """Плотность выше 2 не видна, но стоит вчетверо дороже по пикселям."""
    assert "Math.min(window.devicePixelRatio || 1, 2)" in MASCOT


# --------------------------- микровзаимодействия ---------------------------

def test_mascot_reacts_to_real_success_not_decoration():
    """Реакция маскота привязана к результату действия, а не к таймеру."""
    assert 'if (kind === "success") mascot("success");' in JS
    assert "foxi:success" in MASCOT


def test_mascot_reacts_to_touch():
    assert "pointerdown" in MASCOT


def test_loading_state_has_skeletons():
    """Пустой экран во время загрузки читается как поломка."""
    assert ".skeleton" in CSS
    assert "skeleton" in JS


# --------------------------- доступность и производительность ---------------------------

def test_touch_targets_are_large_enough():
    assert "min-height: 44px" in CSS


def test_focus_is_visible():
    assert ":focus-visible" in CSS


def test_motion_is_disabled_on_request():
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert "animation-duration: .001ms !important" in CSS


def test_inputs_avoid_ios_zoom():
    """Шрифт меньше 16px заставляет iOS зумить страницу при фокусе."""
    assert "font-size: 16px" in CSS


def test_no_horizontal_scroll():
    assert "overflow-x: hidden" in CSS


def test_layout_survives_narrow_screens():
    assert "@media (max-width: 340px)" in CSS


def test_own_palette_layered_over_client_theme():
    """Приложение живёт в мессенджере, но не растворяется в нём."""
    assert "--tg-theme-bg-color" in CSS      # база берётся из темы клиента
    assert "--amber: #ffc53d" in CSS          # акценты остаются фирменными
    assert "backdrop-filter" in CSS           # собственная фактура


def test_screen_ids_used_by_app_js_are_intact():
    """Редизайн не должен ломать логику: контракт DOM тот же."""
    for element_id in (
        "greeting-title", "greeting-sub", "profile-teaser", "age", "age-value",
        "picker-results", "lead-form", "lf-parent", "lf-phone", "lead-status",
        "hw-file", "hw-preview", "hw-hint", "hw-note", "hw-status", "hw-answer",
        "chat-log", "chat-form", "chat-input", "catalog", "branches", "profile",
        "offline",
    ):
        assert f'id="{element_id}"' in HTML, f"потерян элемент #{element_id}"


def test_all_screens_are_present():
    for screen in ("home", "picker", "signup", "homework", "chat", "catalog",
                   "branches", "profile"):
        assert f'data-screen="{screen}"' in HTML
