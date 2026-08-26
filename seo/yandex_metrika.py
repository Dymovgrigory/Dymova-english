#!/usr/bin/env python3
"""Выгрузка поисковых фраз из API Яндекс Метрики v1 (отчёт «Поисковые фразы»).

Что делает:
  1. GET https://api-metrika.yandex.net/stat/v1/data
     dimensions=ym:s:searchPhrase, metrics=ym:s:visits,ym:s:pageviews,
     filters=ym:s:trafficSourceName=='Переходы из поисковых систем' (через ym:s:searchEngine);
  2. Пагинация offset/limit → sqlite metrika_phrases + seo/metrika_phrases.csv.

Подготовка (один раз, владелец):
  1. https://oauth.yandex.ru → «Зарегистрировать новое приложение»,
     платформа: веб-сервисы, права: metrika:read (Яндекс Метрика — чтение);
  2. Открыть https://oauth.yandex.ru/authorize?response_type=token&client_id=<ID>
     под рабочим логином (владелец счётчика 109945462) → скопировать токен;
  3. Вписать в .env.seo: METRIKA_TOKEN=y0__...

Запуск: seo/.venv/bin/python seo/yandex_metrika.py [--days 92]
Без METRIKA_TOKEN выходит мягко с подсказкой.
"""
import argparse
import csv
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SEO_DIR, get_db, load_env

import requests

API = "https://api-metrika.yandex.net/stat/v1/data"
COUNTER_ID = "109945462"
CSV_PATH = os.path.join(SEO_DIR, "metrika_phrases.csv")
LIMIT = 10000  # максимум API за вызов


def api_get(token, params, retries=4):
    headers = {"Authorization": f"OAuth {token}"}
    delay = 2.0
    for attempt in range(retries):
        r = requests.get(API, headers=headers, params=params, timeout=60)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504):
            print(f"  {r.status_code}, повтор через {delay:.0f} с...", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 60)
            continue
        raise SystemExit(f"Ошибка API {r.status_code}: {r.text[:500]}")
    raise SystemExit(f"Не удалось после {retries} попыток")


def fetch_phrases(token, date_from, date_to):
    out, offset = [], 1  # Метрика нумерует offset с 1
    while True:
        data = api_get(token, {
            "id": COUNTER_ID,
            "dimensions": "ym:s:searchPhrase",
            "metrics": "ym:s:visits,ym:s:pageviews",
            "filters": "ym:s:searchEngine!=''",
            "date1": date_from,
            "date2": date_to,
            "sort": "-ym:s:visits",
            "limit": LIMIT,
            "offset": offset,
            "accuracy": "full",
        })
        rows = data.get("data", [])
        for row in rows:
            dim = row["dimensions"][0].get("name", "").strip()
            if not dim or dim == "Not set":
                continue
            visits, pageviews = row["metrics"][0], row["metrics"][1]
            out.append({"query": dim.lower(), "visits": int(visits),
                        "pageviews": int(pageviews)})
        if len(rows) < LIMIT:
            break
        offset += LIMIT
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=92)
    args = ap.parse_args()

    env = load_env()
    token = env.get("METRIKA_TOKEN", "").strip()
    if not token:
        print("METRIKA_TOKEN пуст в .env.seo — см. инструкцию в docstring/README.", file=sys.stderr)
        return

    date_to = date.today().isoformat()
    date_from = (date.today() - timedelta(days=args.days)).isoformat()
    print(f"Период: {date_from} .. {date_to}, счётчик {COUNTER_ID}")

    rows = fetch_phrases(token, date_from, date_to)
    print(f"Фраз получено: {len(rows)}")

    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        conn.execute(
            """INSERT INTO metrika_phrases (query, date_from, date_to, visits, pageviews, fetched_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(query, date_from, date_to) DO UPDATE SET
                 visits=excluded.visits, pageviews=excluded.pageviews,
                 fetched_at=excluded.fetched_at""",
            (r["query"], date_from, date_to, r["visits"], r["pageviews"], now))
    conn.commit()

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["query", "visits", "pageviews"])
        w.writeheader()
        w.writerows(rows)
    print(f"CSV: {CSV_PATH}")


if __name__ == "__main__":
    main()
