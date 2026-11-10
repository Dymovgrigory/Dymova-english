"""Тесты Этапа 3 ЛК: тренажёр слов (наборы, доступность, SRS, импорт).

Покрытые потоки (ТЗ §5):
- библиотека: публичные уровневые наборы видны всем; наборы по учебникам —
  только по назначению (группа/ученик/все);
- тренировка: новые слова по порядку position, повторяемые по due_at SRS;
- ответ: верный поднимает силу и отодвигает срок, ошибка — опускает;
- гостевой профиль тренируется со своим ключом прогресса;
- импорт набора (конструктор): создание, замена слов, дедуп, bad_payload;
- назначения: group/student/all, повтор назначения идемпотентно.
"""
from __future__ import annotations

import pytest

from app.lk import bridge, service, words
from app.world import core
from app.world.db import get_conn

from tests.test_lk_auth import CONSENTS, PHONE, STUDENTS  # noqa: F401

record_membership = service.record_membership


@pytest.fixture()
def lk_words_db(tmp_path, monkeypatch):
    from app.lk import bigben
    from app.world.db import reset_for_tests

    monkeypatch.setattr(bridge, "phone_confirmed", lambda phone: (True, ["telegram"]))
    reset_for_tests(str(tmp_path / "lk.sqlite"))
    monkeypatch.setattr(bigben, "configured", lambda: True)
    monkeypatch.setattr(bigben, "list_students",
                        lambda *a, **kw: list(STUDENTS))
    monkeypatch.setattr(bigben, "groups_by_ids", lambda ids: {})
    words.seed_word_sets()
    yield
    reset_for_tests(str(tmp_path / "lk-after.sqlite"))


def _consents():
    from app.lk.schemas import ConsentIn

    return [ConsentIn(**c) for c in CONSENTS]


def _token(phone: str = PHONE):
    service.start_auth(phone, "Ольга Иванова", _consents(), None, None)
    return service.confirm_via_bot(phone)["token"]


def _set_id(code: str) -> int:
    return int(get_conn().execute(
        "SELECT id FROM lk_word_sets WHERE code=?", (code,)
    ).fetchone()["id"])


# ---------- библиотека ----------

def test_library_lists_public_level_sets(lk_words_db):
    token = _token()
    out = words.list_sets(token, STUDENTS[0]["id"])
    codes = [s["code"] for s in out["sets"]]
    assert "level:pre-a1" in codes and "level:a1" in codes and "level:a2" in codes
    assert "topic:animals:1" in codes  # темы с картинками — публичные
    assert "book:my-level" not in codes  # книги — только по назначению
    pre = next(s for s in out["sets"] if s["code"] == "level:pre-a1")
    assert pre["progress"]["total"] >= 100
    assert pre["icon"] and pre["color"].startswith("#") and len(pre["preview"]) == 4


def test_book_set_requires_assignment(lk_words_db):
    token = _token()
    out = words.list_sets(token, STUDENTS[0]["id"])
    assert all(not s["code"].startswith("book:") for s in out["sets"])
    with pytest.raises(core.Conflict) as ei:
        words.set_words(token, STUDENTS[0]["id"], _set_id("book:my-level"))
    assert "set_not_available" in str(ei.value)


def test_assignment_by_student_and_group(lk_words_db):
    token = _token()
    sid = _set_id("book:my-level")
    # по группе: STUDENTS[0] состоит в группе 7 (из фикстуры профиля)
    record_membership(STUDENTS[0]["id"], 7, "SP1 Группа А")
    words.assign_set(sid, "group", group_id=7)
    out = words.list_sets(token, STUDENTS[0]["id"])
    assert "book:my-level" in [s["code"] for s in out["sets"]]
    # по ученику: STUDENTS[1] не в группе, но назначен персонально
    sid2 = _set_id("book:super-minds")
    words.assign_set(sid2, "student", student_id=STUDENTS[1]["id"])
    out2 = words.list_sets(token, STUDENTS[1]["id"])
    assert "book:super-minds" in [s["code"] for s in out2["sets"]]
    # повтор назначения не падает
    words.assign_set(sid, "group", group_id=7)


def test_assignment_all(lk_words_db):
    token = _token()
    sid = _set_id("book:get-involved")
    words.assign_set(sid, "all")
    out = words.list_sets(token, STUDENTS[0]["id"])
    assert "book:get-involved" in [s["code"] for s in out["sets"]]


