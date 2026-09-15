"""Домашний экран курса, магазин, лига, ежедневные квесты."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from . import catalog, config, core, engine, srs
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
    return [
        {
            "id": "xp-goal",
            "title_ru": f"Набери {config.DAILY_XP_GOAL} XP",
            "progress": min(xp_today, config.DAILY_XP_GOAL),
            "target": config.DAILY_XP_GOAL,
            "done": xp_today >= config.DAILY_XP_GOAL,
        },
        {
            "id": "lesson-1",
            "title_ru": "Пройди 1 урок",
            "progress": min(int(lessons_today), 1),
            "target": 1,
            "done": lessons_today >= 1,
        },
        {
            "id": "perfect-1",
            "title_ru": "Урок без ошибок",
            "progress": min(int(perfect), 1),
            "target": 1,
            "done": perfect >= 1,
        },
    ]


LEAGUE_TIERS = ((500, "gold"), (150, "silver"), (0, "bronze"))
LEAGUE_TOP = 10


def tier_for(weekly_xp: int) -> str:
    for edge, name in LEAGUE_TIERS:
        if weekly_xp >= edge:
            return name
    return "bronze"


def league(external_key: str) -> dict:
    """Недельный рейтинг по всем игрокам: тир, место, размер лиги и таблица лидеров."""
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
    return {
        "tier": tier_for(weekly),
        "weekly_xp": weekly,
        "rank": me["rank"] if me else len(board) + 1,
        "size": len(board),
        "top": board[:LEAGUE_TOP],
    }


def restore_hearts(external_key: str) -> dict:
    player = core.get_player(external_key)
    engine.set_hearts(player["id"], config.HEARTS_MAX)
    return {"hearts": config.HEARTS_MAX, "hearts_max": config.HEARTS_MAX}


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
    spent = core.spend(
        external_key, coins=spec["coins"], source=sku, type_="SHOP_BUY",
        idempotency_key=f"shop:{player['id']}:{sku}:{uuid.uuid4()}",
    )
    if sku == "hearts_refill":
        engine.set_hearts(player["id"], config.HEARTS_MAX)
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
    return {"sku": sku, "ok": True, "player": core.get_player(external_key),
            "coins_delta": spent["coins_delta"], "items_granted": granted}


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
    """Слова с картинками для мини-игры «слово против картинки»."""
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
    return {"unit_id": unit_id, "title_ru": unit["place_ru"], "words": cards[:12],
            "player_id": player["id"]}


def finish_sprint(external_key: str, score: int, total: int) -> dict:
    player = core.get_player(external_key)
    score = max(0, min(int(score), int(total) or 0))
    xp = 5 if score > 0 else 0
    coins = 2 if score == total and total else 0
    result = core.award(
        external_key, xp=xp, coins=coins, source="sprint", type_="SPRINT_REWARD",
        idempotency_key=f"sprint:{player['id']}:{engine._day()}",
    )
    return {"score": score, "total": total, "xp_delta": result["xp_delta"],
            "coins_delta": result["coins_delta"], "player": result["player"]}


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
                "strength": int(stats.get(w["en"], {}).get("strength") or 0),
            }
            for w in unit["words"]
        ],
    }
