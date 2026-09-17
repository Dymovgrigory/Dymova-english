"""Хелперы прохождения урока: `start` намеренно не отдаёт решения, тесты берут их из payload."""
import json
import re

from app.world.db import get_conn


def stored(session_id: str) -> list[dict]:
    row = get_conn().execute("SELECT payload FROM learn_sessions WHERE id=?", (session_id,)).fetchone()
    return json.loads(row["payload"])


def right_answer(challenge: dict) -> dict:
    solution = challenge["solution"]
    kind = solution["kind"]
    if kind == "none":
        return {}
    if kind == "choice":
        return {"index": solution["index"]}
    if kind == "text":
        return {"text": solution["accepted"][0]}
    if kind == "tiles":
        target = solution["accepted"][0]
        return {"tiles": list(target) if solution["joiner"] == "" else re.findall(r"[A-Za-z']+", target)}
    if kind == "pairs":
        return {"pairs": solution["pairs"]}
    return {"transcript": solution["target"]}


def wrong_answer(challenge: dict) -> dict:
    solution = challenge["solution"]
    kind = solution["kind"]
    if kind == "choice":
        return {"index": solution["index"] + 1 if solution["index"] == 0 else 0}
    if kind in ("text",):
        return {"text": "zzzzzz"}
    if kind == "tiles":
        return {"tiles": ["zzz"]}
    if kind == "pairs":
        return {"pairs": []}
    return {"transcript": "zzz"}