# ---------- тренировка и SRS ----------

def test_training_new_words_in_order(lk_words_db):
    token = _token()
    sid = _set_id("level:pre-a1")
    out = words.start_training(token, STUDENTS[0]["id"], sid)
    assert out["new_count"] == 8 and out["review_count"] == 0
    assert len(out["cards"]) == 8
    # новые по порядку position: первое слово набора из базы слов
    by_pos = sorted(out["cards"], key=lambda c: c["position"])
    first = words.content()["sets"]
    first = next(x for x in first if x["code"] == "level:pre-a1")["words"][0]
    assert by_pos[0]["text_en"] == first["en"]
    assert by_pos[0]["image_url"] == first["img"]  # фото Meshy (/w/…) или пусто — тогда плитка в ЛК
    # методика Cambridge: у каждого слова есть предложение-пример со словом внутри
    assert first["en"].lower() in by_pos[0]["example_en"].lower()
    assert all(c["example_en"] for c in out["cards"])
    assert all(p.get("example_en") for p in out["pool"])
    # варианты из других тем — для однозначных заданий (пропуски, картинки)
    assert len(out["pool_far"]) >= 10
    own = {p["text_en"].lower() for p in out["pool"]}
    assert all(p["id"] < 0 and p["image_url"] and p["example_en"] and p["text_en"].lower() not in own for p in out["pool_far"])
    assert by_pos[0]["transcription"] and not any("а" <= ch <= "я" for ch in by_pos[0]["transcription"])
    # без перевода в карточке, но ответы отдельно
    assert "text_ru" not in out["cards"][0]
    assert out["answers"][by_pos[0]["id"]] == first["ru"]
    assert len(out["pool"]) >= 4 and out["icon"]
    # дистракторы для выбора перевода
    assert len(out["cards"][0]["distractors"]) == 3


def test_answer_moves_strength_and_due(lk_words_db):
    token = _token()
    sid = _set_id("level:pre-a1")
    out = words.start_training(token, STUDENTS[0]["id"], sid)
    card = out["cards"][0]
    r = words.answer(token, STUDENTS[0]["id"], card["id"], True)
    assert r["strength"] == 1
    # после верного ответа слово ушло на повторение через 1 день (не due сегодня)
    out2 = words.start_training(token, STUDENTS[0]["id"], sid)
    assert card["id"] not in {c["id"] for c in out2["cards"]}
    # ошибка опускает силу
    words.answer(token, STUDENTS[0]["id"], card["id"], False)
    out3 = words.start_training(token, STUDENTS[0]["id"], sid)
    assert card["id"] in {c["id"] for c in out3["cards"]}


def test_answer_event_key_is_idempotent(lk_words_db):
    token = _token()
    sid = _set_id("level:pre-a1")
    card = words.start_training(token, STUDENTS[0]["id"], sid)["cards"][0]

    first = words.answer(token, STUDENTS[0]["id"], card["id"], True, event_key="attempt-1")
    second = words.answer(token, STUDENTS[0]["id"], card["id"], True, event_key="attempt-1")

    assert second == first
    row = get_conn().execute(
        "SELECT seen_count FROM lk_word_progress WHERE learner_key=? AND word_id=?",
        (f"crm:{STUDENTS[0]['id']}", card["id"]),
    ).fetchone()
    assert row["seen_count"] == 1


def test_stats_tracks_progress(lk_words_db):
    token = _token()
    sid = _set_id("level:pre-a1")
    out = words.start_training(token, STUDENTS[0]["id"], sid)
    for c in out["cards"][:3]:
        words.answer(token, STUDENTS[0]["id"], c["id"], True)
    st = words.stats(token, STUDENTS[0]["id"])
    assert st["seen_words"] == 3
    assert st["answers_total"] == 3 and st["answers_correct"] == 3


def test_guest_uses_account_key(lk_words_db, monkeypatch):
    from app.lk import bigben

    monkeypatch.setattr(bigben, "configured", lambda: False)
    service.start_auth("+79000000001", "Гость", _consents(), None, None)
    token = service.confirm_via_bot("+79000000001")["token"]
    sid = _set_id("level:pre-a1")
    out = words.start_training(token, 0, sid)  # student_id=0 → гостевой профиль
    card = out["cards"][0]
    words.answer(token, 0, card["id"], True)
    st = words.stats(token, 0)
    assert st["seen_words"] == 1
    # ключ гостя в БД — guest:<account_id>, не crm:
    keys = {r["learner_key"] for r in get_conn().execute(
        "SELECT DISTINCT learner_key FROM lk_word_progress").fetchall()}
    assert any(k.startswith("guest:") for k in keys)


