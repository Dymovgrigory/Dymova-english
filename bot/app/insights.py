"""Цикл улучшения: сбор «пробелов» базы знаний и отчёт для администратора.

Когда бот отвечает неуверенно (низкое совпадение запроса с базой знаний), вопрос
клиента логируется в JSONL-журнал. По журналу строится сводка самых частых
«слабых» вопросов — что именно стоит дозаполнить в базе знаний.

Никаких персональных данных не сохраняем: только текст вопроса, причина, оценка
релевантности и время. user_id хэшируется, чтобы оценивать охват, но не
идентифицировать клиента.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections import Counter
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)


def _path() -> Path | None:
    if not settings.INSIGHTS_FILE:
        return None
    return Path(settings.INSIGHTS_FILE)


def _norm(question: str) -> str:
    """Грубая нормализация вопроса для группировки похожих формулировок."""
    return " ".join(_WORD_RE.findall((question or "").lower()))


def log_gap(question: str, reason: str, score: float, user_id: str = "") -> None:
    """Записывает «пробел» в журнал (если включён INSIGHTS_FILE)."""
    path = _path()
    question = (question or "").strip()
    if not path or not question:
        return
    record = {
        "ts": int(time.time()),
        "question": question[:500],
        "norm": _norm(question)[:500],
        "reason": reason,
        "score": round(float(score), 3),
        "uid": hashlib.sha1(user_id.encode("utf-8")).hexdigest()[:10] if user_id else "",
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("insights: не удалось записать пробел")


def _read(since_ts: int = 0) -> list[dict]:
    path = _path()
    if not path or not path.exists():
        return []
    rows: list[dict] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("ts", 0) >= since_ts:
                    rows.append(rec)
    except Exception:
        logger.exception("insights: не удалось прочитать журнал")
    return rows


def summarize(days: int = 30, top: int = 20) -> dict:
    """Сводка пробелов за период: топ повторяющихся вопросов со счётчиками."""
    since = int(time.time()) - days * 86400 if days else 0
    rows = _read(since)
    by_norm: dict[str, dict] = {}
    for rec in rows:
        key = rec.get("norm") or rec.get("question", "")
        if not key:
            continue
        item = by_norm.setdefault(
            key, {"question": rec.get("question", key), "count": 0, "last_ts": 0,
                   "reasons": Counter(), "uids": set()}
        )
        item["count"] += 1
        item["last_ts"] = max(item["last_ts"], rec.get("ts", 0))
        item["reasons"][rec.get("reason", "")] += 1
        if rec.get("uid"):
            item["uids"].add(rec["uid"])
    gaps = sorted(by_norm.values(), key=lambda x: (x["count"], x["last_ts"]), reverse=True)
    top_gaps = [
        {
            "question": g["question"],
            "count": g["count"],
            "users": len(g["uids"]),
            "last_ts": g["last_ts"],
            "reason": (g["reasons"].most_common(1)[0][0] if g["reasons"] else ""),
        }
        for g in gaps[:top]
    ]
    return {
        "period_days": days,
        "total_weak_answers": len(rows),
        "unique_questions": len(by_norm),
        "gaps": top_gaps,
    }


def digest(days: int = 7, top: int = 10) -> str:
    """Готовый текст-дайджест «слабых мест» за период (для отчёта администратору)."""
    s = summarize(days=days, top=top)
    if not s["gaps"]:
        return (f"За последние {days} дн. бот отвечал уверенно — "
                "пробелов в базе знаний не зафиксировано. 👍")
    lines = [
        f"📊 Дайджест улучшений за {days} дн.",
        f"Слабых ответов: {s['total_weak_answers']}, уникальных тем: {s['unique_questions']}.",
        "",
        "Чаще всего бот «плавал» в этих вопросах — стоит дозаполнить базу знаний:",
    ]
    for i, g in enumerate(s["gaps"], 1):
        lines.append(f"{i}. «{g['question']}» — {g['count']} раз(а), {g['users']} клиент(ов)")
    return "\n".join(lines)
