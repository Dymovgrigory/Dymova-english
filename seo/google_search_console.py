#!/usr/bin/env python3
"""Выгрузка поисковых запросов из Google Search Console API.

Что делает:
  1. Берёт JSON-ключ service account из GOOGLE_SA_KEY (.env.seo):
     либо путь к json-файлу, либо сам JSON одной строкой;
  2. searchanalytics.query по ресурсу sc-domain:dymova-english.ru
     (dimensions=query, за последние ~3 месяца, пагинация rowLimit/startRow);
  3. Пишет в sqlite gsc_queries + seo/gsc_queries.csv.

Подготовка (один раз, владелец):
  1. console.cloud.google.com → создать проект → включить «Google Search Console API»;
  2. IAM → Service Accounts → создать, скачать JSON-ключ;
  3. В Search Console (search.google.com/search-console) → Настройки →
     Пользователи и разрешения → добавить email сервисного аккаунта (чтение);
  4. Положить путь к JSON в .env.seo: GOOGLE_SA_KEY=/path/key.json
     (или весь JSON одной строкой).

Запуск: seo/.venv/bin/python seo/google_search_console.py [--days 92]
Без GOOGLE_SA_KEY выходит мягко с подсказкой.
"""
import argparse
import csv
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SEO_DIR, get_db, load_env

import requests

SITE_URL = "sc-domain:dymova-english.ru"
API = "https://www.googleapis.com/webmasters/v3"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
CSV_PATH = os.path.join(SEO_DIR, "gsc_queries.csv")
ROW_LIMIT = 25000  # максимум API за вызов


def get_access_token(sa_info):
    """JWT-флоу service account → access token (без google-api-client)."""
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=[SCOPE])
    creds.refresh(Request())
    return creds.token


def load_sa_info(raw):
    """GOOGLE_SA_KEY: путь к файлу или JSON-строка."""
    if os.path.exists(raw):
        with open(raw, encoding="utf-8") as f:
            return json.load(f)
    return json.loads(raw)


def fetch_queries(token, date_from, date_to):
    headers = {"Authorization": f"Bearer {token}"}
    out, start = [], 0
    while True:
        body = {
            "startDate": date_from,
            "endDate": date_to,
            "dimensions": ["query"],
            "rowLimit": ROW_LIMIT,
            "startRow": start,
        }
        r = requests.post(
            f"{API}/sites/{SITE_URL}/searchAnalytics/query",
            headers={**headers, "Content-Type": "application/json"},
            json=body, timeout=60)
        if r.status_code in (429, 500, 502, 503, 504):
            print(f"  {r.status_code}, повтор через 10 с...", file=sys.stderr)
            time.sleep(10)
            continue
        if r.status_code != 200:
            raise SystemExit(f"Ошибка API {r.status_code}: {r.text[:500]}")
        rows = r.json().get("rows", [])
        for row in rows:
            out.append({
                "query": row["keys"][0],
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": round(row.get("ctr", 0) * 100, 2),      # в %
                "position": round(row.get("position", 0), 1),
            })
        if len(rows) < ROW_LIMIT:
            break
        start += ROW_LIMIT
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=92)
    args = ap.parse_args()

    env = load_env()
    raw_key = env.get("GOOGLE_SA_KEY", "").strip()
    if not raw_key:
        print("GOOGLE_SA_KEY пуст в .env.seo — см. инструкцию в docstring/README.", file=sys.stderr)
        return

    sa_info = load_sa_info(raw_key)
    token = get_access_token(sa_info)
    print(f"Service account: {sa_info.get('client_email')}")

    date_to = (date.today() - timedelta(days=2)).isoformat()  # GSC отдаёт с лагом ~2 дня
    date_from = (date.today() - timedelta(days=args.days)).isoformat()
    print(f"Период: {date_from} .. {date_to}")

    rows = fetch_queries(token, date_from, date_to)
    print(f"Запросов получено: {len(rows)}")

    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        conn.execute(
            """INSERT INTO gsc_queries (query, date_from, date_to, impressions, clicks, ctr, position, fetched_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(query, date_from, date_to) DO UPDATE SET
                 impressions=excluded.impressions, clicks=excluded.clicks,
                 ctr=excluded.ctr, position=excluded.position, fetched_at=excluded.fetched_at""",
            (r["query"].lower().strip(), date_from, date_to,
             r["impressions"], r["clicks"], r["ctr"], r["position"], now))
    conn.commit()

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["query", "impressions", "clicks", "ctr", "position"])
        w.writeheader()
        w.writerows(rows)
    print(f"CSV: {CSV_PATH}")


if __name__ == "__main__":
    main()
