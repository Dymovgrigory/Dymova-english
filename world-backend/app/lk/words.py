"""Домен Этапа 3: тренажёр слов ЛК.

Словари (lk_word_sets): уровневые наборы (Pre-A1…, публичные) и наборы по
учебникам/темам (My Level, Get Involved, Super Minds, Spotlight) — выдаются
через lk_word_assignments группам/ученикам/всем (решение владельца §5 ТЗ).
Словарь работает по порядку: новые слова выдаются в позиции position,
повторяемые — по SRS (интервалы как в Мире: 1,1,3,7,14,30 дней).

Ключ ученика: 'crm:<student_id>' для профилей из CRM, 'guest:<account_id>'
для гостевого режима (решение 11 ТЗ: гости тоже тренируют слова).
"""
from __future__ import annotations

import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from app.world import core
from app.world.db import get_conn

from . import service as auth_service

# SRS: сила 0–5 → интервал до следующего показа, дней.
INTERVALS_DAYS = (1, 1, 3, 7, 14, 30)
MAX_STRENGTH = len(INTERVALS_DAYS) - 1

NEW_PER_TRAIN = 8       # новых слов за подход
REVIEW_PER_TRAIN = 12   # повторяемых за подход
DUE_LIMIT = 30          # страховка: не больше повторяемых за раз


# ---------- стартовый контент ----------

_SEED_LEVELS = [
    ("level:pre-a1", "Pre-A1 · Первые слова", "pre-a1", 10),
    ("level:a1", "A1 · Базовый", "a1", 20),
    ("level:a2", "A2 · Элементарный", "a2", 30),
    ("level:b1", "B1 · Пороговый", "b1", 40),
]

_SEED_BOOKS = [
    ("book:my-level", "My Level — словарь к учебнику", "my-level", 50),
    ("book:get-involved", "Get Involved — словарь к учебнику", "get-involved", 60),
    ("book:super-minds", "Super Minds — словарь к учебнику", "super-minds", 70),
    ("book:spotlight", "Spotlight — словарь к учебнику", "spotlight", 80),
]

# База слов школы: content/words.json (собирается content/build_content.py:
# CEFR-J + IPA + картинки Fluent Emoji 3D + переводы школы). ~2000 слов,
# наборы по темам и уровням. Сид идемпотентный: слова обновляются по
# (набор, английское слово), id и прогресс учеников сохраняются.
_CONTENT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "words.json")
_CONTENT: dict | None = None


def content() -> dict:
    global _CONTENT
    if _CONTENT is None:
        try:
            with open(_CONTENT_PATH, encoding="utf-8") as fh:
                _CONTENT = json.load(fh)
        except (OSError, ValueError):
            _CONTENT = {"version": "", "topics": {}, "sets": []}
    return _CONTENT


def set_meta(code: str) -> dict:
    """Иконка и цвет набора для красивой библиотеки."""
    for s in content()["sets"]:
        if s["code"] == code:
            return {"icon": s.get("icon", "📘"), "color": s.get("color", "#5b4bdb")}
    if code.startswith("book:"):
        return {"icon": "📗", "color": "#10ac84"}
    return {"icon": "📘", "color": "#5b4bdb"}


