# Неделя знакомства, Spotlight 2–5 и фикс заголовков блога — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить на сайт акцию «Неделя знакомства» с заявкой, четыре страницы курсов Spotlight 2–5 со всеми связями (шапка, подвал, карточки, формы) и починить видимую HTML-разметку в заголовках свежих статей блога.

**Architecture:** Сайт статический. Контент подстраниц описывается словарями в `prototype/build_subpages.py` и модулях `pages_*.py`, рендерится функциями `landing_page` / `article_page` / `feed_page` в `page_<slug>.html`, затем `build_static_site.py` оборачивает страницы в шапку/подвал и раскладывает в `dist/<alias>/index.html`. Главная (`main_combined_v7.html`) правится руками и содержит собственные копии шапки, подвала и модалки заявки. Тексты курсов Spotlight берутся импортом из `presentations/spotlight/content.py` — единый источник правды, без копипасты.

**Tech Stack:** Python 3.9, pytest 8.4, чистый HTML/CSS/JS без сборщиков и зависимостей. Сборка — `make all` (`devflow.py build`), выкладка — `python3 prototype/build_static_site.py`.

## Global Constraints

- Python 3.9.6 — никаких `X | Y` в аннотациях, никакого `match`. При необходимости `from __future__ import annotations`.
- Никаких внешних зависимостей во фронтенде: только ванильный JS и CSS.
- Бренд-палитра: `--purple:#392852`, `--purple-2:#662d92`, `--orange:#c24712`, `--yellow:#fcf951`, `--ink:#241a36`, `--muted:#6f6883`.
- Шрифт — Montserrat, self-hosted, подключается в `build_head` (`build_static_site.py`). В блоках `<link>` на Google Fonts не добавлять.
- Все заявки идут только на `POST https://bot.dymova-english.ru/api/lead`. Второго канала отправки не заводить.
- Цена Spotlight: было `9 000 ₽`, стало `7 600 ₽`/мес, `950 ₽` за занятие, экономия `12 600 ₽` за год. Источник — `PRICE` в `presentations/spotlight/content.py`.
- Даты акции: 21–26 сентября 2026. Пробное `0 ₽` вместо `1 125 ₽`, бонус `1 000 ₽`, суммарная выгода `до 2 125 ₽`.
- Ссылка на MAX-бота: `https://max.ru/id611904726658_bot` (в `build_subpages.py` — константа `MAX_BOT`).
- `prototype/blocks_min/` руками не править — это результат минификации.
- Тесты запускаются из корня репозитория: `python3 -m pytest prototype/tests -q`.
- Коммиты — Conventional Commits, каждая задача плана = один коммит.

---

## Структура файлов

**Создаются:**

- `prototype/tests/conftest.py` — добавляет `prototype/` в `sys.path`, чтобы тесты могли импортировать генераторы.
- `prototype/tests/test_blog_titles.py` — заголовки статей без голой разметки (задача 1).
- `prototype/tests/test_spotlight_pages.py` — страницы Spotlight и все связи с ними (задачи 2–4).
- `prototype/tests/test_event_block.py` — секция события и лендинг акции (задачи 5–6).
- `prototype/pages_spotlight.py` — четыре страницы Spotlight, данные читает из `presentations/spotlight/content.py`.
- `prototype/assets/spotlight/` — обложки учебников и PDF-презентации, копируются в `dist/assets/spotlight/`.

**Изменяются:**

- `prototype/build_subpages.py` — хелпер `strip_tags`, четыре места его применения, регистрация страниц Spotlight и лендинга акции.
- `prototype/build_course_pages.py:335-340,420-428` — выпадающий список курсов и `fxbZcoursePreset` в модалке заявки.
- `prototype/build_static_site.py` — `PAGE_ALIASES` для пяти новых страниц.
- `prototype/main_combined_v7.html` — секция события, пункты меню, ссылки в подвале, ряд карточек Spotlight, два выпадающих списка, `fxbZcoursePreset`.
- `prototype/block_shapka.html` — пункты меню.
- `prototype/block_footer.html` — ссылки в колонке «Программы».
- `prototype/block_header_unified.html` — пункты меню (легаси, сборкой не используется, правим для единообразия).

---

### Task 1: Фикс заголовков блога

Поле `title` у 13 статей содержит разметку подсветки (`<span class="fxb-accent">`). `<h1>` выводит её сырой — так и задумано. Карточка в списке, хлебные крошки и JSON-LD получают ту же строку и показывают теги как текст. Чиним генератор, а не готовые файлы.

**Files:**
- Create: `prototype/tests/conftest.py`
- Create: `prototype/tests/test_blog_titles.py`
- Modify: `prototype/build_subpages.py` (добавить `strip_tags` рядом с `faq_jsonld`; применить в строках 877, 890, 906, 959)

**Interfaces:**
- Consumes: ничего.
- Produces: `build_subpages.strip_tags(s: str) -> str` — убирает HTML-теги и схлопывает пробелы. Используется задачами 2 и 6.

- [ ] **Step 1: Создать conftest для тестов**

`prototype/tests/conftest.py`:

```python
"""Тесты импортируют генераторы страниц напрямую — им нужен prototype/ в sys.path."""
import os
import sys

PROTOTYPE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTOTYPE_DIR not in sys.path:
    sys.path.insert(0, PROTOTYPE_DIR)
```

- [ ] **Step 2: Написать падающий тест**

`prototype/tests/test_blog_titles.py`:

```python
"""Заголовок статьи может нести разметку подсветки — она уместна только в <h1>.

В карточке списка, в хлебных крошках и в JSON-LD та же строка обязана быть
обычным текстом, иначе читатель видит теги (баг: 13 статей блога, сентябрь 2026).
"""
import json
import re

import build_subpages as B

POST_WITH_MARKUP = {
    "type": "article",
    "alias": "blog-test-markup",
    "title": 'Past Simple для <span class="fxb-accent">детей</span>: простыми словами',
    "description": "Описание статьи без разметки.",
    "category": "Учим английский",
    "date": "2026-09-16",
    "reading_time": "7 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241540 0%,#662d92 100%)",
    "feed_alias": "blog",
    "feed_label": "Блог",
    "body": [("p", "Текст статьи.")],
}

PLAIN_TITLE = "Past Simple для детей: простыми словами"


def test_news_card_title_has_no_markup():
    card = B.news_card(POST_WITH_MARKUP)
    assert PLAIN_TITLE in card
    assert "&lt;span" not in card
    assert "fxb-accent" not in card


def test_breadcrumbs_title_has_no_markup():
    page = B.article_page(POST_WITH_MARKUP)
    crumbs = re.search(r'<nav class="fxb-breadcrumbs".*?</nav>', page, re.S).group(0)
    assert PLAIN_TITLE in crumbs
    assert "&lt;span" not in crumbs


def test_jsonld_names_are_plain_text():
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>',
        B.article_jsonld(POST_WITH_MARKUP), re.S)
    article, breadcrumb = json.loads(blocks[0]), json.loads(blocks[1])
    assert article["headline"] == PLAIN_TITLE
    assert breadcrumb["itemListElement"][2]["name"] == PLAIN_TITLE


def test_h1_keeps_accent_markup():
    page = B.article_page(POST_WITH_MARKUP)
    h1 = re.search(r"<h1[^>]*>.*?</h1>", page, re.S).group(0)
    assert '<span class="fxb-accent">детей</span>' in h1


def test_no_escaped_markup_in_any_rendered_page():
    dirty = []
    for fname, data in B.PAGES.items():
        html = B.render_page(data)
        if "&lt;span" in html or "&lt;b&gt;" in html or "&lt;/span&gt;" in html:
            dirty.append(fname)
    assert dirty == [], "страницы с голой разметкой в тексте: " + ", ".join(sorted(dirty))
```

- [ ] **Step 3: Запустить тест и убедиться, что он падает**

Run: `python3 -m pytest prototype/tests/test_blog_titles.py -q`
Expected: FAIL — 4 теста падают (`test_news_card_title_has_no_markup`, `test_breadcrumbs_title_has_no_markup`, `test_jsonld_names_are_plain_text`, `test_no_escaped_markup_in_any_rendered_page`), `test_h1_keeps_accent_markup` проходит.

- [ ] **Step 4: Добавить хелпер `strip_tags`**

В `prototype/build_subpages.py`, сразу перед `def faq_jsonld(items):` (строка ~744):

```python
def strip_tags(s):
    """Заголовок статьи может нести разметку подсветки (<span class="fxb-accent">).
    Она уместна только в <h1>; в карточке списка, крошках и JSON-LD нужен
    обычный текст, иначе теги видны читателю."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()
```

- [ ] **Step 5: Применить в четырёх местах**

`build_subpages.py:877` — `article_jsonld`, поле `headline`:

```python
        "headline": strip_tags(p["title"]),
```

`build_subpages.py:890` — `article_jsonld`, третий элемент `BreadcrumbList`:

