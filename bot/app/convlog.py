"""Долговременный JSONL-лог диалогов для аналитики и отчётов."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings

_lock = threading.Lock()


def _resolve_path() -> Path | None:
    raw = (settings.CONV_LOG_FILE or "").strip()
    if raw:
        return Path(raw).expanduser()
    state_file = (settings.STATE_FILE or "").strip()
    if state_file:
        return Path(state_file).expanduser().resolve().parent / "conversations.jsonl"
    return None


def get_log_path() -> Path | None:
    return _resolve_path()


def log_turn(
    user_id: str,
    user_text: str,
    bot_reply: str,
    intent: str,
    stage: str,
    result: str,
) -> None:
    path = _resolve_path()
    if path is None:
        return
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user_id": str(user_id),
        "user_text": str(user_text),
        "bot_reply": str(bot_reply),
        "intent": str(intent),
        "stage": str(stage),
        "result": str(result),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=False)
        with _lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception:
        return


def iter_turns(days: int = 1) -> list[dict]:
    path = _resolve_path()
    if path is None or not path.exists():
        return []
    cutoff = None
    if days and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    turns: list[dict] = []
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                item = json.loads(raw_line)
            except Exception:
                continue
            ts_raw = str(item.get("ts", ""))
            try:
                ts = datetime.fromisoformat(ts_raw)
            except Exception:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if cutoff and ts < cutoff:
                continue
            turns.append(item)
    except Exception:
        return []
    return turns
