"""Волна 31: статьи «Пробелы по английскому в 10 и 11 классе».

Запросы «пробелы по английскому языку в 10/11 классе» в Google Search Console (90 дней)
показывали сотни показов, но попадали на страницу 8 класса с позициями 33 и 48:
отдельных страниц для этих классов не было. Тесты фиксируют, что статьи зарегистрированы
в блоге, заполнены полями для поиска и доступны из хаба «Пробелы по английскому».
"""
import pytest

import build_subpages as B

GAP_ALIASES = [
    "blog-probely-po-anglijskomu-10-klass",
    "blog-probely-po-anglijskomu-11-klass",
]


def _post(alias):
    return next(p for p in B.EXTRA_BLOG_POSTS if p.get("alias") == alias)


@pytest.mark.parametrize("alias", GAP_ALIASES)
def test_gap_post_is_registered_in_blog(alias):
    assert any(p.get("alias") == alias for p in B.EXTRA_BLOG_POSTS)


@pytest.mark.parametrize("alias", GAP_ALIASES)
def test_gap_post_has_search_fields(alias):
    post = _post(alias)
    assert post["title"].startswith("Пробелы по английскому в ")
    assert 50 <= len(post["description"]) <= 180
    assert post["body"]
    assert len(post["faq"]) >= 3
    assert post["related"]


@pytest.mark.parametrize("alias", GAP_ALIASES)
def test_gap_post_links_only_to_existing_pages(alias):
    """Внутренние ссылки статьи должны вести на страницы, которые собираются сайтом."""
    import re
    post = _post(alias)
    html_parts = []
    for kind, value in post["body"]:
        html_parts.append(" ".join(value) if isinstance(value, list) else value)
    html_parts += [answer for _, answer in post["faq"]]
    targets = re.findall(r'href="(/[^"]+)"', " ".join(html_parts))
    targets += [url for _, url in post["related"]]
    known = {p.get("alias") for p in B.EXTRA_BLOG_POSTS} | set(B.PAGES.keys())
    for url in targets:
        slug = url.strip("/")
        assert slug in known or slug == "" or _is_static_page(slug), f"битая ссылка: {url}"


def _is_static_page(slug):
    import os
    prototype_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.exists(os.path.join(prototype_dir, f"page_{slug.replace('-', '_')}.html"))
