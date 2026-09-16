"""Интервальные повторения (SRS) и экзамены юнита."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.world import catalog, config, core, engine, items, learn, srs
from app.world.db import get_conn, reset_for_tests


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    core.get_or_create_player("child-1", "Мария")
    yield
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def _pid() -> int:
    return core.get_player("child-1")["id"]


def _stat(word: str) -> dict:
    row = get_conn().execute(
        "SELECT * FROM word_stats WHERE player_id=? AND word_en=?", (_pid(), word)
    ).fetchone()
    return dict(row)


def _in_days(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


def _make_due(word: str, days_ago: int = 1) -> None:
    when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    get_conn().execute(
        "UPDATE word_stats SET due_at=? WHERE player_id=? AND word_en=?",
        (when, _pid(), word),
    )


def test_leitner_intervals():
    assert [srs.interval_days(s) for s in range(6)] == [1, 1, 3, 7, 14, 30]


def test_correct_answers_push_the_due_date_further():
    for _ in range(3):
        srs.touch(_pid(), "family", "hello", correct=True)
    row = _stat("hello")
    assert row["strength"] == 3
    assert row["correct_count"] == 3
    assert row["due_at"][:10] == _in_days(7)


def test_a_mistake_brings_the_word_back_tomorrow():
    for _ in range(4):
        srs.touch(_pid(), "family", "hello", correct=True)
    assert _stat("hello")["due_at"][:10] == _in_days(14)
    srs.touch(_pid(), "family", "hello", correct=False)
    row = _stat("hello")
    assert row["strength"] == 3
    assert row["wrong_count"] == 1
    assert row["due_at"][:10] == _in_days(7)


def test_review_queue_holds_only_ripe_words():
    srs.touch(_pid(), "family", "hello", correct=True)
    srs.touch(_pid(), "family", "mum", correct=True)
    assert srs.review_count(_pid()) == 0

    _make_due("hello")
    assert srs.review_count(_pid()) == 1
    queue = srs.due_words(_pid())
    assert [w["word_en"] for w in queue] == ["hello"]
    assert queue[0]["unit_id"] == "family"


def test_practice_prefers_ripe_words_over_padding():
    for word in ("hello", "mum", "dad", "sister", "brother", "baby"):
        srs.touch(_pid(), "family", word, correct=True)
        _make_due(word)
    session = engine.start_practice("child-1", seed=4)
    payload = json.loads(get_conn().execute(
        "SELECT payload FROM activity_sessions WHERE id=?", (session["session_id"],)
    ).fetchone()[0])
    drilled = {it.get("en") for it in payload["items"]}
    assert {"hello", "mum", "dad"} <= drilled
    assert session["review_due"] == 6
    assert all(it["kind"] not in ("explain", "word_card", "phrase_card") for it in payload["items"])


def test_review_endpoint_reports_the_queue():
    srs.touch(_pid(), "family", "hello", correct=True)
    _make_due("hello")
    report = learn.review("child-1")
    assert report["due"] == 1
    assert report["words"][0]["en"] == "hello"
    assert report["words"][0]["unit_id"] == "family"
    assert report["words"][0]["ru"]


def test_every_unit_has_a_checkpoint_exam():
    for unit_id in catalog.unit_order():
        unit = catalog.get_unit(unit_id)
        assert unit["has_checkpoint"] is True
        assert unit["checkpoint_ru"]
    path = engine.get_path("child-1")
    nodes = path["units"][0]["lessons"]
    assert len(nodes) == 7
    assert nodes[-1]["kind"] == "checkpoint"
    assert nodes[-1]["id"] == "family-C1"


def test_checkpoint_is_a_drill_only_exam_over_the_whole_unit():
    built = items.build_lesson_items("family", 7, checkpoint=True, seed=3)
    assert len(built) == config.CHECKPOINT_ITEMS
    assert not any(it["kind"] in ("explain", "word_card", "phrase_card") for it in built)
    assert all(it["stage"] == "practice" for it in built)
    unit_words = {w["en"] for w in catalog.get_unit("family")["words"]}
    touched = {it.get("en") for it in built if it.get("en")}
    assert len(touched & unit_words) >= 6

    started = engine.start_lesson("child-1", "family-C1", seed=3)
    assert started["total"] == config.CHECKPOINT_ITEMS
    assert "Проверка" in started["title_ru"]


def test_every_unit_exam_is_full_size():
    for unit_id in catalog.unit_order():
        built = items.build_checkpoint_items(unit_id, seed=5)
        assert len(built) == config.CHECKPOINT_ITEMS, unit_id
        assert all(it.get("foxi_ru") for it in built), unit_id


def test_checkpoint_gates_the_next_unit(monkeypatch):
    monkeypatch.setattr(config, "UNLOCK_ALL", False)
    path = engine.get_path("child-1")
    assert path["units"][1]["locked"] is True
    for n in range(1, 7):
        get_conn().execute(
            "INSERT INTO lesson_progress (player_id, lesson_id, stars, best_score) VALUES (?,?,?,?)",
            (_pid(), f"family-L{n}", 3, 10),
        )
    path = engine.get_path("child-1")
    assert path["units"][0]["lessons"][-1]["locked"] is False
    assert path["units"][1]["locked"] is True

    get_conn().execute(
        "INSERT INTO lesson_progress (player_id, lesson_id, stars, best_score) VALUES (?,?,?,?)",
        (_pid(), "family-C1", config.CHECKPOINT_STARS_TO_UNLOCK, 12),
    )
    path = engine.get_path("child-1")
    assert path["units"][1]["locked"] is False
