#!/usr/bin/env python3
"""Частотность запросов через Wordstat API сервиса Yandex Cloud Search API v2.

⚠️  АКТУАЛЬНАЯ СХЕМА (2026): Яндекс закрыл оба старых доступа к Wordstat —
    сервис WordstatReports в Директ API v5 (https://api.direct.yandex.com/json/v5/wordstatreports
    отдаёт 404) и бету https://api.wordstat.yandex.net (тоже 404). Официальный ответ:
    «Все возможности API Вордстата теперь доступны в Wordstat API сервиса Yandex Search API»
    (yandex.ru/support2/wordstat/ru/content/api-wordstat).

    OAuth-токен Яндекс ID (y0__..., в т.ч. со scope Директа) НЕ принимается —
    нужен API-ключ Yandex Cloud + id каталога. Как получить — seo/README.md, «Wordstat».

Механика:
  POST https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests
  headers: Authorization: Api-Key <WORDSTAT_API_KEY>, Accept-Language: ru
  body: {"folderId": ..., "phrase": ..., "numPhrases": 2000, "regions": ["213","1"]}
  ответ: {"results": [{"phrase": ..., "count": "..."}], "associations": [...], "totalCount": ...}
  Частотность конкретной фразы = count записи results, где phrase совпадает с запросом
  (нормализованно). Если фразы нет в топ-2000 содержащих — freq_base = 0 (запрос НЧ).
  --exact: второй проход с точной формой "\"!слово !слово\"" → freq_exact
  (только для запросов с freq_base > 0, чтобы не сжечь квоту).

Лимиты: 10 запросов/сек, ~1000 запросов/сутки (базовый тариф) — скрипт держит
rate-limit, ведёт счётчик вызовов и останавливается с понятным сообщением.
Retry с backoff на 429 и 5xx.

Вход: keywords.sqlite (таблица keywords). По умолчанию — запросы без свежей freq
(35 дней); --all — все. Результат: sqlite wordstat + seo/wordstat.csv.

Запуск: seo/.venv/bin/python seo/yandex_wordstat.py [--all] [--limit N] [--exact]
"""
import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SEO_DIR, get_db, load_env

import requests

API_BASE = "https://searchapi.api.cloud.yandex.net"
# Регионы Search API (id из v2/wordstat/getRegionsTree): 213 = Москва, 1 = Московская область.
# Уточнить/дополнить по getRegionsTree при первом запуске с ключом.
REGIONS = ["213", "1"]
REGION_LABEL = "msk+mo"
NUM_PHRASES = 2000          # максимум API за один вызов
DAILY_CALL_BUDGET = 950     # стоп-порог суточной квоты (базовый лимит ~1000)
RPS_DELAY = 1.0             # у свежего аккаунта бурст-лимит ниже заявленных 10 rps (50-60 вызовов → 429); идём 1 rps
CSV_PATH = os.path.join(SEO_DIR, "wordstat.csv")


class QuotaExceeded(Exception):
    pass


def api_call(api_key, folder_id, method, body, retries=10, counter=None):
    """POST /v2/wordstat/<method> с retry/backoff на 429 и 5xx. counter=[int] — счётчик вызовов."""
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Accept-Language": "ru",
        "Content-Type": "application/json",
    }
    payload = {"folderId": folder_id, **body}
    delay = 2.0
    for attempt in range(retries):
        if counter is not None:
            counter[0] += 1
            if counter[0] > DAILY_CALL_BUDGET:
                raise QuotaExceeded(
                    f"Исчерпан дневной бюджет вызовов ({DAILY_CALL_BUDGET}). "
                    f"Запустите завтра — скрипт продолжит с места остановки (пропускает свежие freq).")
        try:
            r = requests.post(f"{API_BASE}/v2/wordstat/{method}",
                              json=payload, headers=headers, timeout=60)
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise SystemExit(f"Сеть: {e}")
        if r.status_code == 200:
            time.sleep(RPS_DELAY)
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504):
            # Почасовая квота (100/час у свежих аккаунтов): бесполезно ретраить секундами —
            # ждём до следующего часового окна.
            if r.status_code == 429 and "PerHour" in r.text:
                wait = 610.0
            else:
                wait = float(r.headers.get("Retry-After", delay))
            print(f"  {r.status_code}, повтор через {wait:.0f} с...", file=sys.stderr)
            time.sleep(wait)
            delay = min(delay * 2, 60)
            continue
        raise SystemExit(f"Ошибка API {r.status_code} на {method}: {r.text[:500]}")
    raise SystemExit(f"{method}: не удалось после {retries} попыток")


def norm(phrase):
    return re.sub(r"\s+", " ", (phrase or "")).strip().lower()


