#!/usr/bin/env python3
"""Сводный SEO-отчёт: keywords × Вебмастер × Wordstat × GSC × Метрика → report.md + report.csv.

Источники (sqlite, таблицы): keywords (ядро), webmaster_queries (Яндекс),
wordstat (частотность), gsc_queries (Google), metrika_phrases (визиты).

Флаги (flags, через ';'):
  NO_PAGE_WITH_SHOWS  — показы в Вебмастере, страницы нет (NEW) → создать страницу
  LOW_CTR             — Яндекс: позиция 5–20, CTR<2%, показы≥10 → доработать title/description
  WM_NOT_IN_CORE      — запрос Вебмастера вне ядра (показы≥5) → добавить в карту
  GSC_LOW_CTR         — Google: позиция 5–20, CTR<2%, показы≥10 → доработать сниппет
  GSC_STRIKING        — Google: позиция 4–15, показы≥5 → «striking distance», дожать до топ-3
  GSC_NOT_IN_CORE     — запрос GSC вне ядра (показы≥5) → рассмотреть для карты
  NO_FREQ             — нет данных частотности

Запуск: seo/.venv/bin/python seo/merge_report.py
"""
import csv
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SEO_DIR, get_db

MD_PATH = os.path.join(SEO_DIR, "report.md")
CSV_PATH = os.path.join(SEO_DIR, "report.csv")
LOW_CTR_POS_MIN, LOW_CTR_POS_MAX, LOW_CTR_THRESHOLD = 5, 20, 2.0
STRIKING_MIN, STRIKING_MAX = 4, 15


def latest_range(conn, table):
    r = conn.execute(
        f"SELECT date_from, date_to, fetched_at FROM {table} "
        "ORDER BY fetched_at DESC LIMIT 1").fetchone()
    return r


