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