```python
            {"@type": "ListItem", "position": 3, "name": strip_tags(p["title"]), "item": url},
```

`build_subpages.py:906` — `news_card`, заголовок карточки:

```python
        '<h2>' + escape(strip_tags(p["title"])) + '</h2>'
```

`build_subpages.py:959` — крошки в `article_page`:

```python
    h.append(crumbs_nav([("Главная", "/"), (p.get("feed_label", "Новости"), "/" + p.get("feed_alias", "novosti")), (strip_tags(p["title"]), None)]))
```

Строку 955 (`<h1 class="fxb-h1">' + p["title"] + '</h1>`) **не трогать** — подсветка там нужна.

- [ ] **Step 6: Запустить тесты — должны пройти**

Run: `python3 -m pytest prototype/tests/test_blog_titles.py -q`
Expected: PASS, 5 passed.

- [ ] **Step 7: Пересобрать страницы и проверить, что мусор исчез**

```bash
make build
grep -l '&lt;span class=&quot;fxb-accent&quot;&gt;' prototype/page_*.html | wc -l
```

Expected: `0` (до правки было 14 файлов).

- [ ] **Step 8: Коммит**

```bash
git add prototype/tests/conftest.py prototype/tests/test_blog_titles.py prototype/build_subpages.py prototype/page_blog.html prototype/page_blog_*.html
git commit -m "fix(blog): убираем голую разметку из заголовков в списке, крошках и JSON-LD"
```

---

### Task 2: Страницы курсов Spotlight 2–5

**Files:**
- Create: `prototype/pages_spotlight.py`
- Create: `prototype/assets/spotlight/` (4 обложки + 4 PDF)
- Create: `prototype/tests/test_spotlight_pages.py`
- Modify: `prototype/build_subpages.py` (импорт и регистрация в `PAGES`, рядом с блоком `import pages_wave25` на строке 7041)
- Modify: `prototype/build_static_site.py` (`PAGE_ALIASES`)

**Interfaces:**
- Consumes: `build_subpages.strip_tags` (задача 1).
- Produces:
  - `pages_spotlight.SPOTLIGHT_PAGES: dict[str, dict]` — ключ `page_spotlight_<N>_klass.html`, значение — словарь для `landing_page`.
  - `pages_spotlight._c` — модуль `presentations/spotlight/content.py`, уже импортированный с правильным `sys.path`; тесты берут эталонные данные курсов отсюда.
  - Алиасы: `spotlight-2-klass`, `spotlight-3-klass`, `spotlight-4-klass`, `spotlight-5-klass`.

- [ ] **Step 1: Скопировать ассеты**

```bash
mkdir -p prototype/assets/spotlight
cp assets/spotlight/sp2.jpg prototype/assets/spotlight/cover-sp2.jpg
cp assets/spotlight/sp3.jpg prototype/assets/spotlight/cover-sp3.jpg
cp assets/spotlight/sp4.jpg prototype/assets/spotlight/cover-sp4.jpg
cp assets/spotlight/sp5.jpg prototype/assets/spotlight/cover-sp5.jpg
for n in 2 3 4 5; do
  cp "presentations/spotlight/Spotlight-${n}-kurs-dlya-${n}-klassa-Foxinburg.pdf" \
     "prototype/assets/spotlight/spotlight-${n}-klass-foxinburg.pdf"
done
ls -la prototype/assets/spotlight/
```

Expected: 8 файлов. `prototype/assets/` целиком копируется в `dist/assets/` (`build_static_site.py:835-837`), отдельный код копирования не нужен.

- [ ] **Step 2: Написать падающий тест**

`prototype/tests/test_spotlight_pages.py`:

```python
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
```

- [ ] **Step 3: Запустить тест и убедиться, что он падает**

Run: `python3 -m pytest prototype/tests/test_spotlight_pages.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pages_spotlight'`.

- [ ] **Step 4: Написать `pages_spotlight.py`**

`prototype/pages_spotlight.py`:

