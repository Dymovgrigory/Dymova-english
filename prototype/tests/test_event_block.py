"""Акция «Неделя знакомства» 21–26 сентября 2026: секция на главной и лендинг."""
import os
import re

import build_subpages as B

PROTOTYPE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBJECTS = (
    "Неделя знакомства — Английский язык",
    "Неделя знакомства — Китайский язык",
    "Неделя знакомства — Немецкий язык",
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
    assert len(buttons) >= 5, "4 направления + общая кнопка"
    for tag in buttons:
        subject = re.search(r'data-fxb-subject="([^"]+)"', tag)
        assert subject, "кнопка без data-fxb-subject: " + tag
        assert subject.group(1).startswith("Неделя знакомства")
    for subject in SUBJECTS:
        assert 'data-fxb-subject="%s"' % subject in section


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
