#!/usr/bin/env python3
"""Частотность запросов через Яндекс Директ API v5, сервис WordstatReports.

⚠️  ТРЕБУЕТ DIRECT_TOKEN в .env.seo (токена пока нет — скрипт мягко выйдет).
    Как получить токен — см. seo/README.md, раздел «Wordstat».

Механика API (https://yandex.ru/dev/direct/doc/ru/concepts/wordstat):
  - NewWordstatReport: создать отчёт. В ОДНОМ отчёте до 10 фраз (Phrases).
    Регионы — GeoIds (213 = Москва; 1 = Московская область; уточнить id через
    Dictionaries/get, справочник GeoRegions). Без GeoIds — по всем регионам.
  - GetWordstatReportList: список отчётов и статусы (pending/offline/online).
  - GetWordstatReport: забрать готовый отчёт (Phrases → SearchedWith/SearchedAlso,
    поле Shows — показы в месяц по региону).
  - DeleteWordstatReport: удалить после забора (лимит хранимых отчётов — 5 в очереди,
    WORDSTAT_REPORTS_TOTAL_IN_QUEUE).
  Баллы API: списываются за заказ отчёта; 429/лимиты — retry с backoff.

Частотность: freq_base — Shows по фразе как есть; freq_exact — Shows по фразе
с оператором "!слово !слово" (точное вхождение) — заказываем вторым набором фраз.

Вход: keywords.sqlite (таблица keywords). По умолчанию — только запросы без freq
в wordstat за последние 35 дней; --all — все.
Результат: sqlite wordstat (query, region, freq_base, freq_exact, fetched_at) + CSV.

Запуск: seo/.venv/bin/python seo/yandex_wordstat.py [--all] [--limit N]
"""
import argparse
import csv
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SEO_DIR, get_db, load_env

import requests

API_URL = "https://api.direct.yandex.com/json/v5/wordstatreports"
# Гео: 213 = Москва, 1 = Московская область (проверить/дополнить через
# Dictionaries/get → GeoRegions: Долгопрудный входит в МО, отдельного id может не быть)
GEO_IDS = [213, 1]
REGION_LABEL = "msk+mo"  # метка региона для строк результата
PHRASES_PER_REPORT = 10  # жёсткий лимит API
MAX_QUEUE = 4            # держим не больше 4 отчётов в очереди (лимит 5)
POLL_SEC = 20
CSV_PATH = os.path.join(SEO_DIR, "wordstat.csv")


