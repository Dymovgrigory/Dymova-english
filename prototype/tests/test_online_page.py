"""Страница /online-zanyatiya: маршрут по России, две заявки, без клуба и домашки."""
import build_subpages as B


def page():
    return B.render_page(B.PAGES["page_online_zanyatiya.html"])


def test_programs_and_rhythm():
    html = page()
    for needle in (
        "С 5 лет",
        "My Level 1",
        "My Level 4",
        "Get Involved A1+",
        "Get Involved B2",
        "2 раза в неделю",
        "60 минут",
        "9 000",
        "8 200",
        "1 125",
        "0 ₽",
    ):
        assert needle in html, needle
    assert "45–60" not in html


def test_two_lead_subjects():
    html = page()
    assert 'data-fxb-subject="Онлайн-диагностика"' in html
    assert 'data-fxb-subject="Запись на онлайн-занятия"' in html
    assert "data-fxb-age" in html
    assert "fxb-track" in html


def test_excludes_club_and_homework_help():
    html = page().lower()
    assert "разговорный клуб" not in html
    assert "носител" not in html
    assert "домашк" not in html


def test_supporting_articles_registered():
    aliases = {
        "novosti-nabor-onlajn-anglijskij-rossiya",
        "blog-onlajn-anglijskij-dlya-detej-s-5-let",
        "blog-my-level-get-involved-onlajn",
        "blog-onlajn-diagnostika-anglijskogo",
    }
    found = {p["alias"] for p in B.PAGES.values() if isinstance(p, dict) and p.get("alias")}
    assert aliases <= found
    for alias in aliases:
        html = B.render_page(B.PAGES["page_" + alias.replace("-", "_") + ".html"])
        assert "/online-zanyatiya" in html
        assert "разговорный клуб" not in html.lower()