def seed_word_sets() -> None:
    """Идемпотентный сид наборов и слов из content/words.json (вызывается при старте)."""
    conn = get_conn()
    for code, title, book, pos in _SEED_BOOKS:
        conn.execute(
            "INSERT OR IGNORE INTO lk_word_sets (code, title, kind, book, cefr,"
            " position, is_public) VALUES (?,?,?,?,?,?,0)",
            (code, title, "book", book, "", pos),
        )
    data = content()
    codes = set()
    for s in data["sets"]:
        codes.add(s["code"])
        conn.execute(
            "INSERT INTO lk_word_sets (code, title, kind, book, cefr, topic, position, is_public, active)"
            " VALUES (?,?,?,?,?,?,?,1,1) ON CONFLICT(code) DO UPDATE SET title=excluded.title,"
            " kind=excluded.kind, cefr=excluded.cefr, topic=excluded.topic,"
            " position=excluded.position, is_public=1, active=1",
            (s["code"], s["title"], s["kind"], "", s.get("cefr", ""), s.get("topic", ""), s["position"]),
        )
        set_id = int(conn.execute("SELECT id FROM lk_word_sets WHERE code=?", (s["code"],)).fetchone()["id"])
        existing = {r["text_en"].lower(): int(r["id"]) for r in conn.execute(
            "SELECT id, text_en FROM lk_words WHERE set_id=?", (set_id,)).fetchall()}
        keep = set()
        for i, w in enumerate(s["words"], 1):
            key = w["en"].lower()
            vals = (w["en"], w["ru"], w.get("ipa", ""), w.get("img", ""), w.get("ex", ""), i)
            if key in existing:
                conn.execute(
                    "UPDATE lk_words SET text_en=?, text_ru=?, transcription=?, image_url=?, example_en=?, position=?,"
                    " active=1 WHERE id=?", vals + (existing[key],))
                keep.add(existing[key])
            else:
                cur = conn.execute(
                    "INSERT INTO lk_words (set_id, text_en, text_ru, transcription, image_url, example_en, position)"
                    " VALUES (?,?,?,?,?,?,?)", (set_id,) + vals)
                keep.add(int(cur.lastrowid))
        stale = [wid for wid in existing.values() if wid not in keep]
        for wid in stale:
            conn.execute("UPDATE lk_words SET active=0 WHERE id=?", (wid,))
    # наборы прошлых версий контента (например topic:animals до разбивки на части
    # или level:b1) прячем: их слова уже есть в новых наборах; прогресс не удаляется
    for r in conn.execute("SELECT id, code FROM lk_word_sets WHERE kind IN ('level','topic')").fetchall():
        code = r["code"] or ""
        if code not in codes and (code.startswith("topic:") or code.startswith("level:")):
            conn.execute("UPDATE lk_word_sets SET active=0 WHERE id=?", (r["id"],))


# ---------- доступность и выборка ----------

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _learner_key(profile) -> str:
    if profile["student_id"]:
        return f"crm:{int(profile['student_id'])}"
    return f"guest:{int(profile['account_id'])}"


def _profile(token: str, student_id: int):
    account = auth_service.resolve_session(token)
    if account is None:
        raise core.Conflict("unauthorized")
    if not student_id:
        # гостевой профиль аккаунта (у него student_id IS NULL)
        profile = get_conn().execute(
            "SELECT * FROM lk_profiles WHERE account_id=? AND source='guest'",
            (account["id"],),
        ).fetchone()
    else:
        profile = auth_service._account_profile(account["id"], student_id)
    if profile is None:
        raise core.Conflict("profile_not_found")
    return account, profile


def _assigned_set_ids(student_id: int | None) -> set[int]:
    """Наборы, доступные ученику: назначения по ученику/группе/всем."""
    conn = get_conn()
    out: set[int] = set()
    rows = conn.execute(
        "SELECT set_id FROM lk_word_assignments WHERE kind='all'"
    ).fetchall()
    out.update(int(r["set_id"]) for r in rows)
    if student_id:
        rows = conn.execute(
            "SELECT set_id FROM lk_word_assignments"
            " WHERE kind='student' AND student_id=?",
            (student_id,),
        ).fetchall()
        out.update(int(r["set_id"]) for r in rows)
        group_ids = [
            int(r["group_id"]) for r in conn.execute(
                "SELECT group_id FROM lk_group_members"
                " WHERE student_id=? AND status='active'",
                (student_id,),
            ).fetchall()
        ]
        if group_ids:
            placeholders = ",".join("?" for _ in group_ids)
            rows = conn.execute(
                f"SELECT set_id FROM lk_word_assignments"
                f" WHERE kind='group' AND group_id IN ({placeholders})",
                group_ids,
            ).fetchall()
            out.update(int(r["set_id"]) for r in rows)
    return out


def _set_progress(learner_key: str, set_id: int) -> dict:
    row = get_conn().execute(
        "SELECT COUNT(*) AS total,"
        " SUM(CASE WHEN p.word_id IS NOT NULL THEN 1 ELSE 0 END) AS seen,"
        " SUM(CASE WHEN p.strength>=2 THEN 1 ELSE 0 END) AS learned"
        " FROM lk_words w LEFT JOIN lk_word_progress p"
        " ON p.word_id=w.id AND p.learner_key=?"
        " WHERE w.set_id=? AND w.active=1",
        (learner_key, set_id),
    ).fetchone()
    total = int(row["total"] or 0)
    return {
        "total": total,
        "seen": int(row["seen"] or 0),
        "learned": int(row["learned"] or 0),
        "due": _due_count(learner_key, set_id),
    }


