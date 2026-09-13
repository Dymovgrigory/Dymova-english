#!/usr/bin/env python3
"""Экспорт тематического словаря сайта в данные Foxinburg World.

Читает списки WORDS_* из исходников страниц через ast (без импорта —
модули сайта при импорте строят страницы). Страницы сайта не изменяются.

Запуск: python3 scripts/export_world_vocabulary.py
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCES = [
    REPO / "prototype" / "build_subpages.py",
    REPO / "prototype" / "pages_words2.py",
    REPO / "prototype" / "pages_words3.py",
]
DEFAULT_OUT = REPO / "bot" / "app" / "world" / "data" / "vocabulary.json"

# Имя списка в исходнике -> slug темы на сайте.
VAR_TO_SLUG = {
    "WORDS_ZHIVOTNYE": "zhivotnye", "WORDS_EDA": "eda", "WORDS_SHKOLA": "shkola",
    "WORDS_SEMA": "semya", "WORDS_TSVETA": "tsveta", "WORDS_PROFESSII": "professii",
    "WORDS_ODEZHDA": "odezhda", "WORDS_POGODA": "pogoda", "WORDS_TRANSPORT": "transport",
    "WORDS_DOM": "dom", "WORDS_SPORT": "sport", "WORDS_PUTESHESTVIYA": "puteshestviya",
    "WORDS_VREMYA": "vremya-i-chisla", "WORDS_HOBBI": "hobbi",
    "WORDS_PRIRODA": "priroda", "WORDS_PRAZDNIKI": "prazdniki",
}
# Канонические названия тем — из build_subpages.make_words_page (other_topics).
SLUG_TO_TITLE = {
    "zhivotnye": "Животные", "eda": "Еда", "shkola": "Школа", "semya": "Семья",
    "tsveta": "Цвета", "professii": "Профессии", "odezhda": "Одежда",
    "pogoda": "Погода", "transport": "Транспорт", "dom": "Дом", "sport": "Спорт",
    "puteshestviya": "Путешествия", "vremya-i-chisla": "Время и числа",
    "hobbi": "Хобби", "priroda": "Природа", "prazdniki": "Праздники",
}
FIELDS = ("en", "ipa", "ru", "example_en", "example_ru")


def extract_lists(path: Path) -> dict[str, list[tuple]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, list[tuple]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id not in VAR_TO_SLUG:
            continue
        found[target.id] = ast.literal_eval(node.value)
    return found


def build_themes() -> list[dict]:
    raw: dict[str, list[tuple]] = {}
    for source in SOURCES:
        raw.update(extract_lists(source))
    missing = set(VAR_TO_SLUG) - set(raw)
    if missing:
        raise SystemExit(f"не найдены списки слов: {sorted(missing)}")
    themes = []
    for var, slug in VAR_TO_SLUG.items():
        words = [dict(zip(FIELDS, row)) for row in raw[var]]
        themes.append({"id": slug, "title_ru": SLUG_TO_TITLE[slug], "words": words})
    themes.sort(key=lambda t: t["id"])
    return themes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    themes = build_themes()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"themes": themes}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    total = sum(len(t["words"]) for t in themes)
    print(f"{args.out}: {len(themes)} тем, {total} слов")


if __name__ == "__main__":
    main()
