#!/usr/bin/env python3
"""Выгрузка популярных поисковых запросов из API Яндекс Вебмастера v4.

Что делает:
  1. GET /v4/user → user_id;
  2. GET /v4/user/{user_id}/hosts → находит host_id для dymova-english.ru;
  3. GET .../search-queries/popular (показы/клики/CTR/позиция) за последние 3 месяца
     с пагинацией offset/limit → sqlite webmaster_queries + seo/webmaster_queries.csv.

Точка расширения GSC: добавить google_search_console.py с сервисным аккаунтом
(GOOGLE_SA_KEY в .env.seo) и слить в аналогичную таблицу — см. README.

Запуск: seo/.venv/bin/python seo/yandex_webmaster.py [--days 92] [--limit 500]
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

API = "https://api.webmaster.yandex.net/v4"
HOST_NAME = "dymova-english.ru"
CSV_PATH = os.path.join(SEO_DIR, "webmaster_queries.csv")
INDICATORS = ["TOTAL_SHOWS", "TOTAL_CLICKS", "AVG_SHOW_POSITION", "AVG_CLICK_POSITION"]


def api_get(token, path, params=None, retries=4):
    """GET с retry/backoff на 429 и 5xx."""
    headers = {"Authorization": f"OAuth {token}"}
    delay = 2.0
    for attempt in range(retries):
        r = requests.get(API + path, headers=headers, params=params, timeout=60)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504):
            wait = float(r.headers.get("Retry-After", delay))
            print(f"  {r.status_code}, повтор через {wait:.0f} с...", file=sys.stderr)
            time.sleep(wait)
            delay = min(delay * 2, 60)
            continue
        raise SystemExit(f"Ошибка API {r.status_code} на {path}: {r.text[:500]}")
    raise SystemExit(f"Не удалось выполнить {path} после {retries} попыток")


def find_host(token):
    user = api_get(token, "/user")
    user_id = user["user_id"]
    hosts = api_get(token, f"/user/{user_id}/hosts")
    for h in hosts.get("hosts", []):
        if HOST_NAME in h.get("unicode_host_url", "") or HOST_NAME in h.get("host_url", ""):
            return user_id, h["host_id"], h
    raise SystemExit(f"Хост {HOST_NAME} не найден среди: "
                     f"{[h.get('unicode_host_url') for h in hosts.get('hosts', [])]}")


def fetch_popular(token, user_id, host_id, date_from, date_to, limit=500):
    """Пагинация по popular queries. Возвращает список dict."""
    out, offset = [], 0
    while True:
        data = api_get(
            token,
            f"/user/{user_id}/hosts/{host_id}/search-queries/popular",
            params={
                "order_by": "TOTAL_SHOWS",
                "query_indicator": INDICATORS,
                "date_from": date_from,
                "date_to": date_to,
                "offset": offset,
                "limit": limit,
            },
        )
        batch = data.get("queries", [])
        for q in batch:
            ind = q.get("indicators", {})
            shows = ind.get("TOTAL_SHOWS", 0) or 0
            clicks = ind.get("TOTAL_CLICKS", 0) or 0
            pos = ind.get("AVG_SHOW_POSITION") or ind.get("AVG_CLICK_POSITION")
            out.append({
                "query": (q.get("query_text") or "").strip().lower(),
                "shows": int(shows),
                "clicks": int(clicks),
                "ctr": round(clicks / shows * 100, 2) if shows else 0.0,
                "position": round(float(pos), 1) if pos else None,
            })
        total = data.get("count", 0)
        offset += len(batch)
        print(f"  выгружено {offset}/{total}")
        if not batch or offset >= total:
            break
        time.sleep(0.5)  # бережём лимиты
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=92, help="глубина выгрузки, дней (default 92 ≈ 3 мес)")
    ap.add_argument("--limit", type=int, default=500, help="размер страницы API")
    args = ap.parse_args()

    token = load_env().get("YANDEX_WEBMASTER_TOKEN")
    if not token:
        raise SystemExit("Нет YANDEX_WEBMASTER_TOKEN в .env.seo")

    user_id, host_id, host = find_host(token)
    print(f"user_id={user_id}, host={host.get('unicode_host_url')} ({host_id}), "
          f"verified={host.get('verified')}")

    # Данные Вебмастера отстают на ~2-3 дня
    date_to = (date.today() - timedelta(days=3)).isoformat()
    date_from = (date.today() - timedelta(days=args.days)).isoformat()
    print(f"Диапазон: {date_from} … {date_to}")

    rows = fetch_popular(token, user_id, host_id, date_from, date_to, args.limit)
    rows = [r for r in rows if r["query"]]

    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = get_db()
    conn.execute("DELETE FROM webmaster_queries WHERE date_from=? AND date_to=?",
                 (date_from, date_to))
    conn.executemany(
        """INSERT OR REPLACE INTO webmaster_queries
           (query, date_from, date_to, shows, clicks, ctr, position, fetched_at)
           VALUES (:query, :df, :dt, :shows, :clicks, :ctr, :position, :fa)""",
        [dict(r, df=date_from, dt=date_to, fa=fetched) for r in rows],
    )
    conn.commit()

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["query", "shows", "clicks", "ctr", "position"])
        w.writeheader()
        w.writerows(rows)

    rows.sort(key=lambda r: -r["shows"])
    print(f"\nВыгружено запросов: {len(rows)} → {CSV_PATH}, keywords.sqlite (webmaster_queries)")
    print("\nТоп-10 по показам:")
    for i, r in enumerate(rows[:10], 1):
        pos = f"{r['position']:.1f}" if isinstance(r["position"], (int, float)) else "—"
        print(f"  {i:>2}. {r['query'][:50]:<52} показы={r['shows']:>5} "
              f"клики={r['clicks']:>3} CTR={r['ctr']:>5}% поз={pos}")
    conn.close()


if __name__ == "__main__":
    main()