def _due_count(learner_key: str, set_id: int) -> int:
    row = get_conn().execute(
        "SELECT COUNT(*) AS c FROM lk_word_progress p"
        " JOIN lk_words w ON w.id=p.word_id"
        " WHERE p.learner_key=? AND w.set_id=? AND w.active=1"
        " AND p.strength<5 AND p.due_at<=?",
        (learner_key, set_id, _today()),
    ).fetchone()
    return int(row["c"])


def list_sets(token: str, student_id: int) -> dict:
    """Библиотека словарей: публичные + назначенные, с прогрессом ученика."""
    _, profile = _profile(token, student_id)
    learner = _learner_key(profile)
    allowed = _assigned_set_ids(profile["student_id"])
    rows = get_conn().execute(
        "SELECT * FROM lk_word_sets WHERE active=1 ORDER BY position, id"
    ).fetchall()
    sets = []
    for r in rows:
        sid = int(r["id"])
        if not r["is_public"] and sid not in allowed:
            continue
        progress = _set_progress(learner, sid)
        sets.append({
            "id": sid,
            "code": r["code"],
            "title": r["title"],
            "kind": r["kind"],
            "book": r["book"],
            "cefr": r["cefr"],
            "topic": r["topic"],
            "is_public": bool(r["is_public"]),
            "progress": progress,
            **set_meta(r["code"]),
            "preview": [x["image_url"] for x in get_conn().execute(
                "SELECT image_url FROM lk_words WHERE set_id=? AND active=1 AND image_url!=''"
                " ORDER BY position LIMIT 4", (sid,)).fetchall()],
        })
    return {"student_id": student_id, "child_name": profile["child_name"],
            "sets": sets}


def _word_out(row, progress=None, with_answer: bool = True) -> dict:
    out = {
        "id": int(row["id"]),
        "text_en": row["text_en"],
        "transcription": row["transcription"],
        "image_url": row["image_url"],
        "audio_url": row["audio_url"],
        "example_en": row["example_en"] or "",
        "position": int(row["position"]),
    }
    if with_answer:
        out["text_ru"] = row["text_ru"]
        out["example_en"] = row["example_en"]
        out["example_ru"] = row["example_ru"]
    if progress is not None:
        out["strength"] = int(progress["strength"])
    return out


def _check_set_access(profile, set_id: int) -> None:
    row = get_conn().execute(
        "SELECT id, is_public FROM lk_word_sets WHERE id=? AND active=1", (set_id,)
    ).fetchone()
    if row is None:
        raise core.Conflict("set_not_found")
    if not row["is_public"] and set_id not in _assigned_set_ids(profile["student_id"]):
        raise core.Conflict("set_not_available")


def set_words(token: str, student_id: int, set_id: int) -> dict:
    """Слова набора с прогрессом (для карточек просмотра)."""
    _, profile = _profile(token, student_id)
    _check_set_access(profile, set_id)
    learner = _learner_key(profile)
    rows = get_conn().execute(
        "SELECT w.*, p.strength FROM lk_words w"
        " LEFT JOIN lk_word_progress p ON p.word_id=w.id AND p.learner_key=?"
        " WHERE w.set_id=? AND w.active=1 ORDER BY w.position",
        (learner, set_id),
    ).fetchall()
    return {
        "set_id": set_id,
        "words": [_word_out(r, with_answer=True) for r in rows],
    }


HARD_SQL = ("SELECT w.*, p.strength, p.seen_count, p.correct_count FROM lk_words w"
            " JOIN lk_word_progress p ON p.word_id=w.id"
            " WHERE p.learner_key=? AND w.active=1 AND p.seen_count>p.correct_count AND p.strength<4"
            " ORDER BY (p.seen_count-p.correct_count) DESC, p.last_seen_at DESC LIMIT ?")