```python
# -*- coding: utf-8 -*-
"""Страницы курсов Spotlight 2–5 — английский по школьному учебнику.

Тексты курсов НЕ дублируются: читаем те же словари SP2–SP5, PRICE и SCHOOL,
по которым собираются презентации для родителей
(presentations/spotlight/content.py). Правка текста курса — только там,
сайт и презентация меняются вместе.
"""
from __future__ import annotations

import os
import sys

_SPOTLIGHT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "presentations", "spotlight")
if _SPOTLIGHT_DIR not in sys.path:
    sys.path.insert(0, _SPOTLIGHT_DIR)

import content as _c  # noqa: E402  (путь добавляется выше)

PRICE = _c.PRICE
ASSETS = "/assets/spotlight"

# Градиенты hero — по одному на класс, чтобы четыре страницы не выглядели
# копиями друг друга.
_GRADIENTS = {
    2: "linear-gradient(135deg,#2e1a47 0%,#5a2d8f 55%,#7b4fc0 100%)",
    3: "linear-gradient(135deg,#241a36 0%,#662d92 55%,#8a4fb8 100%)",
    4: "linear-gradient(135deg,#241540 0%,#5f2a8c 55%,#c24712 100%)",
    5: "linear-gradient(135deg,#392852 0%,#7b4fc0 55%,#662d92 100%)",
}

_WHY_ICONS = ("clock", "group", "book", "pencil")
_RESULT_ICONS = ("book", "pencil", "chat", "headset", "target", "star")


def _modules_section(deck):
    """Программа года: все модули учебника по порядку — таблицей-списком."""
    rows = []
    for num, name, topic, detail, is_starter in deck["modules"]:
        badge = "★" if is_starter else num
        mod = " fxb-sp-mod--starter" if is_starter else ""
        rows.append(
            '<div class="fxb-sp-mod' + mod + '">'
            '<span class="fxb-sp-mod-n">' + badge + '</span>'
            '<div class="fxb-sp-mod-txt"><b>' + name + '</b>'
            '<span class="fxb-sp-mod-topic">' + topic + '</span>'
            '<p>' + detail + '</p></div></div>')
    return (
        '<section class="fxb-section" id="fxb-modules"><div class="fxb-wrap">'
        '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Программа года</span>'
        '<h2 class="fxb-h2">Все модули учебника — <span class="fxb-accent">по порядку</span></h2>'
        '<p class="fxb-lead">Курс повторяет структуру учебника. Каждый модуль — лексика, '
        'грамматика, чтение, аудирование, говорение и письмо по одной теме.</p></div>'
        '<div class="fxb-sp-mods">' + "".join(rows) + '</div>'
        '</div></section>')


def _textbook_section(deck):
    """Учебник, уровень и цифры года + кнопка скачивания презентации."""
    grade = deck["grade"]
    stats = "".join(
        '<div class="fxb-sp-stat"><b>' + value + '</b><span>' + label + '</span></div>'
        for value, label in deck["focus_stat"])
    return (
        '<section class="fxb-section fxb-bg-light"><div class="fxb-wrap">'
        '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Учебник</span>'
        '<h2 class="fxb-h2">Работаем по <span class="fxb-accent">Spotlight ' + str(grade) + '</span></h2></div>'
        '<div class="fxb-sp-book">'
        '<img class="fxb-sp-cover" src="' + ASSETS + '/cover-sp' + str(grade) + '.jpg" '
        'alt="Учебник «Английский в фокусе» Spotlight ' + str(grade) + '" width="420" height="595" loading="lazy">'
        '<div class="fxb-sp-book-txt">'
        '<p><b>«Английский в фокусе» · Spotlight ' + str(grade) + '</b><br>' + deck["authors"] + '</p>'
        '<p>Издательство «Просвещение» и Express Publishing, редакция ФГОС 2021.</p>'
        '<p><b>Уровень по итогам года:</b> ' + deck["level"] + '</p>'
        '<p>Spotlight — самый распространённый УМК по английскому в российских школах. '
        'Мы берём <b>тот же учебник</b> и подкрепляем его отработкой каждого правила, '
        'чтением вслух, говорением и домашними заданиями, на которые в школе не хватает времени.</p>'
        '<div class="fxb-sp-stats">' + stats + '</div>'
        '<a class="fxb-btn-sec fxb-sp-pdf" href="' + ASSETS + '/spotlight-' + str(grade) +
        '-klass-foxinburg.pdf" target="_blank" rel="noopener">Скачать презентацию курса (PDF)</a>'
        '</div></div></div></section>')


def _grammar_section(deck):
    """Грамматика и фоника года — два списка рядом."""
    grammar = "".join("<li>" + x + "</li>" for x in deck["grammar"])
    phonics = "".join("<li>" + x + "</li>" for x in deck["phonics"])
    extra = "".join(
        '<div class="fxb-sp-extra"><b>' + title + '</b><p>' + text + '</p></div>'
        for title, text in deck["extra"])
    return (
        '<section class="fxb-section"><div class="fxb-wrap">'
        '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Отрабатываем</span>'
        '<h2 class="fxb-h2">Грамматика и чтение — <span class="fxb-accent">до автоматизма</span></h2></div>'
        '<div class="fxb-sp-cols">'
        '<div class="fxb-sp-col"><h3>Грамматика года</h3><ul class="fxb-sp-list">' + grammar + '</ul></div>'
        '<div class="fxb-sp-col"><h3>Чтение и произношение</h3><ul class="fxb-sp-list">' + phonics + '</ul></div>'
        '</div><div class="fxb-sp-extras">' + extra + '</div>'
        '</div></section>')


SPOTLIGHT_CSS = """
<style>
#fxb-page .fxb-sp-mods{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}
#fxb-page .fxb-sp-mod{display:flex;gap:16px;align-items:flex-start;background:#fff;border:1.5px solid rgba(102,45,146,.08);border-radius:18px;padding:22px 24px}
#fxb-page .fxb-sp-mod--starter{border-color:var(--yellow);background:linear-gradient(135deg,#fffdf0,#fff)}
#fxb-page .fxb-sp-mod-n{flex:0 0 auto;width:38px;height:38px;border-radius:12px;display:grid;place-items:center;font-weight:900;font-size:16px;color:#fff;background:var(--purple-2)}
#fxb-page .fxb-sp-mod--starter .fxb-sp-mod-n{background:var(--orange)}
#fxb-page .fxb-sp-mod-txt b{display:block;font-size:17px;color:var(--ink);margin-bottom:2px}
#fxb-page .fxb-sp-mod-topic{display:block;font-size:13px;font-weight:700;color:var(--purple-2);margin-bottom:8px}
#fxb-page .fxb-sp-mod-txt p{font-size:14px;color:var(--muted);line-height:1.55}
#fxb-page .fxb-sp-book{display:grid;grid-template-columns:280px 1fr;gap:42px;align-items:start}
#fxb-page .fxb-sp-cover{width:100%;height:auto;border-radius:14px;box-shadow:0 18px 44px -18px rgba(57,40,82,.45)}
#fxb-page .fxb-sp-book-txt p{font-size:15px;color:var(--muted);line-height:1.65;margin-bottom:14px}
#fxb-page .fxb-sp-book-txt b{color:var(--ink)}
#fxb-page .fxb-sp-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}
#fxb-page .fxb-sp-stat b{display:block;font-size:26px;font-weight:900;color:var(--purple-2);line-height:1.1}
#fxb-page .fxb-sp-stat span{font-size:12.5px;color:var(--muted);font-weight:600}
#fxb-page .fxb-sp-pdf{display:inline-block;margin-top:6px}
#fxb-page .fxb-sp-cols{display:grid;grid-template-columns:repeat(2,1fr);gap:32px}
#fxb-page .fxb-sp-col h3{font-size:18px;color:var(--ink);margin-bottom:14px}
#fxb-page .fxb-sp-list{list-style:none;padding:0;margin:0}
#fxb-page .fxb-sp-list li{position:relative;padding:9px 0 9px 26px;font-size:14.5px;color:var(--muted);border-bottom:1px solid rgba(102,45,146,.06)}
#fxb-page .fxb-sp-list li::before{content:"";position:absolute;left:0;top:15px;width:12px;height:12px;border-radius:50%;border:2px solid var(--purple-2);background:rgba(102,45,146,.08)}
#fxb-page .fxb-sp-extras{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:32px}
#fxb-page .fxb-sp-extra{background:rgba(102,45,146,.05);border-radius:16px;padding:20px 22px}
#fxb-page .fxb-sp-extra b{display:block;font-size:15px;color:var(--ink);margin-bottom:6px}
#fxb-page .fxb-sp-extra p{font-size:13.5px;color:var(--muted);line-height:1.55}
@media(max-width:900px){
  #fxb-page .fxb-sp-mods,#fxb-page .fxb-sp-cols,#fxb-page .fxb-sp-extras{grid-template-columns:1fr}
  #fxb-page .fxb-sp-book{grid-template-columns:1fr;gap:26px}
  #fxb-page .fxb-sp-cover{max-width:260px}
  #fxb-page .fxb-sp-stats{grid-template-columns:repeat(2,1fr)}
}
</style>
"""


def _page(deck):
    grade = deck["grade"]
    alias = "spotlight-%d-klass" % grade
    url = "https://dymova-english.ru/" + alias
    title_plain = "Английский по Spotlight %d — курс для %d класса" % (grade, grade)
    subject = "Spotlight %d — английский для %d класса" % (grade, grade)
    return {
        "hero_grad": _GRADIENTS[grade],
        "eyebrow": "Spotlight %d · %s · %s" % (grade, deck["klass"], deck["age"]),
        "h1": 'Английский по учебнику <span class="fxb-accent">Spotlight %d</span>' % grade,
        "sub": deck["lead"],
        "cta_label": "Записаться на курс",
        "feat_kicker": "Зачем нужен курс",
        "feat_title": 'Почему в школе <span class="fxb-accent">не хватает времени</span>',
        "feat_lead": "Не «ещё один кружок», а поддержка по школьной программе: "
                     "идём по тому же учебнику на шаг впереди класса.",
        "features": [
            (_WHY_ICONS[i % len(_WHY_ICONS)], head, text)
            for i, (head, text) in enumerate(deck["why"])
        ],
        "facts_title": "Коротко о курсе",
        "facts": [
            ("calendar", "9 месяцев", "Сентябрь — май, параллельно школе"),
            ("clock", "2 раза в неделю", "Занятие 60 минут"),
            ("group", "До 7 человек", "Мини-группы по уровню"),
            ("cap", deck["level"].split("(")[0].strip(), "Уровень по итогам года"),
        ],
        "adv_kicker": "Результат курса",
        "adv_title": 'К концу года ребёнок <span class="fxb-accent">сможет сам</span>',
        "adv_lead": "Главная цель курса — самостоятельность: чтобы вечером ребёнок сам открыл "
                    "учебник, понял задание и выполнил его без взрослого.",
        "advantages": [
            (_RESULT_ICONS[i % len(_RESULT_ICONS)], head, text)
            for i, (head, text) in enumerate(deck["results"])
        ],
        "extra_sections": [
            _textbook_section(deck),
            _modules_section(deck),
            _grammar_section(deck),
        ],
        "prices": True,
        "price_title": "Стоимость курса Spotlight %d" % grade,
        "price_lead": "Цена за месяц занятий в мини-группе. Учебные материалы включены.",
        "price_cards": [
            ("Курс Spotlight %d" % grade, "",
             PRICE["now"] + ' ₽<span>/мес</span>',
             "Вместо " + PRICE["old"] + " ₽ · 2 занятия в неделю по 60 минут"),
            ("За одно занятие", " fxb-price-tag--orange",
             PRICE["per_lesson"] + " ₽",
             "8 занятий в месяц в мини-группе до 7 человек"),
            ("Экономия за год", "",
             PRICE["save_year"] + " ₽",
             PRICE["save_month"] + " ₽ каждый месяц учебного года"),
        ],
        "faq_title": "Частые вопросы про курс Spotlight %d" % grade,
        "faq": [
            ("Мы и так учим английский в школе — зачем ещё курс?",
             "В школе английский идёт 2 раза в неделю на подгруппу около 15 человек: "
             "за 45 минут ребёнок отвечает один-два раза. Мы идём по тому же учебнику "
             "в мини-группе до 7 человек и доводим каждое правило до речи, а не только до упражнения."),
            ("Вы идёте по тому же учебнику, что и школа?",
             "Да. Курс построен на «Английском в фокусе» Spotlight %d (%s), "
             "редакция ФГОС 2021 — тот же учебник, что и в школе, только на шаг впереди." % (grade, deck["authors"])),
            ("Какой уровень будет у ребёнка к концу года?",
             "%s — это соответствует требованиям ФГОС к %s и международной шкале CEFR."
             % (deck["level"], deck["klass"])),
            ("Сколько стоит и сколько занятий в месяц?",
             "%s ₽ в месяц вместо %s ₽ — 2 занятия в неделю по 60 минут, %s ₽ за занятие. "
             "За учебный год экономия %s ₽." % (PRICE["now"], PRICE["old"], PRICE["per_lesson"], PRICE["save_year"])),
            ("Ребёнок отстал от класса — успеет догнать?",
             "Перед стартом проводим бесплатную диагностику: смотрим, какие темы модуля "
             "просели, и подбираем группу по реальному уровню, а не по номеру класса."),
        ],
        "lead_subject": subject,
        "lead_hero_window": "Блок героя",
        "lead_final_window": "Финальный блок",
        "cta_title": 'Запишитесь на курс <span class="fxb-accent">Spotlight %d</span>' % grade,
        "cta_text": "Оставьте заявку — расскажем расписание групп, проведём бесплатную "
                    "диагностику и подберём подходящий уровень.",
        "extra_jsonld": [
            _course_jsonld(title_plain, deck, url),
            _breadcrumb_jsonld(grade, alias),
        ],
        "extra_css": SPOTLIGHT_CSS,
    }


def _course_jsonld(name, deck, url):
    # build_subpages импортирует этот модуль, поэтому импорт здесь, а не наверху:
    # к моменту вызова build_subpages уже определил strip_tags, course_jsonld и
    # breadcrumb_jsonld (строки 744, 800, 815), а сама строка `import pages_spotlight`
    # стоит ниже них. Перенос импорта наверх или строки импорта выше — циклическая ссылка.
    import build_subpages as B
    description = B.strip_tags(deck["lead"])
    return B.course_jsonld(name, description, url,
                           offer_name="Курс Spotlight %d" % deck["grade"],
                           price=PRICE["now"].replace(" ", ""))


def _breadcrumb_jsonld(grade, alias):
    import build_subpages as B
    return B.breadcrumb_jsonld([
        ("Главная", "https://dymova-english.ru/"),
        ("Курсы английского", "https://dymova-english.ru/kursy-v-dolgoprudnom"),
        ("Spotlight %d — %d класс" % (grade, grade), "https://dymova-english.ru/" + alias),
    ])


SPOTLIGHT_PAGES = {
    "page_spotlight_%d_klass.html" % deck["grade"]: _page(deck)
    for deck in _c.DECKS
}
```

