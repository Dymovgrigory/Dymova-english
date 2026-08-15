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


def test_hero_is_a_live_fluid_not_a_picture():
    """В шапке симуляция жидкости: чернила расходятся и реагируют на палец.

    Рисованный маскот из шапки убран — он остаётся знаком школы в фавиконе,
    а шапку держит движение, которое нельзя перепутать с картинкой.
    """
    assert 'id="fluid"' in HTML
    assert "fluid.js" in HTML
    assert "hero__scrim" in HTML, "яркая вспышка съедает белый текст без линзы"


def test_fluid_is_optional_and_cheap():
    """Эффект не имеет права стоить человеку батареи и не имеет права
    ломать шапку, если WebGL недоступен."""
    fluid = (TGAPP / "fluid.js").read_text(encoding="utf-8")
    # Без WebGL — просто градиент.
    assert "if (!gl) return null" in fluid
    assert "background:" in CSS.split(".hero {")[1][:600]
    # Кадры не считаются, когда шапки не видно.
    assert "visibilitychange" in fluid and "IntersectionObserver" in fluid
    assert "if (!visible) return" in fluid
    # На телефоне сетка мельче.
    assert "isMobile() ? 128 : 200" in fluid
    # При «уменьшить движение» симуляция не запускается.
    assert 'prefers-reduced-motion' in JS.split("function startFluid")[1][:400]


def test_hero_phrases_rotate_word_by_word():
    """Фразы сменяют друг друга и набираются по слову."""
    assert "PHRASES" in JS
    assert "Английский не для школы, а для жизни" in HTML, "слоган виден и без скрипта"
    assert "WORD_STAGGER_MS" in JS
    assert ".hero__sub .word" in CSS


def test_hero_phrases_carry_no_facts_that_can_drift():
    """В бегущих фразах нет цен, расписания и цифр: они разошлись бы с базой."""
    phrases = JS.split("var PHRASES = [")[1].split("];")[0]
    assert "₽" not in phrases
    assert not any(ch.isdigit() for ch in phrases)


# --------------------------- микровзаимодействия ---------------------------

def test_success_is_celebrated_by_the_ink_not_by_a_timer():
    """Реакция привязана к результату действия, а не к таймеру."""
    assert 'mascot("success")' in JS
    assert "foxiSplash" in JS
    # Радость наступает после успешного ответа сервера, а не по расписанию.
    assert "setInterval" not in JS


def test_ink_reacts_to_touch():
    fluid = (TGAPP / "fluid.js").read_text(encoding="utf-8")
    assert "touchmove" in fluid


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
        "catalog", "offline", "dock", "sheet",
        "sheet-title", "sheet-body", "toast", "pulse", "team-list",
        "home-advantages", "home-path", "home-faq", "home-branches",
    ):
        assert f'id="{element_id}"' in HTML, f"потерян элемент #{element_id}"


def test_all_tabs_and_dock_buttons_exist():
    """Навигация — постоянный док, а не стопка экранов с кнопкой «назад»."""
    for tab in ("home", "programs", "team", "chat"):
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


def test_menu_enters_in_order_without_javascript():
    """Меню появляется ступенчато — тем же языком, что и шапка. Анимацией,
    а не классом от скрипта: при незагрузившемся JS меню обязано быть."""
    assert "@keyframes menu-in" in CSS
    assert "--ease-entrance" in CSS
    for delay in ("320ms", "480ms", "560ms", "640ms", "760ms"):
        assert delay in CSS, f"нет задержки {delay}"


def test_menu_press_stirs_the_ink():
    """Интерфейс и фон — одно целое: нажатие отзывается в шапке."""
    assert 'closest(".qa, .pulse, .dock__btn")' in JS
    assert "foxiSplash(1)" in JS


def test_keyboard_focus_is_as_visible_as_a_press():
    assert ".dock__btn:focus-visible" in CSS
    assert ".quick .qa:focus-visible" in CSS


def test_lead_form_collects_birthday_course_and_experience():
    """Форма заявки собирает то, что просит школа: дату рождения ребёнка,
    категорию курса (по умолчанию «Пока не определился») и опыт занятий."""
    assert 'id="lf-birthday"' in JS and 'type="date"' in JS
    assert 'id="lf-course-kind"' in JS and "Пока не определился" in JS
    assert 'id="lf-experience"' in JS and "Никогда не занимались" in JS
    assert "birthday" in JS and "experience" in JS
    # Валидация подсвечивает и селекты, не только текстовые поля.
    assert ".form.is-tried select:invalid" in CSS
