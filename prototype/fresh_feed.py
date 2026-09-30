# -*- coding: utf-8 -*-
"""RSS 2.0 для Яндекс Вебмастера «Свежее и актуальное».

Яндекс индексирует из этого фида только сообщения за последние 8 дней.
Обязательны title, link, pubDate и yandex:full-text. Заголовок — как h1
на странице, без точки в конце и без названия источника.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from html import unescape
from pathlib import Path
from xml.sax.saxutils import escape

import build_subpages as B

SITE = "https://dymova-english.ru"
MSK = timezone(timedelta(hours=3))
TAG_RE = re.compile(r"<[^>]+>")
PHONE_RE = re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
WINDOW_DAYS = 8


def plain(value: str) -> str:
    text = unescape(TAG_RE.sub(" ", value))
    text = PHONE_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def full_text(post: dict) -> str:
    parts: list[str] = []
    for kind, value in post.get("body") or []:
        if kind in ("h2", "h3", "p"):
            parts.append(plain(value))
        elif kind == "ul":
            parts.extend(plain(item) for item in value)
    for question, answer in post.get("faq") or []:
        parts.append(plain(question))
        parts.append(plain(answer))
    return "\n\n".join(part for part in parts if part)


def title_ok(title: str) -> str:
    text = plain(title).rstrip(" .")
    if not text or text == text.upper() or len(text) > 200:
        raise ValueError(f"заголовок не проходит правила Яндекса: {text!r}")
    return text


def fresh_posts(today: date | None = None) -> list[dict]:
    today = today or date.today()
    oldest = today - timedelta(days=WINDOW_DAYS)
    found = []
    for post in B.PAGES.values():
        if not isinstance(post, dict) or post.get("type") != "article":
            continue
        published = date.fromisoformat(post["date"])
        if published < oldest or published > today:
            continue
        found.append(post)
    found.sort(key=lambda post: (post["date"], post["alias"]), reverse=True)
    # один URL — один материал
    seen = set()
    unique = []
    for post in found:
        if post["alias"] in seen:
            continue
        seen.add(post["alias"])
        unique.append(post)
    return unique


def pub_date(day: str) -> str:
    moment = datetime.strptime(day, "%Y-%m-%d").replace(hour=12, minute=0, tzinfo=MSK)
    return format_datetime(moment)


def genre(post: dict) -> str:
    if post["alias"].startswith("novosti-"):
        return "message"
    return "article"


def build_xml(today: date | None = None) -> str:
    posts = fresh_posts(today)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss xmlns:yandex="http://news.yandex.ru" xmlns:media="http://search.yahoo.com/mrss/" version="2.0">',
        "  <channel>",
        f"    <title>{escape('Фоксинбург')}</title>",
        f"    <link>{SITE}/</link>",
        f"    <description>{escape('Новости и статьи школы Фоксинбург: набор, программы и занятия.')}</description>",
        "    <language>ru</language>",
    ]
    for post in posts:
        url = f"{SITE}/{post['alias']}"
        if len(url) > 243:
            raise ValueError(f"слишком длинный URL: {url}")
        text = full_text(post)
        if len(text) < 80:
            raise ValueError(f"слишком короткий текст: {post['alias']}")
        lines.extend([
            "    <item>",
            f"      <title>{escape(title_ok(post['title']))}</title>",
            f"      <link>{escape(url)}</link>",
            f"      <description>{escape(plain(post['description']))}</description>",
            f"      <category>{escape(plain(post['category']))}</category>",
            f"      <pubDate>{pub_date(post['date'])}</pubDate>",
            f"      <yandex:genre>{genre(post)}</yandex:genre>",
            f"      <yandex:full-text>{escape(text)}</yandex:full-text>",
            "    </item>",
        ])
    lines.extend(["  </channel>", "</rss>", ""])
    return "\n".join(lines)


def write(path: Path | str, today: date | None = None) -> int:
    xml = build_xml(today)
    Path(path).write_text(xml, encoding="utf-8")
    return xml.count("<item>")


if __name__ == "__main__":
    dest = Path(__file__).resolve().parent / "seo_schema" / "feed_fresh.xml"
    print(write(dest), dest)
