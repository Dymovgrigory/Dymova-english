#!/usr/bin/env python3
"""Восстановление истории CRM из legacy-таблицы `conversations`.

Отличие от scripts/migrate_crm.py: тот перенос однократный (маркер в
crm_meta) и целиком по диалогу, а этот скрипт — починивающий бэкфилл:
- по умолчанию DRY-RUN: печатает отчёт, ничего не пишет;
- --apply применяет перенос;
- дедупликация по сообщению: дубль = то же текст и created_at в пределах
  ±5 секунд от ts из legacy-транскрипта — повторный запуск безопасен.

Запуск из каталога bot/:

    .venv313/bin/python scripts/backfill_crm_history.py [--db PATH] [--apply]

Ничего не удаляет: legacy-таблица остаётся состоянием для AI.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import crm_store  # noqa: E402

logger = logging.getLogger("backfill_crm_history")

# Окно дедупликации: legacy-ts и created_at одного и того же сообщения
# могут расходиться на секунды из-за повторной записи.
_DUP_WINDOW_SEC = 5


def _norm_ts(raw: object, fallback: str) -> str:
    """ISO-метка транскрипта приводится к формату остальных строк crm_messages
    ('%Y-%m-%dT%H:%M:%S+00:00', UTC): смешанные форматы ломают и дедуп, и
    сортировку истории (строковое сравнение ' ' против 'T')."""
    ts = str(raw or "")
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.fromisoformat(fallback.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _find_duplicate(conn, conv_id: int, text: str, ts: str) -> bool:
    # datetime() с обеих сторон: существующие строки хранят ISO с tz,
    # naive-строки без него — приводим всё к UTC-секундам перед сравнением.
    row = conn.execute(
        "SELECT id FROM crm_messages"
        " WHERE conversation_id = ? AND text = ?"
        " AND datetime(created_at) BETWEEN datetime(?, ?) AND datetime(?, ?) LIMIT 1",
        (conv_id, text, ts, f"-{_DUP_WINDOW_SEC} seconds", ts, f"+{_DUP_WINDOW_SEC} seconds"),
    ).fetchone()
    return row is not None


def _iter_transcript(payload: str) -> list[dict]:
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return []
    items = data.get("transcript") or []
    return items if isinstance(items, list) else []


def main() -> int:
    parser = argparse.ArgumentParser(description="Бэкфилл CRM-истории из legacy conversations")
    parser.add_argument("--db", default="", help="Путь к bot.db (по умолчанию DB_PATH из настроек)")
    parser.add_argument("--apply", action="store_true", help="Применить перенос (без флага — dry-run)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    conn = crm_store.get_conn(args.db or None)
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'conversations'"
    ).fetchone()
    if table is None:
        print("Legacy-таблица conversations не найдена — переносить нечего.")
        return 0

    rows = conn.execute("SELECT platform, user_id, payload FROM conversations").fetchall()
    now = crm_store._now()
    report = {
        "apply": bool(args.apply),
        "legacy_conversations": len(rows),
        "legacy_messages": 0,
        "added": 0,
        "duplicates": 0,
        "broken_payloads": 0,
        "new_conversations": 0,
    }
    for row in rows:
        transcript = _iter_transcript(row["payload"])
        if not transcript and row["payload"]:
            try:
                json.loads(row["payload"])
            except (json.JSONDecodeError, TypeError):
                report["broken_payloads"] += 1
        report["legacy_messages"] += len(transcript)
        if not transcript:
            continue

        platform, user_id = row["platform"], row["user_id"]
        existing_conv = crm_store.find_conversation(platform, user_id)
        if existing_conv is not None:
            conv_id = int(existing_conv["id"])
            customer_id = int(existing_conv["customer_id"])
        elif not args.apply:
            # Dry-run ничего не создаёт: весь транскрипт считаем новым.
            report["new_conversations"] += 1
            report["added"] += len(transcript)
            continue
        else:
            customer_id = crm_store.upsert_customer_for_identity(platform, user_id)
            conv_id = crm_store.get_or_create_conversation(customer_id, platform, user_id)
            report["new_conversations"] += 1

        for item in transcript:
            role = str(item.get("role", "user"))
            if role == "user":
                direction, sender_type = "in", "customer"
            elif role in ("assistant", "bot"):
                direction, sender_type = "out", "ai"
            else:
                direction, sender_type = "out", "system"
            text = str(item.get("content", ""))
            ts = _norm_ts(item.get("ts"), now)
            if _find_duplicate(conn, conv_id, text, ts):
                report["duplicates"] += 1
                continue
            if args.apply:
                crm_store.add_message(
                    conv_id, customer_id, platform, direction, sender_type,
                    text, status="delivered", created_at=ts,
                )
            report["added"] += 1

    logger.info("backfill: %s", json.dumps(report, ensure_ascii=False))
    mode = "ПРИМЕНЕНО" if args.apply else "DRY-RUN (запишется только с --apply)"
    print(
        f"{mode}: legacy-диалогов {report['legacy_conversations']}, "
        f"сообщений {report['legacy_messages']}, будет добавлено {report['added']}, "
        f"пропущено как дубли {report['duplicates']}, "
        f"битых payload {report['broken_payloads']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