# ---------- импорт (конструктор) ----------

def test_import_creates_set_with_words(lk_words_db):
    out = words.import_set({
        "code": "topic:halloween", "title": "Хэллоуин", "topic": "halloween",
        "is_public": True,
        "words": [
            {"text_en": "pumpkin", "text_ru": "тыква", "transcription": "пампкин"},
            {"text_en": "ghost", "text_ru": "привидение"},
            {"text_en": "pumpkin", "text_ru": "дубликат — пропустится"},
            {"text_en": "", "text_ru": "нет слова — пропустится"},
        ],
    })
    assert out["words"] == 2
    token = _token()
    out = words.list_sets(token, STUDENTS[0]["id"])
    assert "topic:halloween" in [s["code"] for s in out["sets"]]
    detail = words.set_words(token, STUDENTS[0]["id"], out2 := int(get_conn().execute(
        "SELECT id FROM lk_word_sets WHERE code='topic:halloween'").fetchone()["id"]))
    assert [w["text_en"] for w in detail["words"]] == ["pumpkin", "ghost"]
    assert detail["words"][0]["transcription"] == "пампкин"


def test_import_replaces_words_and_updates_meta(lk_words_db):
    words.import_set({"code": "topic:test", "title": "Старый", "is_public": True,
                      "words": [{"text_en": "one", "text_ru": "один"}]})
    out = words.import_set({"code": "topic:test", "title": "Новый", "is_public": True,
                            "words": [{"text_en": "two", "text_ru": "два"}]})
    assert out["words"] == 1
    token = _token()
    sid = int(get_conn().execute(
        "SELECT id FROM lk_word_sets WHERE code='topic:test'").fetchone()["id"])
    detail = words.set_words(token, STUDENTS[0]["id"], sid)
    assert [w["text_en"] for w in detail["words"]] == ["two"]
    sets = {s["code"]: s for s in words.list_sets(token, STUDENTS[0]["id"])["sets"]}
    assert sets["topic:test"]["title"] == "Новый"


def test_import_bad_payload(lk_words_db):
    with pytest.raises(core.Conflict) as ei:
        words.import_set({"code": "x"})  # нет title и words
    assert "bad_payload" in str(ei.value)


def test_assign_bad_kind(lk_words_db):
    with pytest.raises(core.Conflict) as ei:
        words.assign_set(_set_id("level:a1"), "country")
    assert "bad_kind" in str(ei.value)


def test_foreign_student_no_access(lk_words_db):
    token = _token()
    with pytest.raises(core.Conflict) as ei:
        words.start_training(token, 999999, _set_id("level:pre-a1"))
    assert "profile_not_found" in str(ei.value)



# ---------- игровая статистика ----------

def test_rewards_coins_world_wallet_quest_and_chest(lk_words_db):
    from app.lk import rewards
    token = _token()
    sid = _set_id("level:pre-a1")
    out = words.start_training(token, STUDENTS[0]["id"], sid)
    r = words.answer(token, STUDENTS[0]["id"], out["cards"][0]["id"], True, "type")
    assert r["coins"] == rewards.COIN_CORRECT + rewards.COIN_HARD
    assert words.answer(token, STUDENTS[0]["id"], out["cards"][1]["id"], False)["coins"] == 0
    fin = words.finish_session(token, STUDENTS[0]["id"], sid, 1, 2)
    assert fin["bonus_coins"] == rewards.COIN_LESSON and not fin["perfect"]
    st = words.stats(token, STUDENTS[0]["id"])
    earned = rewards.COIN_CORRECT + rewards.COIN_HARD + rewards.COIN_LESSON
    assert st["coins_today"] == earned
    # монеты попадают в кошелёк Мира — их можно тратить на замок
    assert st["wallet"] == earned
    assert st["rank"]["title"] and st["rank"]["learned"] == st["learned_words"]
    assert len(st["month"]["days"]) >= 28 and st["month"]["active_days"] == 1
    assert len(st["week"]["days"]) == 7 and st["week"]["active_days"] == 1 and not st["week"]["chest_ready"]
    assert st["quest"]["title"] and st["quest"]["target"] >= 1
    assert st["postcards"] and all("percent" in c for c in st["postcards"])
    assert {m["name"] for m in st["medals"]} == {"Starters", "Movers", "Flyers"}
    assert st["collection_total"] >= 4
    assert any(a["id"] == "first-step" for a in st["achievements"])
    # сундук закрыт, пока нет 5 дней из 7; задание дня — пока не выполнено
    with pytest.raises(core.Conflict):
        words.claim_reward(token, STUDENTS[0]["id"], "chest")
    learner = f"crm:{STUDENTS[0]['id']}"
    get_conn().execute("UPDATE lk_learner_days SET new_words=99, correct=99, sessions=9, perfect=9"
                       " WHERE learner_key=?", (learner,))
    got = words.claim_reward(token, STUDENTS[0]["id"], "quest")
    assert got["coins"] == rewards.QUEST_COINS and got["quest"]["claimed"]
    assert got["wallet"] == earned + rewards.QUEST_COINS
    with pytest.raises(core.Conflict):
        words.claim_reward(token, STUDENTS[0]["id"], "quest")  # один раз в день