def _far_pool(conn, exclude_set: int, own: set[str]) -> list[dict]:
    """Слова из других тем: варианты для пропусков и картинок без двусмысленности
    (в «Their ___ is a student» не должны подходить два варианта сразу)."""
    rows = conn.execute(
        "SELECT w.id, w.text_en, w.text_ru, w.image_url, w.example_en FROM lk_words w"
        " JOIN lk_word_sets s ON s.id = w.set_id"
        " WHERE w.set_id != ? AND w.active=1 AND s.active=1 AND s.kind='topic'"
        " AND w.image_url != '' AND w.example_en != ''"
        " ORDER BY RANDOM() LIMIT 40", (exclude_set,)).fetchall()
    return [{"id": -int(r["id"]), "text_en": r["text_en"], "text_ru": r["text_ru"],
             "image_url": r["image_url"], "example_en": r["example_en"]}
            for r in rows if r["text_en"].lower() not in own]


def _pool_item(r) -> dict:
    return {"id": int(r["id"]), "text_en": r["text_en"], "text_ru": r["text_ru"],
            "image_url": r["image_url"], "example_en": r["example_en"] or ""}


def _hard_training(profile) -> dict:
    """Урок «Трудные слова»: слова, в которых ученик ошибался."""
    learner = _learner_key(profile)
    conn = get_conn()
    rows = conn.execute(HARD_SQL, (learner, 12)).fetchall()
    cards = [_word_out(r, with_answer=False) for r in rows]
    for c in cards:
        c["distractors"] = []
    set_ids = {int(r["set_id"]) for r in rows}
    pool = [_pool_item(r) for r in rows]
    if set_ids:
        extra = conn.execute(
            "SELECT id, text_en, text_ru, image_url, example_en FROM lk_words WHERE active=1 AND set_id IN (%s)"
            " ORDER BY RANDOM() LIMIT 30" % ",".join("?" for _ in set_ids), tuple(set_ids)).fetchall()
        seen = {p["id"] for p in pool}
        pool += [_pool_item(r) for r in extra if int(r["id"]) not in seen]
    random.shuffle(cards)
    return {
        "code": "hard", "title": "Трудные слова", "topic": "", "pool": pool,
        "pool_far": _far_pool(conn, -1, {p["text_en"].lower() for p in pool}),
        "icon": "target", "color": "#E5484D", "set_id": 0, "child_name": profile["child_name"],
        "cards": cards, "answers": {int(r["id"]): r["text_ru"] for r in rows},
        "review_count": len(cards), "new_count": 0,
    }


def my_words(token: str, student_id: int) -> dict:
    """«Мой словарь»: выученные слова, слова в процессе и трудные."""
    _, profile = _profile(token, student_id)
    learner = _learner_key(profile)
    conn = get_conn()
    rows = conn.execute(
        "SELECT w.*, p.strength, p.seen_count, p.correct_count, p.last_seen_at FROM lk_words w"
        " JOIN lk_word_progress p ON p.word_id=w.id"
        " WHERE p.learner_key=? AND w.active=1 ORDER BY p.last_seen_at DESC", (learner,)).fetchall()
    out, seen = [], set()
    for r in rows:
        k = r["text_en"].lower()
        if k in seen:
            continue
        seen.add(k)
        item = _word_out(r, with_answer=True)
        item["strength"] = int(r["strength"])
        item["mistakes"] = max(0, int(r["seen_count"]) - int(r["correct_count"]))
        out.append(item)
    hard = [int(r["id"]) for r in conn.execute(HARD_SQL, (learner, 50)).fetchall()]
    return {"words": out, "hard_ids": hard,
            "learned": sum(1 for w in out if w["strength"] >= 2),
            "learning": sum(1 for w in out if w["strength"] < 2)}


