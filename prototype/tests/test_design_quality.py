"""Проверяемые требования к вёрстке: без эмодзи, поля форм выровнены, модалка
влезает в экран. Всё найдено на живой странице, а не придумано."""
import os
import re

PROTOTYPE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U0001F1E6-\U0001F1FF☀-➿️]")


def read(name):
    with open(os.path.join(PROTOTYPE, name), encoding="utf-8") as f:
        return f.read()


def event_section():
    html = read("main_combined_v7.html")
    start = html.find('id="fxb-event"')
    return html[start:html.find('id="fxb-enrollment"', start)]


def test_no_emoji_in_our_own_markup():
    """В проекте политика «эмодзи 0» (критерий QA прошлых сессий), а для языков
    есть свой приём — двухбуквенный код.

    Проверяем только то, что пишем сами. Эмодзи в .fxb-yr-text — дословные
    цитаты из отзывов на Яндекс.Картах, править их нельзя: это чужая речь.
    """
    surfaces = {"секция акции": event_section(), "курсы Spotlight": read("pages_spotlight.py")}
    for name in ("build_course_pages.py", "build_subpages.py"):
        surfaces[name] = read(name)
    dirty = {k: sorted(set(EMOJI.findall(v))) for k, v in surfaces.items() if EMOJI.search(v)}
    assert not dirty, "эмодзи в нашей вёрстке: %r" % dirty


def test_promo_name_is_the_biggest_thing_in_the_section():
    """«Неделя знакомства» должна попадаться на глаза первой, а не теряться
    в мелкой плашке над заголовком о выгоде."""
    section = event_section()
    assert re.search(r'class="fxb-ev-title"[^>]*>\s*Неделя знакомства', section), \
        "название акции не является заголовком секции"
    title = re.search(r"#fxb-event \.fxb-ev-title\{([^}]*)\}", section).group(1)
    offer = re.search(r"#fxb-event \.fxb-ev-offer\{([^}]*)\}", section)
    assert offer, "нет подзаголовка с выгодой"
    def max_px(rule):
        return max([float(x) for x in re.findall(r"(\d+(?:\.\d+)?)px", rule)] or [0])
    assert max_px(title) > max_px(offer.group(1)), "заголовок акции не крупнее строки о выгоде"


def test_modal_fields_share_one_box_model():
    """У <input> браузерный дефолт content-box, у <select> — border-box.
    Без явного сброса поля расходятся по ширине на 35px (замерено в браузере)."""
    for name in ("build_course_pages.py", "main_combined_v7.html"):
        css = read(name)
        rule = re.search(r"\.fxb-zfield input[^{]*\{([^}]*)\}", css)
        assert rule, "%s: не найдено правило полей модалки" % name
        assert "box-sizing:border-box" in rule.group(1).replace(" ", ""), \
            "%s: поля модалки без явного box-sizing — ширины разъезжаются" % name


def test_modal_fits_the_screen():
    """Форма из шести полей выше окна: карточка 929px при экране 900px,
    низ и крестик обрезались. Нужен предел высоты и прокрутка внутри."""
    for name in ("build_course_pages.py", "main_combined_v7.html"):
        css = read(name)
        rule = re.search(r"\.fxb-zbox\{([^}]*)\}", css)
        assert rule, "%s: не найдено правило .fxb-zbox" % name
        body = rule.group(1).replace(" ", "")
        assert "max-height" in body, "%s: у модалки нет предела высоты" % name
    for name in ("build_course_pages.py", "main_combined_v7.html"):
        assert ".fxb-zscroll" in read(name), "%s: нет прокручиваемой области формы" % name


def test_no_shouting_labels_in_the_lead_form():
    """text-transform:uppercase на подписях — типовой признак шаблона."""
    for name in ("build_course_pages.py", "main_combined_v7.html"):
        css = read(name)
        rule = re.search(r"\.fxb-zalt-l\{([^}]*)\}", css)
        assert rule, "%s: не найдено правило .fxb-zalt-l" % name
        assert "uppercase" not in rule.group(1), "%s: подпись капсом" % name


def test_enrollment_form_fields_have_visible_labels():
    """Подпись только в placeholder исчезает, как только человек начал печатать."""
    html = read("main_combined_v7.html")
    form = html[html.find('id="fxbEnrollForm"'):]
    form = form[:form.find("</form>")]
    names = re.findall(r'name="(\w+)"', form)
    labels = re.findall(r'<span class="fxb-field-l">', form)
    assert len(labels) >= len(names), \
        "полей %d, видимых подписей %d" % (len(names), len(labels))


def test_ink_is_dimmed():
    """Чернила мешали читать текст — фоновый холст и след за курсором приглушены."""
    css = read("main_combined_v7.html")
    for sel in (r"#fxb-fluid\{", r"#fxb-fluid-trail\{"):
        rule = re.search(sel + r"([^}]*)\}", css)
        assert rule, "нет правила для " + sel
        op = re.search(r"opacity:\s*([\d.]+)", rule.group(1))
        assert op and float(op.group(1)) < 1, "холст не приглушён: " + sel
