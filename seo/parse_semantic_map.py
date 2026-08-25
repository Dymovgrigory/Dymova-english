#!/usr/bin/env python3
"""Парсер семантической карты SEO_SEMANTIC_MAP.md → seo/keywords.csv + seo/keywords.sqlite.

Формат источника:
  ## N. Pillar X. <название>            — пиллар
  ### Cluster X.Y. <название> → `url` — приоритет P1   — кластер с приоритетом
  ### 15.x. <название>                  — добивочные подблоки (приоритет не задан)
  | Запрос | Интент | Страница |        — строки запросов
  | # | Вопрос | Целевая страница |     — раздел 12, AI-вопросы (intent=AI)

Страница может быть: `/url`, `NEW /url`, несколько URL, сноска `*(...)*`.
Нечисловые/заголовочные строки и служебные таблицы (раздел 13 «Покрытие») отфильтровываются.
"""
import csv
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import REPO_ROOT, SEO_DIR, get_db

MAP_PATH = os.path.join(REPO_ROOT, "SEO_SEMANTIC_MAP.md")
CSV_PATH = os.path.join(SEO_DIR, "keywords.csv")

# Локации гео-уровней (из легенды карты)
GEO_L2 = ["хлебниково", "водники", "павельцево", "новая дача", "виноградово",
          "шереметьевский", "лобня", "мытищи", "ховрино"]

PILLAR_RE = re.compile(r"^##\s+\d+\.\s+Pillar\s+(\d+)\.\s*(.+?)\s*$")
CLUSTER_RE = re.compile(r"^###\s+Cluster\s+([\d.]+)\.\s*(.+?)\s*$")
SUBBLOCK_RE = re.compile(r"^###\s+15\.\d+\.\s*(.+?)\s*$")
PRIORITY_RE = re.compile(r"приоритет\s+(P\d)")
ROW_RE = re.compile(r"^\|(.+)\|\s*$")
SECTION_NUM_RE = re.compile(r"^##\s+(\d+)\.")


def normalize_query(q):
    q = re.sub(r"\s+", " ", q).strip().lower()
    return q


def clean_url(cell):
    """Убирает markdown-разметку и сноски из ячейки страницы."""
    cell = re.sub(r"\*\(.*?\)\*", "", cell)          # сноски *( ... )*
    cell = cell.replace("`", "").strip()
    cell = re.sub(r"\s+", " ", cell)
    return cell


def detect_geo(query, intent):
    """Гео-уровень: сначала из интента (L2/L4/L), затем по локациям в запросе."""
    if "L2" in intent:
        return "L2"
    if "L4" in intent:
        return "L4"
    if "L5" in intent:
        return "L5"
    if "L" in intent:
        return "L1"
    for loc in GEO_L2:
        if loc in query:
            return "L2"
    if "долгопрудн" in query or "физтех" in query or "мфти" in query:
        return "L1"
    if "москв" in query:
        return "L4"
    return ""


def parse(map_path=MAP_PATH):
    rows = []
    pillar_num, pillar_name = "", ""
    cluster, priority = "", ""
    section = 0
    skipped_tables = 0

    with open(map_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")

            m = SECTION_NUM_RE.match(line)
            if m:
                section = int(m.group(1))
                pm = PILLAR_RE.match(line)
                if pm:
                    pillar_num = "P" + pm.group(1)
                    pillar_name = pm.group(2).strip()
                cluster, priority = "", ""
                continue

            cm = CLUSTER_RE.match(line)
            if cm:
                cluster = f"Cluster {cm.group(1)} {re.sub(r'[—-].*$', '', cm.group(2)).strip().rstrip(' —-')}"
                pr = PRIORITY_RE.search(cm.group(2))
                priority = pr.group(1) if pr else ""
                continue

            sm = SUBBLOCK_RE.match(line)
            if sm:
                cluster = "15.x " + sm.group(1).strip()
                priority = ""
                continue

            rm = ROW_RE.match(line.strip())
            if not rm:
                continue

            cells = [c.strip() for c in rm.group(1).split("|")]
            # Таблица должна иметь ровно 3 колонки данных
            if len(cells) != 3:
                skipped_tables += 1
                continue
            # Заголовки и разделители
            joined = " ".join(cells)
            if set(joined) <= set("-: "):
                continue
            first = cells[0].lower()
            if first in ("запрос", "#", "кластер"):
                skipped_tables += 1
                continue

            if section == 12:
                # | # | Вопрос | Целевая страница |
                if not cells[0].isdigit():
                    skipped_tables += 1
                    continue
                query, intent, page = cells[1], "AI", cells[2]
                cur_cluster = "AI-вопросы (раздел 12)"
                cur_pillar, cur_priority = "AI", "P2"
            else:
                query, intent, page = cells
                cur_cluster = cluster
                cur_pillar, cur_priority = (pillar_num + " " + pillar_name).strip(), priority
                if section == 13:  # служебная таблица покрытия — не запросы
                    skipped_tables += 1
                    continue

            query = normalize_query(query)
            if not query or len(query) < 3:
                skipped_tables += 1
                continue

            page = clean_url(page)
            page_needed = 1 if "NEW" in page.upper() else 0
            rows.append({
                "query": query,
                "cluster": cur_cluster,
                "pillar": cur_pillar,
                "intent": intent,
                "geo_level": detect_geo(query, intent),
                "target_url": page,
                "page_needed": page_needed,
                "priority": cur_priority,
                "status": "active",
            })

    # Дедуп по нормализованному запросу (первое вхождение побеждает)
    seen, unique = set(), []
    for r in rows:
        if r["query"] in seen:
            continue
        seen.add(r["query"])
        unique.append(r)
    return unique, len(rows) - len(unique), skipped_tables


def main():
    rows, dupes, skipped = parse()
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")

    conn = get_db()
    conn.execute("DELETE FROM keywords")
    conn.executemany(
        """INSERT INTO keywords (query, cluster, pillar, intent, geo_level, target_url,
                                 page_needed, priority, status)
           VALUES (:query, :cluster, :pillar, :intent, :geo_level, :target_url,
                   :page_needed, :priority, :status)""",
        rows,
    )
    conn.commit()

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["query", "cluster", "pillar", "intent",
                                          "geo_level", "target_url", "page_needed",
                                          "priority", "status"])
        w.writeheader()
        w.writerows(rows)

    new_cnt = sum(r["page_needed"] for r in rows)
    by_pr = {}
    for r in rows:
        by_pr[r["priority"] or "—"] = by_pr.get(r["priority"] or "—", 0) + 1

    print(f"Источник: {MAP_PATH}")
    print(f"Распарсено уникальных запросов: {len(rows)} (дублей отброшено: {dupes}, "
          f"служебных строк отфильтровано: {skipped})")
    print(f"  из них page_needed (NEW): {new_cnt}")
    print(f"  по приоритетам: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_pr.items())))
    print(f"Записано: {CSV_PATH} и keywords.sqlite (таблица keywords), {fetched}")
    conn.close()


if __name__ == "__main__":
    main()
