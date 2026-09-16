"""Учебный путь английского: юниты → уроки → микс форматов, сердца, звёзды."""
import json

import pytest

from app.world import catalog, config, core, engine, items
from app.world.db import get_conn, reset_for_tests


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    core.get_or_create_player("child-1", "Мария")
    yield
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def _solve(item: dict) -> dict:
    kind = item["kind"]
    if kind == "explain":
        return {}
    if kind == "word_card":
        return {}
    if kind == "phrase_card":
        return {}
    if kind in ("mcq_en_ru", "mcq_ru_en", "listen", "fill_blank"):
        return {"choice": item["correct_index"]}
    if kind == "type_en":
        return {"text": item["correct_text"]}
    if kind == "match":
        return {"matches": {p["en"]: p["ru"] for p in item["pairs"]}}
    if kind == "tap_build":
        return {"tokens": item["tokens_correct"]}
    raise AssertionError(kind)


def _payload_items(session_id: str) -> list[dict]:
    row = get_conn().execute(
        "SELECT payload FROM activity_sessions WHERE id=?", (session_id,)
    ).fetchone()
    return json.loads(row[0])["items"]


def _uncleared(player_id: int) -> int:
    return int(get_conn().execute(
        "SELECT COUNT(*) AS n FROM mistakes WHERE player_id=? AND cleared=0", (player_id,)
    ).fetchone()["n"])


def _wrong(item: dict) -> dict:
    kind = item["kind"]
    if kind in ("mcq_en_ru", "mcq_ru_en", "listen", "fill_blank"):
        return {"choice": (item["correct_index"] + 1) % max(1, len(item.get("options") or [0, 1, 2, 3]))}
    if kind == "type_en":
        return {"text": "nope"}
    if kind == "match":
        return {"matches": {}}
    if kind == "tap_build":
        return {"tokens": []}
    return {}


def test_path_has_english_units_and_locks(monkeypatch):
    monkeypatch.setattr(config, "UNLOCK_ALL", False)
    path = engine.get_path("child-1")
    assert path["language"] == "en"
    assert len(path["units"]) == 18
    assert path["units"][0]["locked"] is False
    assert path["units"][1]["locked"] is True
    first = path["units"][0]
    assert first["id"] == "family"
    assert first["title_ru"] == "Моя семья"
    assert first["lessons"][0]["title_ru"] == "Привет!"
    assert first["lessons"][0]["stars"] == 0
    assert first["lessons"][0]["locked"] is False
    assert first["lessons"][1]["locked"] is True
    assert len(first["lessons"]) == 7
    assert [n["kind"] for n in first["lessons"]] == ["lesson"] * 6 + ["checkpoint"]
    assert first["lessons"][-1]["title_ru"].startswith("Проверка")


def test_unlock_all_opens_every_lesson(monkeypatch):
    monkeypatch.setattr(config, "UNLOCK_ALL", True)
    path = engine.get_path("child-1")
    assert path["unlock_all"] is True
    assert all(not u["locked"] for u in path["units"])
    assert all(not ls["locked"] for u in path["units"] for ls in u["lessons"])
    opened = engine.start_lesson("child-1", "satp-L3", seed=1)
    assert opened["total"] >= 8


def test_course_is_not_site_vocabulary():
    import app.world.vocabulary as vocab
    assert "hello" not in vocab.load_themes()
    assert catalog.get_unit("satp")["words"][0]["example_en"] != "The cat sleeps on the sofa."


def test_start_lesson_mixes_formats_without_leaking_keys():
    started = engine.start_lesson("child-1", "family-L1", seed=7)
    assert "Привет" in started["title_ru"]
    assert started["items"][0]["kind"] == "explain"
    for n in range(1, 7):
        built = items.build_lesson_items("family", n, seed=n)
        assert built[0]["kind"] == "explain"
        assert built[0]["title_ru"]
        kinds = [it["kind"] for it in built]
        first_drill = next(i for i, k in enumerate(kinds) if k not in ("explain", "word_card", "phrase_card"))
        assert first_drill >= 2
        assert built[0]["stage"] == "warmup"
        assert any(it.get("kind") == "word_card" for it in built)
        assert "listen" in kinds
        listen_i = kinds.index("listen")
        practice_i = next(i for i, it in enumerate(built) if it.get("stage") == "practice")
        wrap_i = next(i for i, it in enumerate(built) if it.get("stage") == "wrap")
        assert listen_i < practice_i < wrap_i
        assert built[-1]["stage"] == "wrap"
        assert "mcq_en_ru" in kinds
    assert any(it.get("kind") == "word_card" and it.get("image") for it in items.build_lesson_items("family", 1, seed=1))
    phonics = items.build_lesson_items("satp", 1, seed=1)
    assert phonics[1].get("gpc") == "s"
    assert started["hearts"] == 5
    assert started["total"] >= 8
    assert started["items"][0].get("foxi_ru")
    kinds = {item["kind"] for item in started["items"]}
    assert {"mcq_en_ru", "type_en", "match", "listen"} <= kinds
    assert "mcq_ru_en" not in kinds
    assert {"tap_build", "fill_blank"} & kinds
    for item in started["items"]:
        assert "correct_index" not in item
        assert "correct_text" not in item
        assert "tokens_correct" not in item
        assert "pairs" not in item


