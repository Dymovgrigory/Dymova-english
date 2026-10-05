"""Фиды сниппетов: онлайн-образование."""
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