def exact_form(phrase):
    """Точная частотность: кавычки + оператор '!' на каждое слово."""
    return '"' + " ".join("!" + w for w in phrase.split()) + '"'


def fetch_freq(api_key, folder_id, phrase, counter):
    """Частотность фразы через topRequests: ищем точное совпадение в results. Нет → 0."""
    data = api_call(api_key, folder_id, "topRequests",
                    {"phrase": phrase, "numPhrases": NUM_PHRASES, "regions": REGIONS},
                    counter=counter)
    target = norm(phrase)
    for item in data.get("results", []):
        if norm(item.get("phrase")) == target:
            return int(item.get("count") or 0)
    return 0


def save_freq(conn, query, col, value):
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "INSERT OR IGNORE INTO wordstat (query, region, fetched_at) VALUES (?, ?, ?)",
        (query, REGION_LABEL, fetched))
    conn.execute(
        f"UPDATE wordstat SET {col}=?, fetched_at=? WHERE query=? AND region=?",
        (value, fetched, query, REGION_LABEL))
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="все запросы ядра, не только без freq")
    ap.add_argument("--limit", type=int, default=0, help="ограничить число запросов (отладка)")
    ap.add_argument("--exact", action="store_true",
                    help="второй проход: точная частотность (\"!фраза\") для запросов с freq_base > 0")
    args = ap.parse_args()

    env = load_env()
    api_key = env.get("WORDSTAT_API_KEY")
    folder_id = env.get("WORDSTAT_FOLDER_ID")
    old_token = env.get("DIRECT_TOKEN")

    if not api_key or not folder_id:
        print("Нет WORDSTAT_API_KEY / WORDSTAT_FOLDER_ID в .env.seo — Wordstat пропущен.")
        if old_token:
            print("ВАЖНО: DIRECT_TOKEN (OAuth y0__... от Яндекс ID) больше НЕ работает:")
            print("Яндекс закрыл Директ API v5 WordstatReports и бету api.wordstat.yandex.net (404).")
            print("Wordstat переехал в Yandex Cloud Search API v2 — нужен API-ключ и id каталога.")
        print("Как получить ключ и folderId — seo/README.md, раздел «Wordstat».")
        sys.exit(0)

    conn = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
    if args.all:
        queries = [r[0] for r in conn.execute("SELECT query FROM keywords ORDER BY query")]
    else:
        queries = [r[0] for r in conn.execute(
            """SELECT k.query FROM keywords k
               LEFT JOIN wordstat w ON w.query = k.query AND w.region = ?
               WHERE w.fetched_at IS NULL OR w.fetched_at < ?
               ORDER BY k.query""", (REGION_LABEL, cutoff))]
    if args.limit:
        queries = queries[: args.limit]
    if not queries:
        print("Все запросы уже имеют свежую частотность. --all для принудительного обновления.")
        sys.exit(0)

    print(f"Запросов к обработке: {len(queries)} (регионы: {REGIONS}, метка {REGION_LABEL})")
    counter = [0]
    try:
        for i, q in enumerate(queries, 1):
            freq = fetch_freq(api_key, folder_id, q, counter)
            save_freq(conn, q, "freq_base", freq)
            if i % 50 == 0 or i == len(queries):
                print(f"  базовая: {i}/{len(queries)} (вызовов API: {counter[0]})")

        if args.exact:
            exact_qs = [r[0] for r in conn.execute(
                "SELECT query FROM wordstat WHERE region=? AND freq_base > 0 "
                "AND (freq_exact IS NULL) ORDER BY query", (REGION_LABEL,))]
            print(f"Точная форма: {len(exact_qs)} запросов с freq_base > 0")
            for i, q in enumerate(exact_qs, 1):
                freq = fetch_freq(api_key, folder_id, exact_form(q), counter)
                save_freq(conn, q, "freq_exact", freq)
                if i % 50 == 0 or i == len(exact_qs):
                    print(f"  точная: {i}/{len(exact_qs)} (вызовов API: {counter[0]})")
    except QuotaExceeded as e:
        print(f"\n{e}", file=sys.stderr)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["query", "region", "freq_base", "freq_exact", "fetched_at"])
        for row in conn.execute(
                "SELECT query, region, freq_base, freq_exact, fetched_at FROM wordstat ORDER BY query"):
            w.writerow(row)

    total = conn.execute("SELECT COUNT(*) FROM wordstat").fetchone()[0]
    zero = conn.execute("SELECT COUNT(*) FROM wordstat WHERE freq_base = 0").fetchone()[0]
    print(f"Готово. В wordstat {total} строк (freq_base=0: {zero}) → keywords.sqlite, {CSV_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
