#!/usr/bin/env python3
"""Однократная миграция истории диалогов из legacy `conversations` в CRM.

Запуск из каталога bot/:

    .venv313/bin/python scripts/migrate_crm.py [--db PATH] [--force]

Идемпотентно: повторный запуск без --force ничего не делает (маркер в
crm_meta). --force снимает маркер; уже перенесённые диалоги не дублируются
(проверка по числу сообщений в диалоге).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import crm_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Миграция legacy-диалогов в CRM")
    parser.add_argument("--db", default="", help="Путь к bot.db (по умолчанию DB_PATH из настроек)")
    parser.add_argument("--force", action="store_true", help="Снять маркер и перепроверить перенос")
    args = parser.parse_args()

    conn = crm_store.get_conn(args.db or None)
    if args.force:
        conn.execute("DELETE FROM crm_meta WHERE key = 'legacy_migrated'")
    report = crm_store.migrate_from_legacy(conn)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report.get("skipped"):
        print(
            "Перенесено: клиентов {customers_before} -> {customers_after}, "
            "диалогов {conversations_before} -> {conversations_after}, "
            "сообщений {messages_before} -> {messages_after} "
            "(legacy: {legacy_conversations} диалогов, {legacy_messages} сообщений, "
            "пропущено как уже перенесённые: {skipped_existing})".format(**report)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
