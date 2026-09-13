"""Foxinburg World — ядро vertical slice: player, economy ledger, quests.

Проверяет требования брифа: server-authoritative награды (§84),
идемпотентность (§160), ledger (§85), квест→награда→инвентарь→unlock (§214).
"""
import pytest

from app.world import core
from app.world.db import get_conn, reset_for_tests


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    yield
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def test_player_create_and_snapshot():
    p = core.get_or_create_player("child-1", "Мария")
    assert p["xp"] == 0 and p["coins"] == 0 and p["level"] == 1
    assert p["level_title"] == "Explorer"
    p2 = core.get_or_create_player("child-1", "Мария")
    assert p2["id"] == p["id"]


def test_award_idempotent_same_key_no_double_grant():
    core.get_or_create_player("child-1")
    r1 = core.award("child-1", xp=40, coins=15, source="lesson-1",
                    type_="LESSON_REWARD", idempotency_key="k1")
    r2 = core.award("child-1", xp=40, coins=15, source="lesson-1",
                    type_="LESSON_REWARD", idempotency_key="k1")
    assert r1["xp_delta"] == 40 and r1["coins_delta"] == 15
    assert r2["xp_delta"] == 0 and r2["coins_delta"] == 0
    p = core.get_player("child-1")
    assert p["xp"] == 40 and p["coins"] == 15
    rows = get_conn().execute("SELECT COUNT(*) c FROM xp_transactions").fetchone()
    assert rows["c"] == 1


def test_level_up_thresholds():
    core.get_or_create_player("child-1")
    r = core.award("child-1", xp=120, source="t", type_="QUEST_REWARD")
    assert r["level_up"] is True
    assert r["new_level"] == 2
    assert r["new_title"] == "Pathfinder"


def test_quest_flow_start_complete_rewards_inventory_unlock():
    core.get_or_create_player("child-1")
    core.start_quest("child-1", "first-day-at-foxinburg")
    r = core.complete_quest("child-1", "first-day-at-foxinburg")
    assert r["xp_delta"] == 60 and r["coins_delta"] == 30
    assert r["items_granted"] == ["fox-badge-first"]
    assert r["unlocks_granted"] == ["library-courtyard"]
    inv = core.get_inventory("child-1")
    assert [i["id"] for i in inv] == ["fox-badge-first"]
    assert inv[0]["rarity"] == "rare"
    assert core.get_unlocks("child-1") == ["library-courtyard"]


def test_quest_complete_twice_conflict_and_no_double_rewards():
    core.get_or_create_player("child-1")
    core.start_quest("child-1", "first-day-at-foxinburg")
    core.complete_quest("child-1", "first-day-at-foxinburg")
    with pytest.raises(core.Conflict):
        core.complete_quest("child-1", "first-day-at-foxinburg")
    p = core.get_player("child-1")
    assert p["xp"] == 60 and p["coins"] == 30
    assert len(core.get_inventory("child-1")) == 1


def test_quest_complete_requires_start():
    core.get_or_create_player("child-1")
    with pytest.raises(core.Conflict):
        core.complete_quest("child-1", "first-day-at-foxinburg")


def test_quest_listing_shows_progress():
    core.get_or_create_player("child-1")
    qs = core.list_quests("child-1")
    assert qs[0]["status"] == "available"
    core.start_quest("child-1", "first-day-at-foxinburg")
    qs = core.list_quests("child-1")
    assert qs[0]["status"] == "active"
    assert qs[0]["config"]["steps"][0]["target"] == "school-hub"


def test_unknown_quest_404():
    core.get_or_create_player("child-1")
    with pytest.raises(core.NotFound):
        core.start_quest("child-1", "no-such-quest")


def test_advance_quest_step_in_order():
    core.get_or_create_player("child-step")
    core.start_quest("child-step", "first-day-at-foxinburg")
    r1 = core.advance_quest_step("child-step", "first-day-at-foxinburg", "visit", "school-hub")
    assert r1["step"] == 1 and r1["steps_total"] == 3 and r1["all_steps_done"] is False
    r2 = core.advance_quest_step("child-step", "first-day-at-foxinburg", "talk", "foxi")
    assert r2["step"] == 2
    r3 = core.advance_quest_step("child-step", "first-day-at-foxinburg",
                                 "activity", "vocabulary-challenge-1")
    assert r3["step"] == 3 and r3["all_steps_done"] is True


def test_advance_quest_step_rejects_wrong_step():
    core.get_or_create_player("child-step2")
    core.start_quest("child-step2", "first-day-at-foxinburg")
    with pytest.raises(core.Conflict):
        core.advance_quest_step("child-step2", "first-day-at-foxinburg", "talk", "foxi")


def test_advance_quest_step_requires_started_quest():
    core.get_or_create_player("child-step3")
    with pytest.raises(core.Conflict):
        core.advance_quest_step("child-step3", "first-day-at-foxinburg", "visit", "school-hub")


def test_quest_progress_survives_reload():
    core.get_or_create_player("child-step4")
    core.start_quest("child-step4", "first-day-at-foxinburg")
    core.advance_quest_step("child-step4", "first-day-at-foxinburg", "visit", "school-hub")
    quest = next(q for q in core.list_quests("child-step4")
                 if q["id"] == "first-day-at-foxinburg")
    assert quest["step"] == 1 and quest["status"] == "active"