def start_training(token: str, student_id: int, set_id: int) -> dict:
    """Подборка тренировки: повторяемые по сроку SRS + новые по порядку."""
    _, profile = _profile(token, student_id)
    if set_id == 0:
        return _hard_training(profile)
    _check_set_access(profile, set_id)
    learner = _learner_key(profile)
    conn = get_conn()

    review = conn.execute(
        "SELECT w.*, p.strength FROM lk_words w"
        " JOIN lk_word_progress p ON p.word_id=w.id"
        " WHERE p.learner_key=? AND w.set_id=? AND w.active=1"
        " AND p.strength<5 AND p.due_at<=?"
        " ORDER BY p.due_at, w.position LIMIT ?",
        (learner, set_id, _today(), REVIEW_PER_TRAIN),
    ).fetchall()
    review_ids = {int(r["id"]) for r in review}
    limit_new = max(0, min(NEW_PER_TRAIN, DUE_LIMIT - len(review)))
    # Новые = вообще без прогресса у этого ученика (не только не-due).
    new_words = conn.execute(
        "SELECT w.*, NULL AS strength FROM lk_words w"
        " WHERE w.set_id=? AND w.active=1"
        " AND w.id NOT IN (SELECT word_id FROM lk_word_progress"
        "                  WHERE learner_key=?)"
        " ORDER BY w.position LIMIT ?",
        (set_id, learner, limit_new),
    ).fetchall()

    cards = [_word_out(r, with_answer=False) for r in review]
    cards += [_word_out(r, with_answer=False) for r in new_words]
    # Варианты-отвлечения для задания «выбери перевод»: соседние слова набора.
    all_rows = conn.execute(
        "SELECT id, text_ru FROM lk_words WHERE set_id=? AND active=1",
        (set_id,),
    ).fetchall()
    distractors = {int(r["id"]): r["text_ru"] for r in all_rows}
    for c in cards:
        wrong = [ru for wid, ru in distractors.items() if wid != c["id"]]
        random.shuffle(wrong)
        c["distractors"] = wrong[:3]
    random.shuffle(cards)
    # Пул слов набора для заданий (выбери картинку/перевод, пары, на слух).
    pool_rows = conn.execute(
        "SELECT id, text_en, text_ru, image_url, example_en FROM lk_words WHERE set_id=? AND active=1"
        " ORDER BY RANDOM() LIMIT 40", (set_id,)).fetchall()
    pool = [_pool_item(r) for r in pool_rows]
    pool_far = _far_pool(conn, set_id, {p["text_en"].lower() for p in pool})
    set_row = conn.execute("SELECT code, title, topic FROM lk_word_sets WHERE id=?", (set_id,)).fetchone()
    meta = set_meta(set_row["code"])
    return {
        "code": set_row["code"],
        "title": set_row["title"],
        "topic": set_row["topic"],
        "pool": pool,
        "pool_far": pool_far,
        "icon": meta["icon"],
        "color": meta["color"],
        "set_id": set_id,
        "child_name": profile["child_name"],
        "cards": cards,
        "answers": {int(r["id"]): r["text_ru"] for r in review + list(new_words)},
        "review_count": len(review),
        "new_count": len(new_words),
    }



def _msk_day(offset: int = 0) -> str:
    return (datetime.now(timezone(timedelta(hours=3))) + timedelta(days=offset)).strftime("%Y-%m-%d")


def finish_session(token: str, student_id: int, set_id: int, correct: int, total: int) -> dict:
    """Конец урока: монеты за урок (+ за урок без ошибок) и итоги для экрана результата."""
    from . import rewards
    _, profile = _profile(token, student_id)
    learner = _learner_key(profile)
    perfect = bool(total and correct == total)
    bonus = rewards.COIN_LESSON + (rewards.COIN_PERFECT if perfect else 0)
    rewards.add_day(learner, coins=bonus, sessions=1, perfect=1 if perfect else 0)
    rewards.give_world_coins(profile, bonus, f"lk:{learner}:finish:{uuid.uuid4().hex}")
    return {"status": "ok", "bonus_coins": bonus, "perfect": perfect, **_game_stats(learner, profile)}


def claim_reward(token: str, student_id: int, kind: str) -> dict:
    from . import rewards
    _, profile = _profile(token, student_id)
    return rewards.claim(_learner_key(profile), profile, kind)


FOXI_KEYS = {
    "hat": {"none", "cap", "beanie", "wizard", "crown", "tophat", "party", "headphones", "flower", "halo"},
    "hair": {"none", "tuft", "mohawk", "spiky", "curly"},
    "glasses": {"none", "round", "sun", "star", "gold"},
    "pattern": {"none", "stripes", "dots", "checks", "stars", "zigzag"},
    "neck": {"none", "scarf", "bowtie", "medal", "tie"},
    "back": {"none", "cape", "wings"},
    "scene": {"room", "castle", "forest", "space", "beach", "snow"},
}
FOXI_COLORS = ("fur", "eyes", "top", "patternColor", "bottom", "bag", "shoes", "hatColor", "neckColor")


