#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обновление ленты отзывов Яндекс Карт для блока #fxb-yarev на dymova-english.ru.

У Яндекса нет публичного API отзывов (проверено: OAuth-каталог Яндекс ID не
содержит scope'а на отзывы; «API Справочника» (sprav:all) закрыт, кабинетный
yandex.ru/sprav/api требует браузерные сессионные cookie). Поэтому скрипт
снимает отзывы с ОТКРЫТЫХ страниц Яндекс Карт (SSR-разметка, как видит её
любой посетитель без авторизации) — те же данные, что отдаёт Карты-бэкенд.

Что делает:
  1. Скачивает страницы отзывов обоих филиалов Фоксинбурга.
  2. Парсит отзывы (автор, оценка, дата, текст).
  3. Оставляет только 5★ с развёрнутым текстом (>= MIN_TEXT_LEN), дедуп по автору.
  4. Отбирает TOP_N карточек (с миксом филиалов) и раскладывает на 2 ряда ленты.
  5. Пишет wow/yandex_reviews.json — его подхватывает JS блока #fxb-yarev.

Запуск локально (пишет в prototype/wow/):
  python3 ymaps_reviews_fetch.py

На сервере (пишет сразу в каталог сайта, крон раз в сутки):
  python3 /opt/foxinburg/ymaps_reviews_fetch.py --out /home/yc-user/foxinburg-site/wow/yandex_reviews.json

Только stdlib, внешних зависимостей нет.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.request

ORG_PAGES = [
    # (url страницы отзывов, название филиала для карточки)
    ("https://yandex.ru/maps/org/foksinburg/112008441352/reviews/", "филиал Ракетостроителей, 9к3"),
    ("https://yandex.ru/maps/org/foksinburg/162408588499/reviews/", "филиал Лихачёвский, 76к1"),
]

MIN_TEXT_LEN = 170   # «большое описание»
TOP_N = 15           # карточек в ленте (7 + 8 по рядам)
MIN_SECOND_BRANCH = 3  # минимум карточек второго филиала
MAX_CARD_TEXT = 430  # обрезка очень длинных текстов для карточки

# Авторы, которых не показываем на сайте (служебные/странные аккаунты)
SKIP_AUTHORS = {
    "ГБУЗ ДОЛГОПРУДНЫЙ",
    "194558 Г.",
    "Валерий",
    "ByLo4ka tt.me",
    "Елена Безносова",  # отзыв про садик со старым хендлом @dymova.english.club
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "ru-RU,ru;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _clean(fragment: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    return re.sub(r"\s+", " ", text).strip()


def parse_reviews(page: str) -> list[dict]:
    """Разбирает SSR-разметку страницы отзывов Яндекс Карт."""
    out = []
    for block in re.split(r'<div class="business-review-view"', page)[1:]:
        block = block[:80000]
        m = re.search(r'business-review-view__author-name[^>]*>(.*?)</span>', block, re.S)
        author = _clean(m.group(1)) if m else None
        m = re.search(r'<meta itemprop="ratingValue" content="(\d+)"', block)
        if m:
            rating = int(m.group(1))
        else:
            rating = len(re.findall(r'business-rating-badge-view__star[^"]*?_full', block))
        m = re.search(r'business-review-view__date[^>]*>.*?<span[^>]*>(.*?)</span>', block, re.S)
        date = _clean(m.group(1)) if m else None
        m = re.search(r'business-review-view__body[^>]*>(.*?)</div>', block, re.S)
        text = _clean(m.group(1)) if m else None
        if author and text:
            out.append({"author": author, "rating": rating, "date": date, "text": text})
    return out


def select(all_reviews: list[dict]) -> list[dict]:
    """Фильтр 5★ + длинные, дедуп по автору, микс филиалов, обрезка текстов."""
    pool = [
        r for r in all_reviews
        if r["rating"] == 5
        and len(r["text"]) >= MIN_TEXT_LEN
        and r["author"] not in SKIP_AUTHORS
    ]
    seen, picked = set(), []
    for r in sorted(pool, key=lambda x: -len(x["text"])):
        if r["author"] in seen:
            continue
        seen.add(r["author"])
        picked.append(r)
        if len(picked) >= TOP_N:
            break
    # гарантируем микс филиалов
    second = ORG_PAGES[1][1]
    have = sum(1 for r in picked if r["branch"] == second)
    if have < MIN_SECOND_BRANCH:
        for r in sorted((x for x in pool if x["branch"] == second), key=lambda x: -len(x["text"])):
            if r in picked:
                continue
            picked[-1] = r
            have += 1
            if have >= MIN_SECOND_BRANCH:
                break
    for r in picked:
        if len(r["text"]) > MAX_CARD_TEXT:
            r["text"] = r["text"][:MAX_CARD_TEXT].rsplit(" ", 1)[0].rstrip(".,;:") + "…"
    return picked


def main() -> int:
    ap = argparse.ArgumentParser()
    default_out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "wow", "yandex_reviews.json")
    ap.add_argument("--out", default=default_out, help="куда писать JSON")
    args = ap.parse_args()

    all_reviews: list[dict] = []
    for url, branch in ORG_PAGES:
        try:
            page = fetch(url)
        except Exception as e:  # сеть/бан — не роняем весь прогон
            print(f"!! не удалось скачать {url}: {e}", file=sys.stderr)
            continue
        reviews = parse_reviews(page)
        print(f"{branch}: отзывов на странице — {len(reviews)}")
        for r in reviews:
            r["branch"] = branch
        all_reviews.extend(reviews)
        time.sleep(2)  # вежливая пауза между запросами

    if not all_reviews:
        print("!! отзывов не получено — JSON не трогаю", file=sys.stderr)
        return 1

    picked = select(all_reviews)
    if len(picked) < 6:
        print(f"!! подходящих отзывов подозрительно мало ({len(picked)}) — JSON не трогаю",
              file=sys.stderr)
        return 1

    half = 7
    payload = {
        "source": "https://yandex.ru/maps/org/foksinburg/112008441352/reviews/",
        "fetched_at": int(time.time()),
        "rows": [picked[:half], picked[half:]],
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, args.out)  # атомарно, чтобы сайт не увидел половину файла
    print(f"OK: {len(picked)} карточек -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
