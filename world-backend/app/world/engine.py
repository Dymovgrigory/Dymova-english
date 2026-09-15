"""Движок линейного курса: путь, сессии, сердца, звёзды.

Контент — app.world.learn_course (оригинал), не словарь сайта и не Duo.
Проверка на сервере, награда через core.award.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from . import catalog, config, core, items, srs
from .db import get_conn

LANGUAGE = "en"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _day(dt: datetime | None = None) -> str:
    return (dt or _now()).strftime("%Y-%m-%d")


def parse_lesson_id(lesson_id: str) -> tuple[str, int, bool]:
    if lesson_id.endswith("-C1"):
        unit_id = lesson_id[:-3]
        if unit_id not in catalog.load_units():
            raise core.NotFound(f"lesson {lesson_id!r} not found")
        return unit_id, catalog.LESSONS_PER_UNIT + 1, True
    unit_id, sep, rest = lesson_id.rpartition("-L")
    if not sep or not rest.isdigit():
        raise core.NotFound(f"lesson {lesson_id!r} not found")
    n = int(rest)
    if unit_id not in catalog.load_units() or n < 1 or n > catalog.LESSONS_PER_UNIT:
        raise core.NotFound(f"lesson {lesson_id!r} not found")
    return unit_id, n, False


def refill_hearts(player_id: int) -> dict:
    conn = get_conn()
    row = conn.execute(
        "SELECT hearts, hearts_at FROM players WHERE id=?", (player_id,)
    ).fetchone()
    hearts = int(row["hearts"])
    if hearts >= config.HEARTS_MAX:
        return {"hearts": hearts, "next_in_sec": None}
    try:
        last = datetime.fromisoformat(row["hearts_at"].replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        last = _now()
    elapsed = (_now() - last).total_seconds()
    gained = int(elapsed // config.HEART_REGEN_SEC)
    if gained:
        hearts = min(config.HEARTS_MAX, hearts + gained)
        used = gained * config.HEART_REGEN_SEC
        new_at = last + timedelta(seconds=used)
        conn.execute(
            "UPDATE players SET hearts=?, hearts_at=? WHERE id=?",
            (hearts, new_at.replace(tzinfo=None).isoformat(timespec="seconds"), player_id),
        )
    next_in = None
    if hearts < config.HEARTS_MAX:
        remain = config.HEART_REGEN_SEC - (elapsed % config.HEART_REGEN_SEC)
        next_in = int(remain)
    return {"hearts": hearts, "next_in_sec": next_in}


def set_hearts(player_id: int, hearts: int) -> None:
    get_conn().execute(
        "UPDATE players SET hearts=?, hearts_at=datetime('now') WHERE id=?",
        (max(0, hearts), player_id),
    )


def _stars_row(player_id: int, lesson_id: str) -> int:
    row = get_conn().execute(
        "SELECT stars FROM lesson_progress WHERE player_id=? AND lesson_id=?",
        (player_id, lesson_id),
    ).fetchone()
    return int(row["stars"]) if row else 0


def _nodes_for_unit(unit: dict, player_id: int, unit_locked: bool) -> list[dict]:
    nodes = []
    prev_done = True
    for n, spot in enumerate(unit["spots"], start=1):
        lid = f"{unit['id']}-L{n}"
        stars = _stars_row(player_id, lid)
        locked = False if config.UNLOCK_ALL else (unit_locked or not prev_done)
        nodes.append({
            "id": lid, "index": n, "kind": "lesson",
            "title_ru": spot, "stars": stars, "locked": locked,
        })
        prev_done = stars >= 1
    if unit.get("has_checkpoint"):
        cid = f"{unit['id']}-C1"
        cstars = _stars_row(player_id, cid)
        nodes.append({
            "id": cid, "index": catalog.LESSONS_PER_UNIT + 1, "kind": "checkpoint",
            "title_ru": unit["checkpoint_ru"], "stars": cstars,
            "locked": False if config.UNLOCK_ALL else (unit_locked or not prev_done),
        })
    return nodes


def get_path(external_key: str) -> dict:
    player = core.get_player(external_key)
    refill_hearts(player["id"])
    units = []
    prev_unit_done = True
    for unit_id in catalog.unit_order():
        unit = catalog.get_unit(unit_id)
        unit_locked = False if config.UNLOCK_ALL else (not prev_unit_done)
        lessons = _nodes_for_unit(unit, player["id"], unit_locked)
        units.append({
            "id": unit_id,
            "title_ru": unit["place_ru"],
            "topic_ru": unit["topic_ru"],
            "goal_ru": unit.get("goal_ru", ""),
            "book": unit.get("book", "prep"),
            "book_ru": unit.get("book_ru", ""),
            "accent": unit["accent"],
            "locked": unit_locked,
            "lessons": lessons,
        })
        last = lessons[-1]
        need = config.CHECKPOINT_STARS_TO_UNLOCK if last["kind"] == "checkpoint" else 1
        prev_unit_done = last["stars"] >= need
    return {
        "language": LANGUAGE,
        "hearts_max": config.HEARTS_MAX,
        "hearts": refill_hearts(player["id"])["hearts"],
        "program_ru": "1 класс: говорим с Фокси. Потом учимся читать по звукам.",
        "next_book_ru": "После устной линии — 72 урока чтения (phonics).",
        "player": core.get_player(external_key),
        "stickers_owned": sum(1 for i in core.get_inventory(external_key) if i["category"] == "stickers"),
        "unlock_all": config.UNLOCK_ALL,
        "units": units,
    }


def _start_session(external_key: str, lesson_id: str, built: list[dict], *,
                   practice: bool, title: str, extra: dict) -> dict:
    player = core.get_player(external_key)
    hearts = refill_hearts(player["id"])["hearts"]
    if hearts <= 0:
        raise core.Conflict("no hearts left")
    session_id = str(uuid.uuid4())
    payload = {
        "kind": "practice" if practice else "lesson",
        "lesson_id": lesson_id,
        "items": built,
        "hearts": hearts,
        "practice": practice,
        **extra,
    }
    get_conn().execute(
        "INSERT INTO activity_sessions (id, player_id, activity_id, payload) VALUES (?,?,?,?)",
        (session_id, player["id"], lesson_id, json.dumps(payload, ensure_ascii=False)),
    )
    return {
        "session_id": session_id,
        "lesson_id": lesson_id,
        "title_ru": title,
        "practice": practice,
        "hearts": hearts,
        "hearts_max": config.HEARTS_MAX,
        "total": len(built),
        "items": [items.public_item(i, it) for i, it in enumerate(built)],
        **{k: extra[k] for k in ("place_ru", "spot_ru", "accent", "review_due") if k in extra},
    }


def start_lesson(external_key: str, lesson_id: str, seed: int | None = None) -> dict:
    unit_id, lesson_n, checkpoint = parse_lesson_id(lesson_id)
    path = get_path(external_key)
    node = next(
        ls for u in path["units"] if u["id"] == unit_id
        for ls in u["lessons"] if ls["id"] == lesson_id
    )
    if node["locked"]:
        raise core.Conflict(f"lesson {lesson_id} is locked")
    unit = catalog.get_unit(unit_id)
    built = items.build_lesson_items(unit_id, lesson_n, checkpoint=checkpoint, seed=seed)
    spot = node["title_ru"]
    return _start_session(
        external_key, lesson_id, built, practice=False,
        title=f"{unit['place_ru']} · {spot}",
        extra={"place_ru": unit["place_ru"], "spot_ru": spot, "accent": unit["accent"],
               "unit_id": unit_id},
    )


def start_practice(external_key: str, seed: int | None = None) -> dict:
    """Двор тренировки: сначала незакрытые промахи, затем созревшие слова, потом добивка."""
    player = core.get_player(external_key)
    built: list[dict] = []
    seen: set[str] = set()

    def add(item: dict) -> bool:
        if len(built) >= config.PRACTICE_ITEMS:
            return False
        sig = items.signature(item)
        if sig in seen:
            return False
        seen.add(sig)
        built.append(item)
        return True

    for mid, item in _open_mistakes(player["id"]):
        item.setdefault("home_unit", _mistake_unit(mid))
        add(item)

    due = srs.due_words(player["id"], limit=config.PRACTICE_ITEMS)
    review_due = srs.review_count(player["id"])
    for item in items.build_review_items(due, seed=seed):
        add(item)

    if len(built) < config.PRACTICE_ITEMS_MIN:
        here = _current_open_lesson(external_key)
        try:
            unit_id, lesson_n, checkpoint = parse_lesson_id(here)
        except core.NotFound:
            unit_id, lesson_n, checkpoint = "family", 1, False
        padding = items.build_lesson_items(unit_id, lesson_n, checkpoint=checkpoint, seed=seed or 99)
        for item in padding:
            if item["kind"] in ("explain", "word_card", "phrase_card"):
                continue
            item.setdefault("home_unit", unit_id)
            if len(built) >= config.PRACTICE_ITEMS_MIN:
                break
            add(item)

    return _start_session(
        external_key, "practice", built, practice=True,
        title="Двор тренировки",
        extra={"place_ru": "Двор тренировки", "spot_ru": "Повтор", "accent": "#3a2953",
               "unit_id": "practice", "review_due": review_due},
    )


def _mistake_unit(mistake_id: int) -> str:
    row = get_conn().execute("SELECT unit_id FROM mistakes WHERE id=?", (mistake_id,)).fetchone()
    return (row["unit_id"] or "") if row else ""


def _current_open_lesson(external_key: str) -> str:
    for unit in get_path(external_key)["units"]:
        for node in unit["lessons"]:
            if not node["locked"] and int(node.get("stars") or 0) == 0:
                return node["id"]
    return "family-L1"


def _load(external_key: str, session_id: str) -> tuple[dict, dict, dict]:
    player = core.get_player(external_key)
    row = get_conn().execute(
        "SELECT * FROM activity_sessions WHERE id=? AND player_id=?",
        (session_id, player["id"]),
    ).fetchone()
    if row is None:
        raise core.NotFound(f"activity session {session_id!r} not found")
    return player, dict(row), json.loads(row["payload"])


def _touch_word(player_id: int, unit_id: str, item: dict, correct: bool) -> None:
    word = item.get("en")
    if not word:
        return
    home = unit_id if unit_id and unit_id != "practice" else item.get("home_unit") or ""
    if not home:
        return
    srs.touch(player_id, home, word, correct=correct)


def _open_mistakes(player_id: int) -> list[tuple[int, dict]]:
    rows = get_conn().execute(
        "SELECT id, item FROM mistakes WHERE player_id=? AND cleared=0", (player_id,)
    ).fetchall()
    return [(int(r["id"]), json.loads(r["item"])) for r in rows]


def _remember_mistake(player_id: int, unit_id: str, item: dict) -> None:
    sig = items.signature(item)
    if any(items.signature(m) == sig for _, m in _open_mistakes(player_id)):
        return
    get_conn().execute(
        "INSERT INTO mistakes (player_id, unit_id, item) VALUES (?,?,?)",
        (player_id, unit_id, json.dumps(item, ensure_ascii=False)),
    )


def _clear_mistake(player_id: int, item: dict) -> None:
    sig = items.signature(item)
    ids = [mid for mid, m in _open_mistakes(player_id) if items.signature(m) == sig]
    if not ids:
        return
    marks = ",".join("?" * len(ids))
    get_conn().execute(
        f"UPDATE mistakes SET cleared=1 WHERE player_id=? AND id IN ({marks})",
        (player_id, *ids),
    )


def answer(external_key: str, session_id: str, index: int, value: dict) -> dict:
    player, session, payload = _load(external_key, session_id)
    if session["status"] != "active":
        raise core.Conflict("activity already completed")
    hearts = int(payload.get("hearts", config.HEARTS_MAX))
    if hearts <= 0:
        raise core.Conflict("no hearts left")
    built_items = payload["items"]
    if not 0 <= index < len(built_items):
        raise core.NotFound(f"question {index} not found")
    answers = json.loads(session["answers"])
    if str(index) in answers:
        raise core.Conflict(f"question {index} already answered")

    item = built_items[index]
    correct = items.grade(item, value or {})
    drill = item.get("kind") not in ("explain", "word_card", "phrase_card")
    if drill and not correct:
        hearts -= 1
        _remember_mistake(player["id"], payload.get("unit_id") or "", item)
    elif drill and correct:
        _clear_mistake(player["id"], item)
    set_hearts(player["id"], hearts)
    _touch_word(player["id"], payload.get("unit_id") or "", item, correct)
    answers[str(index)] = {"correct": correct, "value": value}
    payload["hearts"] = hearts
    failed = hearts <= 0
    if failed:
        payload["failed"] = True
    get_conn().execute(
        "UPDATE activity_sessions SET answers=?, payload=? WHERE id=?",
        (json.dumps(answers, ensure_ascii=False),
         json.dumps(payload, ensure_ascii=False), session_id),
    )
    result = {
        "index": index,
        "correct": correct,
        "hearts": hearts,
        "failed": failed,
        "answered": len(answers),
        "total": len(built_items),
        "example_en": item.get("example_en", ""),
        "example_ru": item.get("example_ru", ""),
    }
    if not correct:
        result.update(items.leak_correct(item))
    return result


def _bump_streak(player_id: int) -> int:
    row = get_conn().execute(
        "SELECT streak_days, last_lesson_day, streak_freeze FROM players WHERE id=?",
        (player_id,),
    ).fetchone()
    today = _day()
    last = row["last_lesson_day"]
    days = int(row["streak_days"] or 0)
    freeze = int(row["streak_freeze"] or 0)
    if last == today:
        return days
    yesterday = _day(_now() - timedelta(days=1))
    if last is None:
        days = 1
    elif last == yesterday:
        days += 1
    elif freeze > 0:
        freeze -= 1
        days = max(days, 1)
    else:
        days = 1
    get_conn().execute(
        "UPDATE players SET streak_days=?, last_lesson_day=?, streak_freeze=? WHERE id=?",
        (days, today, freeze, player_id),
    )
    return days


def _add_daily_xp(player_id: int, xp: int) -> int:
    row = get_conn().execute(
        "SELECT daily_xp, daily_xp_day FROM players WHERE id=?", (player_id,)
    ).fetchone()
    today = _day()
    current = int(row["daily_xp"] or 0) if row["daily_xp_day"] == today else 0
    current += xp
    get_conn().execute(
        "UPDATE players SET daily_xp=?, daily_xp_day=? WHERE id=?",
        (current, today, player_id),
    )
    return current


def _practice_coins(player_id: int) -> int:
    """Награда за практику в пределах суточного лимита (config.PRACTICE_COINS_DAILY_CAP)."""
    paid = int(get_conn().execute(
        "SELECT COALESCE(SUM(amount),0) AS c FROM coin_transactions"
        " WHERE player_id=? AND type='PRACTICE_REWARD' AND amount>0 AND date(created_at)=?",
        (player_id, _day()),
    ).fetchone()["c"])
    left = config.PRACTICE_COINS_DAILY_CAP - paid
    return max(0, min(config.COIN_REWARDS["practice_complete"], left))


def finish(external_key: str, session_id: str) -> dict:
    player, session, payload = _load(external_key, session_id)
    built_items = payload["items"]
    answers = json.loads(session["answers"])
    if payload.get("failed") or int(payload.get("hearts", config.HEARTS_MAX)) <= 0:
        raise core.Conflict("lesson failed: no hearts left")
    if len(answers) < len(built_items):
        raise core.Conflict("activity not finished: not all questions answered")

    score = sum(1 for a in answers.values() if a["correct"])
    total = len(built_items)
    ratio = score / total if total else 0
    stars = 3 if ratio == 1 else 2 if ratio >= 0.9 else 1

    if session["status"] == "completed":
        return payload["completion"]

    practice = bool(payload.get("practice"))
    xp = config.XP_REWARDS["practice_complete"] if practice else config.XP_REWARDS["lesson_complete"]
    coins = _practice_coins(player["id"]) if practice else config.COIN_REWARDS["lesson_complete"]
    if not practice and score == total:
        xp += config.XP_REWARDS["lesson_perfect"]
        coins += config.COIN_REWARDS["lesson_perfect"]
    stickers: list[str] = []
    if not practice:
        unit_id, _, _ = parse_lesson_id(session["activity_id"])
        stickers.append(f"sticker-{unit_id}")
        if stars == 3:
            stickers.append("sticker-perfect")
        done = get_conn().execute(
            "SELECT COUNT(*) AS n FROM lesson_progress WHERE player_id=?",
            (player["id"],),
        ).fetchone()["n"]
        if int(done) == 0:
            stickers.append("sticker-hello")
    result = core.award(
        external_key,
        xp=xp,
        coins=coins,
        source=session["activity_id"],
        type_="PRACTICE_REWARD" if practice else "LESSON_REWARD",
        items=stickers or None,
        idempotency_key=(
            f"practice-reward:{player['id']}:{session_id}" if practice
            else f"lesson-reward:{player['id']}:{session['activity_id']}"
        ),
    )
    conn = get_conn()
    if not practice:
        conn.execute(
            "INSERT INTO lesson_progress (player_id, lesson_id, stars, best_score)"
            " VALUES (?,?,?,?)"
            " ON CONFLICT(player_id, lesson_id) DO UPDATE SET"
            " stars=MAX(lesson_progress.stars, excluded.stars),"
            " best_score=MAX(lesson_progress.best_score, excluded.best_score)",
            (player["id"], session["activity_id"], stars, score),
        )
        _bump_streak(player["id"])
        fresh = core.get_player(external_key)
        if int(fresh.get("streak_days") or 0) >= 3:
            extra = core.award(
                external_key, source=session["activity_id"], type_="STREAK_STICKER",
                items=["sticker-streak"],
                idempotency_key=f"sticker-streak:{player['id']}",
            )
            result["items_granted"] = list(result.get("items_granted") or []) + list(extra.get("items_granted") or [])
    daily = _add_daily_xp(player["id"], result["xp_delta"])
    completion = {
        "session_id": session_id,
        "lesson_id": session["activity_id"],
        "score": score,
        "total": total,
        "stars": stars,
        "perfect": score == total,
        "xp_delta": result["xp_delta"],
        "coins_delta": result["coins_delta"],
        "items_granted": result.get("items_granted") or [],
        "practice": practice or (result["xp_delta"] == 0 and result["coins_delta"] == 0),
        "daily_xp": daily,
        "daily_goal": config.DAILY_XP_GOAL,
        "level_up": result["level_up"],
        "new_level": result["new_level"],
        "new_title": result["new_title"],
        "player": core.get_player(external_key),
    }
    payload["completion"] = completion
    conn.execute(
        "UPDATE activity_sessions SET status='completed', score=?, payload=?,"
        " completed_at=datetime('now') WHERE id=?",
        (score, json.dumps(payload, ensure_ascii=False), session_id),
    )
    return completion
