"""Четыре страницы курсов Spotlight 2–5 и все связи с ними по сайту."""
import os
import re

import build_subpages as B
import pages_spotlight

PROTOTYPE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRADES = (2, 3, 4, 5)
ALIASES = tuple("spotlight-%d-klass" % g for g in GRADES)


def read(name):
    with open(os.path.join(PROTOTYPE, name), encoding="utf-8") as f:
        return f.read()


def test_four_pages_registered():
    for grade in GRADES:
        assert "page_spotlight_%d_klass.html" % grade in B.PAGES


def test_page_has_price_modules_and_pdf():
    for grade in GRADES:
        html = B.render_page(B.PAGES["page_spotlight_%d_klass.html" % grade])
        assert "7 600" in html, "нет новой цены на Spotlight %d" % grade
        assert "9 000" in html, "нет старой цены на Spotlight %d" % grade
        assert "/assets/spotlight/spotlight-%d-klass-foxinburg.pdf" % grade in html
        assert "/assets/spotlight/cover-sp%d.jpg" % grade in html


def test_page_lists_every_module_of_the_textbook():
    decks = {d["grade"]: d for d in pages_spotlight._c.DECKS}
    for grade in GRADES:
        html = B.render_page(B.PAGES["page_spotlight_%d_klass.html" % grade])
        for _num, name, _topic, _detail, _starter in decks[grade]["modules"]:
            assert B.strip_tags(name) in html, "модуль %r не попал на страницу %d" % (name, grade)


def test_page_has_lead_button_and_jsonld():
    for grade in GRADES:
        html = B.render_page(B.PAGES["page_spotlight_%d_klass.html" % grade])
        assert "data-fxb-zayavka" in html
        assert '"@type": "Course"' in html
        assert '"@type": "FAQPage"' in html
        assert '"@type": "BreadcrumbList"' in html


def test_aliases_registered_for_static_build():
    import build_static_site as S
    for grade, alias in zip(GRADES, ALIASES):
        assert S.PAGE_ALIASES["page_spotlight_%d_klass.html" % grade] == alias


def test_links_in_header_and_footer():
    for name in ("main_combined_v7.html", "block_shapka.html"):
        html = read(name)
        for alias in ALIASES:
            assert 'href="/%s"' % alias in html, "%s: нет ссылки на /%s" % (name, alias)
    footer_sources = (read("block_footer.html"), read("main_combined_v7.html"))
    for alias in ALIASES:
        assert any('href="/%s"' % alias in src for src in footer_sources)


def test_cards_in_enrollment_block_survive_cms():
    """Скрипт подхвата из LMS заменяет innerHTML у .fxb-cards — карточки Spotlight
    обязаны лежать в отдельной обёртке .fxb-sp-row после неё, иначе их сотрёт."""
    html = read("main_combined_v7.html")
    pricing = html[html.find('id="fxb-pricing"'):]
    pricing = pricing[:pricing.find("<style>")]

    cms_row = pricing.find('class="fxb-cards"')
    sp_row = pricing.find('class="fxb-sp-row"')
    assert cms_row > 0, "не найден ряд карточек, управляемый из LMS"
    assert sp_row > cms_row, "ряд Spotlight должен идти после CMS-ряда"

    cms_block = pricing[cms_row:sp_row]
    assert cms_block.count("<div") == cms_block.count("</div>"), \
        "ряд Spotlight оказался внутри .fxb-cards — LMS его затрёт"

    sp_block = pricing[sp_row:]
    assert 'class="fxb-cards fxb-cards-spotlight"' in sp_block
    for grade in GRADES:
        assert "Spotlight %d" % grade in sp_block
        assert 'href="/spotlight-%d-klass"' % grade in sp_block


def test_course_options_in_every_lead_form():
    sources = [read("main_combined_v7.html"), read("build_course_pages.py")]
    for src in sources:
        for grade in GRADES:
            assert "Spotlight %d — английский для %d класса" % (grade, grade) in src
    main = read("main_combined_v7.html")
    assert main.count("Spotlight 2 — английский для 2 класса") >= 2, \
        "нужны обе формы главной: модалка заявки и #fxbEnrollForm"


def test_preset_can_only_return_values_that_exist_in_the_select():
    """fxbZcoursePreset подставляет значение в <select name="Course">.
    Если функция вернёт строку, которой нет среди <option>, браузер молча
    сбросит выбор — заявка уедет без курса. Проверяем обе копии формы."""
    for name in ("build_course_pages.py", "main_combined_v7.html"):
        src = read(name)
        preset = re.search(r"var fxbZcoursePreset=function\(subject\)\{(.*?)\n\s{4}\};", src, re.S)
        assert preset, "%s: не найдена функция fxbZcoursePreset" % name

        returned = set(re.findall(r"return '([^']+)';", preset.group(1)))
        # Spotlight собирается конкатенацией — проверяем его отдельно
        returned.discard("Spotlight ")
        for grade in GRADES:
            assert "Spotlight %d — английский для %d класса" % (grade, grade) in src

        options = set(re.findall(r'<option value="([^"]+)"', src))
        missing = sorted(v for v in returned if v not in options)
        assert not missing, "%s: preset вернёт значения, которых нет в списке: %s" % (name, missing)