- [ ] **Step 5: Поддержать `extra_css` в `landing_page`**

`landing_page` подключает CSS секций по флагам. Для страниц Spotlight нужен свой блок стилей. В `prototype/build_subpages.py`, в `landing_page`, сразу после `h.append(CSS)` (строка ~731) добавить:

```python
    if p.get("extra_css"):
        h.append(p["extra_css"])
```

- [ ] **Step 6: Зарегистрировать страницы**

В `prototype/build_subpages.py`, после строки `import pages_wave25  # волна 25: ...` (строка 7041) добавить:

```python
import pages_spotlight  # курсы Spotlight 2–5: английский по школьному учебнику
```

Строка обязана стоять **после** определений `strip_tags`, `breadcrumb_jsonld` и
`course_jsonld` (строки 744, 800, 815): `pages_spotlight` вызывает их на этапе
импорта. Блок `import pages_wave*` на строке 7024 этому условию удовлетворяет.

И сразу после блока `pages_prep.register_prep_sections()` (строка ~7046) добавить:

```python
PAGES.update(pages_spotlight.SPOTLIGHT_PAGES)
```

- [ ] **Step 7: Зарегистрировать алиасы в статической сборке**

В `prototype/build_static_site.py`, в словарь `PAGE_ALIASES`, рядом с `"page_reading.html": "reading",` добавить:

```python
    "page_spotlight_2_klass.html": "spotlight-2-klass",
    "page_spotlight_3_klass.html": "spotlight-3-klass",
    "page_spotlight_4_klass.html": "spotlight-4-klass",
    "page_spotlight_5_klass.html": "spotlight-5-klass",
```

- [ ] **Step 8: Запустить тесты страниц Spotlight**

Run: `python3 -m pytest prototype/tests/test_spotlight_pages.py -q`
Expected: проходят `test_four_pages_registered`, `test_page_has_price_modules_and_pdf`, `test_page_lists_every_module_of_the_textbook`, `test_page_has_lead_button_and_jsonld`, `test_aliases_registered_for_static_build`. Падают `test_links_in_header_and_footer`, `test_cards_in_enrollment_block_survive_cms`, `test_course_options_in_every_lead_form` — их закрывают задачи 3 и 4.

- [ ] **Step 9: Собрать и глазами проверить одну страницу**

```bash
make build
python3 prototype/build_static_site.py
open prototype/dist/spotlight-2-klass/index.html
```

Expected: страница открывается, видны обложка учебника, все 6 модулей, цена 7 600 ₽ вместо 9 000 ₽, кнопка скачивания PDF работает.

- [ ] **Step 10: Коммит**

```bash
git add prototype/pages_spotlight.py prototype/assets/spotlight prototype/tests/test_spotlight_pages.py \
        prototype/build_subpages.py prototype/build_static_site.py prototype/page_spotlight_*.html
git commit -m "feat(spotlight): страницы курсов Spotlight 2–5 по школьному учебнику"
```

---

### Task 3: Ссылки в шапке и подвале, карточки в блоке записи

**Files:**
- Modify: `prototype/main_combined_v7.html` (меню «Программы», подвал, блок `#fxb-pricing`)
- Modify: `prototype/block_shapka.html` (меню «Программы»)
- Modify: `prototype/block_footer.html` (колонка «Программы»)
- Modify: `prototype/block_header_unified.html` (меню «Программы», легаси)
- Test: `prototype/tests/test_spotlight_pages.py` (тесты уже написаны в задаче 2)

**Interfaces:**
- Consumes: алиасы `spotlight-<N>-klass` из задачи 2.
- Produces: ничего для следующих задач.

- [ ] **Step 1: Убедиться, что тесты связей падают**

Run: `python3 -m pytest prototype/tests/test_spotlight_pages.py -q -k "header_and_footer or enrollment_block"`
Expected: FAIL, 2 failed.

- [ ] **Step 2: Добавить группу в меню «Программы»**

В `prototype/main_combined_v7.html`, `prototype/block_shapka.html` и `prototype/block_header_unified.html` найти в панели дропдауна «Программы» строку `<span class="fxb-dd-head">Курсы</span>` и вставить **перед** ней:

```html
            <span class="fxb-dd-head">Школьная программа</span>
            <a href="/spotlight-2-klass">Spotlight 2 — 2 класс</a>
            <a href="/spotlight-3-klass">Spotlight 3 — 3 класс</a>
            <a href="/spotlight-4-klass">Spotlight 4 — 4 класс</a>
            <a href="/spotlight-5-klass">Spotlight 5 — 5 класс</a>
```

В `block_header_unified.html` отступы могут отличаться — сохранить те, что в файле.

- [ ] **Step 3: Добавить ссылки в подвал**

В `prototype/block_footer.html` (колонка «Программы», после `<a href="/grammar">Курс по грамматике</a>`, строка ~64) и в той же колонке подвала внутри `prototype/main_combined_v7.html` вставить:

```html
        <a href="/spotlight-2-klass">Spotlight 2 (2 класс)</a>
        <a href="/spotlight-3-klass">Spotlight 3 (3 класс)</a>
        <a href="/spotlight-4-klass">Spotlight 4 (4 класс)</a>
        <a href="/spotlight-5-klass">Spotlight 5 (5 класс)</a>
```

- [ ] **Step 4: Добавить ряд карточек в блок записи**

Блок `#fxb-pricing` на главной перерисовывается из LMS: скрипт в конце `main_combined_v7.html` заменяет `innerHTML` у `.fxb-cards`. Поэтому карточки Spotlight кладём **отдельным рядом после** `.fxb-cards`, внутри той же `.fxb-section`.

В `prototype/main_combined_v7.html` найти конец блока `#fxb-pricing`:

```html
      </div>
    </div>
  </div>
</div>
```

(закрытие последней `.fxb-card`, затем `.fxb-cards`, затем `.fxb-section`, затем `#fxb-pricing`).

Вставить между `</div>` закрывающим `.fxb-cards` и `</div>` закрывающим `.fxb-section`:

