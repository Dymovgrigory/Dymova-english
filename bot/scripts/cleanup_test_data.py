#!/usr/bin/env python3
"""Удаление тестовых клиентов/диалогов/заявок из CRM (по запросу владельца).

Удаляет ТОЛЬКО заведомо тестовые сущности — по шаблонам external_user_id,
которые использовали стендовые прогоны (audit-, stress-, retest-, web:hum-,
web:brand-, web:fix-, web:final-, web:prod-, web:deploy-smoke-, e2e-,
reg-smoke-), плюс явно перечисленные заявки (--request-ids).

Реальные клиенты (любой живой external_user_id мессенджера или web-сессии
вне тестовых шаблонов) не трогаются. Режим по умолчанию — dry-run (печатает,
что будет удалено); --apply применяет. Перед запуском на проде сделать бэкап.

Порядок удаления — по внешним ключам: ai_events, сообщения (FTS чистится
триггером), заявки, заметки/задачи/теги, идентичности, диалоги, клиенты.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import crm_store  # noqa: E402

logger = logging.getLogger("cleanup_test_data")

# Шаблоны тестовых external_user_id (префиксы).
TEST_PREFIXES = (
    "audit", "stress-", "retest", "reg-smoke", "e2e-",
    "web:prod-", "prod-smoke", "prod-check",
    "web:hum-", "web:brand-", "web:fix-",
    "web:final-", "web:deploy-smoke-",
)


def _is_test_external(external_user_id: str) -> bool:
    return external_user_id.startswith(TEST_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser(description="Удаление тестовых данных CRM")
    parser.add_argument("--db", default="", help="Путь к БД (по умолчанию DB_PATH)")
    parser.add_argument("--apply", action="store_true", help="Применить удаление")
    parser.add_argument("--request-ids", default="",
                        help="ID заявок на удаление через запятую (тестовые)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    conn = crm_store.get_conn(args.db or None)

    conv_rows = conn.execute(
        "SELECT id, customer_id, channel, external_user_id FROM crm_conversations"
    ).fetchall()
    test_convs = [dict(r) for r in conv_rows if _is_test_external(r["external_user_id"])]
    conv_ids = [c["id"] for c in test_convs]
    # Клиента удаляем, только если ВСЕ его диалоги тестовые. Если у человека
    # есть и реальный диалог (написал позже с настоящего аккаунта) — удаляем
    # только тестовые диалоги, самого клиента оставляем.
    convs_by_customer: dict[int, list[dict]] = {}
    for r in conv_rows:
        convs_by_customer.setdefault(r["customer_id"], []).append(dict(r))
    customer_ids = sorted({
        c["customer_id"] for c in test_convs
        if all(_is_test_external(x["external_user_id"]) for x in convs_by_customer[c["customer_id"]])
    })

    request_ids = [int(x) for x in args.request_ids.split(",") if x.strip().isdigit()]
    if customer_ids:
        marks = ",".join("?" * len(customer_ids))
        request_ids += [
            r["id"] for r in conn.execute(
                f"SELECT id FROM callback_requests WHERE customer_id IN ({marks})",
                customer_ids,
            ).fetchall()
        ]
    request_ids = sorted(set(request_ids))

    report = {
        "apply": bool(args.apply),
        "test_conversations": len(conv_ids),
        "test_customers": len(customer_ids),
        "test_requests": request_ids,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY-RUN: ничего не удалено. Повторите с --apply.")
        return 0

    def _in(ids: list[int]) -> str:
        return ",".join("?" * len(ids)) or "NULL"

    with crm_store._tx(conn):
        if conv_ids:
            # Заявки ссылаются на диалоги (FK) — удаляем их раньше диалогов.
            conn.execute(
                f"DELETE FROM callback_requests WHERE conversation_id IN ({_in(conv_ids)})",
                conv_ids)
            conn.execute(
                f"DELETE FROM ai_events WHERE conversation_id IN ({_in(conv_ids)})", conv_ids)
            conn.execute(
                f"DELETE FROM crm_messages WHERE conversation_id IN ({_in(conv_ids)})", conv_ids)
            conn.execute(
                f"DELETE FROM crm_conversations WHERE id IN ({_in(conv_ids)})", conv_ids)
        if request_ids:
            conn.execute(
                f"DELETE FROM callback_requests WHERE id IN ({_in(request_ids)})", request_ids)
        if customer_ids:
            conn.execute(
                f"DELETE FROM ai_events WHERE customer_id IN ({_in(customer_ids)})", customer_ids)
            conn.execute(
                f"DELETE FROM customer_notes WHERE customer_id IN ({_in(customer_ids)})", customer_ids)
            conn.execute(
                f"DELETE FROM customer_tasks WHERE customer_id IN ({_in(customer_ids)})", customer_ids)
            conn.execute(
                f"DELETE FROM customer_tags WHERE customer_id IN ({_in(customer_ids)})", customer_ids)
            conn.execute(
                f"DELETE FROM broadcast_recipients WHERE customer_id IN ({_in(customer_ids)})",
                customer_ids)
            conn.execute(
                f"DELETE FROM customer_identities WHERE customer_id IN ({_in(customer_ids)})",
                customer_ids)
            conn.execute(
                f"DELETE FROM customers WHERE id IN ({_in(customer_ids)})", customer_ids)
    logger.info("cleanup: удалено диалогов %s, клиентов %s, заявок %s",
                len(conv_ids), len(customer_ids), len(request_ids))
    print("ПРИМЕНЕНО. Осталось клиентов:",
          conn.execute("SELECT count(*) FROM customers").fetchone()[0],
          "| диалогов:", conn.execute("SELECT count(*) FROM crm_conversations").fetchone()[0],
          "| заявок:", conn.execute("SELECT count(*) FROM callback_requests").fetchone()[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
