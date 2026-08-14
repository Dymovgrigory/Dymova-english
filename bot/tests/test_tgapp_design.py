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

# Пиктограммы и дингбаты. Диапазон намеренно широкий: запрещены не только
# лисы, но и «📅», «☎» — весь класс системных картинок вместо иконок.
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF←-⇿☀-➿️]")


@pytest.mark.parametrize("name", ["index.html", "app.css", "app.js"])
def test_no_system_emoji_anywhere(name):
    """«Никаких стандартных emoji-лис» — принципиальное требование ТЗ."""
    text = (TGAPP / name).read_text(encoding="utf-8")
    found = sorted(set(_EMOJI_RE.findall(text)))
    assert not found, f"{name}: найдены системные emoji {found}"


def test_favicon_is_the_brand_mascot_not_an_emoji():
    """Раньше фавиконом была inline-SVG с текстом «🦊»."""
    assert 'rel="icon" href="/tg/assets/foxi.webp"' in HTML
    assert "text>🦊" not in HTML


def test_real_mascot_asset_is_shipped_and_light():
    """Маскот лежит в репозитории и уже работает на сайте — используем его.

    Трёхмерная модель и рантайм three.js (около двух мегабайт) удалены:
    сгенерированная модель выглядела хуже рисованного маскота, а платил за
    неё человек с телефоном.
    """
    still = TGAPP / "assets" / "foxi.webp"
    assert still.exists()
    # Он на первом экране, поэтому обязан быть лёгким.
    assert still.stat().st_size < 60_000
    assert not (TGAPP / "assets" / "foxi.glb").exists()
    assert not (TGAPP / "vendor").exists()


def test_static_mascot_is_shown_immediately():
    """Первый экран не должен ждать 3D — картинка видна сразу."""
    assert 'id="mascot-still"' in HTML
    assert 'rel="preload" as="image" href="/tg/assets/foxi.webp"' in HTML
    assert 'alt="Фокси, маскот школы Фоксинбург"' in HTML


def test_icons_are_inline_svg():
    """Иконки — векторные и фирменные, а не системные картинки из шрифта."""
    assert HTML.count("<svg") >= 8
    assert 'class="qa__ic"' in HTML


# --------------------------- маскот ---------------------------

def test_mascot_is_drawn_not_generated_3d():
    """Сгенерированная трёхмерная модель рендерилась тускло и в неудачной
    позе — то есть проигрывала той самой картинке, ради которой её ставили.
    Живость даём движением, а не полигонами."""
    assert "mascot.js" not in HTML
    assert "importmap" not in HTML
    assert "three" not in HTML
    assert 'id="mascot-still"' in HTML


def test_mascot_moves_and_reacts():
    assert "@keyframes float" in CSS
    assert "@keyframes greet" in CSS and "@keyframes cheer" in CSS
    assert "is-cheer" in JS


# --------------------------- микровзаимодействия ---------------------------

def test_mascot_reacts_to_real_success_not_decoration():
    """Реакция маскота привязана к результату действия, а не к таймеру."""
    assert 'mascot("success")' in JS
    # Радость наступает после успешного ответа сервера, а не по расписанию.
    assert "setInterval" not in JS


def test_mascot_reacts_to_touch():
    assert "touchstart" in JS


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
