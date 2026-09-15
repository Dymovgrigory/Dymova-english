"""Акция «Неделя знакомства» 21–26 сентября 2026: секция на главной и лендинг."""
import os
import re

import build_subpages as B

PROTOTYPE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBJECTS = (
    "Неделя знакомства — Английский язык",
    "Неделя знакомства — Китайский язык",
    "Неделя знакомства — Немецкий язык",
    "Неделя знакомства — Испанский язык",
    "Неделя знакомства — Подготовка к школе",
)


def read(name):
    with open(os.path.join(PROTOTYPE, name), encoding="utf-8") as f:
        return f.read()


def event_section():
    html = read("main_combined_v7.html")
    start = html.find('id="fxb-event"')
    assert start > 0, "секция события не найдена на главной"
    return html[start:html.find('id="fxb-enrollment"', start)]


def test_event_section_present_on_main():
    html = read("main_combined_v7.html")
    assert 'id="fxb-event"' in html
    assert 'data-fxb-event-until="2026-09-26T23:59:59+03:00"' in html


def test_event_section_states_the_offer():
    section = event_section()
    assert "2 125" in section, "нет суммарной выгоды"
    assert "1 125" in section, "нет старой цены пробного"
    assert "1 000" in section or "1000" in section, "нет бонусов"
    assert "21" in section and "26 сентября" in section


def test_every_try_button_opens_a_lead_with_a_subject():
    section = event_section()
    buttons = re.findall(r"<[^>]*data-fxb-zayavka[^>]*>", section)
    assert len(buttons) >= 6, "5 направлений + общая кнопка"
    for tag in buttons:
        subject = re.search(r'data-fxb-subject="([^"]+)"', tag)
        assert subject, "кнопка без data-fxb-subject: " + tag
        assert subject.group(1).startswith("Неделя знакомства")
    for subject in SUBJECTS:
        assert 'data-fxb-subject="%s"' % subject in section


def test_event_section_knows_when_the_promo_starts():
    """Акция идёт 21–26 сентября, а блок выложен раньше: до старта таймер
    обязан считать до начала, иначе он показывает «11 дней» по акции,
    которая ещё не началась."""
    section = event_section()
    assert 'data-fxb-event-from="2026-09-21T00:00:00+03:00"' in section
    assert "до старта" in section.lower() or "До старта" in section


def test_event_section_hides_itself_after_the_promo():
    section = event_section()
    assert "data-fxb-event-until" in section
    assert "hidden=true" in section or "hidden = true" in section


def test_landing_registered_and_aliased():
    import build_static_site as S
    assert "page_nedelya_znakomstva.html" in B.PAGES
    assert S.PAGE_ALIASES["page_nedelya_znakomstva.html"] == "nedelya-znakomstva"


def test_landing_repeats_the_offer_and_collects_leads():
    html = B.render_page(B.PAGES["page_nedelya_znakomstva.html"])
    assert "2 125" in html
    assert "1 125" in html
    assert "data-fxb-zayavka" in html
    assert '"@type": "FAQPage"' in html
    assert '"@type": "BreadcrumbList"' in html


def test_landing_has_a_try_button_on_every_direction():
    """Лендинг — посадочная для рекламы: направление должно выбираться одним
    кликом из карточки, а не только через выпадающий список в форме."""
    html = B.render_page(B.PAGES["page_nedelya_znakomstva.html"])
    for subject in SUBJECTS:
        assert 'data-fxb-subject="%s"' % subject in html, "нет кнопки: " + subject

    buttons = re.findall(r"<[^>]*data-fxb-zayavka[^>]*>", html)
    subjects = [re.search(r'data-fxb-subject="([^"]+)"', b).group(1) for b in buttons]
    assert all(s.startswith("Неделя знакомства") for s in subjects), subjects
    assert len(set(subjects)) >= 6, "5 направлений + общая кнопка заявки"


def test_event_section_blends_into_the_hero():
    """Секция лежит внутри #fxb-cinema, где действует CINEMA MODE: блоки
    прозрачны, фон общий. Свой непрозрачный градиент давал жёсткий шов
    и сверху, и снизу — вместо него мягкое высветление с растворяющимися краями."""
    section = event_section()
    base = re.search(r"#fxb-event\{(.*?)\}", section, re.S).group(1)
    assert "background:transparent" in base.replace(" ", ""), \
        "секция обязана быть прозрачной, фон даёт #fxb-cinema"
    for opaque in ("#241540", "#5f2a8c", "#3a1c5e"):
        assert opaque not in base, "непрозрачный градиент в фоне секции: " + opaque

    veil = re.search(r"#fxb-event::before\{(.*?)\}", section, re.S)
    assert veil, "нет слоя высветления"
    veil = veil.group(1)
    assert "rgba(255,255,255,0)" in veil.replace(" ", ""), \
        "края слоя должны уходить в ноль, иначе шов остаётся"


def test_landing_offers_five_directions():
    html = B.render_page(B.PAGES["page_nedelya_znakomstva.html"])
    for subject in SUBJECTS:
        assert 'data-fxb-subject="%s"' % subject in html, "нет кнопки: " + subject
    assert "4 направления" not in html, "осталось старое «4 направления»"