```html
    <!-- Курсы по школьному учебнику Spotlight. Ряд живёт ВНЕ .fxb-cards:
         тот блок перерисовывается из LMS (home.pricing) и затёр бы эти карточки. -->
    <div class="fxb-sp-row">
      <h3 class="fxb-sp-row-title">Английский по школьному учебнику Spotlight</h3>
      <p class="fxb-sp-row-sub">Идём по тому же учебнику, что и в школе, — на шаг впереди класса</p>
      <div class="fxb-cards fxb-cards-spotlight">
        <div class="fxb-card">
          <div class="fxb-card-head">
            <h3>Spotlight 2</h3>
            <span class="fxb-card-loc">2 класс · 7–9 лет</span>
          </div>
          <div class="fxb-card-body">
            <ul class="fxb-feat-list">
              <li>Тот же учебник, что и в школе</li>
              <li>2 занятия в неделю по 60 минут</li>
              <li>Мини-группы до 7 человек</li>
              <li>Чтение по правилам и домашка без взрослого</li>
            </ul>
            <div class="fxb-price-row">
              <span class="fxb-price">7 600 &#8381;/мес</span>
              <span class="fxb-price-note">вместо 9 000 &#8381;</span>
            </div>
            <a class="fxb-card-btn" data-fxb-zayavka data-fxb-subject="Spotlight 2 — английский для 2 класса" data-fxb-window="Запись на новый учебный год" role="button" tabindex="0">Записаться</a>
            <a class="fxb-card-more" href="/spotlight-2-klass">Подробнее о курсе</a>
          </div>
        </div>
        <div class="fxb-card">
          <div class="fxb-card-head">
            <h3>Spotlight 3</h3>
            <span class="fxb-card-loc">3 класс · 8–10 лет</span>
          </div>
          <div class="fxb-card-body">
            <ul class="fxb-feat-list">
              <li>Тот же учебник, что и в школе</li>
              <li>2 занятия в неделю по 60 минут</li>
              <li>Мини-группы до 7 человек</li>
              <li>Времена и чтение текстов по программе</li>
            </ul>
            <div class="fxb-price-row">
              <span class="fxb-price">7 600 &#8381;/мес</span>
              <span class="fxb-price-note">вместо 9 000 &#8381;</span>
            </div>
            <a class="fxb-card-btn" data-fxb-zayavka data-fxb-subject="Spotlight 3 — английский для 3 класса" data-fxb-window="Запись на новый учебный год" role="button" tabindex="0">Записаться</a>
            <a class="fxb-card-more" href="/spotlight-3-klass">Подробнее о курсе</a>
          </div>
        </div>
        <div class="fxb-card">
          <div class="fxb-card-head">
            <h3>Spotlight 4</h3>
            <span class="fxb-card-loc">4 класс · 9–11 лет</span>
          </div>
          <div class="fxb-card-body">
            <ul class="fxb-feat-list">
              <li>Тот же учебник, что и в школе</li>
              <li>2 занятия в неделю по 60 минут</li>
              <li>Мини-группы до 7 человек</li>
              <li>Подготовка к ВПР и переходу в среднюю школу</li>
            </ul>
            <div class="fxb-price-row">
              <span class="fxb-price">7 600 &#8381;/мес</span>
              <span class="fxb-price-note">вместо 9 000 &#8381;</span>
            </div>
            <a class="fxb-card-btn" data-fxb-zayavka data-fxb-subject="Spotlight 4 — английский для 4 класса" data-fxb-window="Запись на новый учебный год" role="button" tabindex="0">Записаться</a>
            <a class="fxb-card-more" href="/spotlight-4-klass">Подробнее о курсе</a>
          </div>
        </div>
        <div class="fxb-card">
          <div class="fxb-card-head">
            <h3>Spotlight 5</h3>
            <span class="fxb-card-loc">5 класс · 10–12 лет</span>
          </div>
          <div class="fxb-card-body">
            <ul class="fxb-feat-list">
              <li>Тот же учебник, что и в школе</li>
              <li>2 занятия в неделю по 60 минут</li>
              <li>Мини-группы до 7 человек</li>
              <li>Мягкий переход к средней школе</li>
            </ul>
            <div class="fxb-price-row">
              <span class="fxb-price">7 600 &#8381;/мес</span>
              <span class="fxb-price-note">вместо 9 000 &#8381;</span>
            </div>
            <a class="fxb-card-btn" data-fxb-zayavka data-fxb-subject="Spotlight 5 — английский для 5 класса" data-fxb-window="Запись на новый учебный год" role="button" tabindex="0">Записаться</a>
            <a class="fxb-card-more" href="/spotlight-5-klass">Подробнее о курсе</a>
          </div>
        </div>
      </div>
    </div>
```

- [ ] **Step 5: Добавить стили ряда**

В `prototype/main_combined_v7.html`, в `<style>` блока `#fxb-pricing`, в конец (перед `</style>`) добавить:

```css
#fxb-pricing .fxb-sp-row{margin-top:56px;padding-top:48px;border-top:1px solid rgba(102,45,146,.12)}
#fxb-pricing .fxb-sp-row-title{font-size:clamp(20px,2.4vw,28px);font-weight:900;color:var(--purple);margin-bottom:8px}
#fxb-pricing .fxb-sp-row-sub{font-size:15px;color:#6f6280;font-weight:500;margin-bottom:32px}
#fxb-pricing .fxb-cards-spotlight{grid-template-columns:repeat(4,1fr);gap:20px}
#fxb-pricing .fxb-cards-spotlight .fxb-card-head{min-height:74px;padding-top:24px}
#fxb-pricing .fxb-card-more{display:block;text-align:center;margin-top:10px;font-size:13px;font-weight:700;color:var(--purple-2);text-decoration:none}
#fxb-pricing .fxb-card-more:hover{text-decoration:underline}
@media(max-width:1100px){#fxb-pricing .fxb-cards-spotlight{grid-template-columns:repeat(2,1fr)}}
@media(max-width:860px){#fxb-pricing .fxb-cards-spotlight{grid-template-columns:1fr;max-width:420px;margin:0 auto}}
```

- [ ] **Step 6: Запустить тесты**

Run: `python3 -m pytest prototype/tests/test_spotlight_pages.py -q -k "header_and_footer or enrollment_block"`
Expected: PASS, 2 passed.

- [ ] **Step 7: Проверить, что LMS не затирает новый ряд**

```bash
python3 prototype/build_static_site.py
open prototype/dist/index.html
```

Expected: в блоке «Запись на новый учебный год» после карточек из LMS виден отдельный ряд «Английский по школьному учебнику Spotlight» с четырьмя карточками. Ряд остаётся на месте и через несколько секунд после загрузки (когда отработал подхват из LMS).

- [ ] **Step 8: Коммит**

```bash
git add prototype/main_combined_v7.html prototype/block_shapka.html prototype/block_footer.html prototype/block_header_unified.html
git commit -m "feat(spotlight): курсы Spotlight в меню, подвале и блоке записи"
```

---

### Task 4: Курсы Spotlight в выпадающих списках заявки

Список курсов дублируется в трёх местах: модалка заявки для подстраниц (`build_course_pages.py`), её копия на главной (`main_combined_v7.html`) и форма брони `#fxbEnrollForm`. Обобщённую опцию «Языки (английский, немецкий, китайский)» заменяем конкретными языками — администратору нужно видеть язык сразу.

**Files:**
- Modify: `prototype/build_course_pages.py:335-340` (список `<option>`), `:420-428` (`fxbZcoursePreset`)
- Modify: `prototype/main_combined_v7.html` (модалка ~4313, `fxbZcoursePreset` ~4377, `#fxbEnrollForm` ~1697)
- Test: `prototype/tests/test_spotlight_pages.py::test_course_options_in_every_lead_form` (уже написан)

**Interfaces:**
- Consumes: значения `Spotlight N — английский для N класса` — те же строки, что в `data-fxb-subject` карточек (задача 3) и в `lead_subject` страниц (задача 2).
- Produces: ничего для следующих задач.

- [ ] **Step 1: Убедиться, что тест падает**

Run: `python3 -m pytest prototype/tests/test_spotlight_pages.py -q -k lead_form`
Expected: FAIL, 1 failed.

- [ ] **Step 2: Обновить список в модалке подстраниц**

В `prototype/build_course_pages.py` заменить пять строк `<option>` (строки 336–340) на:

```python
            '<option value="Пока не определился" selected>Пока не определился</option>'
            '<option value="Английский язык">Английский язык</option>'
            '<option value="Немецкий язык">Немецкий язык</option>'
            '<option value="Китайский язык">Китайский язык</option>'
            '<option value="Испанский язык">Испанский язык</option>'
            '<option value="Подготовка к школе">Подготовка к школе</option>'
            '<option value="Spotlight 2 — английский для 2 класса">Spotlight 2 — английский для 2 класса</option>'
            '<option value="Spotlight 3 — английский для 3 класса">Spotlight 3 — английский для 3 класса</option>'
            '<option value="Spotlight 4 — английский для 4 класса">Spotlight 4 — английский для 4 класса</option>'
            '<option value="Spotlight 5 — английский для 5 класса">Spotlight 5 — английский для 5 класса</option>'
            '<option value="Интенсивы">Интенсивы</option>'
            '<option value="Репетиторские услуги (1–4 класс)">Репетиторские услуги (1–4 класс)</option>'
```

- [ ] **Step 3: Обновить `fxbZcoursePreset` в модалке подстраниц**

В `prototype/build_course_pages.py`, в `ZAYAVKA_JS`, заменить тело `fxbZcoursePreset` (строки ~424–429) на:

```javascript
    var fxbZcoursePreset=function(subject){
      var sp=subject.match(/Spotlight\s*([2-5])/i);
      if(sp)return 'Spotlight '+sp[1]+' — английский для '+sp[1]+' класса';
      if(/интенсив/i.test(subject))return 'Интенсивы';
      if(/подготовк[аи]\s+к\s+школе/i.test(subject))return 'Подготовка к школе';
      if(/репетитор/i.test(subject))return 'Репетиторские услуги (1–4 класс)';
      if(/немецк/i.test(subject))return 'Немецкий язык';
      if(/китайск/i.test(subject))return 'Китайский язык';
      if(/испанск/i.test(subject))return 'Испанский язык';
      if(/английск|язык/i.test(subject))return 'Английский язык';
      return '';
    };
```