def main():
    conn = get_db()

    keywords = {r["query"]: dict(r) for r in conn.execute("SELECT * FROM keywords")}
    wordstat = {}
    for r in conn.execute("SELECT * FROM wordstat"):
        w = wordstat.setdefault(r["query"], {"freq_base": 0, "freq_exact": 0})
        w["freq_base"] += r["freq_base"] or 0
        w["freq_exact"] += r["freq_exact"] or 0

    rows = {}

    def base_row(q):
        kw = keywords.get(q, {})
        ws = wordstat.get(q, {})
        return {
            "query": q, "in_core": q in keywords,
            "cluster": kw.get("cluster", ""), "priority": kw.get("priority", ""),
            "intent": kw.get("intent", ""), "geo_level": kw.get("geo_level", ""),
            "target_url": kw.get("target_url", ""), "page_needed": kw.get("page_needed", 0),
            "freq_base": ws.get("freq_base"), "freq_exact": ws.get("freq_exact"),
            "shows": 0, "clicks": 0, "ctr": 0.0, "position": None,
            "gsc_impressions": 0, "gsc_clicks": 0, "gsc_ctr": 0.0, "gsc_position": None,
            "mtr_visits": 0,
        }

    # Яндекс Вебмастер
    wm = latest_range(conn, "webmaster_queries")
    wm_queries = set()
    if wm:
        for r in conn.execute(
                "SELECT * FROM webmaster_queries WHERE date_from=? AND date_to=?",
                (wm["date_from"], wm["date_to"])):
            wm_queries.add(r["query"])
            row = rows.setdefault(r["query"], base_row(r["query"]))
            row.update(shows=r["shows"], clicks=r["clicks"], ctr=r["ctr"], position=r["position"])

    # Google Search Console
    gsc = latest_range(conn, "gsc_queries")
    gsc_queries = set()
    if gsc:
        for r in conn.execute(
                "SELECT * FROM gsc_queries WHERE date_from=? AND date_to=?",
                (gsc["date_from"], gsc["date_to"])):
            gsc_queries.add(r["query"])
            row = rows.setdefault(r["query"], base_row(r["query"]))
            row.update(gsc_impressions=r["impressions"], gsc_clicks=r["clicks"],
                       gsc_ctr=r["ctr"], gsc_position=r["position"])

    # Метрика
    mtr = latest_range(conn, "metrika_phrases")
    if mtr:
        for r in conn.execute(
                "SELECT * FROM metrika_phrases WHERE date_from=? AND date_to=?",
                (mtr["date_from"], mtr["date_to"])):
            row = rows.setdefault(r["query"], base_row(r["query"]))
            row["mtr_visits"] = r["visits"]

    # Запросы ядра без показов — тоже в отчёт
    for q in keywords:
        if q not in rows:
            rows[q] = base_row(q)

    rows = list(rows.values())

    # Флаги
    for r in rows:
        flags = []
        if r["shows"] and r["page_needed"]:
            flags.append("NO_PAGE_WITH_SHOWS")
        if (r["position"] is not None and LOW_CTR_POS_MIN <= r["position"] <= LOW_CTR_POS_MAX
                and r["ctr"] < LOW_CTR_THRESHOLD and r["shows"] >= 10):
            flags.append("LOW_CTR")
        if not r["in_core"] and r["shows"] >= 5:
            flags.append("WM_NOT_IN_CORE")
        if (r["gsc_position"] is not None and LOW_CTR_POS_MIN <= r["gsc_position"] <= LOW_CTR_POS_MAX
                and r["gsc_ctr"] < LOW_CTR_THRESHOLD and r["gsc_impressions"] >= 10):
            flags.append("GSC_LOW_CTR")
        if (r["gsc_position"] is not None and STRIKING_MIN <= r["gsc_position"] <= STRIKING_MAX
                and r["gsc_impressions"] >= 5):
            flags.append("GSC_STRIKING")
        if not r["in_core"] and r["gsc_impressions"] >= 5:
            flags.append("GSC_NOT_IN_CORE")
        if r["freq_base"] is None:
            flags.append("NO_FREQ")
        r["flags"] = ";".join(flags)
        r["total_shows"] = (r["shows"] or 0) + (r["gsc_impressions"] or 0)

    rows.sort(key=lambda r: (-r["total_shows"], r["query"]))

    fields = ["query", "in_core", "cluster", "priority", "intent", "geo_level",
              "target_url", "page_needed", "freq_base", "freq_exact",
              "shows", "clicks", "ctr", "position",
              "gsc_impressions", "gsc_clicks", "gsc_ctr", "gsc_position",
              "mtr_visits", "flags"]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    def cnt(flag):
        return sum(1 for r in rows if flag in r["flags"])

    def top(flag, n=15):
        return [r for r in rows if flag in r["flags"]][:n]

    gen = datetime.now(timezone.utc).isoformat(timespec="seconds")
    wm_range = f"{wm['date_from']} … {wm['date_to']}" if wm else "нет данных"
    gsc_range = f"{gsc['date_from']} … {gsc['date_to']}" if gsc else "нет данных"

    lines = [
        "# SEO-сводка: ядро × Вебмастер × Wordstat × GSC × Метрика",
        "",
        f"Сформировано: {gen}",
        f"Вебмастер: {wm_range} ({len(wm_queries)} запросов). "
        f"GSC: {gsc_range} ({len(gsc_queries)} запросов).",
        f"Ядро: {len(keywords)} запросов. Wordstat: {len(wordstat)} с частотностью.",
        "",
        "## Флаги",
        "",
        "| Флаг | Что делать | Кол-во |",
        "|---|---|---|",
        f"| NO_PAGE_WITH_SHOWS | Создать страницу (Яндекс: показы, target NEW) | {cnt('NO_PAGE_WITH_SHOWS')} |",
        f"| LOW_CTR | Доработать title/description (Яндекс: поз. 5–20, CTR<2%, показы≥10) | {cnt('LOW_CTR')} |",
        f"| GSC_LOW_CTR | Доработать сниппет (Google: поз. 5–20, CTR<2%, показы≥10) | {cnt('GSC_LOW_CTR')} |",
        f"| GSC_STRIKING | Дожать до топ-3 (Google: поз. 4–15, показы≥5) | {cnt('GSC_STRIKING')} |",
        f"| WM_NOT_IN_CORE | Добавить в карту (Вебмастер, показы≥5) | {cnt('WM_NOT_IN_CORE')} |",
        f"| GSC_NOT_IN_CORE | Рассмотреть для карты (GSC, показы≥5) | {cnt('GSC_NOT_IN_CORE')} |",
        f"| NO_FREQ | Нет частотности | {cnt('NO_FREQ')} |",
        "",
        "## Топ-15: Google striking distance — дожать до топ-3 (GSC_STRIKING)",
        "",
        "| Запрос | Показы G | Клики G | CTR% | Позиция G | Страница |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(top("GSC_STRIKING", 50), key=lambda r: r["gsc_position"])[:15]:
        lines.append(f"| {r['query']} | {r['gsc_impressions']} | {r['gsc_clicks']} | "
                     f"{r['gsc_ctr']} | {r['gsc_position']:.1f} | {r['target_url']} |")

    lines += ["", "## Топ-15: низкий CTR в Google (GSC_LOW_CTR)", "",
              "| Запрос | Показы G | CTR% | Позиция G | Страница |",
              "|---|---|---|---|---|"]
    for r in top("GSC_LOW_CTR"):
        lines.append(f"| {r['query']} | {r['gsc_impressions']} | {r['gsc_ctr']} | "
                     f"{r['gsc_position']:.1f} | {r['target_url']} |")

    lines += ["", "## Топ-15: показы есть, страницы нет (NO_PAGE_WITH_SHOWS)", "",
              "| Запрос | Показы | Клики | CTR% | Целевой URL (NEW) |",
              "|---|---|---|---|---|"]
    for r in top("NO_PAGE_WITH_SHOWS"):
        lines.append(f"| {r['query']} | {r['shows']} | {r['clicks']} | {r['ctr']} | {r['target_url']} |")

    lines += ["", "## Топ-15: низкий CTR в Яндексе (LOW_CTR)", "",
              "| Запрос | Показы | CTR% | Позиция | Страница |",
              "|---|---|---|---|---|"]
    for r in top("LOW_CTR"):
        pos = f"{r['position']:.1f}" if r["position"] is not None else "—"
        lines.append(f"| {r['query']} | {r['shows']} | {r['ctr']} | "
                     f"{pos} | {r['target_url']} |")

    lines += ["", "## Топ-15: запросы GSC вне ядра (GSC_NOT_IN_CORE)", "",
              "| Запрос | Показы G | Клики G | Позиция G |", "|---|---|---|---|"]
    for r in top("GSC_NOT_IN_CORE"):
        pos = f"{r['gsc_position']:.1f}" if r["gsc_position"] is not None else "—"
        lines.append(f"| {r['query']} | {r['gsc_impressions']} | {r['gsc_clicks']} | {pos} |")

    lines += ["", "## Топ-15: запросы Вебмастера вне ядра (WM_NOT_IN_CORE)", "",
              "| Запрос | Показы | Клики | CTR% |", "|---|---|---|---|"]
    for r in top("WM_NOT_IN_CORE"):
        lines.append(f"| {r['query']} | {r['shows']} | {r['clicks']} | {r['ctr']} |")

    lines += ["",
              f"Полная таблица: `{CSV_PATH}` ({len(rows)} строк).",
              ""]

    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Отчёт: {MD_PATH} и {CSV_PATH}")
    print(f"Строк в отчёте: {len(rows)} (ядро {len(keywords)}, Вебмастер {len(wm_queries)}, GSC {len(gsc_queries)})")
    print(f"Флаги: NO_PAGE_WITH_SHOWS={cnt('NO_PAGE_WITH_SHOWS')}, "
          f"LOW_CTR={cnt('LOW_CTR')}, GSC_LOW_CTR={cnt('GSC_LOW_CTR')}, "
          f"GSC_STRIKING={cnt('GSC_STRIKING')}, WM_NOT_IN_CORE={cnt('WM_NOT_IN_CORE')}, "
          f"GSC_NOT_IN_CORE={cnt('GSC_NOT_IN_CORE')}, NO_FREQ={cnt('NO_FREQ')}")
    conn.close()


if __name__ == "__main__":
    main()
