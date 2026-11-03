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

import random
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

# Стартовые слова уровней (методист догружает полные списки через импорт).
_SEED_WORDS = {
    "level:pre-a1": [
        ("hello", "привет", "хэллоу"), ("goodbye", "до свидания", "гудбай"),
        ("cat", "кот", "кэт"), ("dog", "собака", "дог"),
        ("apple", "яблоко", "эпл"), ("red", "красный", "рэд"),
        ("one", "один", "уан"), ("two", "два", "ту:"),
    ],
    "level:a1": [
        ("family", "семья", "фэмили"), ("house", "дом", "хаус"),
        ("school", "школа", "скул"), ("friend", "друг", "фрэнд"),
        ("water", "вода", "уотэ"), ("eat", "есть", "ит"),
        ("run", "бежать", "ран"), ("book", "книга", "бук"),
    ],
}


def seed_word_sets() -> None:
    """Идемпотентный сид наборов и стартовых слов (вызывается при старте)."""
    conn = get_conn()
    for code, title, cefr, pos in _SEED_LEVELS:
        conn.execute(
            "INSERT OR IGNORE INTO lk_word_sets (code, title, kind, book, cefr,"
            " position, is_public) VALUES (?,?,?,?,?,?,1)",
            (code, title, "level", "", cefr, pos),
        )
    for code, title, book, pos in _SEED_BOOKS:
        conn.execute(
            "INSERT OR IGNORE INTO lk_word_sets (code, title, kind, book, cefr,"
            " position, is_public) VALUES (?,?,?,?,?,?,0)",
            (code, title, "book", book, "", pos),
        )
    for code, words in _SEED_WORDS.items():
        row = conn.execute(
            "SELECT id FROM lk_word_sets WHERE code=?", (code,)
        ).fetchone()
        if row is None:
            continue
        set_id = row["id"]
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM lk_words WHERE set_id=?", (set_id,)
        ).fetchone()["c"]
        if count:
            continue
        for i, (en, ru, tr) in enumerate(words):
            conn.execute(
                "INSERT INTO lk_words (set_id, text_en, text_ru, transcription,"
                " position) VALUES (?,?,?,?,?)",
                (set_id, en, ru, tr, i + 1),
            )


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


def start_training(token: str, student_id: int, set_id: int) -> dict:
    """Подборка тренировки: повторяемые по сроку SRS + новые по порядку."""
    _, profile = _profile(token, student_id)
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
    return {
        "set_id": set_id,
        "child_name": profile["child_name"],
        "cards": cards,
        "answers": {int(r["id"]): r["text_ru"] for r in review + list(new_words)},
        "review_count": len(review),
        "new_count": len(new_words),
    }


def answer(token: str, student_id: int, word_id: int, correct: bool) -> dict:
    """Ответ ученика: двигаем силу слова по SRS."""
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
    return {"status": "ok", "strength": strength, "due_at": due}


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