Порядок проверок важен: Spotlight ловится первым, иначе строку «Spotlight 2 — английский для 2 класса» перехватит ветка про английский.

- [ ] **Step 4: Повторить обе правки в копии на главной**

В `prototype/main_combined_v7.html`: в модалке `#fxb-zayavka-modal` (строка ~4313) заменить тот же набор `<option>` на список из шага 2 (в одну строку, как весь блок модалки), и заменить `fxbZcoursePreset` (строка ~4377) на версию из шага 3.

- [ ] **Step 5: Обновить форму брони `#fxbEnrollForm`**

В `prototype/main_combined_v7.html`, строки ~1697–1703, заменить `<select name="course">` на:

```html
            <select name="course" class="fxb-input fxb-select" aria-label="Выбор курса">
              <option value="Пока не определился" selected>Курс: пока не определился</option>
              <option value="Английский язык">Английский язык</option>
              <option value="Немецкий язык">Немецкий язык</option>
              <option value="Китайский язык">Китайский язык</option>
              <option value="Испанский язык">Испанский язык</option>
              <option value="Подготовка к школе">Подготовка к школе</option>
              <option value="Spotlight 2 — английский для 2 класса">Spotlight 2 — английский для 2 класса</option>
              <option value="Spotlight 3 — английский для 3 класса">Spotlight 3 — английский для 3 класса</option>
              <option value="Spotlight 4 — английский для 4 класса">Spotlight 4 — английский для 4 класса</option>
              <option value="Spotlight 5 — английский для 5 класса">Spotlight 5 — английский для 5 класса</option>
              <option value="Интенсивы">Интенсивы</option>
              <option value="Репетиторские услуги (1–4 класс)">Репетиторские услуги (1–4 класс)</option>
            </select>
```

- [ ] **Step 6: Пересобрать и прогнать все тесты Spotlight**

```bash
make build
python3 -m pytest prototype/tests -q
```

Expected: PASS, все тесты `test_spotlight_pages.py` и `test_blog_titles.py` зелёные.

- [ ] **Step 7: Проверить руками, что предвыбор работает**

```bash
python3 prototype/build_static_site.py
open prototype/dist/spotlight-3-klass/index.html
```

Expected: клик по «Записаться на курс» открывает модалку, в поле «Какой курс интересует» уже выбрано «Spotlight 3 — английский для 3 класса».

- [ ] **Step 8: Коммит**

```bash
git add prototype/build_course_pages.py prototype/main_combined_v7.html prototype/page_*.html
git commit -m "feat(leads): курсы Spotlight и отдельные языки в выпадающих списках заявки"
```

---

### Task 5: Секция «Неделя знакомства» на главной

**Files:**
- Create: `prototype/tests/test_event_block.py`
- Modify: `prototype/main_combined_v7.html` (новая секция между hero и блоком записи, перед строкой `<!-- ===== 2. Запись на новый учебный год (CTA) ... -->`)

**Interfaces:**
- Consumes: механизм `data-fxb-zayavka` / `#fxb-zayavka-modal` (существует).
- Produces: `data-fxb-subject` вида `Неделя знакомства — <направление>` — те же строки использует лендинг из задачи 6.

- [ ] **Step 1: Написать падающий тест**

`prototype/tests/test_event_block.py`:

```python
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


def test_event_section_present_on_main():
    html = read("main_combined_v7.html")
    assert 'id="fxb-event"' in html
    assert 'data-fxb-event-until="2026-09-26T23:59:59+03:00"' in html


def test_event_section_states_the_offer():
    html = read("main_combined_v7.html")
    section = html[html.find('id="fxb-event"'):]
    section = section[:section.find('id="fxb-enrollment"')]
    assert "2 125" in section, "нет суммарной выгоды"
    assert "1 125" in section, "нет старой цены пробного"
    assert "1 000" in section or "1000" in section, "нет бонусов"
    assert "21" in section and "26 сентября" in section


def test_every_try_button_opens_a_lead_with_a_subject():
    html = read("main_combined_v7.html")
    section = html[html.find('id="fxb-event"'):]
    section = section[:section.find('id="fxb-enrollment"')]
    buttons = re.findall(r"<[^>]*data-fxb-zayavka[^>]*>", section)
    assert len(buttons) >= 5, "4 направления + общая кнопка"
    for tag in buttons:
        subject = re.search(r'data-fxb-subject="([^"]+)"', tag)
        assert subject, "кнопка без data-fxb-subject: " + tag
        assert subject.group(1).startswith("Неделя знакомства")
    for subject in SUBJECTS:
        assert 'data-fxb-subject="%s"' % subject in section


def test_event_section_hides_itself_after_the_promo():
    html = read("main_combined_v7.html")
    section = html[html.find('id="fxb-event"'):]
    section = section[:section.find('id="fxb-enrollment"')]
    assert "fxbEventUntil" in section or "data-fxb-event-until" in section
    assert ".hidden" in section or "hidden=true" in section or "hidden = true" in section


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
```

- [ ] **Step 2: Запустить тест и убедиться, что он падает**

Run: `python3 -m pytest prototype/tests/test_event_block.py -q`
Expected: FAIL — все 6 тестов падают.

- [ ] **Step 3: Вставить секцию на главную**

В `prototype/main_combined_v7.html` найти строку:

```html
<!-- ===== 2. Запись на новый учебный год (CTA) (block_cta_enrollment.html) ===== -->
```

и вставить **перед** ней:

