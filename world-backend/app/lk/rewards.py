"""Награды тренажёра слов — своя система школы «Фоксинбург», не копия Duolingo.

Вместо очков, «огонька» и значков:
- **Монеты Фоксинбурга** за верные ответы и уроки. Это те же монеты, что в Мире:
  их тратят в магазине Мира на замок и украшения. Учёба = строительство своего замка.
- **Звания жителя** по числу выученных слов (а не по очкам): от «Гостя Фоксинбурга»
  до «Легенды». Звание растёт только от знаний.
- **Календарь Фокси**: штамп-лапка за каждый день занятий в месяце. Пропуск ничего
  не «сжигает». **Сундук недели** открывается за 5 дней из 7 — без требования «ни дня без».
- **Задание дня от Фокси**: одно понятное задание (выучи 5 слов, урок без ошибок…).
- **Коллекция открыток**: открытка темы открывается, когда выучено 80% её слов.
- **Медали Cambridge**: Starters / Movers / Flyers по доле выученных слов уровня.
- **Трудные слова**: слова с ошибками собираются в отдельный урок.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from app.world import core
from app.world.db import get_conn

log = logging.getLogger("world.lk.rewards")

MSK = timezone(timedelta(hours=3))

COIN_CORRECT = 1      # верный ответ
COIN_HARD = 1         # + за задание «напиши / на слух / скажи»
COIN_LESSON = 5       # урок пройден
COIN_PERFECT = 5      # урок без ошибок
QUEST_COINS = 15      # задание дня
CHEST_COINS = 30      # сундук недели
CHEST_DAYS = 5        # сколько дней из 7 нужно для сундука
POSTCARD_SHARE = 0.8  # доля выученных слов темы для открытки
MEDAL_SHARE = 0.8     # доля выученных слов уровня для медали

RANKS = [
    (0, "Гость Фоксинбурга"), (10, "Новичок"), (30, "Юный следопыт"), (60, "Следопыт"),
    (100, "Знаток"), (160, "Мастер слов"), (250, "Хранитель свитков"), (400, "Рыцарь английского"),
    (600, "Мудрец"), (900, "Магистр"), (1300, "Лорд Фоксинбурга"), (2000, "Легенда Фоксинбурга"),
]

# Задание дня: (код, текст, поле дня, цель). Меняется каждый день по кругу.
QUESTS = [
    ("new5", "Познакомься с 5 новыми словами", "new_words", 5),
    ("correct20", "Дай 20 верных ответов", "correct", 20),
    ("lessons2", "Пройди 2 урока", "sessions", 2),
    ("perfect1", "Пройди урок без единой ошибки", "perfect", 1),
    ("new8", "Познакомься с 8 новыми словами", "new_words", 8),
    ("correct30", "Дай 30 верных ответов", "correct", 30),
    ("lessons3", "Пройди 3 урока", "sessions", 3),
]

LEVEL_MEDALS = [
    ("level:pre-a1", "Starters", "Pre A1"),
    ("level:a1", "Movers", "A1"),
    ("level:a2", "Flyers", "A2"),
]


def day(offset: int = 0) -> str:
    return (datetime.now(MSK) + timedelta(days=offset)).strftime("%Y-%m-%d")


def _monday() -> str:
    now = datetime.now(MSK)
    return (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")


def add_day(learner: str, coins: int = 0, answers: int = 0, correct: int = 0,
            new_words: int = 0, sessions: int = 0, perfect: int = 0) -> None:
    # колонка xp хранит монеты дня (историческое имя)
    get_conn().execute(
        "INSERT INTO lk_learner_days (learner_key, day, xp, answers, correct, new_words, sessions, perfect)"
        " VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(learner_key, day) DO UPDATE SET"
        " xp=xp+excluded.xp, answers=answers+excluded.answers, correct=correct+excluded.correct,"
        " new_words=new_words+excluded.new_words, sessions=sessions+excluded.sessions,"
        " perfect=perfect+excluded.perfect",
        (learner, day(), coins, answers, correct, new_words, sessions, perfect))


def world_key(profile) -> str:
    from .world_link import _external_key
    return _external_key(profile)


def give_world_coins(profile, coins: int, idem: str) -> None:
    """Монеты сразу попадают в кошелёк Мира. Ошибка Мира не ломает тренировку."""
    if coins <= 0:
        return
    try:
        key = world_key(profile)
        core.get_or_create_player(key, profile["child_name"])
        core.award(key, coins=coins, source="lk_words", type_="lk_words", idempotency_key=idem)
    except Exception as exc:  # noqa: BLE001
        log.warning("lk rewards: world coins not granted: %s", exc)


def wallet(profile) -> int:
    try:
        return int(core.get_player(world_key(profile))["coins"])
    except Exception:  # noqa: BLE001 — игрока Мира ещё нет
        return 0


def rank_for(learned: int) -> dict:
    idx = max(i for i, (n, _) in enumerate(RANKS) if learned >= n)
    nxt = RANKS[idx + 1] if idx + 1 < len(RANKS) else None
    return {
        "index": idx + 1,
        "total": len(RANKS),
        "title": RANKS[idx][1],
        "from": RANKS[idx][0],
        "to": nxt[0] if nxt else RANKS[idx][0],
        "next_title": nxt[1] if nxt else "",
        "learned": learned,
    }


def quest_for(day_str: str) -> tuple[str, str, str, int]:
    n = datetime.strptime(day_str, "%Y-%m-%d").toordinal()
    return QUESTS[n % len(QUESTS)]


def _claimed(learner: str, kind: str, period: str) -> bool:
    return get_conn().execute(
        "SELECT 1 FROM lk_learner_claims WHERE learner_key=? AND kind=? AND period=?",
        (learner, kind, period)).fetchone() is not None


def _topic_title(title: str) -> str:
    return re.sub(r"\s*·\s*\d+$", "", title or "").strip()


def collection(learner: str) -> tuple[list[dict], list[dict]]:
    """Открытки тем и медали уровней Cambridge."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT s.id, s.code, s.title, s.kind, s.topic,"
        " COUNT(w.id) AS total,"
        " SUM(CASE WHEN p.strength>=2 THEN 1 ELSE 0 END) AS learned,"
        " COALESCE(MAX(CASE WHEN w.position=1 THEN w.image_url END), MAX(w.image_url)) AS cover"
        " FROM lk_word_sets s JOIN lk_words w ON w.set_id=s.id AND w.active=1"
        " LEFT JOIN lk_word_progress p ON p.word_id=w.id AND p.learner_key=?"
        " WHERE s.active=1 AND s.is_public=1 AND s.kind IN ('topic','level')"
        " GROUP BY s.id, s.code, s.title, s.kind, s.topic ORDER BY s.position, s.id",
        (learner,)).fetchall()
    topics: dict[str, dict] = {}
    levels: dict[str, dict] = {}
    for r in rows:
        total, learned = int(r["total"] or 0), int(r["learned"] or 0)
        if r["kind"] == "level":
            levels[r["code"]] = {"set_id": int(r["id"]), "total": total, "learned": learned}
            continue
        key = r["topic"] or r["code"]
        t = topics.setdefault(key, {"topic": key, "title": _topic_title(r["title"]), "set_id": int(r["id"]),
                                    "total": 0, "learned": 0, "cover": ""})
        t["total"] += total
        t["learned"] += learned
        if not t["cover"] and r["cover"]:
            t["cover"] = r["cover"]
    cards = []
    for t in topics.values():
        share = t["learned"] / t["total"] if t["total"] else 0
        cards.append({**t, "percent": round(share * 100), "unlocked": share >= POSTCARD_SHARE})
    medals = []
    for code, name, cefr in LEVEL_MEDALS:
        lv = levels.get(code)
        if not lv:
            continue
        share = lv["learned"] / lv["total"] if lv["total"] else 0
        medals.append({"code": code, "name": name, "cefr": cefr, "set_id": lv["set_id"], "total": lv["total"],
                       "learned": lv["learned"], "percent": round(share * 100), "earned": share >= MEDAL_SHARE})
    return cards, medals


