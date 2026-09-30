"""RSS «Свежее и актуальное»: только 8 дней, обязательные поля Яндекса."""
import xml.etree.ElementTree as ET
from datetime import date

import fresh_feed as F


NS = {"yandex": "http://news.yandex.ru"}


def feed(today):
    xml = F.build_xml(today)
    return xml, ET.fromstring(xml)


def test_only_last_eight_days_and_required_fields():
    xml, root = feed(date(2026, 9, 30))
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    items = root.findall("./channel/item")
    assert len(items) == 7
    aliases = {item.find("link").text.rsplit("/", 1)[-1] for item in items}
    assert "blog-kak-vybrat-onlajn-shkolu-anglijskogo" in aliases
    assert "novosti-rki-russkij-kak-inostrannyj" in aliases
    assert "blog-onlajn-diagnostika-anglijskogo" in aliases
    for item in items:
        title = item.find("title").text
        assert title and not title.endswith(".")
        assert title != title.upper()
        assert "Фоксинбург" not in title
        assert item.find("link").text.startswith("https://dymova-english.ru/")
        assert "+0300" in item.find("pubDate").text
        text = item.find("yandex:full-text", NS).text
        assert len(text) > 200
        assert "http" not in text
        assert "8 993" not in text
    assert "2026-09-17" not in xml
    assert "blog-razgovornyj-klub" not in xml


def test_drops_posts_older_than_the_window():
    _, root = feed(date(2026, 10, 12))
    assert root.findall("./channel/item") == []