```html
<!-- ===== 1.5. Неделя знакомства (акция 21–26 сентября 2026) =====
     Временный блок. Скрывается сам после даты в data-fxb-event-until.
     Чтобы убрать совсем — удалить этот блок целиком вместе с его <style> и <script>. -->
<section id="fxb-event" data-fxb-event-until="2026-09-26T23:59:59+03:00">
  <div class="fxb-ev-bg" aria-hidden="true">
    <img class="fxb-ev-decor" src="/assets/brand/fox-head-yellow.webp" alt="" loading="lazy">
  </div>
  <div class="fxb-ev-wrap">
    <div class="fxb-ev-top">
      <span class="fxb-ev-kicker">🦊 Неделя знакомства с Фоксинбург · 21–26 сентября</span>
      <div class="fxb-ev-timer" id="fxbEventTimer" aria-live="polite"></div>
    </div>

    <h2 class="fxb-ev-title">Выгода до <span class="fxb-ev-sum">2 125 &#8381;</span></h2>
    <p class="fxb-ev-lead">Не выбирайте школу вслепую. Приходите на бесплатное пробное занятие,
      познакомьтесь с педагогом и форматом — и только потом решайте.</p>

    <div class="fxb-ev-gifts">
      <div class="fxb-ev-gift">
        <span class="fxb-ev-gift-ic">🎁</span>
        <div>
          <b>Пробное занятие <span class="fxb-ev-free">0 &#8381;</span> <s>1 125 &#8381;</s></b>
          <p>Любое направление на выбор, 60 минут, без обязательств.</p>
        </div>
      </div>
      <div class="fxb-ev-gift">
        <span class="fxb-ev-gift-ic">⭐</span>
        <div>
          <b>+ 1 000 &#8381; бонусов</b>
          <p>На оплату первого абонемента, если решите продолжить обучение.</p>
        </div>
      </div>
    </div>

    <div class="fxb-ev-dirs">
      <article class="fxb-ev-dir">
        <span class="fxb-ev-flag">🇬🇧</span>
        <h3>Английский язык</h3>
        <p>От 2 лет до взрослых — игра, разговор и школьная программа.</p>
        <button class="fxb-ev-btn" type="button" data-fxb-zayavka data-fxb-subject="Неделя знакомства — Английский язык" data-fxb-window="Неделя знакомства">Попробовать</button>
      </article>
      <article class="fxb-ev-dir">
        <span class="fxb-ev-flag">🇨🇳</span>
        <h3>Китайский язык</h3>
        <p>Тоны и иероглифы без зубрёжки, мини-группы и утренние потоки.</p>
        <button class="fxb-ev-btn" type="button" data-fxb-zayavka data-fxb-subject="Неделя знакомства — Китайский язык" data-fxb-window="Неделя знакомства">Попробовать</button>
      </article>
      <article class="fxb-ev-dir">
        <span class="fxb-ev-flag">🇩🇪</span>
        <h3>Немецкий язык</h3>
        <p>Второй иностранный для школьников — мягкий старт после английского.</p>
        <button class="fxb-ev-btn" type="button" data-fxb-zayavka data-fxb-subject="Неделя знакомства — Немецкий язык" data-fxb-window="Неделя знакомства">Попробовать</button>
      </article>
      <article class="fxb-ev-dir">
        <span class="fxb-ev-flag">🎒</span>
        <h3>Подготовка к школе</h3>
        <p>Чтение, счёт и письмо для будущих первоклассников 5–7 лет.</p>
        <button class="fxb-ev-btn" type="button" data-fxb-zayavka data-fxb-subject="Неделя знакомства — Подготовка к школе" data-fxb-window="Неделя знакомства">Попробовать</button>
      </article>
    </div>

    <div class="fxb-ev-foot">
      <ul class="fxb-ev-check">
        <li>Подходит ли ребёнку выбранное направление</li>
        <li>Получается ли найти контакт с педагогом</li>
        <li>Комфортно ли ребёнку в нашем формате</li>
        <li>Насколько ему интересны занятия</li>
        <li>Какой формат обучения подойдёт именно ему</li>
      </ul>
      <div class="fxb-ev-cta">
        <button class="fxb-ev-btn fxb-ev-btn--main" type="button" data-fxb-zayavka data-fxb-subject="Неделя знакомства — пробное занятие 0 ₽" data-fxb-window="Неделя знакомства">Попробовать бесплатно</button>
        <a class="fxb-ev-more" href="/nedelya-znakomstva">Подробнее об акции</a>
        <p class="fxb-ev-note">Количество мест на пробные занятия ограничено.</p>
      </div>
    </div>
  </div>
</section>

<style>
#fxb-event{--purple:#392852;--purple-2:#662d92;--orange:#c24712;--yellow:#fcf951;
  font-family:'Montserrat',Arial,sans-serif;-webkit-font-smoothing:antialiased;position:relative;overflow:hidden;
  background:radial-gradient(900px 520px at 12% 0%,rgba(194,71,18,.55),transparent 60%),linear-gradient(135deg,#241540 0%,#5f2a8c 58%,#3a1c5e 100%);
  padding:76px 24px}
#fxb-event *{box-sizing:border-box;margin:0;padding:0}
#fxb-event .fxb-ev-bg{position:absolute;inset:0;pointer-events:none}
#fxb-event .fxb-ev-decor{position:absolute;right:-70px;top:-50px;width:420px;opacity:.06;transform:rotate(14deg)}
#fxb-event .fxb-ev-wrap{max-width:1200px;margin:0 auto;position:relative;z-index:1}
#fxb-event .fxb-ev-top{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-bottom:26px}
#fxb-event .fxb-ev-kicker{display:inline-flex;align-items:center;gap:8px;background:rgba(255,255,255,.12);color:#fff;font-weight:800;font-size:13px;letter-spacing:.04em;padding:9px 18px;border-radius:100px}
#fxb-event .fxb-ev-timer{display:flex;gap:10px;color:#fff;font-weight:800;font-size:13px}
#fxb-event .fxb-ev-timer b{display:block;font-size:22px;line-height:1.1;color:var(--yellow)}
#fxb-event .fxb-ev-timer span{display:inline-block;text-align:center;background:rgba(255,255,255,.1);border-radius:12px;padding:8px 14px;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.06em}
#fxb-event .fxb-ev-title{font-size:clamp(32px,5.4vw,68px);font-weight:900;color:#fff;line-height:1.02;letter-spacing:-.02em;margin-bottom:14px}
#fxb-event .fxb-ev-sum{color:var(--yellow)}
#fxb-event .fxb-ev-lead{max-width:640px;font-size:17px;line-height:1.6;color:rgba(255,255,255,.82);font-weight:500;margin-bottom:38px}
#fxb-event .fxb-ev-gifts{display:grid;grid-template-columns:repeat(2,1fr);gap:20px;margin-bottom:40px}
#fxb-event .fxb-ev-gift{display:flex;gap:18px;align-items:flex-start;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);border-radius:20px;padding:24px 26px;backdrop-filter:blur(8px)}
#fxb-event .fxb-ev-gift-ic{font-size:30px;line-height:1}
#fxb-event .fxb-ev-gift b{display:block;font-size:20px;color:#fff;margin-bottom:6px;font-weight:800}
#fxb-event .fxb-ev-free{color:var(--yellow)}
#fxb-event .fxb-ev-gift s{color:rgba(255,255,255,.5);font-weight:600;font-size:16px}
#fxb-event .fxb-ev-gift p{font-size:14px;color:rgba(255,255,255,.72);line-height:1.55;font-weight:500}
#fxb-event .fxb-ev-dirs{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-bottom:44px}
#fxb-event .fxb-ev-dir{background:#fff;border-radius:20px;padding:26px 24px;display:flex;flex-direction:column;gap:10px;transition:transform .25s,box-shadow .25s}
#fxb-event .fxb-ev-dir:hover{transform:translateY(-4px);box-shadow:0 22px 48px -18px rgba(0,0,0,.45)}
#fxb-event .fxb-ev-flag{font-size:28px;line-height:1}
#fxb-event .fxb-ev-dir h3{font-size:18px;font-weight:800;color:var(--purple)}
#fxb-event .fxb-ev-dir p{font-size:13.5px;color:#6f6280;line-height:1.55;font-weight:500;flex:1}
#fxb-event .fxb-ev-btn{width:100%;cursor:pointer;border:0;font-family:inherit;font-weight:800;font-size:14px;padding:13px 18px;border-radius:12px;color:#fff;background:linear-gradient(135deg,var(--purple-2),#7a3db0);transition:transform .18s,box-shadow .18s}
#fxb-event .fxb-ev-btn:hover{transform:translateY(-1px);box-shadow:0 12px 26px -10px rgba(0,0,0,.5)}
#fxb-event .fxb-ev-foot{display:grid;grid-template-columns:1fr 360px;gap:44px;align-items:center}
#fxb-event .fxb-ev-check{list-style:none}
#fxb-event .fxb-ev-check li{position:relative;padding:9px 0 9px 30px;color:rgba(255,255,255,.86);font-size:15px;font-weight:500}
#fxb-event .fxb-ev-check li::before{content:"✓";position:absolute;left:0;top:9px;color:var(--yellow);font-weight:900}
#fxb-event .fxb-ev-cta{text-align:center}
#fxb-event .fxb-ev-btn--main{background:linear-gradient(135deg,var(--orange),#e8594f);font-size:16px;padding:17px 26px}
#fxb-event .fxb-ev-more{display:inline-block;margin-top:14px;color:var(--yellow);font-weight:700;font-size:14px;text-decoration:none;border-bottom:1px solid rgba(252,249,81,.4)}
#fxb-event .fxb-ev-note{margin-top:12px;font-size:12.5px;color:rgba(255,255,255,.6);font-weight:500}
@media(max-width:1000px){
  #fxb-event .fxb-ev-dirs{grid-template-columns:repeat(2,1fr)}
  #fxb-event .fxb-ev-foot{grid-template-columns:1fr;gap:28px}
}
@media(max-width:640px){
  #fxb-event{padding:56px 20px}
  #fxb-event .fxb-ev-gifts,#fxb-event .fxb-ev-dirs{grid-template-columns:1fr}
  #fxb-event .fxb-ev-top{flex-direction:column;align-items:flex-start}
}
</style>

<script>
(function(){
  /* Акция живёт до даты в data-fxb-event-until. После неё блок прячется сам,
     чтобы сайт не пришлось срочно править в день окончания. */
  var ev=document.getElementById('fxb-event');
  if(!ev)return;
  var until=new Date(ev.getAttribute('data-fxb-event-until')).getTime();
  var timer=document.getElementById('fxbEventTimer');
  var plural=function(n,forms){
    var n10=n%10,n100=n%100;
    if(n10===1&&n100!==11)return forms[0];
    if(n10>=2&&n10<=4&&(n100<10||n100>=20))return forms[1];
    return forms[2];
  };
  var tick=function(){
    var left=until-Date.now();
    if(left<=0){ev.hidden=true;return;}
    var d=Math.floor(left/86400000);
    var h=Math.floor(left%86400000/3600000);
    var m=Math.floor(left%3600000/60000);
    if(timer){
      timer.innerHTML='<span><b>'+d+'</b>'+plural(d,['день','дня','дней'])+'</span>'
        +'<span><b>'+h+'</b>'+plural(h,['час','часа','часов'])+'</span>'
        +'<span><b>'+m+'</b>'+plural(m,['минута','минуты','минут'])+'</span>';
    }
  };
  tick();
  setInterval(tick,30000);
})();
</script>
```

- [ ] **Step 4: Запустить тесты секции**

Run: `python3 -m pytest prototype/tests/test_event_block.py -q -k "section or try_button or hides"`
Expected: PASS, 4 passed. Два теста лендинга (`test_landing_registered_and_aliased`, `test_landing_repeats_the_offer_and_collects_leads`) продолжают падать — их закрывает задача 6.

- [ ] **Step 5: Проверить глазами, включая мобильную ширину**

```bash
python3 prototype/build_static_site.py
open prototype/dist/index.html
```

Expected: секция стоит сразу под hero; таймер показывает реальный остаток до 26 сентября; клик по «Попробовать» у китайского открывает модалку с заголовком «Заявка — Неделя знакомства — Китайский язык». В окне шириной 400 px карточки становятся в одну колонку, горизонтального скролла нет.

- [ ] **Step 6: Коммит**