def _clean_foxi(raw) -> dict:
    """Облик Фокси из ЛК: только известные варианты и цвета #rrggbb."""
    out: dict = {}
    if not isinstance(raw, dict):
        return out
    for key, allowed in FOXI_KEYS.items():
        if raw.get(key) in allowed:
            out[key] = raw[key]
    for key in FOXI_COLORS:
        value = str(raw.get(key) or "")
        if len(value) == 7 and value[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in value[1:]):
            out[key] = value.lower()
    if isinstance(raw.get("logo"), bool):
        out["logo"] = raw["logo"]
    name = " ".join(str(raw.get("name") or "").split())[:24]
    if name:
        out["name"] = name
    return out


def get_foxi(token: str, student_id: int) -> dict:
    _, profile = _profile(token, student_id)
    row = get_conn().execute("SELECT foxi FROM lk_learner_prefs WHERE learner_key=?",
                             (_learner_key(profile),)).fetchone()
    try:
        return {"foxi": _clean_foxi(json.loads(row["foxi"])) if row and row["foxi"] else None}
    except ValueError:
        return {"foxi": None}


def set_foxi(token: str, student_id: int, raw) -> dict:
    _, profile = _profile(token, student_id)
    foxi = _clean_foxi(raw)
    get_conn().execute(
        "INSERT INTO lk_learner_prefs (learner_key, foxi) VALUES (?,?)"
        " ON CONFLICT(learner_key) DO UPDATE SET foxi=excluded.foxi",
        (_learner_key(profile), json.dumps(foxi, ensure_ascii=False)))
    return {"foxi": foxi}


def set_goal(token: str, student_id: int, goal: int) -> dict:
    _, profile = _profile(token, student_id)
    goal = max(20, min(200, int(goal or 50)))
    get_conn().execute(
        "INSERT INTO lk_learner_prefs (learner_key, daily_goal) VALUES (?,?)"
        " ON CONFLICT(learner_key) DO UPDATE SET daily_goal=excluded.daily_goal",
        (_learner_key(profile), goal))
    return {"status": "ok", "daily_goal": goal}


def _game_stats(learner: str, profile) -> dict:
    """Награды ученика (см. rewards.py): монеты, звание, календарь, задание дня, коллекция."""
    from . import rewards
    return rewards.summary(learner, profile)


def answer(token: str, student_id: int, word_id: int, correct: bool, mode: str = "") -> dict:
    """Ответ ученика: двигаем силу слова по SRS и начисляем XP."""
    _, profile = _profile(token, student_id)
    learner = _learner_key(profile)
    conn = get_conn()
    word = conn.execute(
        "SELECT id FROM lk_words WHERE id=? AND active=1", (word_id,)
    ).fetchone()
    if word is None:
        raise core.Conflict("word_not_found")
    row = conn.execute(
        "SELECT * FROM lk_word_progress WHERE learner_key=? AND word_id=?",
        (learner, word_id),
    ).fetchone()
    strength = int(row["strength"]) if row else 0
    seen = int(row["seen_count"]) if row else 0
    ok = int(row["correct_count"]) if row else 0
    strength = min(MAX_STRENGTH, strength + 1) if correct else max(0, strength - 1)
    # Ошибка возвращает слово сразу (сегодня), верный ответ — по интервалу SRS.
    if correct:
        due = (datetime.now(timezone.utc)
               + timedelta(days=INTERVALS_DAYS[strength])).strftime("%Y-%m-%d")
    else:
        due = _today()
    conn.execute(
        "INSERT INTO lk_word_progress (learner_key, word_id, strength, due_at,"
        " seen_count, correct_count, last_seen_at) VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(learner_key, word_id) DO UPDATE SET strength=excluded.strength,"
        " due_at=excluded.due_at, seen_count=excluded.seen_count,"
        " correct_count=excluded.correct_count, last_seen_at=excluded.last_seen_at",
        (learner, word_id, strength, due, seen + 1, ok + (1 if correct else 0),
         datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
    )
    from . import rewards
    coins = (rewards.COIN_CORRECT + (rewards.COIN_HARD if mode in ("type", "listen", "speak") else 0)) if correct else 0
    rewards.add_day(learner, coins=coins, answers=1, correct=1 if correct else 0, new_words=1 if row is None else 0)
    rewards.give_world_coins(profile, coins, f"lk:{learner}:answer:{uuid.uuid4().hex}")
    return {"status": "ok", "strength": strength, "due_at": due, "coins": coins}


def stats(token: str, student_id: int) -> dict:
    _, profile = _profile(token, student_id)
    learner = _learner_key(profile)
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS seen, COALESCE(SUM(correct_count),0) AS correct,"
        " COALESCE(SUM(seen_count),0) AS answers"
        " FROM lk_word_progress WHERE learner_key=?",
        (learner,),
    ).fetchone()
    due = conn.execute(
        "SELECT COUNT(*) AS c FROM lk_word_progress"
        " WHERE learner_key=? AND strength<5 AND due_at<=?",
        (learner, _today()),
    ).fetchone()["c"]
    learned = conn.execute(
        "SELECT COUNT(*) AS c FROM lk_word_progress"
        " WHERE learner_key=? AND strength>=2",
        (learner,),
    ).fetchone()["c"]
    return {
        "seen_words": int(row["seen"] or 0),
        "learned_words": int(learned),
        "due_today": int(due),
        "answers_total": int(row["answers"] or 0),
        "answers_correct": int(row["correct"] or 0),
        **_game_stats(learner, profile),
    }


