"""Домашний экран курса, магазин, лига, ежедневные квесты."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import brain, catalog, config, core, engine, srs
from .db import get_conn


def current_lesson_id(external_key: str) -> str | None:
    path = engine.get_path(external_key)
    for unit in path["units"]:
        for node in unit["lessons"]:
            if not node["locked"] and node["stars"] == 0:
                return node["id"]
    for unit in path["units"]:
        for node in unit["lessons"]:
            if not node["locked"]:
                return node["id"]
    return None


def daily_quests(external_key: str) -> list[dict]:
    player = core.get_player(external_key)
    today = engine._day()
    row = get_conn().execute(
        "SELECT daily_xp, daily_xp_day FROM players WHERE id=?", (player["id"],)
    ).fetchone()
    xp_today = int(row["daily_xp"] or 0) if row["daily_xp_day"] == today else 0
    lessons_today = get_conn().execute(
        "SELECT COUNT(*) AS n FROM lesson_progress WHERE player_id=? AND date(updated_at)=?",
        (player["id"], today),
    ).fetchone()["n"]
    perfect = get_conn().execute(
        "SELECT COUNT(*) AS n FROM lesson_progress WHERE player_id=? AND stars=3 AND date(updated_at)=?",
        (player["id"], today),
    ).fetchone()["n"]
    claimed_rows = get_conn().execute(
        "SELECT idempotency_key FROM xp_transactions"
        " WHERE player_id=? AND type='DAILY_QUEST'"
        " AND idempotency_key LIKE ?",
        (player["id"], f"daily-quest:{player['id']}:{today}:%"),
    ).fetchall()
    claimed: set[str] = set()
    prefix = f"daily-quest:{player['id']}:{today}:"
    for r in claimed_rows:
        key = str(r["idempotency_key"])
        if key.startswith(prefix):
            rest = key[len(prefix):]
            # ledger stores `{idem}:xp`
            if rest.endswith(":xp"):
                rest = rest[:-3]
            claimed.add(rest)

    def pack(qid: str, title: str, progress: int, target: int) -> dict:
        done = progress >= target
        return {
            "id": qid,
            "title_ru": title,
            "progress": min(progress, target),
            "target": target,
            "done": done,
            "claimed": qid in claimed,
            "claimable": done and qid not in claimed,
        }

    return [
        pack("xp-goal", f"Набери {config.DAILY_XP_GOAL} XP", xp_today, config.DAILY_XP_GOAL),
        pack("lesson-1", "Пройди 1 урок", int(lessons_today), 1),
        pack("perfect-1", "Урок без ошибок", int(perfect), 1),
    ]


def claim_daily_quest(external_key: str, quest_id: str) -> dict:
    """Grant daily quest XP once per day when progress is done."""
    quests = {q["id"]: q for q in daily_quests(external_key)}
    q = quests.get(quest_id)
    if q is None:
        raise core.NotFound(f"daily quest {quest_id!r}")
    if not q["done"]:
        raise core.Conflict("quest not complete")
    if q.get("claimed"):
        # Idempotent success for double-tap
        player = core.get_player(external_key)
        return {"quest_id": quest_id, "ok": True, "xp_delta": 0, "coins_delta": 0, "player": player}
    player = core.get_player(external_key)
    day = engine._day()
    xp = int(config.XP_REWARDS.get("daily_quest", 15))
    result = core.award(
        external_key,
        xp=xp,
        source=f"daily:{quest_id}",
        type_="DAILY_QUEST",
        idempotency_key=f"daily-quest:{player['id']}:{day}:{quest_id}",
    )
    return {"quest_id": quest_id, "ok": True, **result}


LEAGUE_TIERS = ((500, "gold"), (150, "silver"), (0, "bronze"))
LEAGUE_TOP = 10


def tier_for(weekly_xp: int) -> str:
    for edge, name in LEAGUE_TIERS:
        if weekly_xp >= edge:
            return name
    return "bronze"


def league(external_key: str) -> dict:
    """Недельный рейтинг по всем игрокам: тир, место, размер лиги и таблица лидеров."""
    from app.castle import league_weeks

    league_weeks.close_previous_week()
    player = core.get_player(external_key)
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = get_conn().execute(
        "SELECT p.id, p.display_name,"
        " COALESCE(SUM(CASE WHEN x.amount>0 AND date(x.created_at)>=? THEN x.amount END),0) AS xp"
        " FROM players p LEFT JOIN xp_transactions x ON x.player_id=p.id"
        " WHERE p.role='child'"
        " GROUP BY p.id ORDER BY xp DESC, p.id ASC",
        (since,),
    ).fetchall()
    board = [
        {
            "rank": i,
            "display_name": r["display_name"],
            "weekly_xp": int(r["xp"]),
            "tier": tier_for(int(r["xp"])),
            "is_me": r["id"] == player["id"],
        }
        for i, r in enumerate(rows, start=1)
    ]
    me = next((row for row in board if row["is_me"]), None)
    weekly = me["weekly_xp"] if me else 0
    history = [
        {"week_start": r["week_start"], "rank": int(r["rank"]),
         "weekly_xp": int(r["weekly_xp"]), "coins_awarded": int(r["coins_awarded"])}
        for r in get_conn().execute(
            "SELECT week_start, rank, weekly_xp, coins_awarded FROM league_weeks"
            " WHERE player_id=? ORDER BY week_start DESC LIMIT 8",
            (player["id"],),
        ).fetchall()
    ]
    return {
        "tier": tier_for(weekly),
        "weekly_xp": weekly,
        "rank": me["rank"] if me else len(board) + 1,
        "size": len(board),
        "top": board[:LEAGUE_TOP],
        "history": history,
    }


def restore_hearts(external_key: str) -> dict:
    """Hearts refill is a shop purchase — never free."""
    bought = buy(external_key, "hearts_refill")
    return {
        "hearts": config.HEARTS_MAX,
        "hearts_max": config.HEARTS_MAX,
        "coins_delta": bought.get("coins_delta", 0),
        "player": bought.get("player"),
    }


def shop() -> list[dict]:
    return [
        {"sku": sku, "coins": spec["coins"], "title_ru": spec["title_ru"]}
        for sku, spec in config.SHOP.items()
    ]


def buy(external_key: str, sku: str) -> dict:
    spec = config.SHOP.get(sku)
    if spec is None:
        raise core.NotFound(f"sku {sku!r} not found")
    player = core.get_player(external_key)
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM coin_transactions"
            " WHERE player_id=? AND type=? AND source=?",
            (player["id"], "SHOP_BUY", sku),
        ).fetchone()["c"]
        spend_key = f"shop:{player['id']}:{sku}:{n}"
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    spent = core.spend(
        external_key, coins=spec["coins"], source=sku, type_="SHOP_BUY",
        idempotency_key=spend_key,
    )
    if not spent.get("applied"):
        return {
            "sku": sku,
            "ok": True,
            "player": core.get_player(external_key),
            "coins_delta": 0,
            "items_granted": [],
        }
    hearts_out = None
    if sku == "hearts_refill":
        engine.set_hearts(player["id"], config.HEARTS_MAX)
        hearts_out = config.HEARTS_MAX
    elif sku == "streak_freeze":
        get_conn().execute(
            "UPDATE players SET streak_freeze=streak_freeze+1 WHERE id=?",
            (player["id"],),
        )
    item_id = spec.get("item")
    granted: list[str] = []
    if item_id:
        extra = core.award(
            external_key, source=sku, type_="SHOP_ITEM", items=[item_id],
            idempotency_key=f"shop-item:{player['id']}:{sku}",
        )
        granted = extra.get("items_granted") or []
    out = {"sku": sku, "ok": True, "player": core.get_player(external_key),
           "coins_delta": spent["coins_delta"], "items_granted": granted}
    if hearts_out is not None:
        out["hearts"] = hearts_out
        out["hearts_max"] = config.HEARTS_MAX
    return out


def album(external_key: str) -> dict:
    owned = {i["id"]: i for i in core.get_inventory(external_key) if i["category"] == "stickers"}
    catalog_rows = []
    rows = get_conn().execute(
        "SELECT id, title_ru, asset_id, rarity FROM items WHERE category='stickers' ORDER BY id"
    ).fetchall()
    for r in rows:
        catalog_rows.append({
            "id": r["id"],
            "title_ru": r["title_ru"],
            "emoji": r["asset_id"] or "🦊",
            "owned": r["id"] in owned,
        })
    return {"owned": len(owned), "total": len(catalog_rows), "items": catalog_rows}


def home(external_key: str) -> dict:
    player = core.get_player(external_key)
    hearts = engine.refill_hearts(player["id"])
    path = engine.get_path(external_key)
    current = current_lesson_id(external_key)
    unit = next((u for u in path["units"] if any(n["id"] == current for n in u["lessons"])), path["units"][0])
    model = brain.learner_model(external_key)
    return {
        "player": core.get_player(external_key),
        "hearts": {"current": hearts["hearts"], "max": config.HEARTS_MAX,
                   "next_in_sec": hearts["next_in_sec"]},
        "streak": {"days": core.get_player(external_key)["streak_days"],
                   "freeze": core.get_player(external_key)["streak_freeze"]},
        "daily": {"xp": core.get_player(external_key)["daily_xp"],
                  "goal": config.DAILY_XP_GOAL},
        "quests": daily_quests(external_key),
        "league": league(external_key),
        "stickers": album(external_key),
        "current_lesson_id": current,
        "current_unit": unit,
        "next_best_action": brain.next_best_action(external_key),
        "lessons_starred": model["lessons_starred"],
        "course": {
            "language": "en",
            "from": "ru",
            "units": len(catalog.unit_order()),
            "source": "foxi-year1",
            "title_ru": "1 класс · Фокси учит, потом читаем",
        },
    }


def review(external_key: str) -> dict:
    """Сколько слов ждёт повторения сегодня и какие именно."""
    player = core.get_player(external_key)
    due = srs.due_words(player["id"])
    out = []
    for row in due:
        try:
            unit = catalog.get_unit(row["unit_id"])
        except KeyError:
            continue
        word = next((w for w in unit["words"] if w["en"] == row["word_en"]), None)
        if word is None:
            continue
        out.append({
            "en": word["en"],
            "ru": word["ru"],
            "unit_id": row["unit_id"],
            "unit_ru": unit["place_ru"],
            "strength": int(row["strength"] or 0),
        })
    return {"due": srs.review_count(player["id"]), "words": out}


def sprint(external_key: str) -> dict:
    """Слова с картинками + серверная сессия (анти-накрутка награды)."""
    import json
    import uuid

    player = core.get_player(external_key)
    current = current_lesson_id(external_key) or "family-L1"
    try:
        unit_id, _, _ = engine.parse_lesson_id(current)
    except (core.NotFound, ValueError):
        unit_id = "family"
    unit = catalog.get_unit(unit_id)
    cards = [
        {"en": w["en"], "ru": w["ru"], "image": w.get("image") or ""}
        for w in unit["words"] if w.get("image")
    ]
    if len(cards) < 4:
        cards = [{"en": w["en"], "ru": w["ru"], "image": w.get("image") or ""} for w in unit["words"]]
    words = cards[:12]
    session_id = str(uuid.uuid4())
    payload = {"kind": "sprint", "unit_id": unit_id, "words": [w["en"] for w in words]}
    get_conn().execute(
        "INSERT INTO activity_sessions (id, player_id, activity_id, payload, answers, status, score)"
        " VALUES (?,?,?,?,?,?,?)",
        (session_id, player["id"], f"sprint:{unit_id}", json.dumps(payload), "{}", "active", 0),
    )
    return {
        "session_id": session_id,
        "unit_id": unit_id,
        "title_ru": unit["place_ru"],
        "words": words,
        "player_id": player["id"],
    }


def sprint_answer(external_key: str, session_id: str, en: str, choice: str) -> dict:
    """Засчитать ответ спринта на сервере. Клиентский score не доверяем."""
    import json

    player = core.get_player(external_key)
    row = get_conn().execute(
        "SELECT * FROM activity_sessions WHERE id=? AND player_id=?",
        (session_id, player["id"]),
    ).fetchone()
    if row is None:
        raise core.NotFound(f"sprint session {session_id!r}")
    if row["status"] != "active":
        raise core.Conflict("sprint session already finished")
    payload = json.loads(row["payload"] or "{}")
    if payload.get("kind") != "sprint":
        raise core.NotFound(f"sprint session {session_id!r}")
    answers = json.loads(row["answers"] or "{}")
    want = (en or "").strip().lower()
    got = (choice or "").strip().lower()
    if want not in {w.lower() for w in payload.get("words") or []}:
        raise core.NotFound(f"word {en!r} not in sprint")
    # One scored attempt per prompt word.
    if want in answers:
        return {
            "en": en,
            "correct": bool(answers[want].get("correct")),
            "score": int(row["score"] or 0),
            "answered": len(answers),
            "total": len(payload.get("words") or []),
        }
    correct = want == got and want != ""
    answers[want] = {"choice": choice, "correct": correct}
    score = int(row["score"] or 0) + (1 if correct else 0)
    get_conn().execute(
        "UPDATE activity_sessions SET answers=?, score=? WHERE id=?",
        (json.dumps(answers), score, session_id),
    )
    return {
        "en": en,
        "correct": correct,
        "score": score,
        "answered": len(answers),
        "total": len(payload.get("words") or []),
    }


def finish_sprint(external_key: str, session_id: str | None = None,
                  score: int | None = None, total: int | None = None) -> dict:
    """Награда только по серверному score сессии. Без ответов — cosmetic_only."""
    import json

    player = core.get_player(external_key)
    if not session_id:
        # Legacy body without session: treat as cosmetic (no XP).
        return {
            "score": max(0, int(score or 0)),
            "total": max(0, int(total or 0)),
            "xp_delta": 0,
            "coins_delta": 0,
            "player": player,
            "daily_xp": int(player.get("daily_xp") or 0),
            "daily_goal": config.DAILY_XP_GOAL,
            "cosmetic_only": True,
        }
    row = get_conn().execute(
        "SELECT * FROM activity_sessions WHERE id=? AND player_id=?",
        (session_id, player["id"]),
    ).fetchone()
    if row is None:
        raise core.NotFound(f"sprint session {session_id!r}")
    payload = json.loads(row["payload"] or "{}")
    if payload.get("kind") != "sprint":
        raise core.NotFound(f"sprint session {session_id!r}")
    words_n = len(payload.get("words") or [])
    server_score = int(row["score"] or 0)
    already = row["status"] == "completed"
    if not already:
        get_conn().execute(
            "UPDATE activity_sessions SET status='completed', completed_at=datetime('now') WHERE id=?",
            (session_id,),
        )

    cosmetic = server_score <= 0
    xp = 0 if cosmetic or already else (5 if server_score > 0 else 0)
    coins = 0 if cosmetic or already else (2 if server_score == words_n and words_n else 0)
    if xp or coins:
        result = core.award(
            external_key, xp=xp, coins=coins, source="sprint", type_="SPRINT_REWARD",
            idempotency_key=f"sprint:{player['id']}:{engine._day()}:{session_id}",
        )
    else:
        result = {
            "xp_delta": 0,
            "coins_delta": 0,
            "player": core.get_player(external_key),
        }
    return {
        "session_id": session_id,
        "score": server_score,
        "total": words_n,
        "xp_delta": result["xp_delta"],
        "coins_delta": result["coins_delta"],
        "player": result["player"],
        "daily_xp": int(result["player"].get("daily_xp") or 0),
        "daily_goal": config.DAILY_XP_GOAL,
        "cosmetic_only": cosmetic,
    }

def words(external_key: str, unit_id: str) -> dict:
    try:
        unit = catalog.get_unit(unit_id)
    except KeyError as exc:
        raise core.NotFound(f"unit {unit_id!r} not found") from exc
    player = core.get_player(external_key)
    rows = get_conn().execute(
        "SELECT word_en, strength, correct_count, wrong_count FROM word_stats"
        " WHERE player_id=? AND unit_id=?",
        (player["id"], unit_id),
    ).fetchall()
    stats = {r["word_en"]: dict(r) for r in rows}
    return {
        "unit_id": unit_id,
        "words": [
            {
                "en": w["en"], "ru": w["ru"], "ipa": w["ipa"],
                "image": w.get("image") or "",
                "strength": int(stats.get(w["en"], {}).get("strength") or 0),
            }
            for w in unit["words"]
        ],
    }