def summary(learner: str, profile) -> dict:
    conn = get_conn()
    days = {r["day"]: dict(r) for r in conn.execute(
        "SELECT * FROM lk_learner_days WHERE learner_key=?", (learner,)).fetchall()}
    active = {d for d, r in days.items() if int(r.get("answers") or 0) > 0}
    today = day()
    t = days.get(today, {})
    learned = int(conn.execute(
        "SELECT COUNT(*) AS c FROM lk_word_progress WHERE learner_key=? AND strength>=2",
        (learner,)).fetchone()["c"])

    # календарь текущего месяца
    now = datetime.now(MSK)
    first = now.replace(day=1)
    nxt_month = (first + timedelta(days=32)).replace(day=1)
    month_days = []
    d = first
    while d < nxt_month:
        ds = d.strftime("%Y-%m-%d")
        month_days.append({"day": ds, "active": ds in active, "coins": int(days.get(ds, {}).get("xp") or 0)})
        d += timedelta(days=1)

    # неделя и сундук
    monday = _monday()
    mon_dt = datetime.strptime(monday, "%Y-%m-%d")
    week_days = [(mon_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    week_active = sum(1 for x in week_days if x in active)
    chest_claimed = _claimed(learner, "chest", monday)

    code, title, field, target = quest_for(today)
    progress = int(t.get(field) or 0)
    quest = {"code": code, "title": title, "progress": min(progress, target), "target": target,
             "done": progress >= target, "claimed": _claimed(learner, "quest", today), "reward": QUEST_COINS}

    cards, medals = collection(learner)
    return {
        "coins_today": int(t.get("xp") or 0),
        "coins_earned": sum(int(r.get("xp") or 0) for r in days.values()),
        "wallet": wallet(profile),
        "learned_words": learned,
        "rank": rank_for(learned),
        "days_total": len(active),
        "month": {"year": now.year, "month": now.month, "days": month_days,
                  "active_days": sum(1 for x in month_days if x["active"])},
        "week": {"days": [{"day": x, "active": x in active} for x in week_days], "active_days": week_active,
                 "need": CHEST_DAYS, "chest_ready": week_active >= CHEST_DAYS and not chest_claimed,
                 "chest_claimed": chest_claimed, "reward": CHEST_COINS},
        "quest": quest,
        "postcards": cards,
        "postcards_unlocked": sum(1 for c in cards if c["unlocked"]),
        "medals": medals,
    }


def claim(learner: str, profile, kind: str) -> dict:
    """Забрать награду: задание дня или сундук недели (один раз за период)."""
    s = summary(learner, profile)
    if kind == "quest":
        if not s["quest"]["done"]:
            raise core.Conflict("quest_not_done")
        period, coins = day(), QUEST_COINS
    elif kind == "chest":
        if s["week"]["active_days"] < CHEST_DAYS:
            raise core.Conflict("chest_locked")
        period, coins = _monday(), CHEST_COINS
    else:
        raise core.Conflict("unknown_reward")
    if _claimed(learner, kind, period):
        raise core.Conflict("already_claimed")
    get_conn().execute(
        "INSERT INTO lk_learner_claims (learner_key, kind, period, coins) VALUES (?,?,?,?)",
        (learner, kind, period, coins))
    add_day(learner, coins=coins)
    give_world_coins(profile, coins, f"lk:{learner}:{kind}:{period}")
    return {"status": "ok", "coins": coins, **summary(learner, profile)}