# ---------- импорт наборов (методист) ----------

def import_set(payload: dict, actor: str = "import") -> dict:
    """Создание/обновление набора со словами (конструктор, ТЗ §5.2).

    payload: {code, title, kind?, book?, cefr?, topic?, is_public?, words:
    [{text_en, text_ru, transcription?, image_url?, audio_url?, example_en?,
    example_ru?}]}. Слова заменяются целиком (перезапис позиций).
    """
    code = str(payload.get("code") or "").strip()
    title = str(payload.get("title") or "").strip()
    words = payload.get("words")
    if not code or not title or not isinstance(words, list):
        raise core.Conflict("bad_payload")
    conn = get_conn()
    conn.execute(
        "INSERT INTO lk_word_sets (code, title, kind, book, cefr, topic,"
        " position, is_public) VALUES (?,?,?,?,?,?,?,?)"
        " ON CONFLICT(code) DO UPDATE SET title=excluded.title,"
        " kind=excluded.kind, book=excluded.book, cefr=excluded.cefr,"
        " topic=excluded.topic, is_public=excluded.is_public",
        (code, title,
         str(payload.get("kind") or "topic"),
         str(payload.get("book") or ""),
         str(payload.get("cefr") or "").lower(),
         str(payload.get("topic") or ""),
         int(payload.get("position") or 100),
         1 if payload.get("is_public") else 0),
    )
    set_id = int(conn.execute(
        "SELECT id FROM lk_word_sets WHERE code=?", (code,)
    ).fetchone()["id"])
    seen: set[str] = set()
    clean = []
    for i, w in enumerate(words):
        en = str(w.get("text_en") or "").strip().lower()
        ru = str(w.get("text_ru") or "").strip()
        if not en or not ru or en in seen:
            continue
        seen.add(en)
        clean.append((en, ru, str(w.get("transcription") or ""),
                      str(w.get("image_url") or ""),
                      str(w.get("audio_url") or ""),
                      str(w.get("example_en") or ""),
                      str(w.get("example_ru") or ""), i + 1))
    conn.execute("DELETE FROM lk_words WHERE set_id=?", (set_id,))
    for en, ru, tr, img, aud, ex_en, ex_ru, pos in clean:
        conn.execute(
            "INSERT INTO lk_words (set_id, text_en, text_ru, transcription,"
            " image_url, audio_url, example_en, example_ru, position)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (set_id, en, ru, tr, img, aud, ex_en, ex_ru, pos),
        )
    return {"status": "ok", "set_id": set_id, "words": len(clean)}


def assign_set(set_id: int, kind: str, group_id: int | None = None,
               student_id: int | None = None,
               age_from: int | None = None, age_to: int | None = None) -> dict:
    """Назначение набора: kind = group|student|all (возраст — когда будет
    дата рождения из CRM)."""
    if kind not in ("group", "student", "all"):
        raise core.Conflict("bad_kind")
    row = get_conn().execute(
        "SELECT id FROM lk_word_sets WHERE id=? AND active=1", (set_id,)
    ).fetchone()
    if row is None:
        raise core.Conflict("set_not_found")
    get_conn().execute(
        "INSERT OR IGNORE INTO lk_word_assignments (set_id, kind, group_id,"
        " student_id, age_from, age_to) VALUES (?,?,?,?,?,?)",
        (set_id, kind, group_id, student_id, age_from, age_to),
    )
    return {"status": "ok"}