def api_call(token, method, params, retries=5):
    """POST json-rpc вызов с retry/backoff на 429 и 5xx."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8",
    }
    body = {"method": method, "params": params}
    delay = 5.0
    for attempt in range(retries):
        r = requests.post(API_URL, json=body, headers=headers, timeout=120)
        if r.status_code in (200, 201, 202):
            data = r.json()
            if "error" in data:
                err = data["error"]
                code = err.get("error_code")
                # 152/155 — лимит баллов/запросов; 56 — превышение очереди отчётов
                if code in (152, 155, 56) or "limit" in err.get("error_string", "").lower():
                    print(f"  лимит API (code {code}), жду {delay:.0f} с...", file=sys.stderr)
                    time.sleep(delay)
                    delay = min(delay * 2, 300)
                    continue
                raise SystemExit(f"Ошибка API: {err}")
            return data.get("result", data)
        if r.status_code in (429, 500, 502, 503, 504):
            wait = float(r.headers.get("Retry-After", delay))
            print(f"  {r.status_code}, повтор через {wait:.0f} с...", file=sys.stderr)
            time.sleep(wait)
            delay = min(delay * 2, 300)
            continue
        raise SystemExit(f"HTTP {r.status_code}: {r.text[:500]}")
    raise SystemExit(f"Метод {method}: не удалось после {retries} попыток")


def exact_form(phrase):
    """'!слова' — оператор точного вхождения каждого слова."""
    return " ".join("!" + w if not w.startswith("!") else w for w in phrase.split())


def wait_queue_slot(token):
    """Ждёт, пока в очереди станет меньше MAX_QUEUE неготовых отчётов."""
    while True:
        reports = api_call(token, "GetWordstatReportList", {}).get("WordstatReports", [])
        pending = [r for r in reports if r.get("StatusReport") != "online"]
        if len(pending) < MAX_QUEUE:
            return reports
        print(f"  в очереди {len(pending)} отчётов, жду {POLL_SEC} с...")
        time.sleep(POLL_SEC)


def collect_ready(token, conn):
    """Забирает все готовые (online) отчёты, пишет в БД, удаляет с сервера."""
    reports = api_call(token, "GetWordstatReportList", {}).get("WordstatReports", [])
    done = 0
    for rep in reports:
        if rep.get("StatusReport") != "online":
            continue
        rid = rep["ReportID"]
        data = api_call(token, "GetWordstatReport", {"ReportID": rid})
        fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for ph in data.get("Phrases", []):
            phrase = (ph.get("Phrase") or "").strip().lower()
            shows = ph.get("Shows")
            if not phrase or shows is None:
                continue
            is_exact = phrase.startswith("!")
            base_query = phrase.replace("!", "").strip()
            conn.execute(
                """INSERT INTO wordstat (query, region, freq_base, freq_exact, fetched_at)
                   VALUES (?, ?, NULL, NULL, ?)
                   ON CONFLICT(query, region) DO NOTHING""",
                (base_query, REGION_LABEL, fetched),
            )
            col = "freq_exact" if is_exact else "freq_base"
            conn.execute(f"UPDATE wordstat SET {col}=?, fetched_at=? WHERE query=? AND region=?",
                         (int(shows), fetched, base_query, REGION_LABEL))
        api_call(token, "DeleteWordstatReport", {"ReportID": rid})
        done += 1
        conn.commit()
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="все запросы ядра, не только без freq")
    ap.add_argument("--limit", type=int, default=0, help="ограничить число запросов (отладка)")
    args = ap.parse_args()

    token = load_env().get("DIRECT_TOKEN")
    if not token:
        print("Нет DIRECT_TOKEN в .env.seo — Wordstat пропущен.")
        print("Как получить токен (нужен владелец) — seo/README.md, раздел «Wordstat».")
        sys.exit(0)

    conn = get_db()
    if args.all:
        queries = [r[0] for r in conn.execute("SELECT query FROM keywords ORDER BY query")]
    else:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
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

    # Формируем фразы: базовая форма + точная ("!слова")
    phrases = []
    for q in queries:
        phrases.append(q)
        phrases.append(exact_form(q))

    print(f"Запросов к обработке: {len(queries)}, фраз (с точной формой): {len(phrases)}")
    print(f"Регионы GeoIds: {GEO_IDS}. Отчётов потребуется ~{(len(phrases) + PHRASES_PER_REPORT - 1) // PHRASES_PER_REPORT}")

    ordered = 0
    for i in range(0, len(phrases), PHRASES_PER_REPORT):
        batch = phrases[i: i + PHRASES_PER_REPORT]
        wait_queue_slot(token)
        res = api_call(token, "NewWordstatReport",
                       {"Phrases": batch, "GeoIds": GEO_IDS})
        ordered += 1
        print(f"  отчёт {ordered} заказан (id={res.get('ReportID')}), фраз {len(batch)}")
        # Периодически собираем готовые
        if ordered % 3 == 0:
            done = collect_ready(token, conn)
            if done:
                print(f"  забрано готовых отчётов: {done}")

    # Дожидаемся остатка
    print("Все отчёты заказаны, дожидаюсь готовности оставшихся...")
    for _ in range(60):  # максимум ~20 минут ожидания
        time.sleep(POLL_SEC)
        collect_ready(token, conn)
        reports = api_call(token, "GetWordstatReportList", {}).get("WordstatReports", [])
        pending = [r for r in reports if r.get("StatusReport") != "online"]
        if not pending:
            break
        print(f"  осталось в очереди: {len(pending)}")

    # CSV-выгрузка
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["query", "region", "freq_base", "freq_exact", "fetched_at"])
        for row in conn.execute(
                "SELECT query, region, freq_base, freq_exact, fetched_at FROM wordstat ORDER BY query"):
            w.writerow(row)

    total = conn.execute("SELECT COUNT(*) FROM wordstat").fetchone()[0]
    print(f"Готово. В wordstat {total} строк → keywords.sqlite, {CSV_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
