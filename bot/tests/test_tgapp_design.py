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


def test_icons_are_inline_svg():
    """Иконки — векторные и фирменные, а не системные картинки из шрифта."""
    assert HTML.count("<svg") >= 8
    assert 'class="qa__ic"' in HTML


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
    assert 'mascot("success")' in JS
    assert "foxi:success" in MASCOT
    # Радость наступает после успешного ответа сервера, а не по расписанию.
    assert "setInterval" not in JS


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


def test_app_stays_light_and_readable_in_any_client_theme():
    """Раньше поверхности брались из темы клиента, и в тёмной теме экран
    становился тёмным и плохо читаемым. Теперь приложение светлое всегда."""
    assert "color-scheme: light;" in CSS
    assert "--bg: #fbfaf7;" in CSS
    assert "--ink: #14110c;" in CSS
    # Тема клиента остаётся подсказкой для акцентов, а не источником фона.
    assert "--tg-theme-text-color" in CSS
    assert "--bg: var(--tg-theme" not in CSS


def test_dom_contract_of_the_shell_is_intact():
    """Постоянная часть приложения: разделы, док, лист, чат, витрина."""
    for element_id in (
        "greeting-title", "greeting-sub", "chat-log", "chat-form", "chat-input",
        "catalog", "branches", "profile", "offline", "dock", "sheet",
        "sheet-title", "sheet-body", "toast", "pulse", "team-list",
        "home-advantages", "home-path", "home-faq", "home-branches",
    ):
        assert f'id="{element_id}"' in HTML, f"потерян элемент #{element_id}"


def test_all_tabs_and_dock_buttons_exist():
    """Навигация — постоянный док, а не стопка экранов с кнопкой «назад»."""
    for tab in ("home", "programs", "team", "chat", "profile"):
        assert f'data-tab="{tab}"' in HTML
        assert f'data-tab-go="{tab}"' in HTML


def test_actions_open_as_sheets():
    """Действия — лист снизу поверх раздела, а не отдельный экран."""
    for sheet in ("quiz", "picker", "signup", "homework"):
        assert f'{sheet}: {{ title:' in JS, f"нет листа {sheet}"
    assert 'data-sheet="quiz"' in HTML or 'data-sheet="picker"' in HTML
    # Лист закрывается жестом, а не только кнопкой.
    assert "touchmove" in JS and "closeSheet()" in JS


def test_sheet_forms_are_built_in_js_with_escaping():
    """Формы листов собираются скриптом — значит там же и экранирование."""
    for element_id in ("lf-parent", "lf-phone", "lead-status", "hw-file",
                       "hw-preview", "hw-status", "hw-answer", "age", "age-value",
                       "picker-results"):
        assert f'id="{element_id}"' in JS, f"потерян элемент #{element_id}"


def test_level_test_answers_never_reach_the_client():
    """Тест, решаемый просмотром исходника страницы, бесполезен."""
    assert "/api/miniapp/level-test" in JS
    # Правильные ответы приходят только на сервер — в приложении их нет.
    assert "question.answer" not in JS
    assert "right_option" not in JS


def test_age_filter_understands_grades():
    """«2-3 класс» — это классы, а не возраст: без пересчёта курс для
    второклассников попадал в фильтр «3–6 лет»."""
    assert "/класс/i.test(text)" in JS
    assert "n + 6" in JS


def test_personal_state_survives_restart():
    """Уровень и возраст помнятся между запусками, но приложение переживает
    запрет хранилища в вебвью."""
    assert "localStorage" in JS
    assert "catch" in JS.split("localStorage")[1][:400]



def test_home_tells_the_story_not_just_buttons():
    """Главная — рассказ о школе, а не один экран с кнопками: путь ученика,
    преимущества, вопросы и филиалы приходят из базы знаний."""
    for block in ("home-advantages", "home-path", "home-faq", "home-branches"):
        assert f'id="{block}"' in HTML
    # Ни одного факта о школе в вёрстке: они разошлись бы с реальностью.
    assert "8 200" not in HTML and "9 000" not in HTML

def test_binding_survives_missing_elements():
    """Кэш мессенджера может отдать старую разметку со свежим скриптом.
    Один null не должен мешать приложению запуститься."""
    assert "function on(" in JS
    assert "console.warn" in JS.split("bind();")[1][:400] or "catch" in JS.split("try {")[1][:200]