def test_mcq_and_type_and_match_answers():
    started = engine.start_lesson("child-1", "family-L1", seed=7)
    sid = started["session_id"]
    payload = json.loads(
        get_conn().execute("SELECT payload FROM activity_sessions WHERE id=?", (sid,)).fetchone()[0]
    )
    built = payload["items"]

    mcq = next(i for i, it in enumerate(built) if it["kind"] == "mcq_en_ru")
    r = engine.answer("child-1", sid, mcq, _solve(built[mcq]))
    assert r["correct"] is True
    assert r["hearts"] == 5

    typed = next(i for i, it in enumerate(built) if it["kind"] == "type_en")
    wrong = engine.answer("child-1", sid, typed, {"text": "zzzz"})
    assert wrong["correct"] is False
    assert wrong["hearts"] == 4
    assert wrong["correct_text"] == built[typed]["correct_text"]

    match_i = next(i for i, it in enumerate(built) if it["kind"] == "match")
    ok = engine.answer("child-1", sid, match_i, _solve(built[match_i]))
    assert ok["correct"] is True

    tap = next(i for i, it in enumerate(built) if it["kind"] == "tap_build")
    assert engine.answer("child-1", sid, tap, _solve(built[tap]))["correct"] is True


def test_hearts_empty_fails_lesson_without_xp():
    started = engine.start_lesson("child-1", "family-L1", seed=1)
    sid = started["session_id"]
    payload = json.loads(
        get_conn().execute("SELECT payload FROM activity_sessions WHERE id=?", (sid,)).fetchone()[0]
    )
    last = None
    for i, item in enumerate(payload["items"]):
        if last is not None and last["hearts"] == 0:
            break
        last = engine.answer("child-1", sid, i, _wrong(item))
    assert last is not None and last["hearts"] == 0
    with pytest.raises(core.Conflict):
        engine.finish("child-1", sid)


def test_finish_awards_stars_and_unlocks_next():
    started = engine.start_lesson("child-1", "family-L1", seed=11)
    sid = started["session_id"]
    payload = json.loads(
        get_conn().execute("SELECT payload FROM activity_sessions WHERE id=?", (sid,)).fetchone()[0]
    )
    for i, item in enumerate(payload["items"]):
        engine.answer("child-1", sid, i, _solve(item))
    fin = engine.finish("child-1", sid)
    assert fin["stars"] == 3
    assert fin["xp_delta"] > 0
    path = engine.get_path("child-1")
    hello = next(u for u in path["units"] if u["id"] == "family")
    assert hello["lessons"][0]["stars"] == 3
    if not config.UNLOCK_ALL:
        assert hello["lessons"][1]["locked"] is False
    assert fin["player"]["streak_days"] >= 1
    assert "sticker-family" in fin["items_granted"]
    assert "sticker-hello" in fin["items_granted"]


def test_wrong_answer_records_one_mistake_per_task():
    pid = core.get_player("child-1")["id"]
    for seed in (11, 12):
        started = engine.start_lesson("child-1", "family-L1", seed=seed)
        sid = started["session_id"]
        built = _payload_items(sid)
        typed = next(i for i, it in enumerate(built) if it["kind"] == "type_en")
        engine.answer("child-1", sid, typed, {"text": "zzzz"})
    assert _uncleared(pid) == 1


def test_correct_answer_clears_the_mistake():
    started = engine.start_lesson("child-1", "family-L1", seed=11)
    sid = started["session_id"]
    built = _payload_items(sid)
    typed = next(i for i, it in enumerate(built) if it["kind"] == "type_en")
    engine.answer("child-1", sid, typed, {"text": "zzzz"})
    pid = core.get_player("child-1")["id"]
    assert _uncleared(pid) == 1

    practice = engine.start_practice("child-1", seed=5)
    psid = practice["session_id"]
    pbuilt = _payload_items(psid)
    same = next(
        i for i, it in enumerate(pbuilt)
        if it["kind"] == "type_en" and it.get("en") == built[typed].get("en")
    )
    res = engine.answer("child-1", psid, same, _solve(pbuilt[same]))
    assert res["correct"] is True
    assert _uncleared(pid) == 0


def test_practice_pays_coins_up_to_daily_cap():
    paid = []
    for n in range(1, 5):
        practice = engine.start_practice("child-1", seed=n)
        sid = practice["session_id"]
        for i, item in enumerate(_payload_items(sid)):
            engine.answer("child-1", sid, i, _solve(item))
        paid.append(engine.finish("child-1", sid)["coins_delta"])
    assert paid[0] == config.COIN_REWARDS["practice_complete"]
    assert sum(paid) == config.PRACTICE_COINS_DAILY_CAP
    assert paid[-1] == 0
