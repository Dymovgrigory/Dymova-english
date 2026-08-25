#!/usr/bin/env python3
"""Сводный SEO-отчёт: keywords × webmaster_queries × wordstat → report.md + report.csv.

Флаги (flags, через ';'):
  NO_PAGE_WITH_SHOWS  — есть показы в Вебмастере, но страницы нет (NEW) → создать страницу
  LOW_CTR             — позиция 5–20 и CTR < 2% → доработать title/description
  WM_NOT_IN_CORE      — запрос из Вебмастера, которого нет в ядре → добавить в карту
  NO_FREQ             — нет данных частотности (Wordstat не запускался / запрос не покрыт)

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


def main():
    conn = get_db()

    # Вебмастер: последний выгруженный диапазон
    last = conn.execute(
        "SELECT date_from, date_to, fetched_at FROM webmaster_queries "
        "ORDER BY fetched_at DESC LIMIT 1").fetchone()

    keywords = {r["query"]: dict(r) for r in conn.execute("SELECT * FROM keywords")}
    wordstat = {}
    for r in conn.execute("SELECT * FROM wordstat"):
        w = wordstat.setdefault(r["query"], {"freq_base": 0, "freq_exact": 0})
        w["freq_base"] += r["freq_base"] or 0
        w["freq_exact"] += r["freq_exact"] or 0

    rows = []
    wm_queries = set()
    if last:
        for r in conn.execute(
                "SELECT * FROM webmaster_queries WHERE date_from=? AND date_to=?",
                (last["date_from"], last["date_to"])):
            wm_queries.add(r["query"])
            kw = keywords.get(r["query"], {})
            ws = wordstat.get(r["query"], {})
            rows.append({
                "query": r["query"],
                "in_core": r["query"] in keywords,
                "cluster": kw.get("cluster", ""),
                "priority": kw.get("priority", ""),
                "intent": kw.get("intent", ""),
                "geo_level": kw.get("geo_level", ""),
                "target_url": kw.get("target_url", ""),
                "page_needed": kw.get("page_needed", 0),
                "freq_base": ws.get("freq_base"),
                "freq_exact": ws.get("freq_exact"),
                "shows": r["shows"],
                "clicks": r["clicks"],
                "ctr": r["ctr"],
                "position": r["position"],
            })

    # Запросы ядра без показов — тоже в отчёт (полнота картины)
    for q, kw in keywords.items():
        if q in wm_queries:
            continue
        ws = wordstat.get(q, {})
        rows.append({
            "query": q, "in_core": True,
            "cluster": kw["cluster"], "priority": kw["priority"], "intent": kw["intent"],
            "geo_level": kw["geo_level"], "target_url": kw["target_url"],
            "page_needed": kw["page_needed"],
            "freq_base": ws.get("freq_base"), "freq_exact": ws.get("freq_exact"),
            "shows": 0, "clicks": 0, "ctr": 0.0, "position": None,
        })

    # Флаги
    for r in rows:
        flags = []
        if r["shows"] and r["page_needed"]:
            flags.append("NO_PAGE_WITH_SHOWS")
        if (r["position"] is not None and isinstance(r["position"], (int, float))
                and LOW_CTR_POS_MIN <= r["position"] <= LOW_CTR_POS_MAX
                and r["ctr"] < LOW_CTR_THRESHOLD and r["shows"] >= 10):
            flags.append("LOW_CTR")
        if not r["in_core"] and r["shows"] >= 5:
            flags.append("WM_NOT_IN_CORE")
        if r["freq_base"] is None:
            flags.append("NO_FREQ")
        r["flags"] = ";".join(flags)

    rows.sort(key=lambda r: (-(r["shows"] or 0), r["query"]))

    fields = ["query", "in_core", "cluster", "priority", "intent", "geo_level",
              "target_url", "page_needed", "freq_base", "freq_exact",
              "shows", "clicks", "ctr", "position", "flags"]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    def cnt(flag):
        return sum(1 for r in rows if flag in r["flags"])

    def top(flag, n=15):
        return [r for r in rows if flag in r["flags"]][:n]

    gen = datetime.now(timezone.utc).isoformat(timespec="seconds")
    wm_range = f"{last['date_from']} … {last['date_to']}" if last else "нет данных"

    lines = [
        "# SEO-сводка: ядро × Вебмастер × Wordstat",
        "",
        f"Сформировано: {gen}",
        f"Данные Вебмастера: {wm_range} (запросов: {len(wm_queries)})",
        f"Ядро: {len(keywords)} запросов. Wordstat: {len(wordstat)} запросов с частотностью.",
        "",
        "## Флаги",
        "",
        f"| Флаг | Что делать | Кол-во |",
        f"|---|---|---|",
        f"| NO_PAGE_WITH_SHOWS | Создать страницу (есть показы, target NEW) | {cnt('NO_PAGE_WITH_SHOWS')} |",
        f"| LOW_CTR | Доработать title/description (поз. 5–20, CTR<2%, показы≥10) | {cnt('LOW_CTR')} |",
        f"| WM_NOT_IN_CORE | Добавить в карту (запрос из Вебмастера, нет в ядре, показы≥5) | {cnt('WM_NOT_IN_CORE')} |",
        f"| NO_FREQ | Нет частотности (ждём Wordstat) | {cnt('NO_FREQ')} |",
        "",
        "## Топ-15: показы есть, страницы нет (NO_PAGE_WITH_SHOWS)",
        "",
        "| Запрос | Показы | Клики | CTR% | Целевой URL (NEW) |",
        "|---|---|---|---|---|",
    ]
    for r in top("NO_PAGE_WITH_SHOWS"):
        lines.append(f"| {r['query']} | {r['shows']} | {r['clicks']} | {r['ctr']} | {r['target_url']} |")

    lines += ["", "## Топ-15: низкий CTR на позициях 5–20 (LOW_CTR)", "",
              "| Запрос | Показы | CTR% | Позиция | Страница |",
              "|---|---|---|---|---|"]
    for r in top("LOW_CTR"):
        lines.append(f"| {r['query']} | {r['shows']} | {r['ctr']} | "
                     f"{r['position']:.1f} | {r['target_url']} |")

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
    print(f"Строк в отчёте: {len(rows)} (ядро {len(keywords)}, Вебмастер {len(wm_queries)})")
    print(f"Флаги: NO_PAGE_WITH_SHOWS={cnt('NO_PAGE_WITH_SHOWS')}, "
          f"LOW_CTR={cnt('LOW_CTR')}, WM_NOT_IN_CORE={cnt('WM_NOT_IN_CORE')}, "
          f"NO_FREQ={cnt('NO_FREQ')}")
    conn.close()


if __name__ == "__main__":
    main()