```bash
git add prototype/main_combined_v7.html prototype/tests/test_event_block.py
git commit -m "feat(event): секция «Неделя знакомства» на главной с заявкой по направлениям"
```

---

### Task 6: Лендинг `/nedelya-znakomstva`

**Files:**
- Modify: `prototype/build_subpages.py` (новая страница в `PAGES`, рядом с другими лендингами)
- Modify: `prototype/build_static_site.py` (`PAGE_ALIASES`)
- Test: `prototype/tests/test_event_block.py` (тесты уже написаны в задаче 5)

**Interfaces:**
- Consumes: `build_subpages.strip_tags` (задача 1), те же `data-fxb-subject`, что в задаче 5.
- Produces: алиас `nedelya-znakomstva`.

- [ ] **Step 1: Убедиться, что тесты лендинга падают**

Run: `python3 -m pytest prototype/tests/test_event_block.py -q -k landing`
Expected: FAIL, 2 failed — `KeyError: 'page_nedelya_znakomstva.html'`.

- [ ] **Step 2: Добавить страницу**

В `prototype/build_subpages.py`, после блока `PAGES["page_grammar.html"] = {...}` (заканчивается около строки 1496), вставить:

```python
# Акция «Неделя знакомства» 21–26 сентября 2026. Временный лендинг под рекламу:
# после окончания акции страницу можно удалить вместе с её алиасом в
# build_static_site.py — секция на главной прячется сама по дате.
PAGES["page_nedelya_znakomstva.html"] = {
    "hero_grad": "linear-gradient(135deg,#241540 0%,#5f2a8c 58%,#c24712 100%)",
    "eyebrow": "Акция 21–26 сентября 2026",
    "h1": 'Неделя знакомства: выгода до <span class="fxb-accent">2 125 ₽</span>',
    "sub": "Бесплатное пробное занятие вместо 1 125 ₽ и 1 000 бонусов на первый абонемент. "
           "Сначала попробуйте школу — потом решайте.",
    "cta_label": "Попробовать бесплатно",
    "feat_kicker": "Что мы дарим",
    "feat_title": "Два подарка новым ученикам",
    "feat_lead": "Предложение действует с 21 по 26 сентября 2026 года для тех, кто ещё не занимался в Фоксинбурге.",
    "features": [
        ("star", "Пробное занятие 0 ₽", "Обычная стоимость — 1 125 ₽. По акции — бесплатно: "
                                        "60 минут с педагогом, любое направление на выбор."),
        ("trophy", "1 000 бонусов на обучение", "Если после пробного решите продолжить, "
                                                "подарим 1 000 ₽ на оплату первого абонемента."),
        ("compass", "Без обязательств", "Сначала знакомитесь со школой, педагогом и форматом — "
                                        "и только потом принимаете решение."),
        ("clock", "Только 6 дней", "С 21 по 26 сентября. Количество мест на пробные занятия ограничено."),
    ],
    "facts_title": "Коротко об акции",
    "facts": [
        ("calendar", "21–26 сентября", "Шесть дней для новых учеников"),
        ("target", "0 ₽", "Пробное занятие вместо 1 125 ₽"),
        ("star", "1 000 ₽", "Бонусы на первый абонемент"),
        ("group", "4 направления", "Английский, китайский, немецкий, подготовка к школе"),
    ],
    "formats_kicker": "Направления",
    "formats_title": "Выберите, что попробовать",
    "formats_lead": "Пробное занятие можно взять по любому из четырёх направлений.",
    "formats": [
        ("globe", "Английский язык", "От 2 лет до взрослых: игра и разговор для малышей, "
                                     "школьная программа и экзамены — для школьников."),
        ("globe", "Китайский язык", "Тоны и иероглифы без зубрёжки, мини-группы до 7 человек, "
                                    "есть утренние группы для второй смены."),
        ("globe", "Немецкий язык", "Второй иностранный для школьников — мягкий старт "
                                   "после английского, с опорой на знакомую грамматику."),
        ("cap", "Подготовка к школе", "Чтение, счёт, письмо и усидчивость для будущих "
                                      "первоклассников 5–7 лет."),
    ],
    "adv_kicker": "Пробное занятие",
    "adv_title": 'Что вы узнаете за <span class="fxb-accent">60 минут</span>',
    "adv_lead": "Пробное занятие нужно не нам, а вам: это способ проверить школу до оплаты.",
    "advantages": [
        ("target", "Подходит ли направление", "Увидите, как ребёнок реагирует на язык "
                                              "и насколько ему интересно."),
        ("heart", "Найдётся ли контакт с педагогом", "Для ребёнка это решает больше, "
                                                     "чем программа и учебники."),
        ("group", "Комфортно ли в формате", "Мини-группа до 7 человек, занятие полностью "
                                            "на изучаемом языке."),
        ("compass", "Какой формат подойдёт", "Группа или индивидуально, офлайн в филиале "
                                             "или онлайн — подскажем после занятия."),
    ],
    "faq_title": "Частые вопросы про Неделю знакомства",
    "faq": [
        ("Кто может участвовать в акции?",
         "Новые ученики Фоксинбурга — те, кто ещё не занимался у нас. "
         "Акция действует с 21 по 26 сентября 2026 года."),
        ("Сколько стоит пробное занятие по акции?",
         "0 ₽. Обычная стоимость пробного занятия — 1 125 ₽."),
        ("Как получить 1 000 бонусов?",
         "Бонусы начисляем, если после пробного занятия вы решите продолжить обучение: "
         "1 000 ₽ пойдут в счёт оплаты первого абонемента."),
        ("Я обязан продолжить обучение после пробного?",
         "Нет. Пробное занятие бесплатное и ни к чему не обязывает — в этом и смысл: "
         "сначала посмотреть школу, потом решать."),
        ("Какие направления можно попробовать?",
         "Английский, китайский, немецкий языки и подготовку к школе — одно направление на выбор."),
        ("Что делать, если удобное время уже занято?",
         "Оставьте заявку — администратор предложит ближайшие свободные окна. "
         "Количество мест на пробные занятия ограничено, поэтому лучше записаться заранее."),
    ],
    "lead_subject": "Неделя знакомства — пробное занятие 0 ₽",
    "lead_hero_window": "Лендинг акции: блок героя",
    "lead_final_window": "Лендинг акции: финальный блок",
    "cta_title": 'Запишитесь на бесплатное пробное <span class="fxb-accent">до 26 сентября</span>',
    "cta_text": "Оставьте заявку — администратор свяжется с вами, подберёт удобное время "
                "и расскажет про направления.",
    "extra_jsonld": [
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Неделя знакомства", SITE + "/nedelya-znakomstva"),
        ]),
        webpage_jsonld(
            "WebPage",
            "Неделя знакомства с Фоксинбург — пробное занятие бесплатно 21–26 сентября",
            "Акция школы Фоксинбург 21–26 сентября 2026: бесплатное пробное занятие вместо "
            "1 125 ₽ и 1 000 бонусов на первый абонемент. Английский, китайский, немецкий, "
            "подготовка к школе.",
            SITE + "/nedelya-znakomstva",
        ),
    ],
}
```

- [ ] **Step 3: Зарегистрировать алиас**

В `prototype/build_static_site.py`, в `PAGE_ALIASES`, рядом с `"page_diagnostika.html": "diagnostika",` добавить:

```python
    "page_nedelya_znakomstva.html": "nedelya-znakomstva",
```

- [ ] **Step 4: Запустить все тесты**

Run: `python3 -m pytest prototype/tests -q`
Expected: PASS, все тесты трёх файлов зелёные.

- [ ] **Step 5: Полная сборка и проверка**

```bash
make all
python3 prototype/build_static_site.py
open prototype/dist/nedelya-znakomstva/index.html
```

Expected: лендинг открывается, шапка и подвал на месте, кнопки открывают модалку заявки, страница есть в `prototype/dist/sitemap.xml`.

- [ ] **Step 6: Коммит**

```bash
git add prototype/build_subpages.py prototype/build_static_site.py prototype/page_nedelya_znakomstva.html
git commit -m "feat(event): лендинг /nedelya-znakomstva под рекламу акции"
```

---

## Финальная проверка

- [ ] `python3 -m pytest prototype/tests -q` — всё зелёное.
- [ ] `make all && python3 prototype/build_static_site.py` — без ошибок и без строк `!! пропускаю`.
- [ ] `grep -l '&lt;span class=&quot;fxb-accent&quot;&gt;' prototype/page_*.html | wc -l` → `0`.
- [ ] `grep -c 'spotlight-2-klass' prototype/dist/sitemap.xml` → не ноль; то же для `nedelya-znakomstva`.
- [ ] Глазами: главная, `/nedelya-znakomstva`, `/spotlight-2-klass`, `/blog` — на ширине 1440 px и 400 px.
- [ ] Одна заявка отправлена с тестовыми данными, администратор подтвердил получение в MAX.
