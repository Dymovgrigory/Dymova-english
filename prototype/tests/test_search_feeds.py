"""Фиды сниппетов: онлайн-образование, вакансии, исполнители."""
import xml.etree.ElementTree as ET
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "seo_schema"


def root(name):
    return ET.parse(SCHEMA / name).getroot()


def test_online_education_is_one_live_course():
    shop = root("feed_education_online.xml").find("shop")
    assert len(shop.find("name").text) <= 30
    assert shop.find("picture").text.endswith(".png")
    offers = shop.findall("offers/offer")
    assert [o.get("id") for o in offers] == ["course-online"]
    offer = offers[0]
    assert offer.find("url").text == "https://dymova-english.ru/online-zanyatiya"
    assert offer.find("categoryId").text == "20001"
    assert offer.find("price").text == "0"
    monthly = offer.find("param[@name='Ежемесячная цена']").text
    assert monthly == "9000"
    # кириллическая «с» — латинская 'c' уже один раз давала PARAM_INVALID_VALUE
    assert offer.find("param[@name='Формат обучения']").text == "В группе с наставником"
    assert len(offer.findall("param[@name='План']")) >= 3


def test_vacancies_match_the_open_roles():
    offers = root("feed_vacancies.xml").findall("shop/offers/offer")
    names = {o.find("name").text for o in offers}
    assert names == {"Преподаватель английского языка", "Администратор языковой школы"}
    pictures = [o.find("picture").text for o in offers]
    assert len(pictures) == len(set(pictures))


def test_services_do_not_reuse_the_online_course_url():
    offer = root("feed_services.xml").find("shop/offers/offer")
    assert offer.find("url").text == "https://dymova-english.ru/repetitor"
    assert offer.find("param[@name='Рейтинг']").text == "0"
    assert offer.find("price").text == "2500"
    assert offer.find("price").get("from") == "true"
