"""Страница /russkij-kak-inostrannyj: только подтверждённая цена и формат."""
import build_subpages as B


def page():
    return B.render_page(B.PAGES["page_russkij_kak_inostrannyj.html"])


def test_price_and_places():
    html = page()
    for needle in (
        "3 000",
        "60 минут",
        "индивидуальн",
        "Лихачёвск",
        "Ракетостроител",
        "Л035-01255-50/01387611",
        'data-fxb-subject="РКИ: запись на занятие"',
        'data-fxb-subject="РКИ: первая встреча"',
    ):
        assert needle in html, needle


def test_does_not_invent_group_or_textbook_line():
    html = page().lower()
    assert "9 000" not in html
    assert "my level" not in html
    assert "разговорный клуб" not in html
    assert "групповой абонемент не" in html or "не набираем" in html


def test_rki_articles_link_the_page():
    aliases = (
        "blog-rki-s-chego-nachat",
        "novosti-rki-russkij-kak-inostrannyj",
        "blog-kak-vybrat-onlajn-shkolu-anglijskogo",
    )
    for alias in aliases:
        html = B.render_page(B.PAGES["page_" + alias.replace("-", "_") + ".html"])
        assert "/russkij-kak-inostrannyj" in html or "/online-zanyatiya" in html
        assert "3 000" in html or "9 000" in html
