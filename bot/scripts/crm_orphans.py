#!/usr/bin/env python3
"""Диагностический отчёт по «сиротам» и рассинхрону CRM-хранилища.

Только чтение, ничего не меняет. Запуск из каталога bot/:

    .venv313/bin/python scripts/crm_orphans.py [--db PATH]

Показывает: сообщения без диалога, диалоги без клиента, заявки без клиента,
недоставленные/без external_id исходящие за 7 дней, дубли по
(channel, external_message_id), клиенты без идентичностей.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import crm_store  # noqa: E402

_CHECKS = (
    (
        "crm_messages без conversation",
        "SELECT COUNT(*) c FROM crm_messages m"
        " LEFT JOIN crm_conversations cv ON cv.id = m.conversation_id"
        " WHERE cv.id IS NULL",
    ),
    (
        "crm_conversations без customer",
        "SELECT COUNT(*) c FROM crm_conversations cv"
        " LEFT JOIN customers cu ON cu.id = cv.customer_id"
        " WHERE cu.id IS NULL",
    ),
    (
        "callback_requests без customer",
        "SELECT COUNT(*) c FROM callback_requests WHERE customer_id IS NULL",
    ),
    (
        "исходящие без external_message_id (7 дней)",
        "SELECT COUNT(*) c FROM crm_messages"
        " WHERE direction = 'out' AND channel IN ('max', 'telegram')"
        " AND external_message_id IS NULL"
        " AND created_at >= datetime('now', '-7 days')",
    ),
    (
        "дубли (channel, external_message_id)",
        "SELECT COUNT(*) c FROM ("
        " SELECT channel, external_message_id FROM crm_messages"
        " WHERE external_message_id IS NOT NULL"
        " GROUP BY channel, external_message_id HAVING COUNT(*) > 1)",
    ),
    (
        "customers без identities",
        "SELECT COUNT(*) c FROM customers cu"
        " LEFT JOIN customer_identities i ON i.customer_id = cu.id"
        " WHERE i.id IS NULL AND cu.status != 'archived'",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Отчёт по сиротам CRM-хранилища")
    parser.add_argument("--db", default="", help="Путь к bot.db (по умолчанию DB_PATH из настроек)")
    args = parser.parse_args()

    conn = crm_store.get_conn(args.db or None)
    print("CRM orphans report")
    print("-" * 56)
    problems = 0
    for title, sql in _CHECKS:
        count = int(conn.execute(sql).fetchone()["c"])
        problems += count
        marker = "OK" if count == 0 else "!!"
        print(f"{marker} {title}: {count}")
    print("-" * 56)
    print("Итог: проблем не найдено" if problems == 0 else f"Итог: {problems} записей требуют внимания")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