def test_rank_by_learned_words():
    from app.lk import rewards
    assert rewards.rank_for(0)["title"] == "Гость Фоксинбурга"
    r = rewards.rank_for(35)
    assert r["title"] == "Юный следопыт" and r["from"] == 30 and r["to"] == 60 and r["next_title"] == "Следопыт"
    assert rewards.rank_for(5000)["next_title"] == ""


def test_hard_words_training_and_my_words(lk_words_db):
    token = _token()
    sid = _set_id("level:pre-a1")
    out = words.start_training(token, STUDENTS[0]["id"], sid)
    bad = out["cards"][0]["id"]
    words.answer(token, STUDENTS[0]["id"], bad, False)
    words.answer(token, STUDENTS[0]["id"], out["cards"][1]["id"], True)
    hard = words.start_training(token, STUDENTS[0]["id"], 0)
    assert hard["code"] == "hard" and [c["id"] for c in hard["cards"]] == [bad]
    assert hard["answers"][bad] and hard["pool"]
    my = words.my_words(token, STUDENTS[0]["id"])
    assert len(my["words"]) == 2 and my["hard_ids"] == [bad]
    assert all("example_en" in w for w in my["words"])


def test_reseed_keeps_word_ids(lk_words_db):
    sid = _set_id("topic:animals:1")
    before = {r["text_en"]: r["id"] for r in get_conn().execute(
        "SELECT id, text_en FROM lk_words WHERE set_id=?", (sid,)).fetchall()}
    words.seed_word_sets()
    after = {r["text_en"]: r["id"] for r in get_conn().execute(
        "SELECT id, text_en FROM lk_words WHERE set_id=?", (sid,)).fetchall()}
    assert before == after and len(after) >= 20


def test_reseed_hides_old_content_sets(lk_words_db):
    conn = get_conn()
    conn.execute("INSERT INTO lk_word_sets (code, title, kind, position, is_public, active)"
                 " VALUES ('topic:animals', 'Животные', 'topic', 1, 1, 1)")
    conn.execute("INSERT INTO lk_word_sets (code, title, kind, position, is_public, active)"
                 " VALUES ('custom-teacher', 'Свой набор', 'topic', 1, 1, 1)")
    words.seed_word_sets()
    act = {r["code"]: r["active"] for r in conn.execute(
        "SELECT code, active FROM lk_word_sets WHERE code IN ('topic:animals','custom-teacher','topic:animals:1')")}
    assert act == {"topic:animals": 0, "custom-teacher": 1, "topic:animals:1": 1}


def test_foxi_creator_saves_only_known_options(lk_words_db):
    token = _token()
    sid = STUDENTS[0]["id"]
    assert words.get_foxi(token, sid) == {"foxi": None}
    saved = words.set_foxi(token, sid, {"fur": "#9AA3AD", "hat": "crown", "top": "#22B3B0", "logo": False,
                                        "glasses": "laser", "shoes": "red", "name": "  Рыжик  "})
    assert saved["foxi"] == {"fur": "#9aa3ad", "hat": "crown", "top": "#22b3b0", "logo": False, "name": "Рыжик"}
    assert words.get_foxi(token, sid)["foxi"]["hat"] == "crown"
